"""Versioned, scoped prediction tools. Rule scores are not fraud probabilities."""
from lab import LabError

REGISTRY={
 'device_integrity_v1':{'name':'Device integrity','version':'1.0','kind':'rule detector','features':['unknown_device','unverified_authorization']},
 'payment_velocity_v1':{'name':'Payment velocity','version':'1.0','kind':'rule detector','features':['rapid_payments','new_recipient']},
 'message_intent_v1':{'name':'Payment request intent','version':'1.0','kind':'rule detector','features':['safe_account_request','secrecy_request','callback_discouraged','beneficiary_change','unlock_earnings','urgent_request','guaranteed_returns','withdrawal_fee']},
}


def score(detector_id,values,available=True):
    if detector_id not in REGISTRY:raise LabError('This detector is not in the approved registry.',422)
    card=REGISTRY[detector_id];hit=[]
    if available:
        hit=[name for name in card['features'] if values.get(name) is True]
        if detector_id=='message_intent_v1':
            pairs=[('safe_account_request','secrecy_request'),('beneficiary_change','callback_discouraged'),('unlock_earnings','urgent_request'),('guaranteed_returns','withdrawal_fee')]
            alert=any(all(values.get(k) is True for k in pair) for pair in pairs)
        else:alert=len(hit)==2
        value=1.0 if alert else .5 if hit else 0.0
    else:alert=None;value=None
    return {'detector_id':detector_id,**card,'available':available,'signal_score':value,
            'result':'insufficient evidence' if not available else 'verification signal' if alert else 'no combined signal',
            'matched_features':hit,'calibrated_fraud_probability':None,
            'limitation':'A predefined rule signal, not a trained or calibrated fraud probability. A low score does not establish customer intent.'}


def predict_case(detector_ids,transactions):
    from prevention import features, FEATURE_SCHEMA_VERSION
    if not isinstance(detector_ids,list) or not 1<=len(detector_ids)<=3 or any(not isinstance(k,str) for k in detector_ids) or len(set(detector_ids))!=len(detector_ids):
        raise LabError('Select one to three distinct approved detectors.',422)
    if any(k not in REGISTRY for k in detector_ids):raise LabError('Unknown detector; no prediction was made.',422)
    outputs=[]
    for detector in detector_ids:
        predictions=[]
        for tx in transactions:
            meta=tx['metadata'];context=meta.get('payment_context',{})
            saved=meta.get('prevention_features') if meta.get('prevention_schema_version')==FEATURE_SCHEMA_VERSION else None
            values=saved or features(tx['to_account'],tx['amount_minor'],meta,tx['occurred_at'],[])
            available=(all(type(meta.get(k)) is bool for k in ('device_known','authorization_verified')) if detector=='device_integrity_v1'
                else bool(saved) if detector=='payment_velocity_v1'
                else isinstance(context,dict) and context.get('before_payment') is True and context.get('kind')=='payment_request' and isinstance(context.get('message'),str) and bool(context.get('message')))
            result=score(detector,values,available)
            predictions.append({'event_id':tx['id'],**{k:result[k] for k in ('available','signal_score','matched_features')}})
        valid=[p for p in predictions if p['available']]
        outputs.append({'detector_id':detector,**REGISTRY[detector],'available':bool(valid),
            'signal_score':max((p['signal_score'] for p in valid),default=None),
            'result':'verification signal' if any(p['signal_score']==1 for p in valid) else 'no combined signal' if valid else 'insufficient evidence',
            'calibrated_fraud_probability':None,'predictions':predictions})
    return {'detectors':outputs,'scope':'Only the frozen disputed transactions. No scenario labels, demographics or future complaint text are model features.',
            'note':'These versioned detectors can be replaced with validated enterprise model endpoints under the same scoped contract.'}
