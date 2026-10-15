# Local operation and cost controls

The live development workflow is a local Python application calling Vertex AI and BigQuery in `minttown-apac-2026`. The current [public hosted release](hosting.md) supports live Gemini investigations under the shared budget. Cloud Run must be paused with manual scaling zero before using the shared ledger locally. No GPU, model fine-tuning, streaming ingestion or scheduler is required.

## Credentials and startup

Use locally configured Application Default Credentials with access to the dedicated project. Never put tokens or API keys in browser files, `.env.example`, reports, or Git. The existing owner's configuration is stored in ignored `web/.env.vertex` and `output/google-cloud/`; teammates configure their own credentials and approved IAM access.

```sh
set -a
source web/.env.vertex
set +a
uv run --locked python -B web/local_vertex.py --live --port=3000
```

The launcher checks that Cloud Run is paused and has no tagged serving revisions, restores `state/minttown.sqlite3.gz`, refuses a missing ledger, provisions the seven typed BigQuery tables and binds to `127.0.0.1`. It enables inference only inside this explicit live process. The saved `.env.vertex` switches remain off.

ADC inherits the account's access. Project pinning in this launcher is an application control, not an IAM restriction on the credential itself. No new service-account key is needed.

## Shared controls

| Resource | Limit |
|---|---|
| Gemini | $2/UTC day; $0.05/case; $8 lifetime model spend |
| Generations | 100/day; six/case shared by resolution, follow-ups and prevention learning |
| Concurrency | One active agent job, one queued; one live request in flight |
| Retry | One SDK attempt; no automatic provider retry or upgrade |
| Pacing | At least six seconds between live requests |
| Simulation admission | 25 new reports and 25 fresh simulation scenes/day; guided complaints/starts exempt; 1,500 writes/day; 600 live world steps/day |
| BigQuery publication | 25/day shared across legacy export, evidence snapshots and the `minttown_world` mirror; 20,000 rows and 16 MiB each |
| BigQuery queries | 100/day; maximum 50 MiB per query; project quota 1 GiB/day |
| Local training | At most two new behavior models/day; bounded CPU iterations |
| Risk research | 2 studies/day, 2 calls and $0.02/study, 3 CPU fits/study; shared global model budget |
| Storage | 64 MiB checkpoint; typed tables expire after seven days; staged exports expire after seven days |

The one-cent model reservation is persisted before a paid request. Token usage reconciles it afterward; an uncertain response retains the reservation. A model failure opens a durable circuit. Canonical GCS checkpoints are spaced to avoid write bursts; failed or unconfirmed writes still fence the writer instead of retrying. Restarting or replying to a case does not reset allowance. Do not delete the database, replace the cloud object, or clear counters to continue a demo.

BigQuery reads poll the same submitted job within a bound. They do not create retry jobs. Failed or uncertain publications retain their allowance. Partial warehouse publications are not exposed as a completed snapshot; they need operator reconciliation before reuse.

The $8/month Vertex and $5/month Cloud Run spend-cap budgets are configured alongside a $20 cumulative project budget and the $16 shutdown trigger. These and the app ledger are different controls; cloud billing delays and unrelated resource usage prevent an account-wide guarantee. Local execution avoids Cloud Run compute, not Vertex, BigQuery, or Storage charges.

## Hosted service

To pause the existing service:

```sh
gcloud run services update minttown --project=minttown-apac-2026 --region=us-central1 --scaling=0
```

Do not resume Cloud Run while the local process owns the shared ledger. Shut down the local server cleanly first. The hosted image includes the new warehouse workflow and is public with live inference enabled and scoped prediction permission. See [hosting](hosting.md) for team permissions, the cumulative project budget and shutdown controls. The product rename does not rename cloud resources.

## Evaluation

Run offline contracts with `web/evaluate_cases.py --mode fake`. This uses an isolated temporary fake ledger and no paid model. For the actual world and Vertex path, run:

```sh
uv run --locked python -B web/evaluate_cases.py --mode gemini --world --run-id=YOUR_UNIQUE_RUN_ID
```

This stages three distinct synthetic complaints and lets Run world produce the other two. It does not approve cases, publish memories, refund funds or increase any limit. Inspect saved outcomes before another live run. Read [evaluation](evaluation.md) for the measured results and remaining coverage gaps.

## Fresh scenes and prevention

`Run world` archives the current synthetic database before replacing its scene. Hosted archives are private GCS objects under `archives/` with seven-day deletion rules; local archives live beside the database. Interactive scenes start with zero transactions; seeded history is available only in offline fixtures. Old cases, memories and active safeguards are cleared from the active scene, but model charges, call counts, daily admissions, warehouse usage, cooldown and the failure circuit remain in the canonical checkpoint. A reset is refused while an agent job is pending. An uncertain cloud checkpoint fences further writes.

Resolution and prevention share the same worker, meter and six-call case allowance. Guided resolution has a hard five-call ceiling, reserving the sixth shared case call for prevention. The model also sees only useful tools: an empty knowledge search and completed one-time checks are not offered. If no allowance remains, the learner stops; approval never creates a new budget. The learner cannot activate its own rule. Human activation requires a passed replay, the current feature schema, an unchanged approved source and an unexpired rule. Rules expire after seven days and can be disabled immediately.

The payment gate is local code: it only uses signals available before debit, ignores future complaints and scenario labels, and makes no model call. A general match requests verification, rather than declaring legal fault. The fake suite verifies routing and accounting contracts; replay controls are synthetic checks, not measured production fraud accuracy.

Research examples, frozen studies, candidate artifacts and research-call receipts survive fresh scenes. Public case reviews do not automatically curate training data. Research writes require `MINTTOWN_RISK_OPERATOR_TOKEN`; see [risk-lab.md](risk-lab.md). Research results never change the active payment gate.

Do not roll back to a release whose spend meter predates `risk_agent_turns` after paid research has run. Use a compatible release or reconcile those receipts into the rollback version’s durable accounting first.

## Demo Fraud Analyst

In **Agent activity → Fraud Analyst**, **Auto-approve demo** replaces the two manual approvals for one completed, current-world synthetic case. It records an explicit demo assumption, uses the normal review judges, and runs prevention through the existing shared meter. Only a replay-passed, unchanged safeguard is activated. Missing evidence, manual handoffs, submitted reports and validation failures remain blocked. Duplicate clicks and restarts never retry learning. Normal manual review and revocation remain available; this shortcut does not claim real human verification.

## Evidence and shared analytics batches

Case intake no longer requires a new BigQuery export. A completed publication is reusable only when its payload exactly matches the current export and is less than seven days old. Otherwise, the investigator receives fresh, immutable ledger features with an explicit `Simulation ledger` / `analytics_sync: deferred` receipt. Features stop at the last reported transaction timestamp, exclude labels and demographics, and survive in the normal generation-checked GCS checkpoint. A cache receipt is not a claim that a new BigQuery query ran.

The first report triggers a shared warehouse + six-table AE batch; the next batch waits for five additional reports. Both publications still count against the existing 25/day allowance, and both slots must be available before starting a new pair. Uncertain loads are not retried. Reviews and revocations apply locally and durably immediately; their analytics copies wait for the next batch or an explicit export. When the publication quota is exhausted, investigation continues from valid ledger evidence while analytics remains deferred. A new intake after allowance returns can flush the backlog. Missing transactions or a failed canonical checkpoint still stop work.

For a report blocked before any investigation began, **Prepare & investigate** explicitly freezes its saved evidence and starts its first investigation. This does not retry a failed model or grant new allowance. Existing completed cases retain their original traces.

## Restarting the simulation

**Restart** beside Run demo asks before archiving the current scene and starting an empty continuous world. Cases, lessons and active safeguards move into the recoverable private scene archive. Spend, daily allowances and the failure circuit remain unchanged. In-flight agent/evidence work must finish first; exhausted world-step allowance cannot be reset this way. Duplicate or stale restart requests do not archive the next scene.

Prevention replay counts show matched/source variants, including partial coverage. In the October 15 isolated gateway check of five newly approved Gemini rules, nine of ten changed-recipient transactions were held, all five legitimate payments settled, and no model was called for payment checks. The smaller investment-fee variant escaped a rule requiring a large amount. This is a synthetic diagnostic, not measured real-world fraud accuracy; no model was retried or rule retuned to conceal the miss.

## Visible agent decisions

In Run demo, **Next** from the report admits the investigation exactly once. The decision map uses native tool receipts: chosen tool, the agent's public purpose, returned evidence, uncertainty and the next recorded choice. Pending requests have no invented result. Replays and manual handoffs are labeled; private reasoning is not exposed. Next/Back retain the reader's position while new receipts arrive. Run simulation still investigates automatically. Rendering and explanations make no additional model calls.

Guided demo starts and their one server-created scam complaint are exempt from simulation report/start quotas. New Gemini calls still use the shared dollar/call meter. Continuous simulation and user-submitted reports retain admission limits; daily writes, live world steps and analytics still have bounds. No counter is cleared. Live admission failures offer the recorded path through Next instead of leaving the walkthrough waiting.

The **Run demo button itself is never quota-blocked**. If a live scene cannot start, it opens the labelled recorded Gemini replay in the browser. Next reveals ordinary payments, the actual disputed transfer, saved tool receipts, the recorded demo analyst review, its approved lesson, and a changed-recipient gateway check with zero debit and a settled legitimate control. The recording is synthetic case `SC-89f16ba52e` from October 15, 2026; the gateway proof was replayed in an isolated ledger using its exact approved rule. It makes no API mutations or new model calls, cannot approve current cases, and returns to the unchanged world on exit. Do not present playback as fresh Gemini inference.

October 15 local verification: case `SC-0d6adcff67` generated 13 transactions and a PHP900 reported transfer. Gemini called `get_case_evidence`, `score_models`, then `submit_case_resolution`; the third call failed the citation contract. Three calls cost $0.002677; no retry or approval occurred. Next offered the recorded case, which completed review → knowledge → changed-recipient protection in the browser without new spend. This demonstrates a working local Vertex connection and a rejected draft, not successful live resolution of that case. Simulation and model limits were preserved; Cloud Run was paused for the local shared-ledger owner.

## Competition comparison

`uv run --locked python -B web/evaluate_upgrade.py --mode fake` runs the 24 investigation contracts and 100 paired ledger attempts locally, with provider construction blocked. It updates the saved UI summary. The scientist also supports `design_ablation`; both research generations and all CPU fits keep their existing limits. See [results](competition-upgrades.md).

The explicitly authorized live mode is `uv run --locked python -B web/evaluate_upgrade.py --mode gemini --output output/upgrades/live-comparison.json --max-cases 12`. Supply `MINTTOWN_RISK_OPERATOR_TOKEN` through the local environment, never a command argument or commit. Pause the world first. The command uses the hosted shared worker and meter; do not run a second local shared-state writer. It reserves 20 calls for demos, at most 12 new runs per UTC day, and saves attempted cases for explicit resumption. HTTP uncertainty stops for reconciliation; it does not retry an investigation. Reuse the same output file across days. No live comparison was run by the upgrade verification.

New feature queries share the 100/day and 50 MiB/query limits. Only covered transactions in the latest completed AE publication are queried. Frozen values and query provenance stay with the case. No extra export is forced when quota is exhausted.
