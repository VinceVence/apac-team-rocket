"""Offline acceptance checks. Never invokes the real Gemini transport."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agents import Agents, Config, RESERVATION_USD
from lab import Lab, LabError, TABLES
from server import make_server
from world import World
from science import Science
from macro import Macro, gini


class LabChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.sqlite3'
        self.lab=Lab(self.path);self.agents=Agents(self.lab,Config())

    def tearDown(self):
        self.lab.db.close();self.temp.cleanup()

    def response(self, packet):
        return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(self.lab.baseline(packet))}]}}],
                'usageMetadata':{'promptTokenCount':3000,'candidatesTokenCount':600,'thoughtsTokenCount':0}}

    def test_six_tables_and_seeded_ledger(self):
        tables={r[0] for r in self.lab.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables,set(TABLES));self.assertTrue(self.lab.integrity())
        self.assertEqual(self.lab.snapshot()['tables']['customers'],24)
        self.assertGreater(self.lab.snapshot()['tables']['financial_events'],1400)
        self.assertEqual(self.lab.snapshot()['tables']['agent_runs'],0)

    def test_baseline_scenarios_and_forecast(self):
        for cid,expected in [('F001','reject'),('F002','release'),('F003','review'),('I001','insight'),('I002','insight')]:
            self.assertEqual(self.agents.analyze(cid,'baseline')['run']['decision']['action'],expected)
        low=next(e['data'] for e in self.lab.evidence('I001')['evidence'] if e['type']=='calculation')
        high=next(e['data'] for e in self.lab.evidence('I002')['evidence'] if e['type']=='calculation')
        self.assertGreater(low['shortfall_minor'],0);self.assertEqual(high['shortfall_minor'],0)
        self.assertEqual(low['projected_wallet_minor'],low['wallet_minor']-low['bills_minor']-low['estimated_7_day_spend_minor'])

    def test_apply_is_bounded_atomic_and_idempotent(self):
        row=self.agents.analyze('F002','baseline')['run']
        before=self.lab.db.execute("SELECT balance_minor FROM accounts WHERE id='C002:wallet'").fetchone()[0]
        self.assertFalse(self.lab.apply_decision('F002',row['id'])['replayed'])
        self.assertTrue(self.lab.apply_decision('F002',row['id'])['replayed'])
        after=self.lab.db.execute("SELECT balance_minor FROM accounts WHERE id='C002:wallet'").fetchone()[0]
        self.assertEqual(before-after,240000);self.assertTrue(self.lab.integrity())
        saved=self.agents.public_run(row['id'])['evidence']
        recorded_wallet=next(e['data']['balance_minor'] for e in saved['evidence'] if e['id']=='account:C002:wallet')
        self.assertEqual(recorded_wallet,before)  # Reopened investigations retain the original evidence.
        for cid in ('F001','F003','I001'):
            run=self.agents.analyze(cid,'baseline')['run'];cash=self.lab.rows('SELECT id,balance_minor FROM accounts')
            self.lab.apply_decision(cid,run['id']);self.assertEqual(cash,self.lab.rows('SELECT id,balance_minor FROM accounts'))

    def test_invalid_evidence_and_policy_are_rejected(self):
        packet=self.lab.evidence('F001');decision=self.lab.baseline(packet)
        decision['evidence_ids']=['made-up-source']
        with self.assertRaises(LabError):self.lab.validate(packet,decision)
        decision=self.lab.baseline(packet);decision['action']='release'
        with self.assertRaises(LabError):self.lab.validate(packet,decision)
        packet=self.lab.evidence('F003');decision=self.lab.baseline(packet);decision['action']='reject'
        with self.assertRaises(LabError):self.lab.validate(packet,decision)

    def test_stale_proposal_does_not_execute(self):
        run=self.agents.analyze('F002','baseline')['run']
        with self.lab.db:self.lab.post('concurrent-payment','C002','payment',100,'2026-10-06','C002:wallet','m1')
        with self.assertRaisesRegex(LabError,'evidence changed'):self.lab.apply_decision('F002',run['id'])
        self.assertEqual(self.lab.case('F002')['status'],'open');self.assertTrue(self.lab.integrity())

    def test_real_provider_off_and_invalid_modes(self):
        with self.assertRaisesRegex(LabError,'off'):self.agents.analyze('F001','gemini')
        with self.assertRaises(LabError):self.agents.analyze('F001','surprise-model')
        self.assertEqual(self.lab.snapshot()['tables']['agent_runs'],0)

    def test_cache_usage_and_restart_persistence(self):
        calls=[]
        def fake(config,packet):calls.append(1);return self.response(packet)
        agent=Agents(self.lab,Config(api_key='test-only',live=True),fake)
        result=agent.analyze('F001','gemini');self.assertFalse(result['cached'])
        self.assertAlmostEqual(result['run']['cost_usd'],0.00054)
        self.assertTrue(agent.analyze('F001','gemini')['cached']);self.assertEqual(len(calls),1)
        self.lab.db.close();self.lab=Lab(self.path)
        again=Agents(self.lab,Config(api_key='test-only',live=True),fake)
        self.assertTrue(again.analyze('F001','gemini')['cached']);self.assertEqual(len(calls),1)
        self.assertEqual(again.budget()['calls_today'],1)

    def test_unknown_failure_keeps_reservation_and_no_retry(self):
        calls=[]
        def timeout(config,packet):calls.append(1);raise TimeoutError('fake timeout')
        agent=Agents(self.lab,Config(api_key='test-only',live=True,daily_usd=RESERVATION_USD),timeout)
        with self.assertRaises(LabError):agent.analyze('F001','gemini')
        self.assertEqual(len(calls),1);self.assertEqual(agent.budget()['committed_usd_today'],RESERVATION_USD)
        with self.assertRaises(LabError) as error:agent.analyze('F002','gemini')
        self.assertEqual(error.exception.status,429);self.assertEqual(len(calls),1)

    def test_concurrent_reservations_and_duplicate_request(self):
        entered=threading.Event();finish=threading.Event();calls=[]
        def slow(config,packet):
            calls.append(1);entered.set();finish.wait(3);return self.response(packet)
        agent=Agents(self.lab,Config(api_key='test-only',live=True,daily_calls=1),slow)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(agent.analyze,'F001','gemini');self.assertTrue(entered.wait(2))
            with self.assertRaises(LabError) as error:agent.analyze('F001','gemini')
            self.assertEqual(error.exception.status,409)
            with self.assertRaises(LabError) as error:agent.analyze('F002','gemini')
            self.assertEqual(error.exception.status,429)
            finish.set();self.assertEqual(future.result()['run']['status'],'completed')
        self.assertEqual(len(calls),1)

    def test_malformed_model_response_and_injection_cannot_move_money(self):
        def bad(config,packet):
            answer=self.response(packet);decision=self.lab.baseline(packet);decision['action']='release'
            answer['candidates'][0]['content']['parts'][0]['text']=json.dumps(decision);return answer
        agent=Agents(self.lab,Config(api_key='test-only',live=True),bad)
        before=self.lab.rows('SELECT id,balance_minor FROM accounts')
        with self.assertRaises(LabError):agent.analyze('F001','gemini')
        self.assertEqual(before,self.lab.rows('SELECT id,balance_minor FROM accounts'))
        self.assertEqual(self.lab.case('F001')['status'],'open')

    def test_http_boundaries_and_durable_api(self):
        server=make_server(0,Path(self.temp.name)/'http.sqlite3',Config())
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/api/state') as r:state=json.load(r)
            body=json.dumps({'case_id':'F001','mode':'baseline'}).encode()
            request=urllib.request.Request(base+'/api/analyze',data=body,headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
            self.assertEqual(e.exception.code,403)
            request.add_header('X-MintTown-Token',state['csrf_token'])
            request.add_header('Origin','https://untrusted.example')
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
            self.assertEqual(e.exception.code,403)
            request.remove_header('Origin')
            with urllib.request.urlopen(request) as r:result=json.load(r)
            self.assertEqual(result['run']['decision']['action'],'reject')
            with urllib.request.urlopen(base+'/api/runs/'+result['run']['id']) as r:saved=json.load(r)
            self.assertEqual(saved['evidence'],result['run']['evidence'])
            with urllib.request.urlopen(base+'/api/evidence/F001') as r:current=json.load(r)
            self.assertEqual(current['evidence_hash'],result['run']['evidence_hash'])
            for path in ('/data/minttown.sqlite3','/.env','/fonts/../server.py'):
                with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+path)
                self.assertEqual(e.exception.code,404)
        finally:
            server.shutdown();server.server_close();thread.join();server.lab.db.close()


class LivingWorldChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.lab=Lab(Path(self.temp.name)/'world.sqlite3')
        self.world=World(self.lab);self.science=Science(self.lab);self.agents=Agents(self.lab,Config())

    def tearDown(self):
        self.lab.db.close();self.temp.cleanup()

    def test_event_to_agent_to_service_and_future_enforcement(self):
        event=self.world.advance(0,2,'fraud');cid=event['alerts'][0]
        self.assertEqual(len(event['motions']),2)
        self.assertTrue(self.world.advance(0,2,'fraud')['replayed'])
        run=self.agents.analyze(cid,'baseline')['run'];self.assertEqual(run['decision']['action'],'reject')
        receipt=self.world.block_device(cid,run['id']);self.assertFalse(receipt['replayed'])
        self.assertTrue(self.world.block_device(cid,run['id'])['replayed'])
        customer=self.lab.case(cid)['customer_id'];before=self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(customer+':wallet',)).fetchone()[0]
        with self.lab.db:
            self.assertEqual(self.world.payment('attack-retry',customer,'m3',10000,receipt['device_id']),'blocked')
            self.assertEqual(self.world.payment('trusted-payment',customer,'m1',10000,'device-'+customer),'settled')
        after=self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(customer+':wallet',)).fetchone()[0]
        self.assertEqual(before-after,10000);self.assertTrue(self.lab.integrity())
        self.assertEqual(self.agents.budget()['calls_today'],0)
        uncertain=self.agents.analyze('F003','baseline')['run']
        with self.assertRaises(LabError):self.world.block_device('F003',uncertain['id'])

    def test_training_uses_disjoint_customers_and_past_features(self):
        report=self.science.train();self.assertEqual(len(report['models']),2)
        for model in report['models']:
            r=model['report'];self.assertGreater(r['train_rows'],60)
            self.assertFalse(set(r['train_customer_ids'])&set(r['holdout_customer_ids']))
            self.assertLessEqual(r['training_label_end'],r['holdout_label_start'])
            self.assertIn('brier',r);self.assertEqual(len(model['scores']),24)
        history=[(91,'payment',5000),(96,'payment',9000)]
        self.assertEqual(self.science.features(history,100),self.science.features(history+[(105,'savings_deposit',1000000)],100))
        self.assertNotEqual(self.science.label(history,100,'propensity'),self.science.label(history+[(105,'savings_deposit',1000000)],100,'propensity'))
        self.assertEqual(self.science.train()['created_models'],0);self.assertEqual(self.lab.db.execute('SELECT count(*) FROM model_runs').fetchone()[0],2)

    def test_clock_cashflows_and_weekly_model_refresh(self):
        self.science.train();self.assertFalse(self.science.due())
        result=self.world.advance(0,1,'income');self.assertEqual(self.lab.case(result['alerts'][0])['kind'],'cashflow')
        for tick in range(1,168):self.world.advance(tick,1)
        self.assertTrue(self.science.due());self.science.train()
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM model_runs').fetchone()[0],4)
        self.assertTrue(self.lab.integrity());self.assertEqual(self.world.state()['tick'],168)

    def test_paid_bills_are_not_forecast_twice(self):
        before=next(e['data']['bills_minor'] for e in self.lab.evidence('I001')['evidence'] if e['type']=='calculation')
        with self.lab.db:self.lab.post('test-bill-paid','C004','bill_payment',450000,self.lab.clock_day,'treasury','m2',{'bill_id':'I001-rent'})
        after=next(e['data']['bills_minor'] for e in self.lab.evidence('I001')['evidence'] if e['type']=='calculation')
        self.assertEqual(before-after,450000)


class MacroPolicyChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.lab=Lab(Path(self.temp.name)/'macro.sqlite3')
        self.world=World(self.lab);self.agents=Agents(self.lab,Config())
        self.macro=Macro(self.lab,self.world,self.agents);self.world.macro=self.macro

    def tearDown(self):self.lab.db.close();self.temp.cleanup()

    def warm(self):
        for i in range(6):self.world.advance(i,3,'demand' if i==0 else 'none')

    def test_measured_basket_and_gini(self):
        self.assertEqual(gini([5,5,5]),0);self.assertAlmostEqual(gini([0,0,9]),2/3)
        self.assertEqual(self.macro.metrics(0)['price_index'],100)
        self.assertIsNone(self.macro.metrics(0)['inflation_6h_pct'])
        self.warm();goods=self.macro.goods();metrics=self.macro.metrics(6)
        index=sum(g['price_minor'] for g in goods)/sum(g['base_minor'] for g in goods)*100
        self.assertAlmostEqual(metrics['price_index'],index,places=3)
        self.assertGreater(metrics['inflation_6h_pct'],1.2)
        self.assertGreater(metrics['trade_volume_minor'],0);self.assertTrue(self.lab.integrity())

    def test_review_apply_idempotence_and_liquidity_conservation(self):
        self.warm();before=self.macro.metrics(6);decision=self.macro.review('baseline')['decision']
        self.assertEqual(decision['recommendation']['stance'],'tighten')
        result=self.macro.apply(decision['id']);self.assertFalse(result['replayed'])
        self.assertTrue(self.macro.apply(decision['id'])['replayed'])
        self.assertEqual(self.macro.policy()['version'],2)
        self.assertEqual(before['circulating_minor']-self.macro.metrics(6)['circulating_minor'],-decision['plan']['liquidity_delta_minor'])
        saved=json.loads(self.lab.db.execute('SELECT metrics FROM macro_observations WHERE tick=6').fetchone()[0])
        self.assertEqual(saved['circulating_minor'],self.macro.metrics(6)['circulating_minor'])
        self.assertTrue(self.lab.integrity());self.assertTrue(self.macro.review('baseline')['cached'])

    def test_loan_contracts_and_reserve_admission(self):
        old=self.macro.request_loan('C001',200000,'loan-before');self.assertEqual(old['rate_bps'],1000)
        self.assertTrue(self.macro.request_loan('C001',200000,'loan-before')['replayed'])
        with self.assertRaises(LabError):self.macro.request_loan('C002',200000,'loan-before')
        self.warm();decision=self.macro.review('baseline')['decision'];self.macro.apply(decision['id'])
        self.assertEqual(self.lab.db.execute('SELECT rate_bps FROM macro_loans WHERE id=?',(old['id'],)).fetchone()[0],1000)
        cid=self.lab.db.execute("SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM macro_loans) LIMIT 1").fetchone()[0]
        new=self.macro.request_loan(cid,200000,'loan-after');self.assertEqual(new['rate_bps'],1100)
        next_cid=self.lab.db.execute("SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM macro_loans) LIMIT 1").fetchone()[0]
        with self.lab.db:self.lab.post('park-all',None,'test_liquidity',self.macro.balance('macro-bank'),self.lab.clock_day,'macro-bank','central-reserves')
        with self.assertRaisesRegex(LabError,'reserve'):self.macro.request_loan(next_cid,200000,'no-reserves')
        self.assertTrue(self.lab.integrity())

    def test_fee_postings_and_atomic_failure(self):
        wallet=self.macro.balance('C001:wallet');merchant=self.macro.balance('m2');fees=self.macro.balance('payment-fees')
        with self.lab.db:quote=self.macro.purchase('priced-test','C001','m2',15000,{'device_id':'known'})
        self.assertEqual(wallet-self.macro.balance('C001:wallet'),quote['total_minor'])
        self.assertEqual(self.macro.balance('m2')-merchant,quote['subtotal_minor'])
        self.assertEqual(self.macro.balance('payment-fees')-fees,quote['fee_minor'])
        self.assertTrue(self.lab.integrity())
        balances=self.lab.rows('SELECT id,balance_minor FROM accounts')
        with self.assertRaises(LabError),self.lab.db:self.lab.post_legs('bad-multi','C001','payment',100,self.lab.clock_day,[('C001:wallet','m2',100),('C001:wallet','payment-fees',100000000000)])
        self.assertEqual(balances,self.lab.rows('SELECT id,balance_minor FROM accounts'))

    def test_stale_and_out_of_bounds_policy_rejected(self):
        self.warm();d=self.macro.review('baseline')['decision']
        with self.lab.db:self.lab.post('changed-ledger','C001','payment',100,self.lab.clock_day,'C001:wallet','m1')
        with self.assertRaisesRegex(LabError,'stale'):self.macro.apply(d['id'])
        self.assertEqual(self.macro.policy()['version'],1)
        for i in range(6,12):self.world.advance(i,2)
        d=self.macro.review('baseline')['decision'];plan=d['plan'];plan['loan_bps']=50000
        with self.lab.db:self.lab.db.execute('UPDATE macro_decisions SET plan=? WHERE id=?',(json.dumps(plan),d['id']))
        with self.assertRaises(LabError):self.macro.apply(d['id'])
        self.assertEqual(self.macro.policy()['version'],1)

    def test_macro_and_fraud_share_one_paid_budget(self):
        calls=[]
        def fake(config,packet):
            calls.append(packet['kind']);answer=self.macro.baseline(packet)
            return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(answer)}]}}],
                    'usageMetadata':{'promptTokenCount':1500,'candidatesTokenCount':300}}
        self.agents=Agents(self.lab,Config(api_key='test-only',live=True,daily_calls=1),fake);self.macro.agents=self.agents
        self.warm();self.macro.review('gemini');self.assertEqual(self.agents.budget()['calls_today'],1)
        with self.assertRaises(LabError) as e:self.agents.analyze('F001','gemini')
        self.assertEqual(e.exception.status,429);self.assertEqual(calls,['macro'])

    def test_business_failure_is_derived_from_unpaid_costs(self):
        for day in range(1,4):
            self.lab.clock_day='2026-10-%02d'%(6+day)
            with self.lab.db:
                balance=self.macro.balance('m3')
                if balance:self.lab.post('firm-drain-'+str(day),None,'test_outflow',balance,self.lab.clock_day,'m3','treasury')
                self.macro.daily(day*24)
        self.assertEqual(self.macro.metrics(72)['bankrupt_businesses'],1)
        with self.assertRaisesRegex(LabError,'insolvent'):self.macro.quote('m3',9000)
        self.assertTrue(self.lab.integrity())


if __name__=='__main__':unittest.main(verbosity=2)
