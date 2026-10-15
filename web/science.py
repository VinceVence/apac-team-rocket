"""Local analytics jobs and small logistic models; no model API or GPU usage."""
import datetime as dt
import json
import hashlib
import math
import random
import time
from collections import defaultdict
from lab import AS_OF, encoded, now, resident_name
from settings import MAX_CUSTOMERS

FEATURES=['purchases_14d','spend_14d','activity_change','days_since_purchase','deposits_14d','payroll_14d']


def sigmoid(value):
    return 1/(1+math.exp(-max(-35,min(35,value))))


def fit(rows,feature_names=None):
    feature_names=feature_names or FEATURES
    xs=[r[0] for r in rows];ys=[r[1] for r in rows];n=len(rows);width=len(feature_names)
    means=[sum(x[j] for x in xs)/n for j in range(width)]
    scales=[max(.01,math.sqrt(sum((x[j]-means[j])**2 for x in xs)/n)) for j in range(width)]
    xs=[[1]+[(x[j]-means[j])/scales[j] for j in range(width)] for x in xs]
    weights=[0.]*(width+1)
    for _ in range(180):
        gradients=[0.]*(width+1)
        for x,y in zip(xs,ys):
            error=sigmoid(sum(w*v for w,v in zip(weights,x)))-y
            for j,v in enumerate(x):gradients[j]+=error*v
        for j in range(width+1):weights[j]-=.16*(gradients[j]/n+(.025*weights[j] if j else 0))
    return {'weights':weights,'means':means,'scales':scales,'features':feature_names}


def predict(artifact,features):
    values=[1]+[(v-m)/s for v,m,s in zip(features,artifact['means'],artifact['scales'])]
    return sigmoid(sum(w*v for w,v in zip(artifact['weights'],values)))


def evaluate(model,rows,prior):
    predictions=[predict(model,r[0]) for r in rows];labels=[r[1] for r in rows];n=len(rows)
    brier=sum((p-y)**2 for p,y in zip(predictions,labels))/n
    baseline=sum((prior-y)**2 for y in labels)/n
    positives=[p for p,y in zip(predictions,labels) if y];negatives=[p for p,y in zip(predictions,labels) if not y]
    auc=sum(1 if p>q else .5 if p==q else 0 for p in positives for q in negatives)/(len(positives)*len(negatives)) if positives and negatives else None
    return {'brier':round(brier,4),'baseline_brier':round(baseline,4),'auc':round(auc,3) if auc is not None else None,
            'holdout_rows':n,'holdout_positives':sum(labels),'better_than_baseline':brier<baseline}


class Science:
    def __init__(self,lab):
        self.lab=lab
        lab.db.executescript('''CREATE TABLE IF NOT EXISTS model_runs(
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, cutoff TEXT NOT NULL, status TEXT NOT NULL,
          report TEXT NOT NULL, artifact TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(kind,cutoff));''')
        self.seed_cohort()

    def seed_cohort(self):
        if self.lab.db.execute("SELECT 1 FROM customers WHERE id='C025'").fetchone():return
        # Additional customers supply a varied historical cohort; only 24 are rendered in the town.
        with self.lab.lock,self.lab.db:
            self.lab.db.execute('INSERT INTO accounts(id,label,kind,opening_minor,balance_minor) VALUES(?,?,?,?,?)',
                                ('cohort-treasury','Historical cohort treasury','treasury',5000000000,5000000000))
            for i in range(25,MAX_CUSTOMERS+1):
                cid='C%03d'%i;income=280000+(i%11)*16000;rng=random.Random(700+i)
                self.lab.db.execute('INSERT INTO customers VALUES(?,?,?)',(cid,resident_name(i),income))
                for kind,amount in [('wallet',1000000),('savings',100000)]:
                    self.lab.db.execute('INSERT INTO accounts(id,customer_id,label,kind,opening_minor,balance_minor) VALUES(?,?,?,?,?,?)',
                                        (cid+':'+kind,cid,cid+' · '+kind,kind,amount,amount))
                rate=.25+(i%7)*.10;save_rate=.10+(i%5)*.16
                for offset in range(84):
                    day=(dt.date.fromisoformat(AS_OF)-dt.timedelta(days=84-offset)).isoformat();week=offset//7
                    inactive=(week+i*2)%9 in (0,1);slowing=(week+1+i*2)%9==0
                    if offset%7==0:self.lab.post('hist-wage-%s-%d'%(cid,offset),cid,'payroll',income,day,'cohort-treasury',cid+':wallet')
                    if not inactive and rng.random()<rate*(.35 if slowing else 1):
                        self.lab.post('hist-buy-%s-%d'%(cid,offset),cid,'payment',rng.randint(45,250)*100,day,cid+':wallet','m%d'%rng.randint(1,3),{'category':'discretionary','device_id':'device-'+cid})
                    if offset%7==5 and rng.random()<save_rate:
                        self.lab.post('hist-save-%s-%d'%(cid,offset),cid,'savings_deposit',30000,day,cid+':wallet',cid+':savings')

    def histories(self):
        histories=defaultdict(list)
        for row in self.lab.rows("SELECT customer_id,kind,amount_minor,occurred_at FROM financial_events WHERE customer_id IS NOT NULL AND status='settled' AND kind IN ('payment','payroll','savings_deposit')"):
            histories[row['customer_id']].append((dt.date.fromisoformat(row['occurred_at'][:10]).toordinal(),row['kind'],row['amount_minor']))
        return histories

    @staticmethod
    def features(history,cutoff):
        recent=[e for e in history if cutoff-14<=e[0]<cutoff]
        purchases=[e for e in recent if e[1]=='payment'];last=[e for e in purchases if e[0]>=cutoff-7]
        return [len(purchases),sum(e[2] for e in purchases)/10000,
                len(last)/(len(purchases)-len(last)+1),min(15,cutoff-max((e[0] for e in purchases),default=cutoff-15)),
                sum(e[1]=='savings_deposit' for e in recent),sum(e[2] for e in recent if e[1]=='payroll')/10000]

    @staticmethod
    def label(history,cutoff,kind):
        future=[e for e in history if cutoff<=e[0]<cutoff+7]
        return int(not any(e[1]=='payment' for e in future)) if kind=='churn' else int(any(e[1]=='savings_deposit' for e in future))

    def train(self,kinds=('churn','propensity')):
        if any(kind not in ('churn','propensity') for kind in kinds):raise ValueError('Unknown training recipe')
        started=time.monotonic();cutoff=self.lab.clock_day;end=dt.date.fromisoformat(cutoff).toordinal()
        created=0;trained=0
        with self.lab.lock:
            histories=self.histories()
            for kind in kinds:
                if self.lab.db.execute('SELECT 1 FROM model_runs WHERE kind=? AND cutoff=?',(kind,cutoff)).fetchone():continue
                training=[];testing=[];train_ids=set();test_ids=set()
                for cid,h in histories.items():
                    holdout=int(hashlib.sha256(cid.encode()).hexdigest()[:8],16)%5==0
                    for day in ([end-7] if holdout else [end-42,end-28,end-14]):
                        features=self.features(h,day)
                        if features[0]<1:continue  # Churn is defined only for recently active customers.
                        (testing if holdout else training).append((features,self.label(h,day,kind)))
                        (test_ids if holdout else train_ids).add(cid)
                report={'train_rows':len(training),'train_customers':len(train_ids),'holdout_customers':len(test_ids),
                        'training_label_end':dt.date.fromordinal(end-7).isoformat(),'holdout_label_start':dt.date.fromordinal(end-7).isoformat(),
                        'train_customer_ids':sorted(train_ids),'holdout_customer_ids':sorted(test_ids),
                        'definition':'No settled purchase in the following 7 days.' if kind=='churn' else 'At least one savings deposit in the following 7 days.',
                        'algorithm':'L2 logistic regression · local CPU','split':'Hashed customer IDs, with later label windows held out',
                        'pipeline_version':'lr-2','data':'Synthetic history; demo evaluation only.'}
                enough=len(training)>=60 and len(testing)>=15 and min(sum(y for _,y in training),sum(1-y for _,y in training))>=10
                artifact={};status='needs_data'
                if enough:
                    artifact=fit(training);prior=sum(y for _,y in training)/len(training);report.update(evaluate(artifact,testing,prior));status='candidate'
                    if min(report['holdout_positives'],report['holdout_rows']-report['holdout_positives'])<5:report['note']='Few examples of one outcome in the holdout. Treat these metrics as exploratory.'
                else:report['note']='Waiting for sufficient labeled history and both training classes.'
                report['training_ms']=round((time.monotonic()-started)*1000)
                with self.lab.db:self.lab.db.execute('INSERT INTO model_runs VALUES(?,?,?,?,?,?,?)',
                                                    (kind+'-'+cutoff,kind,cutoff,status,encoded(report),encoded(artifact),now()))
                created+=1
                trained+=bool(artifact)
        result=self.dashboard();result['created_models']=created;result['trained_models']=trained
        return result

    def due(self):
        last=self.lab.db.execute('SELECT max(cutoff) FROM model_runs').fetchone()[0]
        return not last or (dt.date.fromisoformat(self.lab.clock_day)-dt.date.fromisoformat(last)).days>=7

    def dashboard(self):
        with self.lab.lock:
            end=dt.date.fromisoformat(self.lab.clock_day);start=(end-dt.timedelta(days=13)).isoformat()
            flows=self.lab.rows("SELECT substr(occurred_at,1,10) day,kind,sum(amount_minor) amount,count(*) events FROM financial_events WHERE occurred_at>=? AND occurred_at<? AND status='settled' AND kind IN ('payment','payroll','savings_deposit','bill_payment') GROUP BY day,kind ORDER BY day",(start,(end+dt.timedelta(days=1)).isoformat()))
            models=[];histories=None
            for kind in ('churn','propensity'):
                row=self.lab.db.execute('SELECT * FROM model_runs WHERE kind=? ORDER BY cutoff DESC LIMIT 1',(kind,)).fetchone()
                if not row:continue
                model=dict(row);model['report']=json.loads(model['report']);artifact=json.loads(model.pop('artifact'))
                if artifact:
                    if histories is None:histories=self.histories()
                    model['scores']=[{'customer_id':cid,'probability':round(predict(artifact,self.features(histories[cid],end.toordinal())),3)} for cid in sorted(histories)[:24]]
                    model['scores'].sort(key=lambda r:r['probability'],reverse=True)
                else:model['scores']=[]
                models.append(model)
            return {'as_of':self.lab.clock_day,'flows':flows,'models':models,
                    'jobs':[{'agent':'Cash-flow analyst','task':'Refresh income, spend and savings dashboard','status':'ready'},
                            {'agent':'Model builder','task':'Train churn and savings propensity from labeled history','status':'ready' if models else 'waiting'},
                            {'agent':'Model evaluator','task':'Check later windows and held-out customers','status':'demo candidates'}],
                    'model_api_calls':0}
