"""Karlo's bounded CPU tree model, trained on AE data and served from frozen case inputs."""
import math

from ledger_fraud_features import FEATURES, VERSION, epoch, finite_vector
from trained_models import score


def counts(labels, scores, threshold):
    tp = sum(bool(y) and p >= threshold for y, p in zip(labels, scores))
    fp = sum(not y and p >= threshold for y, p in zip(labels, scores))
    positives = sum(labels); negatives = len(labels)-positives
    return {'tp': tp, 'fp': fp, 'fn': positives-tp, 'tn': negatives-fp,
            'recall': tp/positives if positives else None,
            'false_positive_rate': fp/negatives if negatives else None}


def train_rows(rows):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import average_precision_score
    if not 100 <= len(rows) <= 20000 or len({r['transaction_id'] for r in rows}) != len(rows):
        raise ValueError('Require 100–20,000 unique rows.')
    rows = sorted(rows, key=lambda r: (epoch(r['occurred_at']), r['transaction_id']))
    # Tied timestamps stay together so no future examples leak into model selection.
    times = sorted({epoch(r['occurred_at']) for r in rows})
    first, second = times[int(len(times)*.6)], times[int(len(times)*.8)]
    groups = [[r for r in rows if epoch(r['occurred_at']) < first],
              [r for r in rows if first <= epoch(r['occurred_at']) < second],
              [r for r in rows if epoch(r['occurred_at']) >= second]]
    if any(len(g) < 10 or len({r['label'] for r in g}) != 2 for g in groups):
        raise ValueError('Each chronological train/validation/test partition needs both labels.')
    def xy(group):
        if any(finite_vector(r['features']) is None for r in group):
            raise ValueError('Invalid training features.')
        return [[r['features'][f] for f in FEATURES] for r in group], [int(r['label']) for r in group]
    x_train, y_train = xy(groups[0]); x_val, y_val = xy(groups[1]); x_test, y_test = xy(groups[2])
    model = GradientBoostingClassifier(n_estimators=32, max_depth=2, learning_rate=.12, random_state=71)
    model.fit(x_train, y_train)
    val = model.predict_proba(x_val)[:, 1].tolist()
    choices = [{'threshold': t/100, **counts(y_val, val, t/100)} for t in range(5, 101, 5)]
    picked = max([c for c in choices if c['false_positive_rate'] <= .05], key=lambda c: (c['recall'], -c['false_positive_rate'], c['threshold']))
    artifact = {'kind': 'boosted_tree', 'feature_version': VERSION, 'features': list(FEATURES),
                'threshold': picked['threshold'], 'initial_score': math.log(model.init_.class_prior_[1]/model.init_.class_prior_[0]),
                'parameters': {'trees': 32, 'max_depth': 2, 'learning_rate': .12},
                'trees': [{'children_left': e[0].tree_.children_left.tolist(), 'children_right': e[0].tree_.children_right.tolist(),
                           'feature': e[0].tree_.feature.tolist(), 'threshold': e[0].tree_.threshold.tolist(),
                           'value': e[0].tree_.value.tolist()} for e in model.estimators_]}
    # The selected threshold is fixed before reading any test predictions.
    test = model.predict_proba(x_test)[:, 1].tolist()
    parity = max(abs(score(artifact, r['features'])-p) for r, p in zip(groups[2], test))
    if parity > 1e-10:
        raise ValueError('JSON inference differs from the fitted estimator.')
    evaluation = {'rows': len(rows), 'customers': len({r['customer_id'] for r in rows}), 'positives': sum(r['label'] for r in rows),
                  'split': 'chronological 60/20/20; timestamp ties kept together; threshold selected only on validation',
                  'partitions': {name: {'rows': len(g), 'positives': sum(r['label'] for r in g), 'start': g[0]['occurred_at'], 'end': g[-1]['occurred_at']} for name, g in zip(('train','validation','test'), groups)},
                  'validation': picked, 'test': counts(y_test, test, picked['threshold']),
                  'test_average_precision': float(average_precision_score(y_test, test)), 'json_parity_max_error': parity,
                  'train_test_customer_overlap': len({r['customer_id'] for r in groups[0]} & {r['customer_id'] for r in groups[2]}),
                  'limitations': ['Synthetic AE labels, not measured real-world fraud accuracy.', 'Temporal test can share customers; no unseen-customer or unseen-scam guarantee.', 'Uncalibrated advisory score; not approved for payment blocking.']}
    return artifact, evaluation


def predict(model_id, transactions, lab, entry, model, snapshot=None):
    saved = (snapshot or {}).get('data', {}).get('ledger_features', {})
    records = []; predictions = []
    for tx in transactions:
        record = saved.get(tx['id'], {})
        values = finite_vector(record.get('features', {}))
        valid = record.get('feature_version') == VERSION and record.get('available_at') == tx['occurred_at'] and not record.get('missing_inputs') and values is not None
        missing = [] if valid else ['frozen_ledger_features_v2']
        records.append({'event_id': tx['id'], 'features': values if valid else {}, 'missing_inputs': missing,
                        'available_at': record.get('available_at'), 'feature_version': VERSION})
        predictions.append({'event_id': tx['id'], 'available': bool(valid), 'signal_score': score(model, values) if valid else None,
                            'matched_features': list(FEATURES) if valid else []})
    valid_scores = [r['signal_score'] for r in predictions if r['available']]
    value = max(valid_scores, default=None)
    return {'detector_id': model_id, 'name': entry['name'], 'version': entry['version'], 'features': model['features'],
            'available': bool(valid_scores), 'signal_score': value, 'calibrated_fraud_probability': None,
            'result': 'elevated learned signal' if value is not None and value >= model['threshold'] else 'no elevated learned signal' if valid_scores else 'insufficient evidence',
            'threshold': model['threshold'], 'kind': 'trained_ledger_advisory', 'predictions': predictions,
            'limitation': entry['limitation'], 'input_source': 'Frozen case-time transaction and strictly earlier wallet history; AE-compatible contract.'}, records
