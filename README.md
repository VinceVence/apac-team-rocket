# Pallet Town

A synthetic Philippine fintech environment with a **real Gemini investigation loop**. Customers transact, complaints arrive, customer features are published to BigQuery, and the agent chooses tools before proposing a resolution. An analyst controls approval and memory publication.

The app has three tabs: **Environment**, **Agent activity**, and **Agents**. Active simulation and warehouse exports are capped at **100 customers**. Historical records from the earlier prototype remain in the ledger.

[Open the public saved-case demo](https://minttown-1040017899050.us-central1.run.app/). New Gemini calls are disabled on this release. See [hosting and cost protection](docs/hosting.md) and the [three-minute demo script](docs/demo-script.md).

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

1. **Environment:** customers make purchases and transfers. Two scenario types appear per bounded episode, rotating through five families.
2. **Agent activity:** Gemini reads the complaint and chooses ledger, BigQuery, pattern, model, memory, and Philippine guidance tools. It can ask a follow-up question or stop when evidence or budget is insufficient.
3. **Analyst review:** inspect the recommendation and proposed lesson. Only an analyst can approve and publish it.
4. A later transfer to that approved recipient is held before settlement. The receipt cites the reviewed memory and needs no model call.

All identities, transactions, complaints, recalls and holds are synthetic. The optional CPU model detects unusual behavior; it is not a validated fraud classifier. The broader prevention-learning agent is a researched extension, not an already-deployed autonomous agent.

## Limits

**$0.10 per UTC day · $0.02 per case · $1 lifetime · 30 model calls/day · six/case · five new reports/day.** No automatic model retries, fallback upgrades, or unbounded agent loops. Local and hosted execution share the same durable ledger.

BigQuery is bounded to three publications/day, 20,000 rows and 16 MiB per publication, 20 queries/day, and 50 MiB per query. The project's 1 GiB/day query quota remains. Typed tables expire seven days after provisioning; historical event-date partitions are retained within that table lifetime. Cloud Run serves the public saved-case demo; the shared-ledger local process is stopped. Cloud infrastructure remains metered; the [$8 shutdown trigger](docs/hosting.md) is additional protection, not a guaranteed $10 final-bill ceiling.

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
