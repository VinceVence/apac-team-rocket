from google.cloud import bigquery
import pandas as pd

client = bigquery.Client()
dataset_id = "minttown_simulated_env"

folder_path = '../generator'

# 1. Load CSVs into BigQuery
tables = ["customers", "wallets", "devices", "wallet_transactions"]
for table_name in tables:
    df = pd.read_csv(f"{folder_path}/{table_name}.csv")
    table_ref = client.dataset(dataset_id).table(table_name)
    
    job = client.load_table_from_dataframe(df, table_ref)
    job.result()
    print(f"Loaded table `{table_name}` ({len(df)} rows) successfully!")

# 2. Create Unified Agent Investigation View
view_query = f"""
CREATE OR REPLACE VIEW `{client.project}.{dataset_id}.v_agent_ledger` AS
SELECT 
    t.transaction_id,
    t.timestamp,
    t.amount,
    t.transaction_type,
    t.risk_score,
    t.risk_factors,
    t.is_fraud,
    t.scam_type,
    
    -- Sender Details
    s_w.wallet_id AS sender_wallet_id,
    s_c.full_name AS sender_name,
    s_c.kyc_status AS sender_kyc,
    s_c.risk_tier AS sender_risk_tier,
    
    -- Receiver Details (Mule Tracking)
    r_w.wallet_id AS receiver_wallet_id,
    r_c.full_name AS receiver_name,
    
    -- Device Context
    t.device_id,
    d.device_model,
    d.ip_address,
    d.trust_score
FROM 
    `{client.project}.{dataset_id}.wallet_transactions` t
LEFT JOIN `{client.project}.{dataset_id}.wallets` s_w ON t.sender_wallet_id = s_w.wallet_id
LEFT JOIN `{client.project}.{dataset_id}.customers` s_c ON s_w.customer_id = s_c.customer_id
LEFT JOIN `{client.project}.{dataset_id}.wallets` r_w ON t.receiver_wallet_id = r_w.wallet_id
LEFT JOIN `{client.project}.{dataset_id}.customers` r_c ON r_w.customer_id = r_c.customer_id
LEFT JOIN `{client.project}.{dataset_id}.devices` d ON t.device_id = d.device_id;
"""

query_job = client.query(view_query)
query_job.result()
print("Agent investigation view `v_agent_ledger` created successfully!")