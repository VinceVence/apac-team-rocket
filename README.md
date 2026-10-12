# MintTown

A local fintech simulation and fraud-resolution workbench. Residents transact in a pixel town; a customer report opens an investigation, an analyst reviews the findings, and approved cases become retrievable memory.

The investigation uses **Google ADK 2.11.0** with native function calls. **Live Gemini is off.** The default model is an explicitly labeled fake used to demonstrate and test branching, follow-up questions and budget enforcement. These tests establish the execution contract, not live AI accuracy.

## Run locally

Use Python 3.12.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r web/requirements-google.txt
MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0 .venv/bin/python -B web/server.py
```

Open http://localhost:3000. The UI has two channels: **Town** and **Scam desk**. DM Sans, the mint palette and original canvas pixel art are self-hosted.

## Demo

1. Start a scam demo from the town, then choose **Investigate**. A server worker runs the investigation; the browser only reads its progress.
2. Inspect the ADK tool trail and submit an analyst review with a saved lesson.
3. Create a **Similar report**. The fake model chooses memory retrieval first, verifies the transfer and asks a targeted question.
4. Answer the question. The worker resumes automatically, the same case budget survives, and the investigation proposes a resolution for review.
5. Use **More scenarios** for a benign payment. It takes a shorter tool path when daily allowance remains.

All transfers, recall requests and customer messages are simulated. No real money is moved. Only the operator can approve a case or publish memory.

## Programmatic verification

```sh
.venv/bin/python -B -m unittest discover -s web -p 'test_*.py'
.venv/bin/python -B web/simulate_adk.py
```

The HTTP rehearsal uses a temporary database, exercises the actual ADK runner and function tools, and forbids constructing a Gemini client. Its JSON report is written under `web/reports/`.

The first and second cases consume 5 + 5 simulated generations under the default 10-call daily allowance. The rehearsal proves the next case stops before making a model call, then uses a separate temporary database for the benign comparison. It never clears the saved application's ledger.

## Automatic execution and evidence

`POST /api/fraud-agent/start` queues automatic execution by default and returns HTTP 202 while queued/running. Repeating it reuses the same run. `automatic: false` retains manual stepping for diagnostics. Replies to automatic cases resume the worker. The worker pauses for a customer, analyst review, a cost/call limit, or an error. One worker runs at a time; refreshes and closed browser tabs do not cancel it. Restarted queued/in-flight cases require analyst attention and retain reservations instead of silently retrying.

Each investigation stores an immutable `fraud_evidence_snapshots` row: reported transfers, up to 60 prior payments within 30 days, up to 10 related transfers per recipient, and the latest 100 eligible reviewed memories. Retrieval returns at most 3 matching memories. Copies, capture time, simulator date, event watermark and a content hash preserve what was available, including when later transactions are backdated or history changes. Changes to the reported transfers still block automatic submission and analyst approval. A reply captures a new revision; old observations are reused only if the evidence hash is unchanged, and spending never resets.

The case's decision trail spans revisions and shows the selected tool, public purpose, observed result, snapshot/source references, failure status and actual or simulated cost. It does not expose private model reasoning.

## Budget controls

- Up to **6 model generations per case**, including follow-ups and re-investigations.
- **$0.02 per case**, **$0.10 per UTC day**, **$1 lifetime** and **10 calls per UTC day** by default.
- Reserve **$0.01 before a generation**, then reconcile reported input, output and reasoning tokens. Ambiguous failures retain their reservation.
- Fake calls use a separate simulated-spend ledger; actual API cost remains zero. The HTTP rehearsal raises only its isolated fake call-count allowance to exercise all examples.
- Invalid tools, out-of-scope accounts, fabricated citations, stale evidence and repeated requests cannot bypass the server checks. A stopped run can be handed to the analyst explicitly.

The local application assumes one server process owns its SQLite database. A distributed deployment needs database-level atomic reservations across service instances.

These are application admission limits, not an account-wide billing ceiling. Keep the database: deleting it resets the local spend history. Other scripts and direct Cloud Console calls do not pass through this ledger.

For Vertex AI, also configure a Google Cloud **spend cap enforcement** budget scoped to one dedicated project and `aiplatform.googleapis.com`. The current MintTown setup uses a **$1 monthly** cap, with notifications at 50%, 80% and 100%. Google pauses new eligible usage when the estimated threshold is reached, but reporting delays and in-flight requests can produce overages. The cap resets each month and does not cover unrelated services or persistent infrastructure charges. See [Google's spend-cap documentation](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps). Keep live calls off until the console shows the cap as **Configured** and authentication is ready.

## Gemini integration

The guarded Vertex AI adapter targets `gemini-3.5-flash-lite`. It remains disabled unless the server is explicitly configured with **both** `MINTTOWN_LIVE=1` and `MINTTOWN_FRAUD_LIVE=1`, a `GOOGLE_CLOUD_PROJECT`, supported `GOOGLE_CLOUD_LOCATION` (default `global`), and Application Default Credentials. The UI currently creates fake-mode investigations. No credentials belong in browser code or committed files.

Live model behavior, endpoint access and real token consumption still require an explicitly enabled evaluation. No fine-tuning, external MCP service or paid cloud deployment is required for the local demo.

Local Vertex setup uses an ignored `web/.env.vertex` file and an isolated Cloud SDK/credential directory under ignored `output/google-cloud/`. From the repository root, load the local file with `set -a; source web/.env.vertex; set +a` before starting the server. Both live switches remain `0`; loading the file never enables inference. User ADC inherits the signed-in user's Cloud permissions; it is not an IAM boundary for just this project. Use a dedicated service identity with inference-only permissions for deployment.

See [the investigation implementation](web/fraud_agent.py), [ADK adapter and fake model](web/fraud_adk.py), and [tests](web/test_fraud_agent.py).

## Hosted team demo

[deploy/plan.json](deploy/plan.json) specifies the proposed Cloud Run, Cloud Storage and BigQuery controls. The container serves the same UI and API. Hosted mode forces Gemini off regardless of environment flags, and its runtime service account should have no Vertex inference permission. Browser access uses IAP with explicitly granted Google accounts; this project has no organization, so its first IAP OAuth setup uses the Cloud Console.

For this small, single-worker demo, committed SQLite state is checkpointed to one Cloud Storage object using generation preconditions. Cold starts restore reports, snapshots, memory and budget history. Conflicts and uncertain writes fence the instance instead of overwriting another writer; a liveness probe restarts it. The database is capped at 64 MiB. This checkpoint design has a single-writer ceiling; move operational state to a transactional managed database before scaling instances or enabling cloud inference.

The hosted town has an explicit **Export simulator data** action. It loads one atomic BigQuery batch containing records from `customers`, `accounts`, `financial_events` and `ledger_entries`, with batch IDs and source-table names. Exports are limited to 3 per UTC day, 20,000 records and 16 MiB each. Failed/uncertain submissions retain their allowance and job IDs. The application issues no analytical query jobs. BigQuery partitions and staged exports retain 7 days of data; the live state object is retained and overwritten without object version history.

Cloud Run uses one instance, one CPU, 1 GiB memory, no minimum instances, instance-based billing for the background worker, and a $1 monthly spend cap. Whole-project $5 alerts include other services but are not an overall hard cap. Google enforcement delays can cause overages. Cloud Build is bounded to a 600-second build. Credential/config/data/report directories are excluded by the explicit `.gcloudignore` and `.dockerignore` upload allowlists.
