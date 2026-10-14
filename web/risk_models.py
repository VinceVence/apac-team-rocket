"""Allowlisted CPU model recipes. No generated code, network clients or credentials."""
import datetime as dt
import hashlib
import json
import math
import random

from prevention import FEATURES, features as payment_features

VERSION='risk-features-v1'
GROUPS={
    'transaction':['new_recipient','unknown_device','unverified_authorization','rapid_payments','large_amount','amount_ratio'],
    'request':[k for k in FEATURES if k not in ('new_recipient','unknown_device','unverified_authorization','rapid_payments','large_amount')]+['message_available'],
}
ALLOWED=set(sum(GROUPS.values(),[]))
RECIPES={'logistic':'L2 logistic regression', 'boosted_tree':'Gradient boosting · 32 trees · depth 2'}
MAX_ROWS=1200


def vector(metadata,amount,history,payee,at):
    values=payment_features(payee,amount,metadata,at,history)
    amounts=sorted(x['amount_minor'] for x in history if x['amount_minor']>0)
    median=amounts[len(amounts)//2] if amounts else max(1,amount)
    context=metadata.get('payment_context',{})
    return {**{k:float(v) for k,v in values.items()},'amount_ratio':min(10.,amount/max(1,median)),
            'message_available':float(isinstance(context,dict) and context.get('before_payment') is True and context.get('kind')=='payment_request' and bool(context.get('message')))}


def synthetic_examples(customers):
    """Explicit simulator benchmark; labels are generator truth, not human case reviews.

    Disjoint customers, time windows and request templates across the three splits.
    Inputs go through the same prepayment extractor used by the live world.
    """
    starts={'train':'2026-07-01','validation':'2026-08-01','test':'2026-09-01'}
    messages={
      'train':['Move funds to a safe account immediately. Keep it secret.','Our account has changed. Do not call the office.','Recharge today to unlock earnings.','Guaranteed returns. Pay a withdrawal tax today.'],
      'validation':['Transfer to a secure account right now. Hide the reason.','Use the new beneficiary; the finance team is unavailable.','Make a payment to unlock your earnings immediately.','Guaranteed profit. A withdrawal fee is due.'],
      'test':['A safe account will protect your money. Keep this secret.','Pay the replacement beneficiary. Don\'t call to confirm.','Deposit to unlock commissions right now.','Guaranteed returns. Pay to release your investment profits.'],
    }
    controls=['Your ordinary purchase was received.','I am moving money to my own safe account today.',
      'Our account has changed; I independently verified the supplier by phone.',
      'Never transfer to a safe account. Keep your credentials secret.',
      'I recognize these purchases made on my new device.',
      'A disclosed withdrawal fee was deducted, without guaranteed returns.']
    rows=[]
    for i,cid in enumerate(customers[:100]):
        split='train' if i<60 else 'validation' if i<80 else 'test'
        rng=random.Random(4017+i);start=dt.datetime.fromisoformat(starts[split]).replace(tzinfo=dt.timezone.utc)
        for j in range(10):
            at=start+dt.timedelta(days=j,hours=i%20);stamp=at.isoformat();label=int(j in (0,3,6))
            kind=(i+j)%5;known=not(label and kind==4);authorized=known
            message=messages[split][kind] if label and kind<4 else 'A new device signed in.' if label else controls[(i+j)%len(controls)]
            if not label and j==7:known=False  # Legitimate new-device control.
            if not label and j==8:authorized=False  # A single weak signal is not proof.
            amount=rng.randint(3000,220000)  # Fraud and legitimate amounts deliberately overlap.
            meta={'device_known':known,'authorization_verified':authorized,
                  'payment_context':{'before_payment':True,'kind':'payment_request','message':message}}
            if j==6 and i%5==0:meta.pop('payment_context')  # Missing information is observable.
            history=[{'occurred_at':(at-dt.timedelta(days=d+1)).isoformat(),'amount_minor':rng.randint(5000,60000),'to_account':'merchant:known'} for d in range(12)]
            payee='counterparty:'+hashlib.sha256((cid+str(j)).encode()).hexdigest()[:8]
            row={'id':'BENCH-'+cid+'-'+str(j),'customer_id':cid,'scene_id':'benchmark-v1',
                 'event_id':'request-'+cid+'-'+str(j),'event_time':stamp,'available_at':stamp,
                 'label_available_at':(at+dt.timedelta(hours=24)).isoformat(),'label':label,
                 'origin':'synthetic_benchmark','split':split,'template_group':split+'-'+str(kind),
                 'features':vector(meta,amount,history,payee,stamp),'feature_version':VERSION,
                 'source_report_id':None,'review_id':None,'evidence_hash':hashlib.sha256(json.dumps(meta,sort_keys=True).encode()).hexdigest(),
                 'quality_note':'Generator-labelled payment requests; not actual analyst-reviewed customers.'}
            rows.append(row)
    return rows


def metrics(labels,scores,threshold):
    from sklearn.metrics import average_precision_score,brier_score_loss
    tp=sum(y==1 and p>=threshold for y,p in zip(labels,scores));fp=sum(y==0 and p>=threshold for y,p in zip(labels,scores))
    positives=sum(labels);negatives=len(labels)-positives
    return {'rows':len(labels),'positives':positives,'negatives':negatives,'caught':tp,'false_holds':fp,
            'recall':round(tp/max(1,positives),4),'false_positive_rate':round(fp/max(1,negatives),4),
            'precision':round(tp/max(1,tp+fp),4),'average_precision':round(float(average_precision_score(labels,scores)),4),
            'brier':round(float(brier_score_loss(labels,scores)),4),'threshold':float(threshold)}


def validation_reasons(result,reference):
    reasons=[]
    if result['positives']<10 or result['negatives']<20:reasons.append('Too few independent held-out outcomes to apply the demo gate.')
    if result['false_positive_rate']>.05:reasons.append('More than 5% of held-out legitimate requests would be held.')
    if result['recall']<.8:reasons.append('Fewer than 80% of held-out synthetic scams were detected.')
    if result['recall']<=reference['recall']:reasons.append('No recall improvement over the narrow reference rule.')
    return reasons


def train(payload):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from threadpoolctl import threadpool_limits
    rows=payload['rows'];plan=payload['plan']
    if not 1<=len(rows)<=MAX_ROWS:raise ValueError('Dataset exceeds recipe row limit.')
    if not set(plan['feature_groups'])<=set(GROUPS) or not plan['feature_groups']:raise ValueError('Unknown feature group.')
    if not 1<=len(plan['recipes'])<=2 or not set(plan['recipes'])<=set(RECIPES):raise ValueError('Unknown recipe.')
    names=list(dict.fromkeys(k for g in plan['feature_groups'] for k in GROUPS[g]))
    sets={split:[r for r in rows if r['split']==split] for split in ('train','validation','test')}
    if any(len(v)<20 or len({r['label'] for r in v})<2 for v in sets.values()):raise ValueError('Insufficient split support.')
    y={k:[r['label'] for r in v] for k,v in sets.items()}
    rule_scores={k:[float(r['features']['safe_account_request'] and r['features']['secrecy_request']) for r in v] for k,v in sets.items()}
    reference=metrics(y['test'],rule_scores['test'],.5)
    results=[{'recipe':'rule_reference','name':'Narrow safe-account rule','features':['safe_account_request','secrecy_request'],
              'validation':metrics(y['validation'],rule_scores['validation'],.5),'test':reference,'gate_passed':False,
              'reasons':['Comparison only; not a newly trained candidate.'],'artifact':{'kind':'and_rule'},'status':'reference'}]
    with threadpool_limits(limits=1):
        for recipe in ['amount_baseline']+plan['recipes']:
            selected=['amount_ratio'] if recipe=='amount_baseline' else names
            x={k:[[float(r['features'][f]) for f in selected] for r in v] for k,v in sets.items()}
            model=(GradientBoostingClassifier(n_estimators=32,max_depth=2,learning_rate=.12,random_state=71)
                   if recipe=='boosted_tree' else make_pipeline(StandardScaler(),LogisticRegression(C=.6,max_iter=150,random_state=71)))
            model.fit(x['train'],y['train'])
            val=model.predict_proba(x['validation'])[:,1].tolist()
            # Selection uses validation only. Test results never tune a threshold or recipe.
            choices=[metrics(y['validation'],val,t/100) for t in range(10,96,5)]
            eligible=[m for m in choices if m['false_positive_rate']<=.05]
            selected_metric=max(eligible or choices,key=lambda m:(m['recall'],-m['false_positive_rate'],m['threshold']))
            predictions=model.predict_proba(x['test'])[:,1].tolist();test=metrics(y['test'],predictions,selected_metric['threshold'])
            reasons=validation_reasons(test,reference)
            if recipe=='amount_baseline':reasons.append('Amount-only baseline is ineligible for release; it ignores request and authorization evidence.')
            if recipe=='boosted_tree':
                artifact={'kind':recipe,'feature_importances':dict(zip(selected,model.feature_importances_.tolist())),
                          'parameters':{'trees':32,'max_depth':2,'learning_rate':.12},
                          'trees':[{'children_left':e[0].tree_.children_left.tolist(),'children_right':e[0].tree_.children_right.tolist(),
                                    'feature':e[0].tree_.feature.tolist(),'threshold':e[0].tree_.threshold.tolist(),'value':e[0].tree_.value.tolist()} for e in model.estimators_]}
            else:
                scaler,linear=model.steps[0][1],model.steps[1][1]
                artifact={'kind':'logistic','coefficients':linear.coef_[0].tolist(),'intercept':float(linear.intercept_[0]),
                          'means':scaler.mean_.tolist(),'scales':scaler.scale_.tolist()}
            examples=[{'example_id':r['id'],'label':r['label'],'score':round(p,4),'error':'false_hold' if not r['label'] else 'missed_scam'}
                      for r,p in zip(sets['test'],predictions) if int(p>=selected_metric['threshold'])!=r['label']][:6]
            results.append({'recipe':recipe,'name':'Amount-only logistic baseline' if recipe=='amount_baseline' else RECIPES[recipe],
                'features':selected,'validation':selected_metric,'test':test,'gate_passed':not reasons,'reasons':reasons,
                'artifact':{**artifact,'feature_version':VERSION,'features':selected,'threshold':selected_metric['threshold']},
                'counterexamples':examples,'status':'eligible' if not reasons else 'rejected'})
    # Choose by validation results alone. Final-test results can veto this choice,
    # never promote a different candidate or tune the next experiment.
    selected=max((c for c in results if c['recipe'] in RECIPES),key=lambda c:(
        c['validation']['false_positive_rate']<=.05,c['validation']['recall'],
        -c['validation']['false_positive_rate'],c['recipe']=='logistic'))
    for candidate in results:candidate['preselected']=candidate is selected
    return results


if __name__=='__main__':
    import signal,sys,faulthandler,time,resource
    # Bound this recipe's CPU interval, including library imports. The parent
    # separately enforces the 25-second wall timeout.
    started=time.monotonic()
    def limit_hit(*_):
        u=resource.getrusage(resource.RUSAGE_SELF)
        print('Recipe CPU timer: wall='+str(time.monotonic()-started)+' cpu='+str(u.ru_utime+u.ru_stime),file=sys.stderr,flush=True)
        raise SystemExit(124)
    signal.signal(signal.SIGPROF,limit_hit)
    signal.setitimer(signal.ITIMER_PROF,20)
    faulthandler.dump_traceback_later(10)
    data=sys.stdin.read(2000000)
    if len(data)>=2000000:raise ValueError('Oversized training input.')
    result=train(json.loads(data))
    faulthandler.cancel_dump_traceback_later()
    print(json.dumps(result,allow_nan=False))
