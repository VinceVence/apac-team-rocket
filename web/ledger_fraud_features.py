"""AE ledger features for a local CPU fraud classifier (no BigQuery ML).

Excludes label-derived fields: is_fraud, scam_type, risk_score, risk_factors.
"""
import datetime as dt
import json
import math
from decimal import Decimal
from pathlib import Path

VERSION = 'ledger-features-v1'

TRANSACTION_TYPES = ('P2P_TRANSFER', 'MERCHANT_QR', 'CASH_OUT_AGENT', 'CASH_IN_AGENT')
CHANNELS = ('MOBILE_APP', 'WEB_PORTAL')
KYC = ('BASIC', 'FULLY_VERIFIED')
RISK = ('LOW', 'MEDIUM', 'HIGH')
WALLET_TYPES = ('PERSONAL_PRIMARY', 'MERCHANT', 'AGENT_WALLET')
WALLET_STATUS = ('ACTIVE', 'FROZEN', 'SUSPENDED')
DEVICE_MODELS = ('iPhone 14', 'iPhone 15', 'Samsung S23', 'Xiaomi Redmi', 'Pixel 8')

FEATURES = (
    'amount_php',
    'transaction_type_code',
    'channel_code',
    'sender_kyc_code',
    'sender_risk_tier_code',
    'sender_account_age_days',
    'sender_wallet_type_code',
    'sender_balance_php',
    'sender_daily_spent_php',
    'sender_wallet_status_code',
    'amount_to_balance_ratio',
    'receiver_kyc_code',
    'receiver_risk_tier_code',
    'receiver_wallet_type_code',
    'receiver_wallet_status_code',
    'device_trust_score',
    'device_model_code',
)
ALLOWED = set(FEATURES)


def _code(value, allowed):
    try:
        return float(allowed.index(value))
    except ValueError:
        return float(len(allowed))


def _parse_ts(value):
    return dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def vector_from_ae_row(t, tables):
    wallets = {r['wallet_id']: r for r in tables['wallets']}
    customers = {r['customer_id']: r for r in tables['customers']}
    devices = {r['device_id']: r for r in tables['devices']}
    sw = wallets[t['sender_wallet_id']]
    rw = wallets[t['receiver_wallet_id']]
    sc = customers[sw['customer_id']]
    rc = customers[rw['customer_id']]
    device = devices[t['device_id']]
    amount = float(Decimal(t['amount']))
    balance = float(Decimal(sw['current_balance']))
    txn_ts = _parse_ts(t['timestamp'])
    created = _parse_ts(sc['creation_date'])
    age = max(0, (txn_ts - created).days)
    ratio = min(10.0, amount / balance) if balance > 0 else 10.0
    return {
        'amount_php': amount,
        'transaction_type_code': _code(t.get('transaction_type'), TRANSACTION_TYPES),
        'channel_code': _code(t.get('channel'), CHANNELS),
        'sender_kyc_code': _code(sc.get('kyc_status'), KYC),
        'sender_risk_tier_code': _code(sc.get('risk_tier'), RISK),
        'sender_account_age_days': float(age),
        'sender_wallet_type_code': _code(sw.get('wallet_type'), WALLET_TYPES),
        'sender_balance_php': balance,
        'sender_daily_spent_php': float(Decimal(sw.get('daily_spent', '0'))),
        'sender_wallet_status_code': _code(sw.get('wallet_status'), WALLET_STATUS),
        'amount_to_balance_ratio': ratio,
        'receiver_kyc_code': _code(rc.get('kyc_status'), KYC),
        'receiver_risk_tier_code': _code(rc.get('risk_tier'), RISK),
        'receiver_wallet_type_code': _code(rw.get('wallet_type'), WALLET_TYPES),
        'receiver_wallet_status_code': _code(rw.get('wallet_status'), WALLET_STATUS),
        'device_trust_score': float(device.get('trust_score', 0.5)),
        'device_model_code': _code(device.get('device_model'), DEVICE_MODELS),
    }


def _truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ('true', 't', '1')


def _float(value, default=0.0):
    if value is None or value == '':
        return default
    return float(value)


def training_row_from_flat_export(record):
    ratio_raw = record.get('amount_to_balance_ratio')
    ratio = 10.0 if ratio_raw in (None, '') else min(10.0, _float(ratio_raw, 10.0))
    return {
        'transaction_id': record['transaction_id'],
        'label': _truthy(record['is_fraud']),
        'features': {
            'amount_php': _float(record['amount_php']),
            'transaction_type_code': _code(record.get('transaction_type'), TRANSACTION_TYPES),
            'channel_code': _code(record.get('channel'), CHANNELS),
            'sender_kyc_code': _code(record.get('sender_kyc_status'), KYC),
            'sender_risk_tier_code': _code(record.get('sender_risk_tier'), RISK),
            'sender_account_age_days': _float(record.get('sender_account_age_days')),
            'sender_wallet_type_code': _code(record.get('sender_wallet_type'), WALLET_TYPES),
            'sender_balance_php': _float(record.get('sender_balance_php')),
            'sender_daily_spent_php': _float(record.get('sender_daily_spent_php')),
            'sender_wallet_status_code': _code(record.get('sender_wallet_status'), WALLET_STATUS),
            'amount_to_balance_ratio': ratio,
            'receiver_kyc_code': _code(record.get('receiver_kyc_status'), KYC),
            'receiver_risk_tier_code': _code(record.get('receiver_risk_tier'), RISK),
            'receiver_wallet_type_code': _code(record.get('receiver_wallet_type'), WALLET_TYPES),
            'receiver_wallet_status_code': _code(record.get('receiver_wallet_status'), WALLET_STATUS),
            'device_trust_score': _float(record.get('device_trust_score'), 0.5),
            'device_model_code': _code(record.get('device_model'), DEVICE_MODELS),
        },
        'feature_version': VERSION,
    }


def load_bigquery_csv(path):
    import csv

    rows = []
    with Path(path).open(newline='', encoding='utf-8') as handle:
        for record in csv.DictReader(handle):
            rows.append(training_row_from_flat_export(record))
    if not rows:
        raise ValueError('BigQuery export CSV is empty.')
    return rows


def load_export_rows(export_dir):
    root = Path(export_dir)
    tables = {}
    for name in ('customers', 'wallets', 'devices', 'wallet_transactions'):
        path = root / f'{name}.jsonl'
        if not path.exists():
            raise FileNotFoundError(path)
        tables[name] = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows = []
    for t in tables['wallet_transactions']:
        rows.append({
            'transaction_id': t['transaction_id'],
            'label': bool(t['is_fraud']),
            'features': vector_from_ae_row(t, tables),
            'feature_version': VERSION,
        })
    return rows


def finite_vector(values):
    out = {}
    for key in FEATURES:
        value = values.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        out[key] = float(value)
    return out
