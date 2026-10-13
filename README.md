# Pallet Town

A synthetic Philippine fintech environment with a **real Gemini investigation loop**. Customers transact, complaints arrive, customer features are published to BigQuery, and the agent chooses tools before proposing a resolution. An analyst controls approval and memory publication.

The app has three tabs: **Environment**, **Agent activity**, and **Agents**. Active simulation and warehouse exports are capped at **100 customers**. Every new world starts a fresh scene with seeded customer history; prior cases are privately archived and spending remains counted.

[Open the public live demo](https://minttown-1040017899050.us-central1.run.app/). Gemini investigations are enabled within the shared budget. See [hosting and cost protection](docs/hosting.md) and the [three-minute demo script](docs/demo-script.md).

## Start locally

Use Python 3.12 and install `web/requirements-google.txt` in `.venv`.

For an offline preview:

```sh
MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0 .venv/bin/python -B web/server.py
```

For live Vertex AI, load your ignored local credential configuration and start the guarded launcher:

```sh
set -a
source web/.env.vertex
set +a
.venv/bin/python -B web/local_vertex.py --live
```

Open **http://localhost:3000/** and choose **Run world**. The live launcher requires Cloud Run to be disabled with manual scaling zero, restores the existing shared spend ledger, provisions the bounded warehouse, and binds only to loopback. It refuses to create a fresh paid ledger. See [operations](docs/operations.md) for authentication and hosting controls.

## Demo

1. **Run world:** a fresh scene starts. Customers transact, a victim gets an orange **!**, and a complaint is filed automatically. The world pauses so judges can follow the case.
2. **Agent activity:** Gemini selects validated evidence and detector tools. Device integrity can look normal while the payment-request detector finds a scam signal. The timeline shows each call, public purpose, model version and result.
3. **Analyst review:** inspect the resolution, uncertainty and lesson, then **Approve & learn**. Only the human review publishes knowledge.
4. **Prevention agent:** one remaining case call proposes a narrow safeguard or declines. The app replays the changed-recipient attempt and 20 legitimate controls. Inspect the results, then **Enable safeguard**.
5. **Test a similar payment:** the new recipient is held before debit while a normal payment passes, with **zero additional Gemini calls**. **Run new world** archives this scene and starts over without resetting limits.

All identities, payments and bank actions are synthetic. Registered detectors are versioned rules, not calibrated fraud probabilities. The optional CPU model is unsupervised anomaly detection. The prevention check runs inside this simulator's payment gateway; a device-edge deployment is future work.

## Limits

**$2 per UTC day · $0.05 per case · $8 lifetime model spend · 100 model calls/day · six/case shared by both agents · 25 new reports/day.** No automatic model retries, fallback upgrades, or unbounded agent loops. Local and hosted execution share the same durable ledger.

BigQuery is bounded to 25 publications/day, 20,000 rows and 16 MiB per publication, 100 queries/day, and 50 MiB per query. The project's 1 GiB/day query quota remains. Typed tables expire seven days after provisioning; historical event-date partitions are retained within that table lifetime. Cloud Run serves the public live demo; the shared-ledger local process is stopped. Cloud infrastructure remains metered; the [$16 shutdown trigger](docs/hosting.md) is additional protection, not a guaranteed $20 final-bill ceiling.

## Help and verification

- [Help index](docs/README.md)
- [Architecture and seven-table data model](docs/architecture.md)
- [Agent roles and extension guide](docs/agents.md)
- [Operations and cost controls](docs/operations.md)
- [Research and Philippine complaint workflow](docs/research.md)
- [Evaluation results and limitations](docs/evaluation.md)

```sh
.venv/bin/python -B -m unittest discover -s web -p 'test_*.py'
.venv/bin/python -B web/evaluate_cases.py --mode fake
.venv/bin/python -B web/evaluate_cases.py --mode gemini --world --run-id=YOUR_UNIQUE_RUN_ID
```

The fake suite uses injected expected decisions to test execution contracts; it is not an AI-accuracy evaluation. The live command consumes the shared allowance. Detailed synthetic receipts stay under ignored `web/reports/`; source-controlled summaries contain no credentials.
