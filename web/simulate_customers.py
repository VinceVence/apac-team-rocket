"""Exercise the customer-agent tools and marketing feedback loop over local HTTP."""
import json
import time
from pathlib import Path
from simulate import sandbox


def main():
    started=time.perf_counter()
    with sandbox() as (server,call,state):
        run=call('/api/mesh/start',{'playbook_id':'customer-growth','mode':'baseline','request_id':'customer-dna-demo'})
        while run['status']=='running':
            run=call('/api/mesh/runs/'+run['id']+'/step',{'expected_step':run['step']})
            turn=run['turns'][-1]
            print(str(run['step'])+'. '+turn['from_role']+' → '+(turn['to_role'] or '')+' · '+turn['decision']['tool'],flush=True)
        assert run['status']=='completed',run.get('error')
        before=call('/api/customer-data');campaign=before['campaigns'][0]
        result=call('/api/customer-data/advance',{'expected_tick':server.world.state()['tick'],'days':7,'activity':2})
        assert not result['replayed']
        after=call('/api/customer-data');matured=after['campaigns'][0]
        assert matured['status']=='completed'
        feedback=server.customer_data.build_layers()
        final=call('/api/state');assert final['ledger_balanced'] and final['budget']['calls_today']==0
        report={'mode':'Scripted tool rehearsal; not live agent reasoning','roles':run['playbook']['role_ids'],
                'elapsed_seconds':round(time.perf_counter()-started,3),'pipeline_before':before['pipeline'],
                'model_results':[{k:m.get(k) for k in ('target','fitted','eligible','auc','brier','baseline_brier','accuracy','gate_reasons')} for m in before['models']],
                'dna_customers':len(before['dna']),'sample_dna':before['dna'][:3], 'campaign_before':campaign,
                'campaign_after':matured,'feedback_pipeline':feedback,'run':run,
                'ledger_balanced':final['ledger_balanced'],'live_gemini_calls':0,
                'limitations':['Synthetic behavior and outcomes; no production accuracy or marketing effect claim.',
                               'The eight tasks are predictive tags; randomized pilot outcomes separately measure response.',
                               'Gemini decision quality remains untested while live calls are disabled.']}
    output=Path(__file__).resolve().parent/'reports'/'latest-customer-dna.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(str(output)+' · '+str(report['elapsed_seconds'])+' seconds',flush=True)


if __name__=='__main__':main()
