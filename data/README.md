# MintTown: Simulated Environment Implementation

This document outlines the architecture, data generation strategy, and deployment steps for the MintTown simulated e-wallet environment and agentic memory layer in Google Cloud BigQuery[cite: 1].

---

## Architecture Overview

The simulated environment is structured into a star-schema fact ledger, forensic dimensions, and static/semi-dynamic agent memory tables optimized for single-query agent retrieval:

- **Forensic Dimensions:** `customers`, `wallets`, `devices`
- **Core Event Facts:** `wallet_transactions` (partitioned by date, containing ML risk scores and risk factor arrays)
- **Agentic Memory & Knowledge:** `scam_knowledge` (10 e-wallet typologies) and `scam_memory` (6 historical reviewed cases)[cite: 1]
- **Agent Integration View:** `v_agent_ledger` (pre-joined view for single tool-call access)

---

## Implementation Steps

### Step 1: Local Synthetic Data Generation

- **Script:** `generator/generate_minttown_data.py`
- **Action:** Run the script locally to produce the core CSV datasets.
- **Parameters:** Generates 5,000 customer profiles, 5,000 primary wallets, 5,000 devices, and 100,000 risk-scored transactions spanning a 90-day window with injected scam archetypes (APP, ATO, Vishing, Task Scams, etc.).

### Step 2: BigQuery Schema Initialization & Seeding

- **Script:** `schemas/etup_bigquery.sql`
- **Action:** Execute the DDL statements in the BigQuery console.
- **Tasks:**
  - Create the `minttown_simulated_env` dataset.
  - Establish the daily-partitioned `wallet_transactions` table.
  - Populate the `scam_knowledge` master library with 10 detailed typology definitions and red flags.
  - Seed the `scam_memory` table with 6 historical human-reviewed cases and analyst resolution rules[cite: 1].

### Step 3: Batch Data Ingestion & View Creation

- **Script:** `ingestion/load_to_bq.py`
- **Action:** Run the Python ingestion script.
- **Tasks:**
  - Batch-upload local CSVs (`customers.csv`, `wallets.csv`, `devices.csv`, `wallet_transactions.csv`) into BigQuery.
  - Programmatically create the `v_agent_ledger` unified view joining customer risk tiers, receiver mule details, and device fingerprints.

### Step 4: Agent Tool Connection & Testing

- **Action:** Provide the GCP Project ID, dataset name (`minttown_simulated_env`), and credentials to the agent development team.
- **Tasks:**
  - Configure the Gemini investigation agent to query `v_agent_ledger` for transaction facts[cite: 1].
  - Enable secondary agent tool calls to cross-reference `scam_knowledge` and `scam_memory` during active investigations[cite: 1].
  - Run a test "Golden Query" to verify sub-second response times ahead of the hackathon judging presentation.
