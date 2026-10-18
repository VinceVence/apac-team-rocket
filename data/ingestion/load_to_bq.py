"""Validate AE CSVs locally; explicit apply can fill only empty, owned simulator tables."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'web'))
from environment_data import schema
from cloud_data import MAX_EXPORT_BYTES, MAX_EXPORT_ROWS

TABLES = ('customers','wallets','devices','wallet_transactions')
DATASET = 'minttown_world'


def read_tables(folder):
    paths = [Path(folder)/f'{name}.csv' for name in TABLES]
    if sum(p.stat().st_size for p in paths) > MAX_EXPORT_BYTES:
        raise ValueError('CSV input exceeds the publication byte cap.')
    tables = {}
    for name, path in zip(TABLES, paths):
        with path.open(newline='') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != [v['name'] for v in schema(name)]:
                raise ValueError('Column contract differs: '+name)
            records = []
            for row in reader:
                if None in row:
                    raise ValueError('Extra CSV values: '+name)
                for field in schema(name):
                    key, kind = field['name'], field['type']
                    value = row[key]
                    if value is None or (field['mode']=='REQUIRED' and not value):
                        raise ValueError('Missing required value: '+key)
                    if kind == 'NUMERIC':
                        amount=Decimal(value)
                        if not amount.is_finite() or amount < 0:
                            raise ValueError('Invalid amount.')
                        row[key]=str(amount)
                    elif kind == 'FLOAT':
                        number=float(value)
                        if not math.isfinite(number):
                            raise ValueError('Invalid numeric value.')
                        row[key]=number
                    elif kind == 'BOOLEAN':
                        if value.lower() not in ('true','false'):
                            raise ValueError('Invalid boolean.')
                        row[key]=value.lower()=='true'
                    elif kind == 'TIMESTAMP':
                        dt.datetime.fromisoformat(value.replace('Z','+00:00'))
                records.append(row)
                if len(records)>MAX_EXPORT_ROWS:
                    raise ValueError('Too many rows.')
        tables[name]=records
    if not 2<=len(tables['customers'])<=100 or sum(map(len,tables.values()))>MAX_EXPORT_ROWS:
        raise ValueError('Customer or publication row cap exceeded.')
    identities={}
    for name,key in zip(TABLES,('customer_id','wallet_id','device_id','transaction_id')):
        ids=[r[key] for r in tables[name]]
        if len(ids)!=len(set(ids)):
            raise ValueError('Duplicate key: '+name)
        identities[name]=set(ids)
    wallet_owners={r['wallet_id']:r['customer_id'] for r in tables['wallets']}
    device_owners={r['device_id']:r['customer_id'] for r in tables['devices']}
    def timestamp(value):
        value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        return value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value
    created={r['customer_id']:timestamp(r['creation_date']) for r in tables['customers']}
    if any(c not in identities['customers'] for c in [*wallet_owners.values(),*device_owners.values()]):
        raise ValueError('Unknown customer reference.')
    for tx in tables['wallet_transactions']:
        sender,receiver=tx['sender_wallet_id'],tx['receiver_wallet_id']
        if sender==receiver or sender not in wallet_owners or receiver not in wallet_owners:
            raise ValueError('Invalid payment participants.')
        if device_owners.get(tx['device_id'])!=wallet_owners[sender]:
            raise ValueError('Device does not belong to the sender.')
        if timestamp(tx['timestamp'])<max(created[wallet_owners[sender]],created[wallet_owners[receiver]]):
            raise ValueError('Payment predates an account.')
    if len(json.dumps(tables).encode())>MAX_EXPORT_BYTES:
        raise ValueError('JSON input exceeds the publication byte cap.')
    return tables


def apply(tables, project, dataset, receipt, world_stopped=False, client=None):
    if dataset!=DATASET or not project or not world_stopped:
        raise ValueError('Explicit project, minttown_world and --world-stopped are required. Never run beside an active world writer.')
    if (set(tables)!=set(TABLES) or not 2<=len(tables.get('customers',[]))<=100
            or sum(map(len,tables.values()))>MAX_EXPORT_ROWS
            or len(json.dumps(tables).encode())>MAX_EXPORT_BYTES):
        raise ValueError('Import contract or publication caps exceeded.')
    if Path(receipt).exists():
        raise ValueError('A load receipt already exists. Inspect existing jobs; do not retry automatically.')
    from google.cloud import bigquery
    client = client or bigquery.Client(project=project)
    owner = client.get_dataset(f'{project}.{dataset}', retry=None, timeout=30)
    if (owner.labels or {}).get('purpose')!='simulator_mirror' or owner.location!='US':
        raise ValueError('Destination is not an owned simulator dataset.')
    for name in TABLES:
        table=client.get_table(f'{project}.{dataset}.{name}', retry=None, timeout=30)
        if (table.labels or {}).get('purpose')!='simulator_mirror' or table.num_rows or table.streaming_buffer:
            raise ValueError('Every destination must be owned and empty; existing data is never replaced.')
        actual=[{'name':f.name,'type':f.field_type,'mode':f.mode} for f in table.schema]
        if actual!=schema(name):
            raise ValueError('Destination schema differs: '+name)
    digest=hashlib.sha256(json.dumps(tables,sort_keys=True).encode()).hexdigest()[:24]
    state={'status':'pending','digest':digest,'jobs':{name:f'minttown_fixture_{digest}_{name}' for name in TABLES}}
    receipt=Path(receipt);receipt.parent.mkdir(parents=True,exist_ok=True)
    with receipt.open('x') as f:json.dump(state,f,indent=2)
    # WRITE_EMPTY also checks at the server, preventing a race from overwriting data.
    for name in TABLES:
        config=bigquery.LoadJobConfig(write_disposition='WRITE_EMPTY',create_disposition='CREATE_NEVER')
        job=client.load_table_from_json(tables[name],f'{project}.{dataset}.{name}',
            job_config=config,job_id=state['jobs'][name],location='US',num_retries=0,timeout=60)
        job.result(retry=None,timeout=60)
    state['status']='complete';receipt.write_text(json.dumps(state,indent=2)+'\n')
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'output/ae-fixtures')
    parser.add_argument('--project')
    parser.add_argument('--dataset',default=DATASET)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--world-stopped',action='store_true')
    parser.add_argument('--receipt',type=Path,default=ROOT/'output/ae-fixtures/load-receipt.json')
    args=parser.parse_args()
    if args.dataset!=DATASET:
        parser.error('Only minttown_world is writable. AE source datasets are protected.')
    tables=read_tables(args.input)
    if args.apply:
        result=apply(tables,args.project,args.dataset,args.receipt,args.world_stopped)
    else:
        result={'mode':'validation-only','rows':{k:len(v) for k,v in tables.items()},'cloud_calls':0}
    print(json.dumps(result))


if __name__=='__main__':
    main()
