# Operation and cost controls

The hosted demo uses one Cloud Run instance and a generation-checked SQLite checkpoint in Cloud Storage. All data is synthetic. Public visitors share the same world; do not enter real customer information. Local offline work uses a separate temporary database. Never run a local writer against the hosted shared ledger at the same time as Cloud Run.

## Start offline

```sh
uv sync --locked
MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0 uv run --locked python -B web/server.py
```

The server does not automatically load `.env` files. Use Python 3.12. The UI is static and requires no Node build. New interactive worlds have 100 residents and no historical transactions. Opening balances are not transactions.

## Authorized local Vertex work

Use your own ADC and the dedicated `minttown-apac-2026` project. Credentials and the owner's ignored configuration must never be copied to teammates, committed or exposed through the UI.

Only after the owner authorizes a live run and Cloud Run has been paused at **manual scaling zero**, configure the project/ADC locally and run:

```sh
uv run --locked python -B web/local_vertex.py --live --port=3000
```

The launcher verifies the hosted service is paused and has no tagged serving revisions. It restores the existing shared ledger, refuses a missing ledger, provisions the warehouse schema, and binds to loopback. It does not create a fresh paid allowance or retry a failed request. ADC retains its account permissions; application project pinning does not restrict the credential itself.

## Shared controls

| Resource | Enforced application bound |
|---|---|
| Model spend | $2/UTC day, $0.05/case, $8 lifetime model spend |
| Case generations | Six total, including follow-ups, one optional specialist and prevention; reserve synthesis and prevention room |
| Concurrency and retries | One worker plus one queued job, one paid call in flight, six-second spacing, one SDK attempt, no automatic retries |
| Request envelope | 16,000 input bytes including declarations; 512 output tokens; one-cent durable reservation before a call |
| Simulation | 100 residents; renewable 15-minute run lease |
| HTTP | 600 API reads/minute, 60 mutations/minute; bounded request bodies and incomplete-upload timeout |
| BigQuery | At most 20,000 rows / 16 MiB per publication and 50 MiB per query; project quotas also apply |
| Research | Legacy studies: two calls/$0.02; request studies: three calls/$0.03, at most three CPU fits and one refinement |
| Stored research | At most 20 studies and 4,000 curated rows; advisory registration is operator-only |
| Persistence | 64 MiB checkpoint; typed publications and staged exports expire after seven days |

Fixed daily call/report/start/export/query counts are telemetry, not admission gates. Leave `MINTTOWN_DAILY_CALLS` unset for spend-based admission. Explicit smaller limits remain supported for offline tests. Restart never replenishes dollars, admissions or the circuit.

The reservation precedes provider execution. Recorded token usage reconciles it; uncertain execution retains it and opens the circuit. A fully accounted invalid draft stops its own case. A missing/conflicting GCS checkpoint fences the writer. Do not clear these records to make a demo pass.

The **$20 project envelope is not a guaranteed bill ceiling**: billing reports and shutdown controls are delayed. Builds, BigQuery, storage and teammate training are outside the app's model-call meter. Existing project safeguards remain separate.

## Evidence, review and restart

The first report triggers a warehouse/AE batch, then each five additional reports can share another. A complete matching publication is reusable. Case features may use a bounded four-table BigQuery query whose rows and values match the pinned AE projection. Otherwise the agent gets immutable case-time ledger features with explicit deferred-sync provenance. Missing history stays missing; no future outcomes, hidden labels or demographic predictors are introduced. Unknown load/query outcomes are never resubmitted automatically.

Human review publishes a lesson. A separate approval activates only a replay-passed safeguard and playbook. Demo auto-approval is an explicitly labelled assumption for a completed synthetic case; blocked evidence and incomplete drafts cannot use it. Revocation removes future knowledge/safeguard use. Gateways check payments locally without an LLM call per payment.

Restart archives the current scene while retaining accounting, research and failure controls. It waits for active agent/publication work. A normal stop pauses payments and lets admitted investigations finish. Do not roll out another shared-ledger writer over an active investigation.

## Demo presentation and checks

**Run demo → Next** shows payments, the complaint, evidence preparation, actual selected tools, review, knowledge and a later payment. The scene stays scroll-locked and the reader controls advancement. Show public decision purposes and tool receipts, never private reasoning.

Run demo stays on the live Gemini case and never silently changes to playback. Watch saved demo is a separate, explicitly selected browser-only replay. It cannot approve current cases, write payments, or spend money. Exiting restores the unchanged real world. Never describe replay as fresh inference.

```sh
uv run --locked python -B -m unittest discover -s web -p 'test_*.py'
node --test web/test_*.mjs
uv run --locked python -B web/evaluate_harness.py
```

[Live evidence](visual-demo.md) · [Earlier measured failures](learning-evaluation.md) · [Hosting and team access](hosting.md)
