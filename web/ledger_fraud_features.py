"""Point-in-time ledger contract shared by AE training and frozen case inference."""
import csv
import datetime as dt
import math
from pathlib import Path

VERSION = 'ledger-features-v2'
TRANSACTION_TYPES = ('P2P_TRANSFER', 'MERCHANT_QR', 'CASH_OUT_AGENT', 'CASH_IN_AGENT')
CHANNELS = ('MOBILE_APP', 'WEB_PORTAL')
FEATURES = ('amount_php', 'transaction_type_code', 'channel_code', 'hour_utc',
            'prior_count_1h', 'prior_spend_24h_php', 'prior_mean_30d_php', 'prior_count_30d')
ALLOWED = set(FEATURES)


def epoch(value):
    parsed = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Ledger model requires an explicit timestamp timezone.')
    return int(parsed.timestamp())


def finite_vector(values):
    if any(type(values.get(k)) not in (int, float) or not math.isfinite(values[k]) or values[k] < 0 for k in FEATURES):
        return None
    if values['transaction_type_code'] >= len(TRANSACTION_TYPES) or values['channel_code'] >= len(CHANNELS) or values['hour_utc'] >= 24:
        return None
    return {k: float(values[k]) for k in FEATURES}


def training_row_from_flat_export(record):
    # IDs, timestamps and labels control offline splits; they never enter predictors.
    values = {k: float(record[k]) for k in FEATURES}
    if not finite_vector(values):
        raise ValueError('Incomplete or invalid ledger training row.')
    label = str(record['is_fraud']).lower()
    if label not in ('true', 'false', '1', '0'):
        raise ValueError('Missing binary training label.')
    return {'transaction_id': record['transaction_id'], 'customer_id': record['customer_id'],
            'occurred_at': record['event_timestamp'], 'label': label in ('true', '1'),
            'features': values, 'feature_version': VERSION}


def load_bigquery_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as handle:
        rows = [training_row_from_flat_export(r) for r in csv.DictReader(handle)]
    if not 40 <= len(rows) <= 20000 or len({r['transaction_id'] for r in rows}) != len(rows):
        raise ValueError('Require 40–20,000 unique labelled ledger rows.')
    return rows


def snapshot_records(lab, transactions):
    """Freeze scoped, strictly earlier wallet history before any agent can request it."""
    records = {}
    for tx in transactions:
        record = {'event_id': tx['id'], 'feature_version': VERSION, 'available_at': tx['occurred_at'],
                  'features': {}, 'missing_inputs': [], 'source': 'frozen canonical ledger; AE-compatible contract'}
        try:
            at = epoch(tx['occurred_at'])
            if tx['status'] != 'settled' or not tx.get('from_account'):
                raise ValueError('settled_sender_wallet')
            target = lab.db.execute('SELECT kind FROM accounts WHERE id=?', (tx['to_account'],)).fetchone()
            kind = tx['metadata'].get('transaction_type')
            if kind not in TRANSACTION_TYPES:
                kind = 'CASH_IN_AGENT' if tx['kind'] == 'payroll' else 'MERCHANT_QR' if target and target[0] == 'merchant' else 'P2P_TRANSFER'
            channel = tx['metadata'].get('channel', 'MOBILE_APP')
            since = dt.datetime.fromtimestamp(at - 30*86400, dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            history = lab.rows("SELECT amount_minor,occurred_at FROM financial_events WHERE from_account=? AND status='settled' AND kind IN ('payment','payroll') AND occurred_at>=? AND occurred_at<? ORDER BY occurred_at LIMIT 20001", (tx['from_account'], since, tx['occurred_at']))
            if len(history) > 20000:
                raise ValueError('bounded_wallet_history')
            prior = [(epoch(r['occurred_at']), r['amount_minor']/100) for r in history]
            prior = [(t, a) for t, a in prior if 0 < at-t <= 30*86400]
            values = {'amount_php': tx['amount_minor']/100, 'transaction_type_code': TRANSACTION_TYPES.index(kind),
                      'channel_code': CHANNELS.index(channel), 'hour_utc': dt.datetime.fromtimestamp(at, dt.timezone.utc).hour,
                      'prior_count_1h': sum(at-t <= 3600 for t, _ in prior),
                      'prior_spend_24h_php': sum(a for t, a in prior if at-t <= 86400),
                      'prior_mean_30d_php': sum(a for _, a in prior)/len(prior) if prior else 0,
                      'prior_count_30d': len(prior)}
            record['features'] = finite_vector(values)
            if record['features'] is None:
                raise ValueError('finite_ledger_features')
        except (KeyError, ValueError, TypeError):
            record.update(features={}, missing_inputs=['valid_point_in_time_ledger_history'])
        records[tx['id']] = record
    return records
