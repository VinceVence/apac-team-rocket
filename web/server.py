"""Loopback-only local server. Database and credentials are outside the public directory."""
import argparse
import functools
import json
import os
import secrets
import signal
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from agents import Agents, Config
from lab import Lab, LabError, encoded
from world import World
from science import Science
from macro import Macro,TABLES as MACRO_TABLES
from science_ops import ScienceTeam,TABLES as SCIENCE_TABLES
from mesh import Mesh,TABLES as MESH_TABLES
from customer_data import CustomerData,TABLES as CUSTOMER_TABLES
from fraud_desk import FraudDesk,TABLES as FRAUD_TABLES
from fraud_agent import FraudAgent
from fraud_runner import InvestigationRunner
from demo_guard import DemoGuard
from world_demo import WorldDemo

ROOT=Path(__file__).resolve().parent


class MintTownServer(ThreadingHTTPServer):
    def server_close(self):
        super().server_close()
        if hasattr(self,'world_demo'):self.world_demo.close()
        if hasattr(self, 'fraud_runner'): self.fraud_runner.close()


def make_server(port=3000, db_path=None, config=None, cloud=None, public_host=None):
    (ROOT/'data').mkdir(exist_ok=True)
    canary=bool(cloud and os.getenv('MINTTOWN_CLOUD_LIVE_CANARY')=='1' and os.getenv('MINTTOWN_LIVE')=='1' and os.getenv('MINTTOWN_FRAUD_LIVE')=='1')
    if canary and os.getenv('GOOGLE_CLOUD_PROJECT')!='minttown-apac-2026':raise ValueError('The live pilot is scoped to the MintTown project.')
    lab=Lab(db_path or ROOT/'data'/'minttown.sqlite3'); agents=Agents(lab,Config(live=canary,model='gemini-3.5-flash-lite') if cloud else config)
    world=World(lab);science=Science(lab)
    macro=Macro(lab,world,agents);world.macro=macro
    science_team=ScienceTeam(lab,science,agents)
    if not cloud:
        try:science_team.autorun()
        except LabError:pass  # A recorded failed quality gate must not prevent the UI from opening.
    customer_data=CustomerData(lab);world.customer_data=customer_data
    mesh=Mesh(lab,world,macro,science_team,agents,customer_data)
    fraud_desk=FraudDesk(lab,world);world.fraud_desk=fraud_desk
    checkpoint=(lambda: cloud.save(lab)) if cloud else None
    fraud_agent=FraudAgent(fraud_desk,agents,checkpoint=checkpoint,live_case_limit=1 if canary else None)
    fraud_runner=InvestigationRunner(fraud_agent)
    guard=DemoGuard(lab,checkpoint,live_canary=canary) if cloud else None
    world_demo=WorldDemo(world,fraud_desk,fraud_runner,checkpoint,guard)
    if cloud: cloud.initialize(lab)
    csrf=secrets.token_urlsafe(32)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)

        def allowed_host(self):
            return self.headers.get('Host') in tuple(h for h in (public_host,'localhost:'+str(self.server.server_port),'127.0.0.1:'+str(self.server.server_port)) if h)

        def end_headers(self):
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            super().end_headers()

        def reply(self,status,value):
            if cloud and self.command=='POST' and status<400: cloud.save(lab)
            body=encoded(value).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

        def do_GET(self):
            if urlsplit(self.path).path=='/healthz': return self.reply(200 if not cloud or cloud.healthy else 503,{'healthy':not cloud or cloud.healthy})
            if not self.allowed_host(): return self.reply(403,{'error':'Use the loopback address.'})
            path=urlsplit(self.path).path
            if cloud and not cloud.healthy and path.startswith('/api/'):
                return self.reply(503,{'error':'Cloud state is unavailable. Retry after this instance restarts.'})
            try:
                if guard and path.startswith('/api/'):guard.allow('GET',path)
                if path=='/api/state':
                    with lab.lock:
                        result=lab.snapshot();result.update(budget=agents.budget(),csrf_token=csrf)
                        result['world']=world.status()
                        result['demo']=world_demo.status()
                        result['macro']={'policy':macro.policy(),'metrics':macro.metrics(world.state()['tick']),'goods':macro.goods(),'due':macro.due()}
                        for table in ('simulation_state','service_actions','model_runs','fraud_agent_turns','fraud_evidence_snapshots',*MACRO_TABLES,*SCIENCE_TABLES,*MESH_TABLES,*CUSTOMER_TABLES,*FRAUD_TABLES):
                            result['tables'][table]=lab.db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                    return self.reply(200,result)
                if path=='/api/science':return self.reply(200,science_team.dashboard())
                if path=='/api/customer-data':return self.reply(200,customer_data.dashboard())
                if path=='/api/fraud-desk':return self.reply(200,fraud_desk.dashboard())
                if path=='/api/cloud':return self.reply(200,{**cloud.status(lab),'guardrails':guard.status(),'gemini':'one-case private pilot' if canary else 'disabled'} if cloud else {'enabled':False})
                if path.startswith('/api/fraud-desk/reports/'):
                    return self.reply(200,fraud_desk.detail(path.rsplit('/',1)[-1]))
                if path=='/api/mesh':
                    from adk_mesh import runtime
                    return self.reply(200,{**mesh.catalogue(),'runtime':runtime()})
                if path.startswith('/api/mesh/runs/'):
                    with lab.lock:return self.reply(200,mesh.run(path.rsplit('/',1)[-1]))
                if path=='/api/macro':return self.reply(200,macro.dashboard())
                if path.startswith('/api/evidence/'):
                    with lab.lock: packet=lab.evidence(path.rsplit('/',1)[-1])
                    return self.reply(200,{'packet':packet,'evidence_hash':lab.fingerprint(packet)})
                if path.startswith('/api/runs/'):
                    with lab.lock: run=agents.public_run(path.rsplit('/',1)[-1])
                    return self.reply(200,run)
                if path.startswith('/api/'): return self.reply(404,{'error':'Endpoint not found.'})
                if path not in ('/','/index.html','/app.js','/mesh-ui.js','/customer-ui.js','/fraud-ui.js','/town.js','/styles.css','/mark.svg','/favicon.svg') and not path.startswith('/fonts/'):
                    return self.reply(404,{'error':'File not found.'})
                if '..' in path or '%' in path: return self.reply(404,{'error':'File not found.'})
                return super().do_GET()
            except LabError as exc: return self.reply(exc.status,{'error':str(exc)})

        def do_POST(self):
            origins=('http://localhost:'+str(self.server.server_port),'http://127.0.0.1:'+str(self.server.server_port))
            if public_host:origins+=('https://'+public_host,)
            if (not self.allowed_host() or self.headers.get('Origin') not in (None,*origins) or
                not secrets.compare_digest(self.headers.get('X-MintTown-Token',''),csrf)):
                return self.reply(403,{'error':'Request origin or session token was rejected.'})
            try:
                if cloud and not cloud.healthy:raise LabError('Cloud state is unavailable. Retry after this instance restarts.',503)
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=12288: raise LabError('Invalid request size.',413)
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict): raise LabError('Expected a JSON object.')
                path=urlsplit(self.path).path
                if guard:guard.allow('POST',path,body)
                if path=='/api/world/start':
                    if set(body)!={'expected_run','activity','speed'}:raise LabError('Invalid world start.')
                    return self.reply(200,world_demo.start(**body))
                if path=='/api/world/stop':
                    if set(body)!={'expected_run'}:raise LabError('Invalid world stop.')
                    return self.reply(200,world_demo.stop(**body))
                if path=='/api/cloud/export':
                    if not cloud:raise LabError('BigQuery export is available on the hosted demo.',409)
                    if set(body)!={'request_id'}:raise LabError('Exports require a request ID and use only the approved simulator tables.')
                    return self.reply(200,cloud.export(lab,body['request_id']))
                if path=='/api/fraud-agent/start':
                    if 'report_id' not in body or set(body)-{'report_id','mode','automatic'}:raise LabError('Invalid ADK start command.')
                    automatic=body.pop('automatic',True)
                    if type(automatic) is not bool:raise LabError('Automatic must be true or false.')
                    run=(fraud_runner.start if automatic else fraud_agent.start)(**body)
                    queued=run['context'].get('execution',{}).get('status') in ('queued','running')
                    return self.reply(202 if queued else 200,run)
                if path=='/api/fraud-agent/step':
                    if set(body)!={'run_id','expected_step'}:raise LabError('Invalid ADK generation command.')
                    return self.reply(200,fraud_agent.step(**body))
                if path=='/api/fraud-agent/handoff':
                    if set(body)!={'run_id'}:raise LabError('Invalid analyst handoff.')
                    return self.reply(200,fraud_agent.handoff(**body))
                if path.startswith('/api/fraud-desk/'):
                    commands={
                        '/api/fraud-desk/demo': (fraud_desk.demo, {'scenario','request_id'}),
                        '/api/fraud-desk/report': (fraud_desk.create, {'customer_id','story','message','event_ids','request_id'}),
                        '/api/fraud-desk/investigate': (fraud_desk.start, {'report_id'}),
                        '/api/fraud-desk/step': (fraud_desk.step, {'run_id','expected_step'}),
                        '/api/fraud-desk/review': (fraud_desk.review, {'report_id','investigation_id','disposition','action','note','publish_memory','lesson','next_question'}),
                        '/api/fraud-desk/reply': (fraud_runner.reply, {'report_id','answer','expected_revision'})}
                    if path not in commands:raise LabError('Endpoint not found.',404)
                    handler,fields=commands[path]
                    if set(body)!=fields:raise LabError('Invalid fraud-desk command fields.')
                    return self.reply(200,handler(**body))
                if path=='/api/customer-data/advance':
                    if set(body)!={'expected_tick','days','activity'} or type(body['days']) is not int or not 1<=body['days']<=7 or type(body['expected_tick']) is not int or type(body['activity']) is not int or body['activity'] not in range(1,5):raise LabError('Use a current tick, 1–7 days and 1–4 payments per hour.')
                    with lab.lock:
                        if body['expected_tick']!=world.state()['tick']:return self.reply(200,{'replayed':True,'world':world.status()})
                        for _ in range(body['days']*24):
                            result=world.advance(world.state()['tick'],body['activity'])
                            if result.get('day_closed'):science_team.autorun()
                        return self.reply(200,{'replayed':False,'world':world.status(),'customer_data':customer_data.summary()})
                if path=='/api/mesh/start':
                    if not {'playbook_id','mode','request_id'}<=set(body) or set(body)-{'playbook_id','mode','request_id','case_id','objective'}:raise LabError('Invalid playbook run request.')
                    return self.reply(200,mesh.start(**body))
                if path.startswith('/api/mesh/playbooks/'):
                    if set(body)!={'expected_revision','objective','prompts','max_turns'}:raise LabError('Only the objective, role prompts and turn limit can be edited.')
                    return self.reply(200,mesh.save(path.rsplit('/',1)[-1],**body))
                if path.startswith('/api/mesh/runs/') and path.endswith('/step'):
                    if set(body)!={'expected_step'}:raise LabError('Expected the current turn number.')
                    from adk_mesh import dispatch
                    return self.reply(200,dispatch(mesh,path.split('/')[-2],body['expected_step']))
                if path=='/api/macro/review':
                    if set(body)!={'mode'} or not isinstance(body['mode'],str):raise LabError('Invalid policy review request.')
                    return self.reply(200,macro.review(body['mode']))
                if path=='/api/policy/apply':
                    if set(body)!={'decision_id'} or not isinstance(body['decision_id'],str):raise LabError('Invalid policy command.')
                    return self.reply(200,macro.apply(body['decision_id']))
                if path=='/api/bank/loan':
                    if set(body)!={'customer_id','amount_minor','operation_id'}:raise LabError('Invalid bank request.')
                    return self.reply(200,macro.request_loan(body['customer_id'],body['amount_minor'],body['operation_id']))
                if path=='/api/world/step':
                    if set(body)!={'expected_tick','activity','scenario'}:raise LabError('Invalid world step.')
                    result=world.advance(body['expected_tick'],body['activity'],body['scenario'])
                    if result.get('day_closed') and not cloud:
                        try:
                            science_result=science_team.autorun()
                            if science_result:
                                pipeline=science_result['pipeline']
                                result['science_handoff']={'id':pipeline['id'],'cutoff':pipeline['cutoff'],
                                    'status':pipeline['status'],'stages':pipeline['stages'],
                                    'analysis':pipeline['report'].get('analysis'),
                                    'mode':pipeline['report'].get('mode','baseline'),
                                    'created_models':pipeline['report'].get('created_models',0),
                                    'trained_models':pipeline['report'].get('trained_models',0),
                                    'releases':pipeline['report'].get('releases',[]),
                                    'batch_scored':pipeline['report'].get('batch_scored',{})}
                        except LabError as exc:result['science_notice']=str(exc)
                    return self.reply(200,result)
                if path=='/api/science/run':
                    if set(body) not in (set(),{'mode'}):raise LabError('Only a specialist mode may be selected.')
                    return self.reply(200,science_team.run_pipeline(body.get('mode','baseline')))
                if path=='/api/models/promote':
                    if set(body)!={'model_id','expected_active_id'} or not isinstance(body['model_id'],str) or not (body['expected_active_id'] is None or isinstance(body['expected_active_id'],str)):raise LabError('Invalid release request.')
                    return self.reply(200,science_team.promote(body['model_id'],body['expected_active_id']))
                if path.startswith('/api/models/'):
                    parts=path.split('/')
                    if len(parts)!=5:raise LabError('Endpoint not found.',404)
                    kind,action=parts[3:]
                    if action=='predict':
                        if set(body)!={'customer_id'}:raise LabError('Predictions accept a known customer ID; raw feature injection is disabled.')
                        return self.reply(200,science_team.serve(kind,body['customer_id']))
                    if action=='rollback':
                        if set(body)!={'expected_active_id'} or not isinstance(body['expected_active_id'],str):raise LabError('Invalid rollback request.')
                        return self.reply(200,science_team.rollback(kind,body['expected_active_id']))
                    raise LabError('Endpoint not found.',404)
                if path=='/api/services/block-device':
                    if set(body)!={'case_id','run_id'} or not all(isinstance(v,str) for v in body.values()):raise LabError('Invalid service request.')
                    return self.reply(200,world.block_device(body['case_id'],body['run_id']))
                if path=='/api/analyze':
                    if set(body)!={'case_id','mode'} or not all(isinstance(v,str) for v in body.values()): raise LabError('Invalid investigation request.')
                    return self.reply(200,agents.analyze(body['case_id'],body['mode']))
                if path=='/api/apply':
                    if set(body)!={'case_id','run_id'} or not all(isinstance(v,str) for v in body.values()): raise LabError('Invalid decision request.')
                    return self.reply(200,lab.apply_decision(body['case_id'],body['run_id']))
                raise LabError('Endpoint not found.',404)
            except LabError as exc: return self.reply(exc.status,{'error':str(exc)})
            except (ValueError,TypeError): return self.reply(400,{'error':'Invalid JSON request.'})
            except Exception: return self.reply(500,{'error':'The local service could not complete this request.'})

        def log_message(self,format,*args):
            # Request bodies, headers and provider credentials never enter access logs.
            pass

    server=MintTownServer(('0.0.0.0' if cloud else '127.0.0.1',port),Handler)
    server.lab=lab;server.agents=agents
    server.world=world;server.science=science
    server.macro=macro
    server.science_team=science_team
    server.mesh=mesh
    server.customer_data=customer_data
    server.fraud_desk=fraud_desk
    server.fraud_agent=fraud_agent
    server.fraud_runner=fraud_runner
    server.demo_guard=guard
    server.world_demo=world_demo
    return server


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=int(os.getenv('PORT','3000')))
    args=parser.parse_args(); cloud=None; db_path=None
    if os.getenv('K_SERVICE'):
        from cloud_data import CloudData
        cloud=CloudData.environment()
        db_path=Path(tempfile.mkdtemp(prefix='minttown-'))/'minttown.sqlite3'; cloud.restore(db_path)
    server=make_server(args.port,db_path,cloud=cloud,public_host=os.getenv('MINTTOWN_PUBLIC_HOST'))
    def terminate(signum, frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,terminate)
    print('MintTown: http://127.0.0.1:%d · %s' % (server.server_port,server.agents.budget()['mode']),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close();server.lab.db.close()
