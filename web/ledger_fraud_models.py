"""Train and score the ledger-features-v1 classifier without BigQuery ML."""
import hashlib
import json
import math
import random

from environment_data import digest_id
from lab import LabError
from ledger_fraud_features import FEATURES, VERSION, finite_vector, vector_from_ae_row
from trained_models import score


def _txn_index(tables):
    return {r['transaction_id']: r for r in tables['wallet_transactions']}


def event_transaction_id(lab, event_id):
    scene = lab.db.execute('SELECT scene_id FROM demo_scene WHERE id=1').fetchone()[0]
    return digest_id('TXN', scene, event_id)


def feature_record_for_event(lab, event_id, tables):
    txn_id = event_transaction_id(lab, event_id)
    txn = _txn_index(tables).get(txn_id)
    if not txn:
        return None, ['ledger_transaction_projection']
    values = finite_vector(vector_from_ae_row(txn, tables))
    if not values:
        return None, ['nonfinite_ledger_features']
    return values, []


def train_rows(rows):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import average_precision_score, brier_score_loss
    from sklearn.model_selection import train_test_split

    if len(rows) < 40:
        raise ValueError('Need at least 40 ledger rows to train.')
    labels = [int(r['label']) for r in rows]
    if len(set(labels)) < 2:
        raise ValueError('Training labels must include fraud and non-fraud.')
    x = [[float(r['features'][f]) for f in FEATURES] for r in rows]
    x_train, x_test, y_train, y_test = train_test_split(x, labels, test_size=0.2, random_state=42, stratify=labels)
    model = GradientBoostingClassifier(n_estimators=32, max_depth=2, learning_rate=0.12, random_state=71)
    model.fit(x_train, y_train)
    val = model.predict_proba(x_test)[:, 1].tolist()
    choices = []
    for threshold in range(10, 96, 5):
        tp = sum(y == 1 and p >= threshold / 100 for y, p in zip(y_test, val))
        fp = sum(y == 0 and p >= threshold / 100 for y, p in zip(y_test, val))
        positives = sum(y_test)
        negatives = len(y_test) - positives
        choices.append({
            'threshold': threshold / 100,
            'recall': tp / max(1, positives),
            'false_positive_rate': fp / max(1, negatives),
        })
    eligible = [m for m in choices if m['false_positive_rate'] <= 0.05]
    picked = max(eligible or choices, key=lambda m: (m['recall'], -m['false_positive_rate']))
    test_scores = model.predict_proba(x_test)[:, 1].tolist()
    evaluation = {
        'rows': len(rows),
        'positives': sum(labels),
        'test_average_precision': round(float(average_precision_score(y_test, test_scores)), 4),
        'test_brier': round(float(brier_score_loss(y_test, test_scores)), 4),
        'validation_threshold': picked['threshold'],
        'validation_recall': round(picked['recall'], 4),
        'validation_false_positive_rate': round(picked['false_positive_rate'], 4),
    }
    artifact = {
        'kind': 'boosted_tree',
        'feature_version': VERSION,
        'features': list(FEATURES),
        'threshold': picked['threshold'],
        'initial_score': float(math.log(model.init_.class_prior_[1] / model.init_.class_prior_[0])),
        'parameters': {'trees': 32, 'max_depth': 2, 'learning_rate': 0.12},
        'trees': [{
            'children_left': est[0].tree_.children_left.tolist(),
            'children_right': est[0].tree_.children_right.tolist(),
            'feature': est[0].tree_.feature.tolist(),
            'threshold': est[0].tree_.threshold.tolist(),
            'value': est[0].tree_.value.tolist(),
        } for est in model.estimators_],
    }
    return artifact, evaluation


def synthetic_training_rows(count=600):
    rng = random.Random(42)
    tables = {name: [] for name in ('customers', 'wallets', 'devices', 'wallet_transactions')}
    for i in range(30):
        cid = f'CUST_{i:04d}'
        tables['customers'].append({
            'customer_id': cid,
            'full_name': f'Resident {i}',
            'kyc_status': 'BASIC' if i % 5 == 0 else 'FULLY_VERIFIED',
            'creation_date': '2026-09-01T00:00:00Z' if i % 7 == 0 else '2026-01-01T00:00:00Z',
            'risk_tier': 'HIGH' if i % 9 == 0 else 'MEDIUM' if i % 3 == 0 else 'LOW',
        })
        wid = f'WAL_{i:04d}'
        tables['wallets'].append({
            'wallet_id': wid,
            'customer_id': cid,
            'wallet_type': 'PERSONAL_PRIMARY',
            'current_balance': f'{rng.randint(5000, 80000):.2f}',
            'daily_spent': f'{rng.randint(0, 40000):.2f}',
            'wallet_status': 'ACTIVE',
        })
        tables['devices'].append({
            'device_id': f'DEV_{i:04d}',
            'customer_id': cid,
            'device_model': ('iPhone 14', 'Samsung S23', 'Pixel 8')[i % 3],
            'ip_address': f'198.51.100.{i % 200 + 1}',
            'trust_score': 0.25 if i % 11 == 0 else 0.85,
        })
    for j in range(count):
        sender = j % 30
        fraud = bool((j % 17 == 0) or (rng.random() < 0.18 and sender % 9 == 0))
        amount = rng.randint(800, 45000) if not fraud else rng.randint(15000, 70000)
        tables['wallet_transactions'].append({
            'transaction_id': f'TXN_{j:06d}',
            'sender_wallet_id': f'WAL_{sender:04d}',
            'receiver_wallet_id': f'WAL_{(sender + 7) % 30:04d}',
            'amount': f'{amount:.2f}',
            'timestamp': '2026-10-06T12:00:00Z',
            'transaction_type': 'P2P_TRANSFER' if fraud else rng.choice(['MERCHANT_QR', 'P2P_TRANSFER']),
            'channel': 'MOBILE_APP',
            'device_id': f'DEV_{sender:04d}',
            'risk_score': 80.0 if fraud else 10.0,
            'risk_factors': '[]',
            'is_fraud': fraud,
            'scam_type': 'ATO_DRAIN' if fraud else 'LEGITIMATE',
        })
    return [{
        'transaction_id': t['transaction_id'],
        'label': bool(t['is_fraud']),
        'features': vector_from_ae_row(t, tables),
        'feature_version': VERSION,
    } for t in tables['wallet_transactions']]


def predict(model_id, transactions, lab, entry, model):
    env = getattr(lab, 'environment_data', None) if lab else None
    tables = env.tables() if env else None
    records = []
    predictions = []
    for tx in transactions:
        missing = []
        values = None
        if not tables:
            missing.append('ledger_feature_projection')
        else:
            values, missing = feature_record_for_event(lab, tx['id'], tables)
        records.append({
            'event_id': tx['id'],
            'features': values or {},
            'missing_inputs': missing,
            'available_at': tx.get('occurred_at'),
        })
        if missing or not values:
            predictions.append({'event_id': tx['id'], 'available': False, 'signal_score': None, 'matched_features': []})
            continue
        prob = score(model, values)
        predictions.append({
            'event_id': tx['id'],
            'available': True,
            'signal_score': prob,
            'matched_features': [k for k, v in values.items() if v > 0],
        })
    valid = [row['signal_score'] for row in predictions if row['available']]
    value = max(valid, default=None)
    return {
        'detector_id': model_id,
        'name': entry['name'],
        'version': entry['version'],
        'features': model['features'],
        'available': bool(valid),
        'signal_score': value,
        'calibrated_fraud_probability': None,
        'result': 'elevated learned signal' if value is not None and value >= model['threshold'] else 'no elevated learned signal' if valid else 'insufficient evidence',
        'threshold': model['threshold'],
        'kind': 'trained_ledger_advisory',
        'predictions': predictions,
        'limitation': entry['limitation'],
        'input_source': 'AE ledger projection at case time; excludes simulator truth labels and heuristic risk scores.',
    }, records
