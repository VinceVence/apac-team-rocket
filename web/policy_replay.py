"""Paired before/after policy checks on the same requests; zero model calls."""
import hashlib
from copy import deepcopy

from lab import encoded


def compare(signals,source):
    from prevention import features,matches
    if not source.get('requests'):return {'available':False,'reason':'Legacy source has no replayable prepayment requests.'}
    cases=[]
    for i,request in enumerate(source['requests']):
        for variant in ('new_recipient','lower_amount','alternate_wording','missing_context'):
            r=deepcopy(request);r['payee']='external:paired-unseen-'+str(i)
            if variant=='lower_amount':r['amount_minor']=min(r['amount_minor'],20000)
            if variant=='alternate_wording':
                message=r['metadata'].get('payment_context',{}).get('message','')
                for old,new in (('safe account','secure account'),('keep it secret','hide the reason'),('account has changed','replacement beneficiary'),('unlock earnings','unlock commissions'),('guaranteed returns','guaranteed profit'),('withdrawal tax','withdrawal fee')):message=message.replace(old,new)
                if 'payment_context' in r['metadata']:r['metadata']['payment_context']['message']=message
            if variant=='missing_context':r['metadata'].pop('payment_context',None)
            cases.append((variant+'-'+str(i),'unknown' if variant=='missing_context' else 'reviewed_scam',r))
    first=source['requests'][0]
    controls=[('Ordinary purchase','I am paying for groceries I ordered.',True,True),
        ('Own savings','I am moving money to my own safe account today.',True,True),
        ('Verified supplier','Our account has changed; I independently verified the supplier by phone.',True,True),
        ('Security warning','Never transfer to a safe account. Keep your credentials secret.',True,True),
        ('Disclosed fee','A disclosed withdrawal fee was deducted, without guaranteed returns.',True,True),
        ('Recognized new device','I recognize my purchase on this new device.',False,True)]
    for name,message,known,authorized in controls:
        cases.append((name,'legitimate_control',{'payee':'merchant:paired-control','amount_minor':first['amount_minor'],
            'occurred_at':first['occurred_at'],'history':first['history'],
            'metadata':{'device_known':known,'authorization_verified':authorized,'payment_context':{'before_payment':True,'kind':'payment_request','message':message}}}))
    rows=[];baseline=source.get('baseline_rules',[]);watched=set(source.get('baseline_recipients',[]))
    for name,expected,r in cases:
        values=features(r['payee'],r['amount_minor'],r['metadata'],r['occurred_at'],r['history'])
        before=r['payee'] in watched or any(matches(rule['signals'],values) for rule in baseline)
        after=before or matches(signals,values)
        rows.append({'name':name,'expected':expected,'recipient_changed':r['payee'] not in watched,
            'before':'verify' if before else 'allow','after':'verify' if after else 'allow',
            'amount_php':r['amount_minor']/100,'message_available':'payment_context' in r['metadata'],
            'matched_signals':[s for s in signals if values.get(s) is True],
            'overbroad_baseline_holds':values['new_recipient']})
    scams=[r for r in rows if r['expected']=='reviewed_scam'];legit=[r for r in rows if r['expected']=='legitimate_control']
    count=lambda subset,phase:sum(r[phase]=='verify' for r in subset)
    before_hits=count(scams,'before');after_hits=count(scams,'after');false_before=count(legit,'before');false_after=count(legit,'after')
    reasons=[]
    if after_hits<len(scams):reasons.append('The candidate misses a reviewed-pattern variant, including the lower-amount check.')
    if false_after>false_before:reasons.append('The candidate adds holds on legitimate payment requests.')
    return {'available':True,'passed':not reasons,'reasons':reasons,'cases':rows,
        'scam_variants':len(scams),'before_stopped':before_hits,'after_stopped':after_hits,'newly_stopped':after_hits-before_hits,
        'legitimate_controls':len(legit),'before_false_holds':false_before,'after_false_holds':false_after,'new_false_holds':false_after-false_before,
        'baseline_policy_hash':hashlib.sha256(encoded([baseline,sorted(watched)]).encode()).hexdigest(),
        'candidate_policy_hash':hashlib.sha256(encoded(sorted(signals)).encode()).hexdigest(),
        'rejected_baseline':{'name':'Hold every new recipient','false_holds':sum(r['overbroad_baseline_holds'] for r in legit),
            'controls':len(legit),'status':'ineligible','reason':'Recipient novelty alone fails the signal contract and holds legitimate controls.'},
        'scope':'Paired policy simulation on identical recorded/context-control inputs. No payments or model calls executed; not production accuracy.'}
