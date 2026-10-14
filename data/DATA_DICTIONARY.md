# MintTown BigQuery Data Dictionary

**Dataset ID:** `minttown_simulated_env`

**Target Platform:** Google Cloud BigQuery

**Environment:** Simulated Hackathon Demo Environment

## Table of Contents

1. [`customers`](#1-customers)

2. [`wallets`](#2-wallets)

3. [`devices`](#3-devices)

4. [`wallet_transactions`](#4-wallet_transactions)

5. [`scam_knowledge`](#5-scam_knowledge)

6. [`scam_memory`](#6-scam_memory)

7. [`v_agent_ledger` (View)](#7-v_agent_ledger-view)

---

## 1. `customers`

Stores user profile information, identity verification levels, and baseline risk categorizations.

| Field Name | Data Type | Mode | Description | Allowed / Categorical Values | 
| :--- | :--- | :--- | :--- | :--- | 
| `customer_id` | `STRING` | `REQUIRED` | Unique alphanumeric identifier for the customer. | *Unique String (`CUST_XXXXXXXX`)* | 
| `full_name` | `STRING` | `NULLABLE` | Full legal name of the user. | *Free Text* | 
| `kyc_status` | `STRING` | `NULLABLE` | Identity verification tier. | `BASIC`, `FULLY_VERIFIED` | 
| `creation_date` | `TIMESTAMP` | `NULLABLE` | Timestamp when the customer account was registered. | *Timestamp (UTC)* | 
| `risk_tier` | `STRING` | `NULLABLE` | System-assigned baseline risk classification. | `LOW`, `MEDIUM`, `HIGH` | 

---

## 2. `wallets`

Stores financial account details, current balances, and account status for each customer's e-wallet.

| Field Name | Data Type | Mode | Description | Allowed / Categorical Values | 
| :--- | :--- | :--- | :--- | :--- | 
| `wallet_id` | `STRING` | `REQUIRED` | Unique identifier for the e-wallet account. | *Unique String (`WAL_XXXXXXXX`)* | 
| `customer_id` | `STRING` | `REQUIRED` | Foreign key referencing `customers.customer_id`. | *Foreign Key* | 
| `wallet_type` | `STRING` | `NULLABLE` | Functional classification of the e-wallet. | `PERSONAL_PRIMARY`, `MERCHANT`, `AGENT_WALLET` | 
| `current_balance` | `NUMERIC` | `NULLABLE` | Current stored fiat balance in local currency. | *Numeric Decimal* | 
| `daily_spent` | `NUMERIC` | `NULLABLE` | Total cumulative spend for the current rolling 24-hour window. | *Numeric Decimal* | 
| `wallet_status` | `STRING` | `NULLABLE` | Operational state of the wallet. | `ACTIVE`, `FROZEN`, `SUSPENDED` | 

---

## 3. `devices`

Contains hardware fingerprinting, network metadata, and historical device trust scores.

| Field Name | Data Type | Mode | Description | Allowed / Categorical Values | 
| :--- | :--- | :--- | :--- | :--- | 
| `device_id` | `STRING` | `REQUIRED` | Unique hardware identifier or device fingerprint hash. | *Unique String (`DEV_XXXXXXXX`)* | 
| `customer_id` | `STRING` | `REQUIRED` | Foreign key referencing `customers.customer_id`. | *Foreign Key* | 
| `device_model` | `STRING` | `NULLABLE` | Mobile device model or operating system profile. | `iPhone 14`, `iPhone 15`, `Samsung S23`, `Xiaomi Redmi`, `Pixel 8` | 
| `ip_address` | `STRING` | `NULLABLE` | Primary or last known IPv4 address. | *Valid IPv4 Address* | 
| `trust_score` | `FLOAT64` | `NULLABLE` | Calculated trust score between `0.00` (suspicious) and `1.00` (trusted). | *Float Range [0.00, 1.00]* | 

---

## 4. `wallet_transactions`

**Partition Key:** `DATE(timestamp)`

Core fact table recording all P2P, merchant, and cash-in/out transactions along with real-time risk scoring output.

| Field Name | Data Type | Mode | Description | Allowed / Categorical Values | 
| :--- | :--- | :--- | :--- | :--- | 
| `transaction_id` | `STRING` | `REQUIRED` | Unique transaction reference string. | *Unique String (`TXN_XXXXXXXX`)* | 
| `sender_wallet_id` | `STRING` | `REQUIRED` | Foreign key referencing originating `wallets.wallet_id`. | *Foreign Key* | 
| `receiver_wallet_id` | `STRING` | `REQUIRED` | Foreign key referencing destination `wallets.wallet_id`. | *Foreign Key* | 
| `amount` | `NUMERIC` | `REQUIRED` | Monetary value of the transaction. | *Numeric Decimal* | 
| `timestamp` | `TIMESTAMP` | `REQUIRED` | Exact UTC timestamp of transaction authorization. | *Timestamp (UTC)* | 
| `transaction_type` | `STRING` | `NULLABLE` | Payment channel / transaction category. | `P2P_TRANSFER`, `MERCHANT_QR`, `CASH_OUT_AGENT`, `CASH_IN_AGENT` | 
| `channel` | `STRING` | `NULLABLE` | Client interaction channel. | `MOBILE_APP`, `WEB_PORTAL` | 
| `device_id` | `STRING` | `NULLABLE` | Hardware ID utilized for transaction creation. | *Foreign Key* | 
| `risk_score` | `FLOAT64` | `NULLABLE` | Automated risk assessment score (`0.0` to `100.0`). | *Float Range [0.0, 100.0]* | 
| `risk_factors` | `STRING` | `NULLABLE` | JSON/String array of triggered heuristic red flags. | `NOVEL_IP`, `VELOCITY_SPIKE`, `NEW_RECIPIENT`, `MAX_LIMIT_HIT`, `OTP_TRIGGERED` | 
| `is_fraud` | `BOOL` | `REQUIRED` | Ground-truth flag indicating confirmed or synthetic fraud. | `TRUE`, `FALSE` | 
| `scam_type` | `STRING` | `NULLABLE` | Injected typology label for demo/training scenarios. | `LEGITIMATE`, `PHISHING_APP`, `ATO_DRAIN`, `FAKE_MERCHANT_QR`, `VISHING`, `TASK_SCAM`, `PIG_BUTCHERING`, `AGENT_FRAUD`, `SUBSIDY_PHISHING`, `PREDATORY_LENDING`, `REFUND_SCAM` | 

---

## 5. `scam_knowledge`

Static master reference table containing fraud typology definitions, key indicators, and severity impacts.

| Field Name | Data Type | Mode | Description | Allowed / Categorical Values | 
| :--- | :--- | :--- | :--- | :--- | 
| `scam_id` | `STRING` | `REQUIRED` | Master typology ID code. | *Unique Code (`KNOW_XXX_00X`)* | 
| `scam_category` | `STRING` | `REQUIRED` | High-level threat classification. | `Authorized Push Payment`, `Account Takeover`, `Social Engineering`, `Merchant Fraud`, `Long-Term Scam`, `Agent Fraud`, `Employment Scam`, `Phishing & Smishing`, `Predatory Lending`, `Refund Scam` | 
| `scam_name` | `STRING` | `REQUIRED` | Descriptive human-readable name of the fraud scheme. | *Specific Scam Title Strings* | 
| `typology_description` | `STRING` | `NULLABLE` | In-depth narrative explaining how the scam operates. | *Free Text Narrative* | 
| `key_red_flags` | `ARRAY<STRING>` | `NULLABLE` | Array of key indicators associated with this typology. | *Array of strings (e.g., `["Rapid P2P drain", "Telegram lead"]`)* | 
| `base_impact` | `INT64` | `NULLABLE` | Inherent severity/risk weight rating. | *Integer Range [30, 50]* | 

---

## 6. `scam_memory`

Agentic long-term memory store containing historical, human-analyst-approved fraud case resolutions and learned mitigation rules.

| Field Name | Data Type | Mode | Description | Allowed / Categorical Values | 
| :--- | :--- | :--- | :--- | :--- | 
| `case_id` | `STRING` | `REQUIRED` | Unique historical case record ID. | *Unique String (`CASE_YYYY_XXX`)* | 
| `incident_timestamp` | `TIMESTAMP` | `REQUIRED` | Date and time when the case was resolved. | *Timestamp (UTC)* | 
| `scam_category` | `STRING` | `NULLABLE` | Fraud category associated with the case. | *Matches categories from `scam_knowledge`* | 
| `victim_id` | `STRING` | `NULLABLE` | Wallet ID of the target victim. | *Foreign Key (`WAL_XXXXXXXX`)* | 
| `fraudster_id` | `STRING` | `NULLABLE` | Wallet ID of the flagged fraudster/mule. | *Foreign Key (`WAL_XXXXXXXX`)* | 
| `evidence_summary` | `STRING` | `NULLABLE` | Analyst summary of key findings and chat logs. | *Free Text Summary* | 
| `investigation_outcome` | `STRING` | `NULLABLE` | Formal case status and action taken. | `CONFIRMED_FRAUD_REFUNDED`, `CONFIRMED_ATO_FROZEN`, `CONFIRMED_FRAUD_PARTIAL_RECOVERY`, `CONFIRMED_QR_SPOOFING`, `CONFIRMED_TASK_SCAM`, `CONFIRMED_SUBSIDY_PHISHING` | 
| `approved_by_analyst` | `STRING` | `NULLABLE` | Name or ID of the human investigator. | *Analyst Identifiers (e.g., `ANALYST_SARAH`, `ANALYST_MARCUS`, `ANALYST_ELENA`)* | 
| `learned_pattern_rule` | `STRING` | `NULLABLE` | Recommended rule/action derived from the resolution. | *Free Text Action Rule* | 

---

## 7. `v_agent_ledger` (View)

Unified pre-joined view combining `wallet_transactions`, `customers`, `wallets`, and `devices` for single-tool-call Gemini agent context retrieval.

| Field Name | Data Type | Description | Source Field & Allowed Values | 
| :--- | :--- | :--- | :--- | 
| `transaction_id` | `STRING` | Transaction reference identifier. | `wallet_transactions.transaction_id` | 
| `timestamp` | `TIMESTAMP` | Time of transaction occurrence. | `wallet_transactions.timestamp` | 
| `amount` | `NUMERIC` | Monetary amount transferred. | `wallet_transactions.amount` | 
| `transaction_type` | `STRING` | Transaction channel classification. | `P2P_TRANSFER`, `MERCHANT_QR`, `CASH_OUT_AGENT`, `CASH_IN_AGENT` | 
| `risk_score` | `FLOAT64` | Transaction risk score. | `wallet_transactions.risk_score` | 
| `risk_factors` | `STRING` | Array/JSON string of triggered risk heuristics. | *Triggered Red Flags Array String* | 
| `is_fraud` | `BOOL` | Fraud truth indicator flag. | `TRUE`, `FALSE` | 
| `scam_type` | `STRING` | Typology label. | *Matches `wallet_transactions.scam_type` allowed values* | 
| `sender_wallet_id` | `STRING` | Originating wallet identifier. | `wallets.wallet_id` | 
| `sender_name` | `STRING` | Originating customer full name. | `customers.full_name` | 
| `sender_kyc` | `STRING` | Originating customer KYC tier. | `BASIC`, `FULLY_VERIFIED` | 
| `sender_risk_tier` | `STRING` | Originating customer risk tier. | `LOW`, `MEDIUM`, `HIGH` | 
| `receiver_wallet_id` | `STRING` | Destination wallet identifier. | `wallets.wallet_id` | 
| `receiver_name` | `STRING` | Destination customer full name (Mule tracking). | `customers.full_name` | 
| `device_id` | `STRING` | Hardware device identifier used. | `devices.device_id` | 
| `device_model` | `STRING` | Device hardware model. | `iPhone 14`, `iPhone 15`, `Samsung S23`, `Xiaomi Redmi`, `Pixel 8` | 
| `ip_address` | `STRING` | Network IP address recorded. | *Valid IPv4 Address* | 
| `trust_score` | `FLOAT64` | Recorded trust score for the device. | *Float Range [0.00, 1.00]* |
