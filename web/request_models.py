"""Fixed, data-only CPU recipes for the bounded MLE search and refinement loop."""
import json,math,re,unicodedata
from risk_models import metrics

VERSION='request-risk-v1'
NUMERIC=['unknown_device','unverified_authorization','rapid_payments','new_recipient','amount_ratio']
RECIPES={'transaction':'Observed payment behavior only','word':'Word phrases + payment behavior',
    'char':'Character fragments + payment behavior','word_char':'Word phrases + character fragments + payment behavior'}
BLOCKS={'transaction':['transaction'],'word':['word','transaction'],'char':['char','transaction'],'word_char':['word','char','transaction']}


def validate_artifact(model):
    blocks=model.get('blocks',[])
    if model.get('feature_version')!=VERSION or blocks not in BLOCKS.values() or model.get('numeric_features')!=NUMERIC or model.get('hash_dimensions')!=1024:
        raise ValueError('Unsupported request feature contract.')
    size=sum(len(NUMERIC) if b=='transaction' else 1024 for b in blocks)
    if len(model.get('coefficients',[]))!=size or not all(type(v) in (int,float) and math.isfinite(v) for v in model['coefficients']+[model.get('intercept'),model.get('threshold')]):
        raise ValueError('Invalid request predictor dimensions or parameters.')
    if not 0<model['threshold']<1:raise ValueError('Invalid request predictor threshold.')
    return model


def normalized(message):
    return re.sub(r'\d+','#',unicodedata.normalize('NFKC',message).casefold())[:2000]


def matrix(rows,blocks):
    from scipy.sparse import csr_matrix,hstack
    from sklearn.feature_extraction.text import HashingVectorizer
    parts=[];text=[normalized(r.get('request_text','')) for r in rows]
    for block in blocks:
        if block=='transaction':parts.append(csr_matrix([[float(r['features'][k])/(10 if k=='amount_ratio' else 1) for k in NUMERIC] for r in rows]))
        else:parts.append(HashingVectorizer(n_features=1024,analyzer='char' if block=='char' else 'word',
            ngram_range=(3,5) if block=='char' else (1,2),alternate_sign=False,norm='l2').transform(text))
    return hstack(parts,format='csr')


def predict(artifact,rows):
    import numpy as np
    z=matrix(rows,artifact['blocks']).dot(np.array(artifact['coefficients']))+artifact['intercept']
    return (1/(1+np.exp(-np.clip(z,-40,40)))).tolist()


def choose_threshold(labels,scores):
    options=[metrics(labels,scores,t/100) for t in range(10,96,5)]
    eligible=[m for m in options if m['false_positive_rate']<=.05]
    return max(eligible or options,key=lambda m:(m['recall'],-m['false_positive_rate'],m['threshold']))


def fit(rows,recipe,regularization=.6):
    from sklearn.linear_model import LogisticRegression
    from threadpoolctl import threadpool_limits
    if recipe not in RECIPES or regularization not in (.2,.6,2.):raise ValueError('Recipe is not allowlisted.')
    train=[r for r in rows if r['split']=='train'];validation=[r for r in rows if r['split']=='validation'];blocks=BLOCKS[recipe]
    with threadpool_limits(limits=1):
        estimator=LogisticRegression(C=regularization,class_weight='balanced',solver='liblinear',max_iter=150,random_state=891)
        estimator.fit(matrix(train,blocks),[r['label'] for r in train])
        artifact={'kind':'request_logistic','feature_version':VERSION,'blocks':blocks,'coefficients':estimator.coef_[0].tolist(),
            'intercept':float(estimator.intercept_[0]),'regularization':regularization,'numeric_features':NUMERIC,'hash_dimensions':1024}
    predicted=predict(artifact,validation);labels=[r['label'] for r in validation];scores=choose_threshold(labels,predicted)
    artifact['threshold']=scores['threshold']
    ablations=[]
    # Frozen-coefficient ablation: remove one input block and measure the change.
    # It identifies a component worth refining; it does not refit on test data.
    offset=0
    for block in blocks:
        width=len(NUMERIC) if block=='transaction' else 1024;changed={**artifact,'coefficients':artifact['coefficients'].copy()}
        changed['coefficients'][offset:offset+width]=[0]*width;offset+=width
        ablated=metrics(labels,predict(changed,validation),scores['threshold'])
        ablations.append({'component':block,'validation_recall_drop':round(scores['recall']-ablated['recall'],4),
            'validation_false_hold_change':ablated['false_holds']-scores['false_holds']})
    errors=[{'example_id':r['id'],'label':r['label'],'request':r['request_text'][:240],
        'score':round(p,4),'error':'missed_scam' if r['label'] else 'false_hold'} for r,p in zip(validation,predicted) if int(p>=scores['threshold'])!=r['label']][:6]
    return {'recipe':recipe,'name':RECIPES[recipe],'artifact':artifact,'validation':scores,'ablation':ablations,'validation_errors':errors,
        'preselected':False,'features':blocks,'counterexamples':[]}


def nominate(candidates):
    eligible=[c for c in candidates if c['recipe']!='transaction']
    winner=max(eligible,key=lambda c:(c['validation']['false_positive_rate']<=.05,c['validation']['recall'],
        -c['validation']['false_positive_rate'],-len(c['artifact']['blocks'])))
    for c in candidates:c['preselected']=c is winner
    return winner


def finalize(rows,candidates):
    test=[r for r in rows if r['split']=='test'];labels=[r['label'] for r in test]
    nominate(candidates)  # Sealed nomination before any final-test inference.
    for c in candidates:
        scores=predict(c['artifact'],test);c['test']=metrics(labels,scores,c['artifact']['threshold']);reasons=[]
        if c['recipe']=='transaction':reasons.append('Behavior-only reference; cannot establish payment-request deception.')
        if c['test']['recall']<.8:reasons.append('Final-test synthetic recall is below 80%.')
        if c['test']['false_positive_rate']>.05:reasons.append('Final-test legitimate flags exceed 5%.')
        c['gate_passed']=not reasons;c['reasons']=reasons;c['status']='eligible' if not reasons else 'rejected'
        c['counterexamples']=[{'example_id':r['id'],'label':r['label'],'score':round(p,4),'error':'missed_scam' if r['label'] else 'false_hold'} for r,p in zip(test,scores) if int(p>=c['artifact']['threshold'])!=r['label']][:6]
    return candidates


def run(payload):
    rows=payload['rows']
    if not 100<=len(rows)<=1200:raise ValueError('Use a bounded frozen corpus.')
    if payload['mode']=='search':
        recipe=payload['recipe']
        if recipe not in ('word','char'):raise ValueError('Choose word or char for the initial search.')
        return [fit(rows,'transaction'),fit(rows,recipe)]
    if payload['mode']=='refine':
        return fit(rows,payload['recipe'],payload['regularization'])
    if payload['mode']=='finalize':return finalize(rows,payload['candidates'])
    raise ValueError('Unknown fixed recipe operation.')


if __name__=='__main__':
    import sys,signal
    signal.alarm(20)
    body=sys.stdin.read(2500000)
    if len(body)>=2500000:raise ValueError('Oversized fixed-recipe input.')
    print(json.dumps(run(json.loads(body)),allow_nan=False))
