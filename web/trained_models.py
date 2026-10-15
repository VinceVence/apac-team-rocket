"""Versioned, data-only CPU predictors. No pickle, downloads or executable artifacts."""
import hashlib
import json
import math
from pathlib import Path

from lab import LabError,encoded

ROOT=Path(__file__).with_name('model_artifacts')


def read_json(path):
    body=path.read_bytes()
    if len(body)>262144:raise LabError('Model artifact exceeds the size limit.',413)
    return json.loads(body),hashlib.sha256(body).hexdigest()


def catalog(lab=None):
    path=ROOT/'catalog.json'
    entries=read_json(path)[0].get('models',[]) if path.exists() else []
    if lab and lab.db.execute("SELECT 1 FROM sqlite_master WHERE name='risk_model_registry'").fetchone():
        entries += [json.loads(r['card_json'])|{'_registry_id':r['id']} for r in lab.rows("SELECT * FROM risk_model_registry WHERE status='advisory' ORDER BY created_at DESC LIMIT 2")]
    return entries


def artifact(entry,lab=None):
    from risk_models import ALLOWED,VERSION
    if entry.get('_registry_id'):
        if not lab:raise LabError('Registered artifact store is unavailable.',409)
        row=lab.db.execute("SELECT artifact_json FROM risk_model_registry WHERE id=? AND status='advisory'",(entry['_registry_id'],)).fetchone()
        if not row:raise LabError('Registered artifact is no longer available.',409)
        model=json.loads(row['artifact_json']);digest=hashlib.sha256(row['artifact_json'].encode()).hexdigest()
    else:
        path=(ROOT/entry['file']).resolve()
        if path.parent!=ROOT.resolve() or path.suffix!='.json':raise LabError('Predictor artifact path is not allowed.',403)
        model,digest=read_json(path)
    if digest!=entry['artifact_sha256']:raise LabError('Predictor artifact digest changed.',409)
    if model.get('kind')=='request_logistic':
        from request_models import validate_artifact
        return validate_artifact(model)
    names=model.get('features',[])
    if model.get('feature_version')!=VERSION or not names or len(names)!=len(set(names)) or not set(names)<=ALLOWED:raise LabError('Unsupported trained feature contract.',422)
    if model.get('kind') not in ('logistic','boosted_tree'):raise LabError('Unsupported data-only model format.',422)
    if model['kind']=='logistic':
        if any(len(model.get(k,[]))!=len(names) for k in ('coefficients','means','scales')) or any(v<=0 for v in model['scales']):raise LabError('Invalid logistic model dimensions.',422)
    else:
        if not 1<=len(model.get('trees',[]))<=32 or 'initial_score' not in model:raise LabError('Tree model lacks its bounded ensemble or initial score.',422)
        for tree in model['trees']:
            n=len(tree['feature'])
            if not 1<=n<=63 or any(len(tree[k])!=n for k in ('children_left','children_right','threshold','value')):raise LabError('Invalid tree dimensions.',422)
            for i,(left,right) in enumerate(zip(tree['children_left'],tree['children_right'])):
                if left==right==-1:continue
                if not i<left<n or not i<right<n or not 0<=tree['feature'][i]<len(names):raise LabError('Invalid or cyclic model tree.',422)
    def finite(v):
        if isinstance(v,dict):return all(finite(x) for x in v.values())
        if isinstance(v,list):return all(finite(x) for x in v)
        return not isinstance(v,(int,float)) or math.isfinite(v)
    if not finite(model):raise LabError('Nonfinite model parameter.',422)
    return model


def score(model,values):
    x=[float(values[k]) for k in model['features']]
    if not all(math.isfinite(v) for v in x):raise LabError('Nonfinite model input.',422)
    if model['kind']=='logistic':z=model['intercept']+sum(w*(v-m)/s for w,v,m,s in zip(model['coefficients'],x,model['means'],model['scales']))
    else:
        z=model['initial_score']
        for tree in model['trees']:
            node=0
            for _ in range(64):
                if tree['children_left'][node]==-1:break
                node=tree['children_left'][node] if x[tree['feature'][node]]<=tree['threshold'][node] else tree['children_right'][node]
            z+=model['parameters']['learning_rate']*tree['value'][node][0][0]
    return 1/(1+math.exp(-max(-700,min(700,z))))


def manifests(lab=None):
    from risk_models import VERSION
    result={}
    for entry in catalog(lab):
        card={k:v for k,v in entry.items() if k not in ('file','_registry_id')}
        card.update(score_kind='uncalibrated_model_score',calibrated=False,feature_version=VERSION,
            contract_version='fraud-model-contract-v1',missing_input_behavior='not_available; never zero risk',allowed_use='investigation_only',
            adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            feature_builder_sha256=hashlib.sha256(Path(__file__).with_name('risk_models.py').read_bytes()+Path(__file__).with_name('prevention.py').read_bytes()+Path(__file__).with_name('request_models.py').read_bytes()).hexdigest())
        try:
            model=artifact(entry,lab);card['required_inputs']=model.get('features',model.get('numeric_features',[])+(['recorded_prepayment_message'] if any(b!='transaction' for b in model.get('blocks',[])) else []));card['available']=True;card['feature_version']=model['feature_version']
        except (LabError,ValueError,KeyError,OSError,TypeError) as exc:card.update(available=False,required_inputs=[],unavailable_reason=str(exc))
        result[entry['model_id']]=card
    return result


def predict(model_id,transactions,lab=None):
    from risk_models import VERSION
    entry=next(e for e in catalog(lab) if e['model_id']==model_id);model=artifact(entry,lab);records=[];predictions=[]
    for tx in transactions:
        m=tx['metadata'];saved=m.get('risk_features',{});missing=[]
        if model['kind']=='request_logistic':
            from request_models import NUMERIC,predict as request_predict,normalized
            ctx=m.get('payment_context',{});needs_message=any(b!='transaction' for b in model['blocks'])
            message=ctx.get('message','') if isinstance(ctx,dict) and ctx.get('before_payment') is True and ctx.get('kind')=='payment_request' else ''
            if m.get('risk_feature_version')!=VERSION or not m.get('risk_recorded_at'):missing.append('versioned_prepayment_features')
            missing += [k for k in NUMERIC if type(saved.get(k)) not in (int,float) or not math.isfinite(saved[k])]
            missing += [k for k in ('device_known','authorization_verified') if type(m.get(k)) is not bool]
            if needs_message and (not isinstance(message,str) or not message):missing.append('recorded_prepayment_message')
            value=request_predict(model,[{'request_text':message,'features':saved}])[0] if not missing else None
            records.append({'event_id':tx['id'],'features':{k:saved.get(k) for k in NUMERIC},
                'request_hash':hashlib.sha256(normalized(message).encode()).hexdigest() if isinstance(message,str) else None,
                'available_at':m.get('risk_recorded_at'),'missing_inputs':sorted(set(missing))})
            predictions.append({'event_id':tx['id'],'available':not missing,'signal_score':value,'matched_features':model['blocks'] if not missing else []})
            continue
        if m.get('risk_feature_version')!=VERSION or not m.get('risk_recorded_at'):missing.append('versioned_prepayment_features')
        missing += [k for k in model['features'] if type(saved.get(k)) not in (int,float) or not math.isfinite(saved[k])]
        # Do not turn an absent message into a benign risk inference.
        if any(k in model['features'] for k in ('safe_account_request','unlock_earnings','withdrawal_fee')) and saved.get('message_available')!=1:missing.append('recorded_prepayment_message')
        values={k:saved.get(k) for k in model['features']};value=score(model,values) if not missing else None
        records.append({'event_id':tx['id'],'features':values,'available_at':m.get('risk_recorded_at'),'missing_inputs':sorted(set(missing))})
        predictions.append({'event_id':tx['id'],'available':not missing,'signal_score':value,
            'matched_features':[k for k,v in values.items() if isinstance(v,(int,float)) and v>0] if not missing else []})
    valid=[r['signal_score'] for r in predictions if r['available']];value=max(valid,default=None)
    return {'detector_id':model_id,'name':entry['name'],'version':entry['version'],'features':model.get('features',model.get('blocks',[])),
        'available':bool(valid),'signal_score':value,'calibrated_fraud_probability':None,
        'result':'elevated learned signal' if value is not None and value>=model['threshold'] else 'no elevated learned signal' if valid else 'insufficient evidence',
        'threshold':model['threshold'],'kind':'trained_synthetic_advisory','predictions':predictions,
        'limitation':entry['limitation'],'input_source':'Immutable prepayment feature snapshot; no complaint, outcome or hidden label inputs.'},records
