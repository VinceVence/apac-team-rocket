"""Gab's AE-shaped fixtures, bounded and repeatable. No cloud or model calls."""
import argparse
import csv
import datetime as dt
import json
import random
from pathlib import Path

TABLES = ('customers', 'wallets', 'devices', 'wallet_transactions')
MAX_CUSTOMERS, MAX_TRANSACTIONS = 100, 10000
TRANSACTION_COLUMNS = ('transaction_id','sender_wallet_id','receiver_wallet_id','amount','timestamp',
    'transaction_type','channel','device_id','risk_score','risk_factors','is_fraud','scam_type')


def generate(customers=100, transactions=1000, seed=42):
    if not 2 <= customers <= MAX_CUSTOMERS or not 0 <= transactions <= MAX_TRANSACTIONS:
        raise ValueError('Require 2–100 residents and 0–10,000 transactions.')
    rng = random.Random(seed)
    anchor = dt.datetime(2026, 10, 6, 9, tzinfo=dt.timezone.utc)
    stamp = lambda value: value.isoformat(timespec='seconds').replace('+00:00', 'Z')
    rows = {name: [] for name in TABLES}
    for i in range(1, customers + 1):
        customer, wallet, device = f'CUST_{i:04d}', f'WAL_{i:04d}', f'DEV_{i:04d}'
        rows['customers'].append(dict(customer_id=customer, full_name=f'Resident {i}',
            kyc_status=rng.choice(['BASIC', 'FULLY_VERIFIED']), creation_date=stamp(anchor-dt.timedelta(days=365)),
            risk_tier=rng.choice(['LOW', 'MEDIUM', 'HIGH'])))
        rows['wallets'].append(dict(wallet_id=wallet, customer_id=customer, wallet_type='PERSONAL_PRIMARY',
            current_balance=f'{rng.randint(2000, 800000)/100:.2f}', daily_spent='0.00', wallet_status='ACTIVE'))
        rows['devices'].append(dict(device_id=device, customer_id=customer,
            device_model=rng.choice(['iPhone 14', 'Samsung S23', 'Pixel 8']),
            ip_address=f'192.0.2.{i}', trust_score=round(rng.uniform(.4, 1), 2)))
    for i in range(transactions):
        sender, receiver = rng.sample(range(1, customers+1), 2)
        scam = rng.choice(['LEGITIMATE']*3 + ['PHISHING_APP','ATO_DRAIN','FAKE_MERCHANT_QR','VISHING','TASK_SCAM'])
        fraud = scam != 'LEGITIMATE'
        rows['wallet_transactions'].append(dict(transaction_id=f'TXN_{i+1:08d}',
            sender_wallet_id=f'WAL_{sender:04d}', receiver_wallet_id=f'WAL_{receiver:04d}',
            amount=f'{rng.randint(500,150000)/100:.2f}',
            timestamp=stamp(anchor-dt.timedelta(days=90)+dt.timedelta(seconds=1+i*60)),
            transaction_type=rng.choice(['P2P_TRANSFER','MERCHANT_QR','CASH_OUT_AGENT','CASH_IN_AGENT']),
            channel='MOBILE_APP', device_id=f'DEV_{sender:04d}',
            risk_score=round(rng.uniform(75,99) if fraud else rng.uniform(1,35),1),
            risk_factors=json.dumps(rng.sample(['NOVEL_IP','VELOCITY_SPIKE','NEW_RECIPIENT'],2) if fraud else []),
            is_fraud=fraud, scam_type=scam))
    return rows


def write_csv(rows, output):
    output = Path(output)
    if any((output/f'{name}.csv').exists() for name in TABLES):
        raise ValueError('Choose a new output directory; existing datasets are preserved.')
    output.mkdir(parents=True, exist_ok=True)
    for name, records in rows.items():
        with (output/f'{name}.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]) if records else TRANSACTION_COLUMNS)
            writer.writeheader(); writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--customers', type=int, default=100)
    parser.add_argument('--transactions', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=Path('output/ae-fixtures'))
    args = parser.parse_args()
    rows = generate(args.customers, args.transactions, args.seed)
    write_csv(rows, args.output)
    print(json.dumps({'output':str(args.output),'rows':{k:len(v) for k,v in rows.items()},'cloud_calls':0}))


if __name__ == '__main__':
    main()
