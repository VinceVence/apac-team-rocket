"""Shared case service, analyst review, memory, and the retained fixed-step baseline.

The independent FraudAgent controller adds ADK without changing the human approval gate.
"""
import json
import statistics
import uuid

from lab import LabError, encoded, now
from fraud_scenarios import SCENARIOS, catalogue, create_scenario
from settings import MAX_CUSTOMERS
import fraud_knowledge

TABLES = ('fraud_reports', 'fraud_investigations', 'fraud_reviews', 'scam_memories')
LESSON = 'A familiar device and a successful PIN do not rule out deception. Check who requested the transfer and why.'
QUESTION = 'Did the caller tell you to move money to a safe account or hide the reason for the transfer?'


def text(value, name, minimum=1, maximum=2000):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise LabError('%s must contain %d–%d characters.' % (name, minimum, maximum))
    return value.strip()


def cues(story):
    lower = story.lower()
    terms = {'safe_account': ('safe account', 'secure account', 'protect my money'),
             'impersonation': ('bank support', 'bank security', 'support caller', 'bank employee'),
             'pressure': ('urgent', 'immediately', 'hurry', 'right now'),
             'secrecy': ('keep it secret', 'hide the reason', 'not tell')}
    return [key for key, values in terms.items() if any(term in lower for term in values)]


def watch_matches(recipients, payee):
    return payee in recipients


def scenario_title(scenario):
    if not scenario:return None
    key={'first':'phishing','repeat':'phishing'}.get(scenario,scenario.removesuffix('.control'))
    title=SCENARIOS.get(key,{}).get('title')
    return (title+' · lookalike' if scenario.endswith('.control') else title) if title else 'Legitimate payment' if scenario=='benign' else None


class FraudDesk:
    def __init__(self, lab, world):
        self.lab, self.world = lab, world
        self.agent = None
        self.prevention = None
        self.demo_analyst = None
        fraud_knowledge.initialize(lab)
        lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS fraud_reports(
          id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, request_json TEXT NOT NULL,
          customer_id TEXT NOT NULL REFERENCES customers(id), story TEXT NOT NULL,
          message TEXT NOT NULL, event_ids TEXT NOT NULL, answers TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'reported', revision INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fraud_investigations(
          id TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES fraud_reports(id),
          report_revision INTEGER NOT NULL, step INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'running', context TEXT NOT NULL, trace TEXT NOT NULL,
          recommendation TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fraud_reviews(
          id TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES fraud_reports(id),
          investigation_id TEXT NOT NULL UNIQUE REFERENCES fraud_investigations(id),
          command TEXT NOT NULL, disposition TEXT NOT NULL, note TEXT NOT NULL,
          resolution TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scam_memories(
          id TEXT PRIMARY KEY, source_report_id TEXT NOT NULL UNIQUE REFERENCES fraud_reports(id),
          review_id TEXT NOT NULL UNIQUE REFERENCES fraud_reviews(id), pattern TEXT NOT NULL,
          lesson TEXT NOT NULL, next_question TEXT NOT NULL, validation TEXT NOT NULL,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fraud_case_preparation(
          report_id TEXT PRIMARY KEY REFERENCES fraud_reports(id),status TEXT NOT NULL,
          stage TEXT NOT NULL,detail TEXT NOT NULL,updated_at TEXT NOT NULL);
        ''')
        with lab.db:lab.db.execute("UPDATE fraud_case_preparation SET status='interrupted',detail='Evidence preparation stopped when the service restarted. Review the saved state; no work was retried.',updated_at=? WHERE status='running'",(now(),))

    def prepare(self,report_id,status,stage,detail):
        """Observable intake state; no model request, retry or extra cloud operation."""
        with self.lab.lock,self.lab.db:
            self.report(report_id)
            self.lab.db.execute('INSERT OR REPLACE INTO fraud_case_preparation VALUES(?,?,?,?,?)',(report_id,status,stage,detail,now()))

    def memories(self,include_inactive=False):
        from fraud_playbook import for_memory
        rows = self.lab.rows('SELECT * FROM scam_memories ORDER BY rowid DESC')
        for row in rows:
            for key in ('pattern', 'validation'): row[key] = json.loads(row[key])
            row['lifecycle']=fraud_knowledge.lifecycle(self.lab,row)
            row['playbook']=for_memory(self.lab,row['id']) if row['lifecycle']['active'] else None
        return rows if include_inactive else [r for r in rows if r['lifecycle']['active']]

    def screen(self, customer_id, payee):
        # ponytail: a small reviewed-recipient watchlist; indexed serving if the demo grows.
        return [{'memory_id': m['id'], 'source_report_id': m['source_report_id'],
                 'reason': 'Recipient appeared in an analyst-confirmed scam; review this transfer.'}
                for m in self.memories() if m['validation']['passed'] and
                watch_matches(m['pattern']['recipient_accounts'], payee)]

    def report(self, report_id):
        row = self.lab.db.execute('SELECT * FROM fraud_reports WHERE id=?', (report_id,)).fetchone()
        if not row: raise LabError('Scam report not found.', 404)
        result = dict(row)
        for key in ('event_ids', 'answers'): result[key] = json.loads(result[key])
        result.pop('request_json'); result.pop('request_id')
        return result

    def run(self, run_id):
        row = self.lab.db.execute('SELECT * FROM fraud_investigations WHERE id=?', (run_id,)).fetchone()
        if not row: raise LabError('Investigation not found.', 404)
        result = dict(row)
        for key in ('context', 'trace', 'recommendation'):
            result[key] = json.loads(result[key]) if result[key] else None
        result.update(provider='offline', gemini_calls=0)
        if result['context'].get('controller') == 'adk':
            result['provider'] = result['context']['provider']
            result['model'] = result['context']['model']
            if self.agent:
                result['budget'] = self.agent.budget(result['report_id'], result['provider'])
                result['gemini_calls'] = result['budget']['case_calls'] if result['provider'] == 'gemini' else 0
                snapshot = self.lab.db.execute('SELECT id,as_of,captured_at,event_watermark,evidence_hash FROM fraud_evidence_snapshots WHERE run_id=?', (run_id,)).fetchone()
                result['snapshot'] = dict(snapshot) if snapshot else None
        return result

    def detail(self, report_id):
        with self.lab.lock:return self._detail(report_id)

    def _detail(self, report_id):
        with self.lab.lock:
            report = self.report(report_id)
            latest = self.lab.db.execute('SELECT id FROM fraud_investigations WHERE report_id=? ORDER BY rowid DESC LIMIT 1', (report_id,)).fetchone()
            reviews = self.lab.rows('SELECT * FROM fraud_reviews WHERE report_id=? ORDER BY rowid DESC', (report_id,))
            for review in reviews:
                review['resolution'] = json.loads(review['resolution']); review.pop('command')
            report.update(customer=dict(self.lab.db.execute('SELECT * FROM customers WHERE id=?', (report['customer_id'],)).fetchone()),
                          transactions=self.transactions(report), investigation=self.run(latest[0]) if latest else None,
                          reviews=reviews)
            preparation=self.lab.db.execute('SELECT * FROM fraud_case_preparation WHERE report_id=?',(report_id,)).fetchone()
            report['preparation']=dict(preparation) if preparation else None
            if self.agent:
                report['decision_trail'] = self.agent.timeline(report_id)
                report['harness']=self.agent.harness.dashboard(report['investigation'])
            if self.prevention:report['prevention']=self.prevention.for_report(report_id)
            payload=json.loads(self.lab.db.execute('SELECT request_json FROM fraud_reports WHERE id=?',(report_id,)).fetchone()[0])
            report['scenario_title']=scenario_title(payload.get('scenario') or next((t['metadata'].get('scenario') for t in report['transactions'] if t['metadata'].get('scenario')),None))
            if self.agent and report['investigation'] and report['investigation']['recommendation']:
                report['validation_warnings']=self.agent.amount_warnings(report['investigation']['recommendation'],report['investigation']['context'])
                checks=report.get('harness',{}).get('checks',[])
                if report['investigation']['status']=='awaiting_review' and checks and not checks[0]['passed']:
                    report['validation_warnings'] += [b for j in checks[0]['judges'] for b in j['blockers']]
            if self.demo_analyst:report['demo_analyst']=self.demo_analyst.status(report)
            return report

    def dashboard(self):
        with self.lab.lock:
            reports=self.lab.rows("SELECT r.id,r.customer_id,c.name,r.status,r.created_at,coalesce(json_extract(r.request_json,'$.scenario'),json_extract((SELECT metadata FROM financial_events WHERE id=json_extract(r.event_ids,'$[0]')),'$.scenario')) AS scenario FROM fraud_reports r JOIN customers c ON c.id=r.customer_id ORDER BY r.rowid DESC")
            for report in reports:report['scenario_title']=scenario_title(report.pop('scenario'))
            live=bool(self.agent and self.agent.live_enabled())
            return {'mode': 'ADK · Gemini' if live else 'ADK · fake model' if self.agent else 'Offline tool rehearsal', 'gemini_calls': self.agent.agents.budget()['calls_today'] if self.agent else 0,
                    'agent_runtime': self.agent.runtime() if self.agent else None, 'scenarios':catalogue(),
                    'reports':reports,
                    'memories': self.memories(include_inactive=True),
                    'customers': self.lab.rows('SELECT id,name FROM customers ORDER BY id LIMIT ?', (MAX_CUSTOMERS,)),
                    'transactions': self.lab.rows("SELECT id,customer_id,amount_minor,to_account,occurred_at FROM (SELECT id,customer_id,amount_minor,to_account,occurred_at,row_number() OVER (PARTITION BY customer_id ORDER BY occurred_at DESC,rowid DESC) AS recent FROM financial_events WHERE status='settled' AND kind='payment') WHERE recent<=5 ORDER BY occurred_at DESC,id DESC")}

    def transactions(self, report):
        result = []
        for eid in report['event_ids']:
            row = self.lab.db.execute('SELECT * FROM financial_events WHERE id=? AND customer_id=?', (eid, report['customer_id'])).fetchone()
            if not row: raise LabError('The reported transaction no longer matches this customer.', 409)
            item = dict(row); item['metadata'] = json.loads(item['metadata']); result.append(item)
        return result

    def _create(self, customer_id, story, message, event_ids, request_id, request_json):
        text(customer_id, 'Customer ID'); story = text(story, 'Report', 20, 4000)
        if customer_id not in {c['id'] for c in self.lab.rows('SELECT id FROM customers ORDER BY id LIMIT ?', (MAX_CUSTOMERS,))}:
            raise LabError('This customer is outside the active simulation cohort.',403)
        message = text(message, 'Message transcript', 0, 2000)
        if not isinstance(event_ids, list) or not 1 <= len(event_ids) <= 10 or any(not isinstance(e, str) for e in event_ids) or len(set(event_ids)) != len(event_ids):
            raise LabError('Choose 1–10 distinct transactions belonging to this customer.')
        for eid in event_ids:
            if not self.lab.db.execute("SELECT 1 FROM financial_events WHERE id=? AND customer_id=? AND kind IN ('payment','payment_request')", (eid, customer_id)).fetchone():
                raise LabError('A transaction is not an eligible payment for this customer.')
        rid = 'SC-' + uuid.uuid4().hex[:10]
        self.lab.db.execute('INSERT INTO fraud_reports(id,request_id,request_json,customer_id,story,message,event_ids,created_at) VALUES(?,?,?,?,?,?,?,?)',
                            (rid, request_id, request_json, customer_id, story, message, encoded(event_ids), now()))
        return self.detail(rid)

    def existing_request(self, request_id, payload):
        text(request_id, 'Request ID', 1, 100)
        row = self.lab.db.execute('SELECT id,request_json FROM fraud_reports WHERE request_id=?', (request_id,)).fetchone()
        if row:
            if row['request_json'] != encoded(payload): raise LabError('Request ID was already used for a different report.', 409)
            return self.detail(row['id'])

    def create(self, customer_id, story, message, event_ids, request_id):
        payload = dict(customer_id=customer_id, story=story, message=message, event_ids=event_ids)
        with self.lab.lock, self.lab.db:
            return self.existing_request(request_id, payload) or self._create(customer_id, story, message, event_ids, request_id, encoded(payload))

    def demo(self, scenario, request_id):
        if isinstance(scenario,str) and scenario.removesuffix('.control') in SCENARIOS:
            return create_scenario(self,scenario,request_id)
        if scenario not in ('first', 'repeat', 'benign'): raise LabError('Choose first, repeat or benign.')
        payload = {'scenario': scenario}
        with self.lab.lock, self.lab.db:
            previous = self.existing_request(request_id, payload)
            if previous: return previous
            cid = {'first': 'C001', 'repeat': 'C002', 'benign': 'C003'}[scenario]
            payee = 'm1' if scenario == 'benign' else 'external:demo-safety'
            self.lab.db.execute("INSERT OR IGNORE INTO accounts(id,label,kind,opening_minor,balance_minor) VALUES('external:demo-safety','External transfer recipient · synthetic','counterparty',0,0)")
            desired = {'first': 120000, 'repeat': 95000, 'benign': 5000}[scenario]
            balance = self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?', (cid + ':wallet',)).fetchone()[0]
            amount = min(desired, balance)
            if amount < 100: raise LabError('The demo resident needs available wallet funds. Choose another existing transaction instead.', 409)
            eid = 'report-transfer-' + uuid.uuid4().hex[:10]
            meta = {'device_id': 'device-' + cid, 'device_known': True, 'authorization_verified': True,
                    'authorized_payee': payee, 'rail': 'Wallet', 'review_flags': self.screen(cid, payee)}
            self.lab.post(eid, cid, 'payment', amount, self.lab.clock_day, cid + ':wallet', payee, meta)
            stories = {
                'first': 'A caller said they were bank support and my wallet was compromised. They told me to move money to a safe account immediately. I entered my PIN myself. Now they have disappeared and I am panicking.',
                'repeat': 'Bank security called about an urgent wallet problem. I was told to protect my money in a secure account and not tell anyone. I approved the transfer on my usual phone. Was I scammed?',
                'benign': 'I paid for groceries using my usual phone and PIN. I recognize this shop and received my items, but the unfamiliar statement description worried me.'}
            message = 'Move your balance to this secure account right now. Do not tell anyone why.' if scenario != 'benign' else 'Thank you for shopping with us. Your receipt is ready.'
            return self._create(cid, stories[scenario], message, [eid], request_id, encoded(payload))

    def start(self, report_id):
        with self.lab.lock, self.lab.db:
            report = self.report(report_id)
            existing = self.lab.db.execute('SELECT id FROM fraud_investigations WHERE report_id=? AND report_revision=? ORDER BY rowid DESC LIMIT 1', (report_id, report['revision'])).fetchone()
            if existing:
                old = self.run(existing[0])
                if old['status'] == 'awaiting_review' and old['context']['evidence_hash'] != self.lab.fingerprint(self.transactions(report)):
                    self.lab.db.execute("UPDATE fraud_investigations SET status='superseded' WHERE id=?", (old['id'],))
                    self.lab.db.execute("UPDATE fraud_reports SET status='reported',revision=revision+1 WHERE id=?", (report_id,))
                    report = self.report(report_id)
                else: return old
            if report['status'] != 'reported': raise LabError('This report is not ready for a new investigation.', 409)
            rid = 'INV-' + uuid.uuid4().hex[:10]
            self.lab.db.execute('INSERT INTO fraud_investigations(id,report_id,report_revision,context,trace,created_at) VALUES(?,?,?,?,?,?)',
                                (rid, report_id, report['revision'], '{}', '[]', now()))
            self.lab.db.execute("UPDATE fraud_reports SET status='investigating' WHERE id=?", (report_id,))
            return self.run(rid)

    def step(self, run_id, expected_step):
        if type(expected_step) is not int or expected_step < 0: raise LabError('Use the current tool-step number.')
        with self.lab.lock, self.lab.db:
            run = self.run(run_id)
            if run['context'].get('controller') == 'adk': raise LabError('Use the ADK investigation endpoint for this run.', 409)
            if expected_step > run['step']: raise LabError('The requested tool step is ahead of this investigation.', 409)
            if expected_step < run['step'] or run['status'] != 'running': return run
            report = self.report(run['report_id']); context = run['context']; step = run['step']
            if report['revision'] != run['report_revision']: raise LabError('Report evidence changed; start a fresh investigation.', 409)
            if step == 0:
                tx = self.transactions(report)
                context.update(transactions=tx, cues=cues(' '.join([report['story'], report['message']] + [a['text'] for a in report['answers']])),
                               report_story=report['story'], report_message=report['message'], answers=report['answers'])
                tool, summary = 'query_customer_ledger', '%d reported payment(s) verified against the simulator ledger.' % len(tx)
                output = {'event_ids': [t['id'] for t in tx], 'total_minor': sum(t['amount_minor'] for t in tx),
                          'customer_id': report['customer_id'], 'report_is_unverified_claim': True}
            elif step == 1:
                tx = context['transactions']; excluded = {t['id'] for t in tx}
                cutoff = min(t['occurred_at'] for t in tx)
                history = [t for t in self.lab.rows("SELECT id,amount_minor,to_account,occurred_at FROM financial_events WHERE customer_id=? AND status='settled' AND kind='payment' AND occurred_at<? ORDER BY occurred_at DESC LIMIT 40", (report['customer_id'], cutoff)) if t['id'] not in excluded]
                median = statistics.median(t['amount_minor'] for t in history) if history else None
                context['signals'] = output = {'method': 'Local behavioral checks v1; not a trained fraud model',
                    'median_previous_payment_minor': median, 'history_event_ids': [t['id'] for t in history],
                    'unusual_amount': any(t['amount_minor'] > 4 * median for t in tx) if median else None,
                    'new_recipient': any(t['to_account'] not in {h['to_account'] for h in history} for t in tx) if history else None,
                    'authorization_recorded': all(t['metadata'].get('authorization_verified') is True for t in tx),
                    'reported_scam_cues': context['cues'], 'distress_used_as_fraud_evidence': False}
                tool, summary = 'check_behavioral_signals', 'Compared recorded activity. Authorization and reported deception are assessed separately.'
            elif step == 2:
                payees = {t['to_account'] for t in context['transactions']}; matches = []
                for memory in self.memories():
                    if memory['source_report_id'] == report['id']: continue
                    shared = sorted(set(memory['pattern']['cues']) & set(context['cues']))
                    same_payee = sorted(payees & set(memory['pattern']['recipient_accounts']))
                    if same_payee or len(shared) >= 2:
                        matches.append({**memory, 'matched_cues': shared, 'matched_recipients': same_payee})
                context['memories'] = sorted(matches, key=lambda m: (bool(m['matched_recipients']), len(m['matched_cues'])), reverse=True)[:3]
                output = {'matches': context['memories'], 'scope': 'Analyst-approved memory only'}
                tool, summary = 'retrieve_reviewed_cases', ('Retrieved %d approved case(s). Add a cross-case check before recommending action.' % len(context['memories'])) if matches else 'No approved case matches yet. Continue using this report and its ledger evidence.'
            elif step == 3:
                memories = context['memories']; payees = sorted({t['to_account'] for t in context['transactions']})
                links = self.lab.rows("SELECT id,customer_id,to_account,amount_minor FROM financial_events WHERE status='settled' AND kind='payment' AND to_account IN (%s) ORDER BY rowid DESC LIMIT 30" % ','.join('?' for _ in payees), payees)
                questions = list(dict.fromkeys(m['next_question'] for m in memories)) if memories else ['Who asked you to make the transfer, and what reason did they give?']
                context['followup'] = output = {'questions': questions, 'related_transfers': links,
                    'memory_ids': [m['id'] for m in memories], 'lessons': [m['lesson'] for m in memories],
                    'effect': 'Added a reviewed-pattern comparison and a targeted follow-up question.' if memories else 'Generic evidence gathering; no prior reviewed case was available.',
                    'limit': 'Similar wording or a shared recipient is a review signal, not proof of the current allegation.'}
                tool = 'compare_reviewed_pattern' if memories else 'request_missing_context'
                summary = output['effect']
            else:
                suspected = len(context['cues']) >= 2
                recommendation = {'disposition': 'suspected_scam' if suspected else 'needs_information',
                    'summary': 'The report describes possible impersonation and a pressured transfer. Recorded authorization does not establish informed intent.' if suspected else 'The records do not establish a scam. Verify the transaction purpose with the customer before deciding.',
                    'facts': ['%d payment(s) found in the customer ledger.' % len(context['transactions']),
                              'Authorization recorded: ' + str(context['signals']['authorization_recorded']).lower()],
                    'evidence_ids': [t['id'] for t in context['transactions']],
                    'memory_ids': [m['id'] for m in context['memories']],
                    'uncertainties': ['Caller identity and the truth of the report are not independently verified.', 'No reimbursement or liability decision has been made.'],
                    'questions': context['followup']['questions'], 'suggested_action': 'request_recall' if suspected else 'support_followup',
                    'suggested_lesson': LESSON, 'suggested_question': QUESTION,
                    'customer_message': 'We have recorded your report and are reviewing the transfer. Please use the official support channel and do not send further money at the caller’s request.'}
                context['evidence_hash'] = self.lab.fingerprint(context['transactions'])
                run['recommendation'] = output = recommendation
                tool, summary = 'prepare_analyst_packet', 'Evidence, reported claims, unknowns and a proposed next step are ready for human review.'
                run['status'] = 'awaiting_review'
                self.lab.db.execute("UPDATE fraud_reports SET status='awaiting_review' WHERE id=?", (report['id'],))
            run['trace'].append({'step': step + 1, 'tool': tool, 'summary': summary, 'output': output, 'created_at': now()})
            self.lab.db.execute('UPDATE fraud_investigations SET step=?,status=?,context=?,trace=?,recommendation=? WHERE id=?',
                                (step + 1, run['status'], encoded(context), encoded(run['trace']), encoded(run['recommendation']) if run['recommendation'] else None, run_id))
            return self.run(run_id)

    def review(self, report_id, investigation_id, disposition, action, note, publish_memory, lesson, next_question):
        if disposition not in ('confirmed_scam', 'not_scam', 'needs_information'): raise LabError('Choose a review disposition.')
        if action not in ('request_recall', 'support_followup'): raise LabError('Choose a supported simulated action.')
        if type(publish_memory) is not bool: raise LabError('Memory publication must be true or false.')
        note = text(note, 'Analyst note', 10, 2000)
        if action == 'request_recall' and disposition != 'confirmed_scam': raise LabError('A recall request requires an analyst-confirmed scam.')
        if publish_memory and disposition != 'confirmed_scam': raise LabError('Only analyst-confirmed scam cases may become scam memory.')
        if publish_memory:
            lesson = text(lesson, 'Reviewed lesson', 10, 1000); next_question = text(next_question, 'Next question', 10, 500)
        command = encoded(dict(investigation_id=investigation_id, disposition=disposition, action=action, note=note,
                               publish_memory=publish_memory, lesson=lesson, next_question=next_question))
        with self.lab.lock, self.lab.db:
            report = self.report(report_id); run = self.run(investigation_id)
            if run['report_id'] != report_id: raise LabError('Investigation belongs to a different report.', 409)
            existing = self.lab.db.execute('SELECT command FROM fraud_reviews WHERE investigation_id=?', (investigation_id,)).fetchone()
            if existing:
                if existing[0] != command: raise LabError('This investigation already has a different review.', 409)
                return self.detail(report_id)
            if run['status'] != 'awaiting_review' or run['report_revision'] != report['revision']:
                raise LabError('Complete the current investigation before reviewing it.', 409)
            if self.lab.fingerprint(self.transactions(report)) != run['context']['evidence_hash']:
                raise LabError('Transaction evidence changed. Refresh the report and investigate again.', 409)
            if self.agent:
                self.agent.harness.guard_review(run)
                warnings=self.agent.amount_warnings(run['recommendation'],run['context'])
                if warnings:raise LabError('Resolve the draft validation warning before approval: '+'; '.join(warnings),409)
            rid = 'REV-' + uuid.uuid4().hex[:10]
            message = {'confirmed_scam': 'An analyst reviewed your report as a scam. We have recorded the next support action. Recovery is not guaranteed.',
                       'not_scam': 'An analyst reviewed the available evidence and did not confirm a scam. Please contact us if you have additional information.',
                       'needs_information': 'We need more information to assess your report. Your case remains open.'}[disposition]
            resolution = {'customer_message': message, 'action': action, 'receipt_id': 'resolution-' + rid,
                          'simulated': True, 'money_recovered_minor': 0, 'analyst_note': note,
                          'questions': run['recommendation']['questions'] if disposition == 'needs_information' else []}
            self.lab.db.execute('INSERT INTO fraud_reviews VALUES(?,?,?,?,?,?,?,?)',
                                (rid, report_id, investigation_id, command, disposition, note, encoded(resolution), now()))
            # The receipt records a simulated support/recall request; it never reverses a ledger transfer.
            self.lab.event(resolution['receipt_id'], report['customer_id'], 'recall_requested' if action == 'request_recall' else 'support_followup', 0,
                           self.lab.clock_day, 'recorded', metadata={'report_id': report_id, 'review_id': rid, 'simulated': True})
            if publish_memory:
                recipients = sorted({t['to_account'] for t in run['context']['transactions'] if t['to_account']})
                # An exact-recipient watch, tested against a different destination; not fraud-model evaluation.
                validation = {'passed': bool(recipients) and all(watch_matches(recipients, p) for p in recipients) and not watch_matches(recipients, 'unrelated:control'),
                              'checks': ['Reviewed recipient matches', 'Unrelated recipient does not match'],
                              'scope': 'Exact-recipient watch only; not a measured fraud-detection accuracy.'}
                memory_id='MEM-'+uuid.uuid4().hex[:10]
                pattern={'cues':run['context']['cues'],'recipient_accounts':recipients,'evidence_ids':run['recommendation']['evidence_ids']}
                self.lab.db.execute('INSERT INTO scam_memories VALUES(?,?,?,?,?,?,?,?)',
                    (memory_id,report_id,rid,encoded(pattern),lesson,next_question,encoded(validation),now()))
                fraud_knowledge.publish(self.lab,memory_id,pattern,run)
            self.lab.db.execute('UPDATE fraud_reports SET status=? WHERE id=?', ('awaiting_customer' if disposition == 'needs_information' else 'resolved', report_id))
            self.lab.db.execute("UPDATE fraud_investigations SET status='reviewed' WHERE id=?", (investigation_id,))
            from fraud_playbook import feedback
            feedback(self.lab,run,rid,disposition)
            return self.detail(report_id)

    def revoke_memory(self,memory_id,reason):
        with self.lab.lock,self.lab.db:return fraud_knowledge.revoke(self.lab,memory_id,reason)

    def answer(self, report_id, answer, expected_revision):
        answer = text(answer, 'Customer reply', 10, 2000)
        if type(expected_revision) is not int: raise LabError('Use the current report revision.')
        with self.lab.lock, self.lab.db:
            report = self.report(report_id)
            if expected_revision != report['revision'] or report['status'] != 'awaiting_customer':
                raise LabError('This report is not waiting for that reply.', 409)
            answers = report['answers'] + [{'text': answer, 'created_at': now()}]
            self.lab.db.execute("UPDATE fraud_reports SET answers=?,status='reported',revision=revision+1 WHERE id=?", (encoded(answers), report_id))
            return self.detail(report_id)
