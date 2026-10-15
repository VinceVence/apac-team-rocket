"""Train our fixed request-tool pack locally; no cloud calls or payment release."""
import hashlib,json
from pathlib import Path
from request_corpus import examples,CORPUS_VERSION
from request_models import run


def build(root):
    rows=examples(['C%03d'%i for i in range(1,101)])
    candidates=run({'mode':'search','rows':rows,'recipe':'word'})
    candidates.append(run({'mode':'refine','rows':rows,'recipe':'word_char','regularization':.6}))
    candidates=run({'mode':'finalize','rows':rows,'candidates':candidates})
    catalog=json.loads((root/'catalog.json').read_text());new_ids={'payment_behavior_v1','payment_request_v1'}
    catalog['models']=[m for m in catalog['models'] if m['model_id'] not in new_ids]
    for identifier,candidate in [('payment_behavior_v1',candidates[0]),('payment_request_v1',next(c for c in candidates if c['preselected']))]:
        path=root/(identifier+'.json');body=json.dumps(candidate['artifact'],indent=2,allow_nan=False)+'\n';path.write_text(body)
        catalog['models'].append({'model_id':identifier,'version':'1.0','name':'Learned payment behavior' if identifier=='payment_behavior_v1' else 'Learned request patterns',
            'task':'Observed payment behavior compared with generator-labelled scam examples; cannot rule out deception' if identifier=='payment_behavior_v1' else 'Learned prepayment request and channel patterns in a synthetic corpus',
            'positive_class':'Generator-labelled suspicious payment','release_status':'synthetic_advisory_only',
            'training_cutoff':max(r['label_available_at'] for r in rows if r['split']=='train'),
            'eligible_population':'Synthetic payments with versioned prepayment inputs',
            'file':path.name,'artifact_sha256':hashlib.sha256(body.encode()).hexdigest(),
            'evaluation_reference':'web/model_artifacts/request_evaluation.json',
            'limitation':'Advisory only; uncalibrated and not approved to block payments. '+('Passed' if candidate['gate_passed'] else 'Failed')+' the synthetic prevention gate.'})
    (root/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    result={'corpus':CORPUS_VERSION,'scope':'Synthetic development benchmark. No production or bank accuracy claim.',
        'selection':'Initial word recipe and one predeclared word+character refinement; validation chooses before final test. No test-driven retuning.',
        'candidates':[{k:v for k,v in c.items() if k not in ('artifact','validation_errors')} for c in candidates]}
    (root/'request_evaluation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    result=build(Path(__file__).with_name('model_artifacts'));print(json.dumps({'registered':['payment_behavior_v1','payment_request_v1'],'candidates':[{k:c[k] for k in ('recipe','preselected','gate_passed','test')} for c in result['candidates']]}))
