"""Build one advisory JSON artifact locally. No cloud, Gemini, release or activation."""
import argparse,hashlib,json
from pathlib import Path
from risk_models import synthetic_examples,train,VERSION

def build(destination):
    rows=synthetic_examples(['C%03d'%i for i in range(1,101)])
    plan={'feature_groups':['transaction','request'],'recipes':['logistic','boosted_tree']}
    results=train({'rows':rows,'plan':plan});chosen=next(r for r in results if r.get('preselected'))
    path=destination/'synthetic_triage_v1.json';destination.mkdir(parents=True,exist_ok=True)
    body=json.dumps(chosen['artifact'],sort_keys=True,indent=2,allow_nan=False)+'\n';path.write_text(body)
    evaluation={'source':'Generator-labelled synthetic benchmark, not analyst-reviewed production data.',
        'training_customers':60,'validation_customers':20,'test_customers':20,'selection':'Validation only; ties favor simpler logistic. No test-driven promotion.',
        'selected':chosen['recipe'],'validation':chosen['validation'],'test':chosen['test'],'prevention_gate_passed':chosen['gate_passed'],
        'reasons':chosen['reasons'],'candidates':[{k:v for k,v in r.items() if k!='artifact'} for r in results]}
    (destination/'synthetic_triage_evaluation.json').write_text(json.dumps(evaluation,indent=2)+'\n')
    entry={'model_id':'synthetic_triage_v1','version':'1.0','name':'Learned payment patterns','task':'Similarity to scam patterns in a synthetic payment-request benchmark',
        'positive_class':'Generator-labelled scam request','release_status':'synthetic_advisory_only',
        'training_cutoff':max(r['label_available_at'] for r in rows if r['split']=='train'),
        'eligible_population':'Synthetic wallet payments with complete risk-features-v1 snapshots',
        'file':path.name,'artifact_sha256':hashlib.sha256(body.encode()).hexdigest(),
        'evaluation_reference':'web/model_artifacts/synthetic_triage_evaluation.json',
        'limitation':'Synthetic-only, uncalibrated advisory score. Not DS-approved for prevention or real customer decisions. Final-test gate: '+('passed' if chosen['gate_passed'] else 'failed')}
    (destination/'catalog.json').write_text(json.dumps({'models':[entry]},indent=2)+'\n')
    return evaluation

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default=str(Path(__file__).with_name('model_artifacts')));args=p.parse_args()
    result=build(Path(args.output));print(json.dumps({k:v for k,v in result.items() if k!='candidates'}))
