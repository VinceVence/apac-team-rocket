# Local operation and cost controls

The live development workflow is a local Python application calling Vertex AI and BigQuery in `minttown-apac-2026`. The current [public hosted release](hosting.md) serves saved cases with new Gemini calls disabled. Cloud Run must be paused with manual scaling zero before using the shared ledger locally. No GPU, model fine-tuning, streaming ingestion or scheduler is required.

## Credentials and startup

Use locally configured Application Default Credentials with access to the dedicated project. Never put tokens or API keys in browser files, `.env.example`, reports, or Git. The existing owner's configuration is stored in ignored `web/.env.vertex` and `output/google-cloud/`; teammates configure their own credentials and approved IAM access.

```sh
set -a
source web/.env.vertex
set +a
.venv/bin/python -B web/local_vertex.py --live --port=3000
```

The launcher checks that Cloud Run is paused and has no tagged serving revisions, restores `state/minttown.sqlite3.gz`, refuses a missing ledger, provisions the seven typed BigQuery tables and binds to `127.0.0.1`. It enables inference only inside this explicit live process. The saved `.env.vertex` switches remain off.

ADC inherits the account's access. Project pinning in this launcher is an application control, not an IAM restriction on the credential itself. No new service-account key is needed.

## Shared controls

| Resource | Limit |
|---|---|
| Gemini | $0.10/UTC day; $0.02/case; $1 lifetime |
| Generations | 30/day; six/case including follow-ups |
| Concurrency | One active investigation, one queued; one live request in flight |
| Retry | One SDK attempt; no automatic provider retry or upgrade |
| Pacing | At least six seconds between live requests |
| Case admission | Five new reports/day; 600 writes/day; 240 world steps/day |
| BigQuery publication | Three/day, shared with legacy export; 20,000 rows and 16 MiB each |
| BigQuery queries | 20/day; maximum 50 MiB per query; project quota 1 GiB/day |
| Local training | At most two new behavior models/day; bounded CPU iterations |
| Storage | 64 MiB checkpoint; typed tables expire after seven days; staged exports expire after seven days |

The one-cent model reservation is persisted before a paid request. Token usage reconciles it afterward; an uncertain response retains the reservation. A model failure opens a durable circuit. Restarting or replying to a case does not reset allowance. Do not delete the database, replace the cloud object, or clear counters to continue a demo.

BigQuery reads poll the same submitted job within a bound. They do not create retry jobs. Failed or uncertain publications retain their allowance. Partial warehouse publications are not exposed as a completed snapshot; they need operator reconciliation before reuse.

The $1/month Vertex and Cloud Run spend-cap budgets remain configured, with the existing whole-project alerts. These and the app ledger are different controls; cloud billing delays and unrelated resource usage prevent an account-wide guarantee. Local execution avoids Cloud Run compute, not Vertex, BigQuery, or Storage charges.

## Hosted service

To pause the existing service:

```sh
gcloud run services update minttown --project=minttown-apac-2026 --region=us-central1 --scaling=0
```

Do not resume Cloud Run while the local process owns the shared ledger. Shut down the local server cleanly first. The hosted image includes the new warehouse workflow and is public with all live-inference flags off. See [hosting](hosting.md) for team permissions, the cumulative project budget and shutdown controls. The product rename does not rename cloud resources.

## Evaluation

Run offline contracts with `web/evaluate_cases.py --mode fake`. This uses an isolated temporary fake ledger and no paid model. For the actual world and Vertex path, run:

```sh
.venv/bin/python -B web/evaluate_cases.py --mode gemini --world --run-id=YOUR_UNIQUE_RUN_ID
```

This stages three distinct synthetic complaints and lets Run world produce the other two. It does not approve cases, publish memories, refund funds or increase any limit. Inspect saved outcomes before another live run. Read [evaluation](evaluation.md) for the measured results and remaining coverage gaps.
