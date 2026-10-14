"""Offline model-harness execution report. Never constructs a paid model client."""
import argparse,json,tempfile,hashlib,importlib.metadata
from pathlib import Path
from unittest.mock import patch
from agents import Config
from server import make_server
from fraud_scenarios import SCENARIOS


def evaluate():
    rows=[]
    for scenario in SCENARIOS:
        for control in (False,True):
            with tempfile.TemporaryDirectory(prefix='harness-eval-') as folder,patch('google.genai.Client.__init__',side_effect=AssertionError('Paid model disabled')):
                server=make_server(0,Path(folder)/'case.db',Config(live=False))
                try:
                    desk,agent=server.fraud_desk,server.fraud_agent
                    case=desk.demo(scenario+('.control' if control else ''),'evaluation')
                    run=agent.start(case['id'])
                    for _ in range(7):
                        if run['status']=='awaiting_customer':
                            current=desk.report(case['id']);desk.answer(case['id'],SCENARIOS[scenario]['control_reply' if control else 'reply'],current['revision']);run=agent.start(case['id'])
                        if run['status']!='running':break
                        run=agent.step(run['id'],run['step'])
                    detail=desk.detail(case['id']);harness=detail['harness']
                    proposed=(run['recommendation'] or {}).get('disposition')
                    checks={'within_shared_limit':run['budget']['case_calls']<=5,
                        'at_most_one_specialist':len(harness['tasks'])<=1,
                        'no_self_approval':not detail['reviews'] and not desk.memories(),
                        'ledger_balanced':server.lab.integrity(),
                        'safe_terminal_state':run['status'] in ('awaiting_review','budget_exhausted','awaiting_customer'),
                        'judge_pass_before_review':run['status']!='awaiting_review' or bool(harness['checks'] and harness['checks'][0]['passed']),
                        'no_confirmed_verdict':proposed in ('suspected_scam','likely_legitimate','needs_information',None)}
                    rows.append({'scenario':scenario,'fixture':'legitimate lookalike' if control else 'reported scam',
                        'status':run['status'],'proposal':proposed,'calls':run['budget']['case_calls'],
                        'tools':[t['tool'] for t in detail['decision_trail']],
                        'roles':[t['role'] for t in detail['decision_trail']],
                        'judge_results':harness['checks'],'checks':checks,'passed':all(checks.values())})
                finally:server.server_close();server.lab.db.close()
    from fraud_agent import MODEL,PROMPT_VERSION,TOOL_CONTRACT_VERSION
    from fraud_harness import VERSION
    files=('fraud_agent.py','fraud_adk.py','fraud_runner.py','fraud_harness.py','fraud_harness_fixtures.py','fraud_models.py','fraud_knowledge.py','prevention.py','fraud_detectors.py','settings.py')
    configuration={'model':MODEL,'prompt_version':PROMPT_VERSION,'tool_contract':TOOL_CONTRACT_VERSION,'harness':VERSION,'adk':importlib.metadata.version('google-adk'),'source_hashes':{f:hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest() for f in files}}
    return {'configuration':configuration,'mode':'fake','paid_model_calls':0,'scope':'Execution, guardrails and final-state checks; not Gemini accuracy or production fraud performance.',
        'passed':all(r['passed'] for r in rows),'cases':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='output/harness/evaluation.json');args=parser.parse_args()
    result=evaluate();path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'cases':len(result['cases']),'paid_model_calls':0,'output':str(path)}))
    raise SystemExit(0 if result['passed'] else 1)
