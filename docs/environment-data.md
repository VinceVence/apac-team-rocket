# Simulation data

[DATA_DICTIONARY.md](../data/DATA_DICTIONARY.md) is Gab's unchanged dictionary from [commit f03a384](https://github.com/VinceVence/apac-team-rocket/blob/f03a38491e2b3e2b1428cae7fb7430a5346d1f2c/data/DATA_DICTIONARY.md). The generator and ingestion scripts on his branch have not been merged.

The running world projects its ledger into these six schemas through `web/environment_data.py`:

| Table | Generated from |
|---|---|
| `customers` | Up to 100 active residents; synthetic KYC and a stable registration timestamp |
| `wallets` | Actual wallet, merchant and agent-account balances; exact decimal amounts and rolling 24-hour outgoing spend |
| `devices` | Stable sender-owned devices; documented example IP ranges |
| `wallet_transactions` | Settled P2P, merchant QR, cash-in and cash-out digital transfers |
| `scam_knowledge` | Ten reference typologies; none activates a safeguard |
| `scam_memory` | Actual analyst-approved cases in this scene; empty before approval |

`v_agent_ledger` is the joined projection. `GET /api/environment-data` previews records with evaluation labels and heuristic risk fields removed. The Environment tab has a collapsed **Generated data** panel showing current row counts.

## Export for the data/model team

```sh
uv run --locked python -B web/export_environment.py --steps 24 --scenario payment_burst --output output/environment-data
```

This creates a fresh isolated simulation and writes six NDJSON files, six BigQuery schema files, a joined-ledger preview and a manifest. It uses no Gemini or cloud calls. Exports stay under ignored `output/` because they contain private evaluation labels. Existing row/byte limits apply.

IDs use the dictionary's prefixes with 16 hex digits, are stable within a scene, and change for a fresh scene. References and uniqueness are validated. Decimal values are serialized as strings for BigQuery NUMERIC; timestamps are UTC. `risk_factors` contains valid JSON, while `key_red_flags` is an array.

Blocked/declined attempts remain in the operational ledger: the dictionary has no transaction-status column, so they must not appear as settled transfers. Only the digital leg of cash services is modeled. Current balances come from the full ledger, including older compatibility flows outside this export.

Scam truth comes from controlled fixtures, never customer wording. Heuristic scores use observed device, recipient and timing signals; they are not trained fraud probabilities. Exclude `is_fraud`, `scam_type`, `risk_score` and `risk_factors` from agent/model features. Date-only historical records cannot establish minute-level velocity. Fix and validate source data before training claims.

A recall request does not prove a refund or account freeze. `investigation_outcome` therefore stays null when none of the dictionary's supported outcome values is justified. `ANALYST_DEMO` identifies the synthetic review role; it does not impersonate a named investigator.

## BigQuery publishing

The destination is **`minttown-apac-2026.minttown_world` (US)**, enabled with `MINTTOWN_ENV_DATASET=minttown_world`. Gab's `minttown_simulated_env` is untouched. `web/environment_cloud.py` accepts only this isolated, app-owned dataset; mismatched ownership, schema or retention stops the load.

The world publishes before opening an investigation and after an analyst publishes a confirmed case. `POST /api/cloud/export` also publishes the current scene. Reads and individual payments never start an export. Six typed batch loads replace the current mirror, including clearing old memory on a new scene; a content-identical publication is a no-op. The existing seven-table versioned warehouse still supplies the current agent tools. The new tables are the AE/DS integration surface; this update does not silently change an agent's feature contract.

Each batch uses the **same 25/day allowance** as existing exports, with **20,000 rows / 16 MiB** maximum. A durable reservation precedes external work. Failed or ambiguous loads retain their allowance, block further publication and prevent a fresh scene until operator reconciliation. No automatic retry, streaming job or scheduler is added. Model budgets are unchanged.

Tables expire after seven inactive days; publication renews their expiration. `wallet_transactions` uses daily `timestamp` partitions, a required partition filter, and sender/receiver clustering. Historical synthetic partitions have no partition TTL. The joined view restricts its scan to the exported simulation window. [Google's location guidance](https://docs.cloud.google.com/bigquery/docs/locations#load-cloud-storage-data-into-bigquery) permits the existing Iowa bucket with the US dataset without cross-location load charges; ordinary storage and request costs still apply.

**The six loads are not atomic across tables.** `GET /api/environment-data` exposes `publication.latest.status`, job IDs and an archive prefix. Consume a completed batch; freeze its immutable `exports/environment/<batch-id>/` NDJSON files and manifest for training/evaluation. These private objects expire after seven days. Raw BigQuery tables and `v_agent_ledger` contain evaluation labels and must not be attached directly to an agent as unrestricted SQL tools. App previews exclude those fields; they do not constitute an IAM boundary for teammates with warehouse access.

If a batch is uncertain, inspect its recorded BigQuery job IDs in location `US` and the GCS manifest. Do not delete its receipt, reset quotas or blindly submit the loads again. A missing/failed job requires an explicit operator repair; only a verified six-table batch can be marked completed. Do not run Gab's truncating ingestion script against shared data to publish a demo.
