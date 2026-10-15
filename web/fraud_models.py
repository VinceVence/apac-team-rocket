"""Trusted local predictor contracts. No dynamic imports, arbitrary URLs or label features."""
import hashlib
from pathlib import Path

from fraud_detectors import REGISTRY, predict_case
from lab import LabError, encoded
import trained_models

FEATURE_VERSION='prepayment-signals-v1'
CONTRACT_VERSION='fraud-model-contract-v1'
TARGETS={
 'device_integrity_v1':'Unrecognized device together with unverified authorization',
 'payment_velocity_v1':'Rapid payments together with a new recipient',
 'message_intent_v1':'Paired deception indicators in a recorded payment request',
}


def manifests(lab=None):
    # Pin both the predictor and feature implementation, not merely a display version.
    artifact=hashlib.sha256((Path(__file__).read_bytes()+Path(__file__).with_name('fraud_detectors.py').read_bytes()+Path(__file__).with_name('prevention.py').read_bytes())).hexdigest()
    rules={identifier:{'model_id':identifier,'version':card['version'],'name':card['name'],
        'task':TARGETS[identifier],'positive_class':None,'score_kind':'rule_signal','calibrated':False,
        'release_status':'registered_demo_rule','training_cutoff':None,'artifact_sha256':artifact,
        'feature_version':FEATURE_VERSION,'required_inputs':list(card['features']),
        'eligible_population':'Synthetic wallet payments with the declared prepayment inputs',
        'missing_input_behavior':'not_available; never zero risk','evaluation_reference':'web/test_fraud_models.py',
        'contract_version':CONTRACT_VERSION} for identifier,card in REGISTRY.items()}
    return rules|trained_models.manifests(lab)


def input_records(model_id,transactions):
    from prevention import features
    records=[]
    for tx in transactions:
        meta=tx['metadata'];context=meta.get('payment_context',{})
        saved=meta.get('prevention_features') if meta.get('prevention_schema_version')==FEATURE_VERSION else None
        values=saved or features(tx['to_account'],tx['amount_minor'],meta,tx['occurred_at'],[])
        if model_id=='device_integrity_v1':missing=[k for k in ('device_known','authorization_verified') if type(meta.get(k)) is not bool]
        elif model_id=='payment_velocity_v1':missing=[] if saved else ['versioned_gateway_history']
        else:missing=[] if isinstance(context,dict) and context.get('before_payment') is True and context.get('kind')=='payment_request' and isinstance(context.get('message'),str) and context['message'] else ['recorded_prepayment_message']
        missing += ['feature:'+name for name in REGISTRY[model_id]['features'] if type(values.get(name)) is not bool]
        # All other metadata, demographics and simulation truth remain outside the adapter.
        records.append({'event_id':tx['id'],'occurred_at':tx['occurred_at'],
            'features':{k:values.get(k) if not missing else None for k in REGISTRY[model_id]['features']},'missing_inputs':missing})
    return records


def predict(model_ids,event_ids,snapshot,pinned,customer_id,lab=None):
    current=manifests(lab);tx=snapshot['data']['transactions'];allowed={t['id'] for t in tx}
    if not isinstance(model_ids,list) or not 1<=len(model_ids)<=3 or any(not isinstance(m,str) or m not in current for m in model_ids) or len(set(model_ids))!=len(model_ids):
        raise LabError('Choose one to three registered local predictors.',422)
    if not isinstance(event_ids,list) or len(event_ids)>10 or any(not isinstance(e,str) or e not in allowed for e in event_ids):
        raise LabError('Model event IDs must belong to this frozen case.',403)
    ids=event_ids or sorted(allowed);selected=[t for t in tx if t['id'] in ids]
    if any(t['customer_id']!=customer_id for t in selected):raise LabError('Predictor customer scope differs.',403)
    if any(t['occurred_at'][:10]>snapshot['as_of'] for t in selected):raise LabError('Prediction evidence is beyond the pinned cutoff.',422)
    results=[]
    for model_id in model_ids:
        card=current[model_id]
        stale=pinned.get(model_id)!=card
        learned=model_id not in REGISTRY
        if learned and not stale and card.get('available'):
            result,inputs=trained_models.predict(model_id,selected,lab)
        else:
            inputs=input_records(model_id,selected) if not learned else []
            result=predict_case([model_id],selected)['detectors'][0] if not learned and not stale else None
        missing=[{'event_id':r['event_id'],'fields':r['missing_inputs']} for r in inputs if r['missing_inputs']]
        if result and not learned:
            missing_ids={r['event_id'] for r in missing}
            for row in result['predictions']:
                if row['event_id'] in missing_ids:row.update(available=False,signal_score=None,matched_features=[])
            valid=[row for row in result['predictions'] if row['available']]
            result.update(available=bool(valid),signal_score=max((row['signal_score'] for row in valid),default=None),
                result='verification signal' if any(row['signal_score']==1 for row in valid) else 'no combined signal' if valid else 'insufficient evidence')
        results.append({'model_id':model_id,'model_version':card['version'],'feature_version':card['feature_version'],
            'manifest':card,'manifest_hash':hashlib.sha256(encoded(card).encode()).hexdigest(),
            'input_hash':hashlib.sha256(encoded(inputs).encode()).hexdigest(),'event_ids':[t['id'] for t in selected],
            'snapshot_id':snapshot['id'],'snapshot_hash':snapshot['evidence_hash'],'as_of':snapshot['as_of'],
            'score_kind':card['score_kind'],'target':card['task'],'calibrated':False,'missing_inputs':missing,
            'status':'not_available' if stale or not result or not result['available'] else 'partial' if missing else 'scored',
            'reason':'Pinned model or feature implementation changed.' if stale else card.get('unavailable_reason','Registered artifact is unavailable.') if learned and not card.get('available') else 'Required evidence is missing.' if missing else None,
            'prediction':result,'input_fields':list(card['required_inputs']),
            'input_source':'Versioned prepayment feature snapshot' if learned else 'Frozen payment observations',
            'case_feature_source':snapshot['data'].get('customer_features',{}).get('source')})
    return results
