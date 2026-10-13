"""Marketing interaction lakehouse, eight CPU models, Customer DNA and pilots.

All identities, interactions and outcomes are synthetic. Age/region/occupation
are descriptive profile fields, excluded from model inputs and campaign targeting.
"""
import datetime as dt
import hashlib
import json
import math
import random
import uuid
from collections import Counter, defaultdict

from lab import AS_OF, LabError, encoded, now
from science import fit, predict, evaluate
from settings import MAX_CUSTOMERS

TABLES = ('customer_profiles', 'bronze_interactions', 'silver_interactions', 'gold_customer_features',
          'customer_dna_models', 'gold_customer_dna', 'marketing_campaigns', 'campaign_assignments', 'customer_pipeline_runs')
KINDS = ('app_open', 'product_view', 'campaign_impression', 'campaign_click', 'product_activated', 'purchase', 'income', 'savings')
PRODUCTS = ('savings', 'budgeting', 'qr', 'rewards')
FEATURES = ['sessions_14d', 'active_days_14d', 'activity_change', 'days_since_active', 'purchases_14d',
            'spend_14d', 'average_purchase', 'spend_change', 'impressions_14d', 'click_rate',
            'savings_interest', 'budgeting_interest', 'qr_interest', 'rewards_interest', 'income_14d', 'savings_14d',
            'goal_savings', 'goal_budgeting', 'goal_qr', 'goal_rewards', 'prefers_in_app']
MODEL_SPECS = {
    'churn': {'column': 'churn_score', 'title': 'Digital disengagement', 'horizon': 14, 'definition': 'No app or marketing engagement in the next 14 days.'},
    'response': {'column': 'response_score', 'title': 'Campaign engagement', 'horizon': 7, 'definition': 'At least one campaign click in the next 7 days; observational propensity, not uplift.'},
    'savings': {'column': 'savings_score', 'title': 'Savings affinity', 'horizon': 7, 'definition': 'Engagement with savings content or a savings event in the next 7 days.'},
    'budgeting': {'column': 'budgeting_score', 'title': 'Budgeting affinity', 'horizon': 7, 'definition': 'Engagement with budgeting content in the next 7 days.'},
    'qr': {'column': 'qr_score', 'title': 'QR feature affinity', 'horizon': 7, 'definition': 'Engagement with QR content in the next 7 days; not first-ever adoption.'},
    'rewards': {'column': 'rewards_score', 'title': 'Rewards affinity', 'horizon': 7, 'definition': 'Engagement with rewards content in the next 7 days.'},
    'repeat_spend': {'column': 'repeat_spend_score', 'title': 'Repeat spending', 'horizon': 7, 'definition': 'At least three recorded purchases in the next 7 days.'},
    'capacity': {'column': 'capacity_band', 'title': 'Spending-capacity proxy', 'horizon': 14, 'definition': 'Low/middle/high next-14-day recorded spending, using training-only cut points. Not wealth or verified income.'},
}


def digest(value): return hashlib.sha256(encoded(value).encode()).hexdigest()
def ordinal(day): return dt.date.fromisoformat(day[:10]).toordinal()
def iso(day): return dt.date.fromordinal(day).isoformat()
def seeded(*parts): return random.Random(int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()[:16], 16))


class CustomerData:
    def __init__(self, lab):
        self.lab = lab
        lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS customer_profiles(customer_id TEXT PRIMARY KEY REFERENCES customers(id), profile TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS bronze_interactions(customer_id TEXT NOT NULL,event_key TEXT NOT NULL,event_date TEXT NOT NULL,
          payload TEXT NOT NULL,payload_hash TEXT NOT NULL,ingested_at TEXT NOT NULL,PRIMARY KEY(customer_id,event_key));
        CREATE INDEX IF NOT EXISTS bronze_customer_date ON bronze_interactions(customer_id,event_date);
        CREATE TABLE IF NOT EXISTS silver_interactions(customer_id TEXT NOT NULL REFERENCES customers(id),event_key TEXT NOT NULL,event_date TEXT NOT NULL,
          kind TEXT NOT NULL,value_minor INTEGER NOT NULL,product TEXT,channel TEXT,campaign_id TEXT,source TEXT NOT NULL,available_on TEXT NOT NULL,
          PRIMARY KEY(customer_id,event_key));
        CREATE INDEX IF NOT EXISTS silver_customer_date ON silver_interactions(customer_id,event_date);
        CREATE TABLE IF NOT EXISTS gold_customer_features(customer_id TEXT PRIMARY KEY REFERENCES customers(id),as_of TEXT NOT NULL,
          features TEXT NOT NULL,observed_events INTEGER NOT NULL,source_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS customer_dna_models(id TEXT PRIMARY KEY,target TEXT NOT NULL,as_of TEXT NOT NULL,recipe TEXT NOT NULL,
          source_hash TEXT NOT NULL,artifact TEXT NOT NULL,report TEXT NOT NULL,checksum TEXT NOT NULL,created_at TEXT NOT NULL,
          UNIQUE(target,as_of,recipe,source_hash));
        CREATE TABLE IF NOT EXISTS gold_customer_dna(customer_id TEXT PRIMARY KEY REFERENCES customers(id),as_of TEXT NOT NULL,
          churn_score REAL,response_score REAL,savings_score REAL,budgeting_score REAL,qr_score REAL,rewards_score REAL,repeat_spend_score REAL,
          capacity_band TEXT,capacity_confidence REAL,tags TEXT NOT NULL,model_versions TEXT NOT NULL,source_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_campaigns(id TEXT PRIMARY KEY,operation_id TEXT UNIQUE NOT NULL,started_on TEXT NOT NULL,
          due_on TEXT NOT NULL,status TEXT NOT NULL,config TEXT NOT NULL,report TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS campaign_assignments(campaign_id TEXT NOT NULL REFERENCES marketing_campaigns(id),customer_id TEXT NOT NULL REFERENCES customers(id),
          arm TEXT NOT NULL,product TEXT NOT NULL,message TEXT NOT NULL,snapshot TEXT NOT NULL,outcome INTEGER,observed_on TEXT,
          PRIMARY KEY(campaign_id,customer_id));
        CREATE TABLE IF NOT EXISTS customer_pipeline_runs(id TEXT PRIMARY KEY,as_of TEXT NOT NULL,source_hash TEXT NOT NULL UNIQUE,
          report TEXT NOT NULL,created_at TEXT NOT NULL);
        ''')
        self.seed_profiles()
        self.seed_interactions()

    def profiles(self):
        return {r['customer_id']: json.loads(r['profile']) for r in self.lab.rows('SELECT * FROM customer_profiles ORDER BY customer_id LIMIT ?', (MAX_CUSTOMERS,))}

    def seed_profiles(self):
        with self.lab.db:
            for customer in self.lab.rows('SELECT * FROM customers ORDER BY id LIMIT ?', (MAX_CUSTOMERS,)):
                cid = customer['id']; r = seeded(cid, 'profile-v1')
                profile = {'age_band': r.choice(['18–24', '25–34', '35–44', '45–59', '60+']),
                           'region': r.choice(['Metro Manila', 'Central Luzon', 'Visayas', 'Mindanao']),
                           'occupation': r.choice(['Salaried', 'Self-employed', 'Freelance', 'Retired']),
                           'household_size': r.randint(1, 5), 'goal': r.choice(PRODUCTS),
                           'preferred_channel': r.choice(['in_app', 'email', 'sms']), 'preferred_rail': r.choice(['QR', 'Card', 'Wallet']),
                           'marketing_consent': r.random() > .17, 'activity_rate': round(r.uniform(.3, .9), 3),
                           'typical_spend_minor': r.randint(50, 260) * 100, 'income_volatility': round(r.uniform(.05, .5), 3),
                           'merchant_weights': [r.randint(1, 8) for _ in range(3)], 'origin': 'Synthetic profile; not a real person'}
                self.lab.db.execute('INSERT OR IGNORE INTO customer_profiles VALUES(?,?)', (cid, encoded(profile)))

    def record(self, cid, event_id, event_date, kind, **attributes):
        timestamp = event_date if 'T' in event_date else event_date + 'T12:00:00Z'
        key = timestamp + '#' + event_id
        payload = {'event_id': event_id, 'kind': kind, 'source': 'environment', **attributes}
        fingerprint = digest(payload)
        existing = self.lab.db.execute('SELECT payload_hash FROM bronze_interactions WHERE customer_id=? AND event_key=?', (cid, key)).fetchone()
        if existing:
            if existing[0] != fingerprint: raise LabError('An interaction key already has different content.', 409)
            return False
        self.lab.db.execute('INSERT INTO bronze_interactions VALUES(?,?,?,?,?,?)', (cid, key, timestamp, encoded(payload), fingerprint, now()))
        return True

    def active(self, cid, day):
        # Deterministic absences create real inactive periods rather than forcing daily use.
        index = int(cid[1:]); cycle = (ordinal(day) + index * 7) % 56
        # Half the toy cohort alternates between this app and another wallet over
        # four-week periods. This assumption supplies dormant/reactivated users.
        return not (index % 2 == 0 and cycle < 28)

    def daily_interactions(self, day, origin='environment'):
        for cid, p in self.profiles().items():
            r = seeded(cid, day, 'interactions-v1')
            if not self.active(cid, day) or r.random() > p['activity_rate']: continue
            self.record(cid, 'session-' + cid + '-' + day, day, 'app_open', source=origin, channel='in_app')
            product = p['goal'] if r.random() < .78 else r.choice(PRODUCTS)
            self.record(cid, 'view-' + cid + '-' + day, day, 'product_view', source=origin, product=product, channel='in_app')
            if origin=='synthetic_bootstrap' and p['marketing_consent'] and ordinal(day) % 4 == int(cid[1:]) % 4:
                offer = r.choice(PRODUCTS)
                self.record(cid, 'impression-' + cid + '-' + day, day, 'campaign_impression', source=origin, product=offer, channel='in_app')
                if r.random() < .10 + .55 * (offer == p['goal']) + .1 * (p['preferred_channel'] == 'in_app'):
                    self.record(cid, 'click-' + cid + '-' + day, day, 'campaign_click', source=origin, product=offer, channel='in_app')

    def seed_interactions(self):
        if self.lab.db.execute('SELECT 1 FROM bronze_interactions LIMIT 1').fetchone(): return
        with self.lab.lock, self.lab.db:
            for day in range(ordinal(AS_OF)-84,ordinal(self.lab.clock_day)):
                self.daily_interactions(iso(day), 'synthetic_bootstrap')
            self.ingest_ledger()

    def ingest_ledger(self):
        mapping = {'payment': 'purchase', 'payroll': 'income', 'savings_deposit': 'savings'}
        for event in self.lab.rows("SELECT * FROM financial_events WHERE customer_id IS NOT NULL AND status='settled' AND kind IN ('payment','payroll','savings_deposit')"):
            self.record(event['customer_id'], 'ledger-' + event['id'], event['occurred_at'], mapping[event['kind']],
                        source='ledger', value_minor=event['amount_minor'], ledger_id=event['id'], channel='transaction')

    def source(self):
        row = self.lab.db.execute('SELECT count(*),coalesce(max(rowid),0) FROM bronze_interactions').fetchone()
        return digest({'raw': list(row), 'day': self.lab.clock_day, 'profiles': self.profiles(), 'version': 'dna-v1'})

    def histories(self):
        grouped = defaultdict(list)
        for event in self.lab.rows('SELECT * FROM silver_interactions ORDER BY event_date,event_key'):
            grouped[event['customer_id']].append({**event, 'day': ordinal(event['event_date']), 'available':ordinal(event['available_on'])})
        return grouped

    @staticmethod
    def features(history, cutoff, profile, recipe='contextual'):
        recent = [e for e in history if cutoff - 14 <= e['day'] < cutoff and e.get('available',e['day'])<=cutoff]
        first = [e for e in recent if e['day'] < cutoff - 7]; last = [e for e in recent if e['day'] >= cutoff - 7]
        active = [e for e in recent if e['kind'] in ('app_open', 'campaign_click', 'product_view', 'product_activated')]
        purchases = [e for e in recent if e['kind'] == 'purchase']
        spend = sum(e['value_minor'] for e in purchases)
        impressions = sum(e['kind'] == 'campaign_impression' for e in recent)
        x = [sum(e['kind'] == 'app_open' for e in recent), len({e['day'] for e in active}),
             min(5, len(last) / (len(first) + 1)), min(30, cutoff - max((e['day'] for e in active), default=cutoff - 30)),
             len(purchases), math.log1p(spend / 100), math.log1p(spend / max(1, len(purchases)) / 100),
             min(5, sum(e['value_minor'] for e in last if e['kind'] == 'purchase') / (100 + sum(e['value_minor'] for e in first if e['kind'] == 'purchase'))),
             impressions, sum(e['kind'] == 'campaign_click' for e in recent) / (impressions + 1)]
        x += [sum(e['product'] == product and e['kind'] in ('product_view', 'campaign_click', 'product_activated') for e in recent) for product in PRODUCTS]
        x += [math.log1p(sum(e['value_minor'] for e in recent if e['kind'] == kind) / 100) for kind in ('income', 'savings')]
        if recipe == 'contextual': x += [int(profile['goal'] == p) for p in PRODUCTS] + [int(profile['preferred_channel'] == 'in_app')]
        return x

    def build_layers(self):
        with self.lab.lock, self.lab.db:
            self.ingest_ledger(); source = self.source()
            old = self.lab.db.execute('SELECT report FROM customer_pipeline_runs WHERE source_hash=?', (source,)).fetchone()
            if old: return {**json.loads(old[0]), 'cached': True}
            profiles = self.profiles(); rejected = []; valid = 0
            for event in self.lab.rows('SELECT * FROM bronze_interactions ORDER BY rowid'):
                try:
                    payload = json.loads(event['payload']); day = ordinal(event['event_date'])
                    dt.datetime.fromisoformat(event['event_date'].replace('Z', '+00:00'))
                    if event['customer_id'] not in profiles: raise ValueError('Unknown customer')
                    if payload['kind'] not in KINDS: raise ValueError('Unsupported interaction')
                    value = payload.get('value_minor', 0)
                    if type(value) is not int or value < 0: raise ValueError('Invalid monetary value')
                    if payload.get('product') not in (None, *PRODUCTS): raise ValueError('Unknown product')
                    if day > ordinal(self.lab.clock_day): raise ValueError('Future interaction')
                    available=payload.get('available_on',event['event_date'][:10])
                    if not day<=ordinal(available)<=ordinal(self.lab.clock_day):raise ValueError('Invalid observation availability')
                    if payload.get('source') not in ('environment','ledger','synthetic_bootstrap'):raise ValueError('Unknown data source')
                    self.lab.db.execute('INSERT OR IGNORE INTO silver_interactions VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (event['customer_id'], event['event_key'], event['event_date'], payload['kind'], value,
                         payload.get('product'), payload.get('channel', 'unknown'), payload.get('campaign_id'), payload['source'],available))
                    valid += 1
                except (KeyError, TypeError, ValueError):
                    rejected.append({'customer_id': event['customer_id'], 'event_key': event['event_key'], 'reason': 'Invalid customer, date, event type, product or value'})
            end = ordinal(self.lab.clock_day); histories = self.histories()
            for cid, profile in profiles.items():
                x = self.features(histories[cid], end, profile)
                self.lab.db.execute('INSERT OR REPLACE INTO gold_customer_features VALUES(?,?,?,?,?)',
                    (cid, self.lab.clock_day, encoded(dict(zip(FEATURES, x))), sum(e['day'] < end for e in histories[cid]), source))
            report = {'id': 'layers-' + source[:12], 'as_of': self.lab.clock_day, 'source_hash': source,
                      'bronze_rows': valid + len(rejected), 'silver_rows': valid, 'gold_customers': len(profiles),
                      'rejected_rows': len(rejected), 'quarantine_sample': rejected[:20],
                      'quality_passed': valid >= 100 and len(rejected) <= max(0, (valid + len(rejected)) // 100),
                      'grain': 'customer_id + ordered event_date#event_id; gold is one row per customer',
                      'feature_window': 'Previous 14 completed days', 'feature_columns': FEATURES,
                      'excluded_predictors': ['age_band', 'region', 'occupation', 'household_size'], 'cached': False}
            self.lab.db.execute('INSERT INTO customer_pipeline_runs VALUES(?,?,?,?,?)', (report['id'], self.lab.clock_day, source, encoded(report), now()))
            return report

    @staticmethod
    def target(history, day, kind):
        future = [e for e in history if day <= e['day'] < day + MODEL_SPECS[kind]['horizon']]
        if kind == 'churn': return int(not any(e['kind'] in ('app_open', 'campaign_click', 'product_view', 'product_activated') for e in future))
        if kind == 'response': return int(any(e['kind'] == 'campaign_click' for e in future))
        if kind in PRODUCTS: return int(any((e['product'] == kind and e['kind'] in ('product_view', 'campaign_click', 'product_activated')) or (kind == 'savings' and e['kind'] == 'savings') for e in future))
        if kind == 'repeat_spend': return int(sum(e['kind'] == 'purchase' for e in future) >= 3)
        return sum(e['value_minor'] for e in future if e['kind'] == 'purchase')

    def fit_models(self, recipe='contextual', targets=None, feature_names=None):
        if recipe not in ('behavioral', 'contextual'): raise LabError('Choose the behavioral or contextual recipe.')
        targets=list(MODEL_SPECS) if targets is None else targets
        if not isinstance(targets,list) or not 5<=len(targets)<=8 or len(set(targets))!=len(targets) or any(t not in MODEL_SPECS for t in targets):raise LabError('Select 5–8 distinct registered predictive tasks.')
        names=feature_names if feature_names is not None else FEATURES if recipe=='contextual' else FEATURES[:16]
        if not isinstance(names,list) or not 4<=len(names)<=len(FEATURES) or len(set(names))!=len(names) or any(k not in FEATURES for k in names):raise LabError('Use 4–21 observed or declared-preference features. Demographic and outcome columns are not predictors.')
        with self.lab.lock:
            layers = self.build_layers()
            if not layers['quality_passed']: raise LabError('Data quality blocked model fitting.', 409)
            source = layers['source_hash']; end = ordinal(self.lab.clock_day); profiles = self.profiles(); histories = self.histories()
            rows = []
            for target in targets:
                spec=MODEL_SPECS[target]
                identifier = 'dna-' + target + '-' + source[:10] + '-' + recipe+'-'+digest(names)[:6]
                existing = self.lab.db.execute('SELECT report FROM customer_dna_models WHERE id=?', (identifier,)).fetchone()
                if existing: rows.append(json.loads(existing[0])); continue
                train, test, train_ids, test_ids = [], [], set(), set()
                for cid, profile in profiles.items():
                    heldout = int(hashlib.sha256(cid.encode()).hexdigest()[:8], 16) % 5 == 0
                    for day in ([end - 14] if heldout else [end - 70, end - 56, end - 42, end - 28]):
                        all_x=dict(zip(FEATURES,self.features(histories[cid],day,profile,'contextual')))
                        x=[all_x[k] for k in names]
                        if not any(e['day'] < day for e in histories[cid]): continue
                        (test if heldout else train).append((x, self.target(histories[cid], day, target)))
                        (test_ids if heldout else train_ids).add(cid)
                report = {'id': identifier, 'target': target, 'title': spec['title'], 'definition': spec['definition'], 'recipe': recipe,
                          'train_rows': len(train), 'holdout_rows': len(test), 'feature_columns': names,
                          'train_customer_ids': sorted(train_ids), 'holdout_customer_ids': sorted(test_ids),
                          'training_label_end': iso(end - 14), 'holdout_label_start': iso(end - 14),
                          'source_hash': source, 'as_of': self.lab.clock_day, 'gate_reasons': [], 'data': 'Synthetic environment interactions'}
                artifact = {}; reasons = report['gate_reasons']
                if len(train) < 100 or len(test) < 30: reasons.append('Insufficient training or held-out customers.')
                elif target == 'capacity':
                    values = sorted(y for _, y in train); cuts = [values[len(values) // 3], values[2 * len(values) // 3]]
                    category = lambda y: int(y > cuts[0]) + int(y > cuts[1])
                    counts = Counter(category(y) for _, y in train)
                    if min(counts.get(i, 0) for i in range(3)) < 10: reasons.append('Spending-capacity classes need more examples.')
                    else:
                        models = [fit([(x, int(category(y) == c)) for x, y in train], names) for c in range(3)]
                        artifact = {'type': 'multiclass', 'models': models, 'cuts_minor': cuts, 'features': names}
                        labels = [category(y) for _, y in test]
                        predicted = [max(range(3), key=lambda c: predict(models[c], x)) for x, _ in test]
                        report['accuracy'] = sum(a == b for a, b in zip(predicted, labels)) / len(labels)
                        majority = counts.most_common(1)[0][0]; report['baseline_accuracy'] = labels.count(majority) / len(labels)
                        report['cut_points_minor'] = cuts
                        if report['accuracy'] < report['baseline_accuracy']: reasons.append('Capacity classifier does not beat the training-majority baseline.')
                else:
                    positives = sum(y for _, y in train)
                    if min(positives, len(train) - positives) < 10: reasons.append('Both outcome classes need training examples.')
                    else:
                        artifact = fit(train, names); report.update(evaluate(artifact, test, positives / len(train)))
                        if min(report['holdout_positives'], len(test) - report['holdout_positives']) < 5: reasons.append('Holdout class coverage is too small.')
                        if report['auc'] is None or report['auc'] < .55: reasons.append('Holdout ranking is not adequate for this demo.')
                        if report['brier'] >= report['baseline_brier']: reasons.append('Does not improve the prevalence baseline Brier score.')
                report['fitted'] = bool(artifact)
                report['eligible'] = bool(artifact) and not reasons
                checksum = digest({'artifact': artifact, 'report': report})
                with self.lab.db: self.lab.db.execute('INSERT INTO customer_dna_models VALUES(?,?,?,?,?,?,?,?,?)',
                    (identifier, target, self.lab.clock_day, recipe, source, encoded(artifact), encoded(report), checksum, now()))
                rows.append(report)
            return {'type': 'model_batch', 'source_hash': source, 'recipe': recipe, 'as_of': self.lab.clock_day,
                    'model_ids': [r['id'] for r in rows], 'models': [{k: r.get(k) for k in ('id', 'target', 'title', 'eligible', 'auc', 'brier', 'baseline_brier', 'accuracy', 'baseline_accuracy', 'gate_reasons')} for r in rows],
                    'model_tasks': len(rows), 'trained_models': sum(r.get('fitted',True) for r in rows), 'eligible_models': sum(r['eligible'] for r in rows),
                    'scope': 'Synthetic predictive tasks; propensity is not causal impact. Comparing experiments on this holdout makes it validation evidence, not an untouched final test.'}

    def publish_dna(self, batch):
        if batch.get('type') != 'model_batch' or batch['source_hash'] != self.source(): raise LabError('Model batch belongs to a stale dataset.', 409)
        selected = {}; held = []
        for identifier in batch['model_ids']:
            row = self.lab.db.execute('SELECT * FROM customer_dna_models WHERE id=?', (identifier,)).fetchone()
            if not row: raise LabError('Model artifact is missing.', 409)
            artifact, report = json.loads(row['artifact']), json.loads(row['report'])
            if digest({'artifact': artifact, 'report': report}) != row['checksum']: raise LabError('Model artifact integrity failed.', 409)
            if row['source_hash'] != batch['source_hash']: raise LabError('Mixed model source versions are not allowed.', 409)
            if report['eligible']: selected[row['target']] = (row['id'], artifact)
            else: held.append(row['target'])
        if len(selected) < 5: return {'type': 'dna_release', 'approved': False, 'reason': 'Fewer than five models qualified; no Customer DNA release.', 'eligible_models': len(selected), 'held_models': held}
        with self.lab.lock, self.lab.db:
            profiles = self.profiles()
            for row in self.lab.rows('SELECT * FROM gold_customer_features ORDER BY customer_id'):
                if row['source_hash'] != batch['source_hash']: raise LabError('Gold features changed.', 409)
                all_features = json.loads(row['features']); scores = {}; versions = {}; tags = []
                for target, (identifier, artifact) in selected.items():
                    x = [all_features[k] for k in artifact['features']]; versions[target] = identifier
                    if target == 'capacity':
                        p = [predict(m, x) for m in artifact['models']]; index = max(range(3), key=lambda k: p[k])
                        scores['capacity_band'] = ['low', 'middle', 'high'][index]; scores['capacity_confidence'] = p[index] / max(.00001, sum(p))
                    else: scores[MODEL_SPECS[target]['column']] = round(predict(artifact, x), 5)
                if scores.get('churn_score', 0) > .6: tags.append('disengagement risk')
                for product in PRODUCTS:
                    if scores.get(product + '_score', 0) >= .6: tags.append(product + ' affinity')
                tags.append('declared goal: ' + profiles[row['customer_id']]['goal'])
                columns = [MODEL_SPECS[k]['column'] for k in MODEL_SPECS if k != 'capacity']
                self.lab.db.execute('INSERT OR REPLACE INTO gold_customer_dna VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (row['customer_id'], self.lab.clock_day, *[scores.get(k) for k in columns], scores.get('capacity_band'), scores.get('capacity_confidence'), encoded(tags), encoded(versions), batch['source_hash']))
        return {'type': 'dna_release', 'approved': True, 'source_hash': batch['source_hash'], 'eligible_models': len(selected), 'held_models': held,
                'dna_digest':self.dna_digest(),'customers': len(profiles), 'columns': [MODEL_SPECS[k]['column'] for k in selected], 'sample': self.dna(limit=3)}

    def dna_digest(self):
        return digest(self.lab.rows('SELECT * FROM gold_customer_dna ORDER BY customer_id'))

    def dna(self, limit=24):
        profiles = self.profiles(); result = []
        for row in self.lab.rows('SELECT d.*,c.name FROM gold_customer_dna d JOIN customers c ON c.id=d.customer_id ORDER BY d.customer_id LIMIT ?', (limit,)):
            row['tags'] = json.loads(row['tags']); row['model_versions'] = json.loads(row['model_versions']); row['profile'] = profiles[row['customer_id']]
            result.append(row)
        return result

    def eligible_audience(self, strategy, limit, experience='auto', audience='all'):
        if strategy not in ('needs_first', 'retention', 'adoption') or type(limit) is not int or not 8 <= limit <= 60: raise LabError('Use a known marketing objective and 8–60 customers.')
        if experience not in ('auto',*PRODUCTS) or audience not in ('all','at_risk','high_engagement','low_engagement'):raise LabError('Use a supported experience and behavioral audience.')
        if self.lab.db.execute("SELECT 1 FROM marketing_campaigns WHERE status='running'").fetchone(): raise LabError('A pilot is already collecting outcomes. Monitor it before launching another.', 409)
        profiles = self.profiles(); eligible = []; skipped = Counter(); cutoff = iso(ordinal(self.lab.clock_day) - 7)
        for dna in self.dna(1000):
            cid = dna['customer_id']; profile = profiles[cid]
            if not profile['marketing_consent']: skipped['no_consent'] += 1; continue
            feature=self.lab.db.execute('SELECT features FROM gold_customer_features WHERE customer_id=?',(cid,)).fetchone()
            active_days=json.loads(feature[0])['active_days_14d'] if feature else 0
            if (audience=='at_risk' and (dna['churn_score'] is None or dna['churn_score']<.6)) or (audience=='high_engagement' and active_days<7) or (audience=='low_engagement' and active_days>3):skipped['outside_requested_audience']+=1;continue
            if ordinal(self.lab.clock_day) - ordinal(dna['as_of']) > 7: skipped['stale_dna'] += 1; continue
            if self.lab.db.execute("SELECT 1 FROM campaign_assignments a JOIN marketing_campaigns c ON c.id=a.campaign_id WHERE a.customer_id=? AND a.arm='message' AND c.started_on>?", (cid, cutoff)).fetchone(): skipped['frequency_cap'] += 1; continue
            choices = {p: dna[p + '_score'] for p in PRODUCTS if dna[p + '_score'] is not None and experience in ('auto',p)}
            wallet = self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?', (cid + ':wallet',)).fetchone()[0]
            if wallet < 100000: choices.pop('savings', None)
            if not choices: skipped['no_eligible_score'] += 1; continue
            product = max(choices, key=lambda p: choices[p] + (.12 if strategy == 'needs_first' and profile['goal'] == p else 0))
            score = choices[product] + (.3 * (dna['churn_score'] or 0) if strategy == 'retention' else .2 * (dna['response_score'] or 0))
            eligible.append({'customer_id': cid, 'name': dna['name'], 'product': product, 'rank': score, 'dna': dna})
        return sorted(eligible, key=lambda x: (-x['rank'], x['customer_id']))[:limit], dict(skipped)

    def launch_campaign(self, release, strategy, size, tone, operation_id, experience='auto', audience='all'):
        if tone not in ('practical', 'encouraging'): raise LabError('Choose a known message tone.')
        old = self.lab.db.execute('SELECT id FROM marketing_campaigns WHERE operation_id=?', (operation_id,)).fetchone()
        if old: return {**self.campaign(old[0]), 'replayed': True}
        if not release.get('approved') or release.get('source_hash') != self.source(): raise LabError('Marketing needs a current, qualified Customer DNA release.', 409)
        if release.get('dna_digest')!=self.dna_digest():raise LabError('Customer DNA changed after publication.',409)
        selected, skipped = self.eligible_audience(strategy, size,experience,audience)
        if len(selected)%2:selected.pop()
        if len(selected) < 8: raise LabError('Too few eligible customers for a randomized pilot.', 409)
        r = seeded(release['source_hash'], strategy, self.lab.db.execute('SELECT count(*) FROM marketing_campaigns').fetchone()[0]); r.shuffle(selected)
        identifier = 'campaign-' + uuid.uuid4().hex[:12]; due = iso(ordinal(self.lab.clock_day) + 7)
        config = {'strategy': strategy, 'tone': tone, 'experience':experience,'audience':audience,'source_hash': release['source_hash'], 'skipped': skipped,
                  'channel': 'simulated_in_app', 'randomization': 'Shuffled eligible audience, alternating message/control; 50% assignment probability.'}
        messages = {'savings': 'Explore a savings goal that fits your routine. Keep essentials covered first.',
                    'budgeting': 'Review your spending categories and upcoming needs in one place.',
                    'qr': 'Explore QR payment tips for your everyday purchases.',
                    'rewards': 'Explore the rewards guide for the ways you already spend. No purchase is required.'}
        with self.lab.lock, self.lab.db:
            self.lab.db.execute('INSERT INTO marketing_campaigns VALUES(?,?,?,?,?,?,?,?)', (identifier, operation_id, self.lab.clock_day, due, 'running', encoded(config), '{}', now()))
            for i, person in enumerate(selected):
                arm = 'message' if i % 2 == 0 else 'control'; cid = person['customer_id']; product = person['product']
                message = person['name'].split()[0] + ', ' + ('here is a small step toward your goals. ' if tone == 'encouraging' else '') + messages[product]
                snapshot = {'dna': person['dna'], 'profile': self.profiles()[cid], 'assignment_probability': .5}
                self.lab.db.execute('INSERT INTO campaign_assignments VALUES(?,?,?,?,?,?,NULL,NULL)', (identifier, cid, arm, product, message if arm == 'message' else '', encoded(snapshot)))
                if arm == 'message': self.record(cid, identifier + '-impression', self.lab.clock_day, 'campaign_impression', product=product, channel='in_app', campaign_id=identifier)
        return {**self.campaign(identifier), 'replayed': False}

    def inspect_cohorts(self, group_by):
        if group_by not in ('goal','preferred_channel','activity_band'):raise LabError('Use goal, preferred_channel or activity_band for this analysis.')
        profiles=self.profiles();groups=defaultdict(list)
        for row in self.lab.rows('SELECT * FROM gold_customer_features'):
            f=json.loads(row['features']);p=profiles[row['customer_id']]
            key=('active' if f['active_days_14d']>=7 else 'occasional' if f['active_days_14d']>=1 else 'dormant') if group_by=='activity_band' else p[group_by]
            groups[key].append((p,f))
        return {'group_by':group_by,'cohorts':[{'cohort':key,'customers':len(rows),
                'consented':sum(p['marketing_consent'] for p,f in rows),
                'mean_active_days_14d':round(sum(f['active_days_14d'] for p,f in rows)/len(rows),2),
                'mean_recorded_click_rate':round(sum(f['click_rate'] for p,f in rows)/len(rows),3)} for key,rows in groups.items()],
                'interpretation':'Observed associations; not a causal campaign effect. No demographic targeting.'}

    def preview_campaign(self, release, strategy, size, tone, experience='auto', audience='all'):
        if tone not in ('practical','encouraging'):raise LabError('Use a known message tone.')
        if not release.get('approved') or release.get('source_hash')!=self.source() or release.get('dna_digest')!=self.dna_digest():raise LabError('Preview requires a current qualified DNA release.',409)
        selected,skipped=self.eligible_audience(strategy,size,experience,audience)
        return {'type':'campaign_preview','release':{k:release[k] for k in ('approved','source_hash','dna_digest')},
                'strategy':strategy,'size':size,'tone':tone,'experience':experience,'audience':audience,'eligible_customers':len(selected),'skipped':skipped,
                'experience_mix':dict(Counter(p['product'] for p in selected)),
                'sample':[{'customer_id':p['customer_id'],'name':p['name'],'experience':p['product'],'declared_goal':p['dna']['profile']['goal']} for p in selected[:5]],
                'decision_needed':'Launch only if this audience supports the objective; otherwise request another analysis or model experiment. No messages sent yet.'}

    def mature_campaigns(self):
        for campaign in self.lab.rows("SELECT * FROM marketing_campaigns WHERE status='running' AND due_on<=?", (self.lab.clock_day,)):
            counts = {'message': [], 'control': []}
            with self.lab.db:
                for person in self.lab.rows('SELECT * FROM campaign_assignments WHERE campaign_id=?', (campaign['id'],)):
                    snapshot = json.loads(person['snapshot']); profile = snapshot['profile']; match = profile['goal'] == person['product']
                    # Outcomes come from an independent stochastic environment equation,
                    # never from the model score being evaluated.
                    probability = .05 + .15 * match + .10 * profile['activity_rate']
                    if person['arm'] == 'message': probability += .14 + .19 * match
                    outcome = int(seeded(person['customer_id'], campaign['started_on'], person['product'], 'pilot-response').random() < probability)
                    self.lab.db.execute('UPDATE campaign_assignments SET outcome=?,observed_on=? WHERE campaign_id=? AND customer_id=?', (outcome, self.lab.clock_day, campaign['id'], person['customer_id']))
                    counts[person['arm']].append(outcome)
                    if outcome:
                        occurred=iso(ordinal(campaign['due_on'])-1)
                        if person['arm'] == 'message': self.record(person['customer_id'], campaign['id'] + '-click', occurred, 'campaign_click', product=person['product'], channel='in_app', campaign_id=campaign['id'],available_on=self.lab.clock_day)
                        self.record(person['customer_id'], campaign['id'] + '-activation', occurred, 'product_activated', product=person['product'], channel='in_app', campaign_id=campaign['id'],available_on=self.lab.clock_day)
                rates = {arm: sum(values) / len(values) for arm, values in counts.items()}
                def wilson(p,n):
                    z=1.96;denom=1+z*z/n;mid=(p+z*z/(2*n))/denom
                    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
                    return mid-half,mid+half
                mt,ut=wilson(rates['message'],len(counts['message']));mc,uc=wilson(rates['control'],len(counts['control']))
                lift = rates['message'] - rates['control']
                interval=[max(-1,lift-math.sqrt((rates['message']-mt)**2+(uc-rates['control'])**2)),
                          min(1,lift+math.sqrt((ut-rates['message'])**2+(rates['control']-mc)**2))]
                report = {'message_n': len(counts['message']), 'control_n': len(counts['control']), 'message_rate': rates['message'], 'control_rate': rates['control'],
                          'difference': lift, 'approximate_95pct_interval': interval,
                          'conclusion': 'Promising in this synthetic pilot; replicate before rollout.' if interval[0] > 0 else 'Inconclusive; collect more randomized outcomes before claiming benefit.',
                          'next_step': 'Refresh bronze-to-gold and refit Customer DNA with these observed interactions.',
                          'limitations': 'Small synthetic pilot; approximate Newcombe/Wilson interval. Not real-world marketing performance.'}
                self.lab.db.execute("UPDATE marketing_campaigns SET status='completed',report=? WHERE id=?", (encoded(report), campaign['id']))

    def campaign(self, identifier):
        row = self.lab.db.execute('SELECT * FROM marketing_campaigns WHERE id=?', (identifier,)).fetchone()
        if not row: raise LabError('Campaign not found.', 404)
        result = dict(row); result['config'] = json.loads(result['config']); result['report'] = json.loads(result['report'])
        result['assignments'] = self.lab.rows('SELECT customer_id,arm,product,message,outcome,observed_on FROM campaign_assignments WHERE campaign_id=? ORDER BY customer_id', (identifier,))
        return result

    def advance_day(self, day):
        with self.lab.lock, self.lab.db:
            self.daily_interactions(day); self.mature_campaigns()

    def summary(self):
        profiles = self.profiles(); current = self.lab.db.execute('SELECT report FROM customer_pipeline_runs ORDER BY rowid DESC LIMIT 1').fetchone()
        return {'customers': len(profiles), 'declared_goals': dict(Counter(p['goal'] for p in profiles.values())),
                'marketing_consent': sum(p['marketing_consent'] for p in profiles.values()),
                'pipeline': json.loads(current[0]) if current else None,
                'campaigns': [{k: c[k] for k in ('id', 'status', 'started_on', 'due_on', 'report')} for c in [self.campaign(r[0]) for r in self.lab.db.execute('SELECT id FROM marketing_campaigns ORDER BY rowid DESC LIMIT 3')]],
                'model_targets': {k: v['definition'] for k, v in MODEL_SPECS.items()}, 'data_scope': 'Synthetic marketing, app engagement and observed transaction interactions.'}

    def dashboard(self):
        with self.lab.lock:
            overview = self.summary(); profiles = self.profiles()
            overview['profiles'] = [{**c, 'profile': profiles[c['id']]} for c in self.lab.rows('SELECT * FROM customers ORDER BY id')]
            overview['dna'] = self.dna(1000)
            overview['tables'] = {t: self.lab.db.execute('SELECT count(*) FROM ' + t).fetchone()[0] for t in TABLES}
            overview['models'] = [json.loads(r['report']) for r in self.lab.rows('SELECT report FROM customer_dna_models ORDER BY rowid DESC LIMIT 8')]
            overview['events'] = self.lab.rows('SELECT customer_id,event_key,event_date,kind,product,channel,source FROM silver_interactions ORDER BY rowid DESC LIMIT 12')
            overview['campaigns'] = [self.campaign(r[0]) for r in self.lab.db.execute('SELECT id FROM marketing_campaigns ORDER BY rowid DESC LIMIT 4')]
            return overview
