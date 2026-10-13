import pandas as pd
import numpy as np
from faker import Faker
import uuid
import random
from datetime import datetime, timedelta

fake = Faker()
random.seed(42)
np.random.seed(42)

NUM_CUSTOMERS = 5000
NUM_TRANSACTIONS = 100000

print(f"Generating {NUM_CUSTOMERS} customers, wallets, and devices...")
customers, wallets, devices = [], [], []

for _ in range(NUM_CUSTOMERS):
    c_id = f"CUST_{uuid.uuid4().hex[:8].upper()}"
    w_id = f"WAL_{uuid.uuid4().hex[:8].upper()}"
    d_id = f"DEV_{uuid.uuid4().hex[:8].upper()}"
    
    customers.append({
        "customer_id": c_id,
        "full_name": fake.name(),
        "kyc_status": random.choices(["BASIC", "FULLY_VERIFIED"], weights=[0.2, 0.8])[0],
        "creation_date": fake.date_time_between(start_date="-1y", end_date="-30d").strftime('%Y-%m-%d %H:%M:%S'),
        "risk_tier": random.choices(["LOW", "MEDIUM", "HIGH"], weights=[0.7, 0.2, 0.1])[0]
    })
    
    wallets.append({
        "wallet_id": w_id,
        "customer_id": c_id,
        "wallet_type": "PERSONAL_PRIMARY",
        "current_balance": round(random.uniform(20.0, 8000.0), 2),
        "daily_spent": round(random.uniform(0.0, 800.0), 2),
        "wallet_status": "ACTIVE"
    })
    
    devices.append({
        "device_id": d_id,
        "customer_id": c_id,
        "device_model": random.choice(["iPhone 14", "iPhone 15", "Samsung S23", "Xiaomi Redmi", "Pixel 8"]),
        "ip_address": fake.ipv4(),
        "trust_score": round(random.uniform(0.4, 1.0), 2)
    })

df_cust = pd.DataFrame(customers)
df_wall = pd.DataFrame(wallets)
df_dev = pd.DataFrame(devices)

print(f"Generating {NUM_TRANSACTIONS} wallet transactions...")
wallet_ids = df_wall['wallet_id'].tolist()
device_ids = df_dev['device_id'].tolist()
scam_types = ["LEGITIMATE", "LEGITIMATE", "LEGITIMATE", "PHISHING_APP", "ATO_DRAIN", "FAKE_MERCHANT_QR", "VISHING", "TASK_SCAM"]

transactions = []
for i in range(NUM_TRANSACTIONS):
    t_id = f"TXN_{uuid.uuid4().hex[:8].upper()}"
    sender = random.choice(wallet_ids)
    receiver = random.choice([w for w in wallet_ids if w != sender])
    s_type = random.choice(scam_types)
    
    is_fraud = s_type != "LEGITIMATE"
    risk_score = round(random.uniform(75.0, 99.0), 1) if is_fraud else round(random.uniform(1.0, 35.0), 1)
    
    risk_factors = []
    if risk_score > 70:
        risk_factors = random.sample(["NOVEL_IP", "VELOCITY_SPIKE", "NEW_RECIPIENT", "MAX_LIMIT_HIT"], k=random.randint(1, 3))
    
    transactions.append({
        "transaction_id": t_id,
        "sender_wallet_id": sender,
        "receiver_wallet_id": receiver,
        "amount": round(random.uniform(5.0, 1500.0), 2),
        "timestamp": fake.date_time_between(start_date="-90d", end_date="now").strftime('%Y-%m-%d %H:%M:%S'),
        "transaction_type": random.choices(["P2P_TRANSFER", "MERCHANT_QR", "CASH_OUT_AGENT", "CASH_IN_AGENT"], weights=[0.5, 0.3, 0.1, 0.1])[0],
        "channel": "MOBILE_APP",
        "device_id": random.choice(device_ids),
        "risk_score": risk_score,
        "risk_factors": str(risk_factors),
        "is_fraud": is_fraud,
        "scam_type": s_type
    })

df_txn = pd.DataFrame(transactions)

# Export to CSV
df_cust.to_csv("customers.csv", index=False)
df_wall.to_csv("wallets.csv", index=False)
df_dev.to_csv("devices.csv", index=False)
df_txn.to_csv("wallet_transactions.csv", index=False)

print("Local data generation complete!")