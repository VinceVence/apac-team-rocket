# Public demo and cost protection

Public URL: https://minttown-1040017899050.us-central1.run.app/

The public release supports real Gemini investigations. **Run simulation** generates synthetic transactions and reports; Gemini chooses tools, reads frozen case-time ledger evidence and proposes a resolution for analyst review. Analytics is mirrored to BigQuery in batches. Matching completed AE publications support bounded, parameterized four-table BigQuery aggregates, verified against canonical records. Otherwise the case uses frozen ledger features with explicit deferred-sync provenance. The runtime has only `aiplatform.endpoints.predict` for model access. The labelled recorded Gemini demo is available without new paid calls when live work cannot start.

The October 13 limit increase preserves all existing usage and case histories. Availability is shared across visitors; a new browser session or server restart does not replenish budgets.

The local shared-ledger process must remain stopped while Cloud Run serves this database. The cloud deployment keeps one maximum instance, zero minimum instances and the existing global request, report, warehouse and model limits. All data is synthetic. Public visitors share the same demo, including case approvals; do not enter real customer information.

Evaluation-period optimization: idle guided phases stop polling until a user action, while actual world/agent work continues refreshing. Background workers retain CPU allocation. Karlo's [ledger classifier](ledger-model.md) runs inside the existing service without another endpoint; its deployment script reuses image layers and preserves the single writer and all cost controls.

## Cost controls

- Native spend caps are **$8/month for Vertex AI** and **$5/month for Cloud Run**, scoped to this project. These can stop the demo before the project-wide guard triggers.
- The application retains **$2/UTC day, $0.05/case, $8 lifetime model spend, six calls/case**, and no automatic model retries.
- A separate **$20 cumulative project budget**, starting October 1, 2026 with no end date, sends budget messages to `pallet-cost-guard`. It does not reset each month and excludes credits from cost calculations.
- Eventarc delivers those messages to the `pallet-cost-guard` workflow. At **$16 reported cost**, the workflow requests that Vertex AI be disabled and the `minttown` Cloud Run service be paused with manual scaling zero.
- The workflow checks the exact budget ID, billing account, schema, USD currency and configured amount. Its service account has the required shutdown permissions, including permission to act as this demo's runtime account when pausing Cloud Run. It cannot enable services or modify billing. It has no model calls or repeated shutdown submissions; status polling is bounded to 15 reads of the same operation.

The workflow source is [deploy/cost-guard.yaml](../deploy/cost-guard.yaml). It disables the Vertex API and pauses the demo; it does not delete datasets, model artifacts, or the project. Existing fixed resources and unrelated services can still incur charges. Budget notifications and native caps can be delayed, and in-flight usage can finish. **These controls cannot guarantee an absolute $20 final bill.** The $16 trigger provides headroom, not a prepaid balance.

Google references: [native spend caps](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps), [budget notification format](https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications), and [service disabling](https://docs.cloud.google.com/service-usage/docs/reference/rest/v1/services/disable).

## Daily demo allowance

Model admission is spend-based; fixed daily call/report/start/publication/query counters are telemetry. Reads are limited to 600/minute and writes to 60/minute. Publications remain capped at 20,000 rows/16 MiB and queries at 50 MiB; Google Cloud project quotas also apply. A simulation lease lasts 15 minutes before requiring resume. One investigation runs and one may queue, with six-second paid-call spacing, one SDK attempt and no automatic retries. Unknown provider execution/usage opens the persistent circuit; fully accounted invalid drafts stop their own case. The browser-only recording makes no mutations or model calls.

## Team development

Gab and Jansen use their supplied Google accounts. Both retain scoped Cloud Run development, the existing BigQuery dataset and query jobs, the existing container repository, logs, and Vertex prediction, plus permission to act as the runtime service account.

On October 14, Gab's access was expanded: project-scoped BigQuery data/jobs/models and dataset/table access management, excluding reservations and capacity purchases; Cloud Build Editor; administration of the existing `minttown` Cloud Run service and container repository; permission to act as the existing runtime and builder accounts; build-prefix object management and bucket metadata/list access. The BigQuery permissions are in the custom `minttownBigQueryManager` role. Jansen's existing grants were unchanged.

On October 15, Karlo (`karlomfdp@gmail.com`) received Vertex AI User, BigQuery Job User, Service Usage Consumer and Logs Viewer in this project. He can read `minttown_simulated_env`, `minttown_world` and `minttown_demo`, and write training outputs to `minttown_models`. He can act as `minttown-training@minttown-apac-2026.iam.gserviceaccount.com`, which has scoped data and artifact access. Model artifacts use `gs://minttown-apac-2026-demo-state/models/`; container uploads use the existing `minttown` Artifact Registry repository. The checkpoint prefix is not granted. No training jobs or service-account keys were created.

On October 16, the owner explicitly expanded Karlo’s account to **BigQuery Admin** (`roles/bigquery.admin`) for `minttown-apac-2026`. He can now manage all project datasets and BQML models, including Gab’s source dataset. This supersedes the earlier read-only dataset scope; preserve AE data ownership in team workflows.

Karlo also has Cloud Build Editor, scoped access to the dedicated `minttown-apac-2026_cloudbuild` source/log bucket, and permission to use `minttown-builder@minttown-apac-2026.iam.gserviceaccount.com`. The staging bucket has seven-day object cleanup. Use that explicit build identity and log directory; no project-wide Storage Admin role was added.

Billing administration, project IAM administration and service enablement were not granted. Vertex AI User permits paid training and model resource operations outside the demo's model-call meter. The existing project budget/shutdown controls remain separate and delayed; they do not guarantee a hard total bill. Use your own Google credentials and stop idle training resources. Never copy the owner's ADC file or put credentials in source control. Enabling live inference or restoring Vertex after a shutdown is an owner operation; it requires reviewing both the cumulative budget and the app's existing spend ledger. GitHub collaborator invitations are separate and require verified GitHub usernames; email addresses alone do not confirm repository access.

Detailed deployment, IAM and shutdown-test receipts remain in ignored `output/google-cloud/`. The guided and saved-result walkthrough is [demo-script.md](demo-script.md).

## Verified shutdown behavior

On October 13, 2026, below-threshold and unrelated-budget messages were checked, followed by a synthetic $8 message sent through the real Pub/Sub → Eventarc → Workflows path. The completed test confirmed `aiplatform.googleapis.com` was `DISABLED` and the demo was at manual scaling zero. This was a control test, not a claim that spending had reached $8. The demo was then reopened with Vertex still disabled. The owner subsequently authorized live inference and a $20 project envelope; the same budget IDs and cumulative period were retained, with the shutdown threshold raised to $16.

The test exposed an oversized Service Usage metadata response and missing shutdown-status permissions. The final workflow requests only the response fields it needs and confirms the shutdown operations before reporting success. Failed test receipts remain available alongside the successful receipt.

## Guided public demo

Every **Run new world** privately archives the previous synthetic scene and resets its visible cases and policies. Durable cost history and all daily counters remain. Private scene archives expire after seven days. The site shares one synthetic analyst workspace: visitors can approve demo cases and activate replay-passed rules, but cannot call real bank actions.

The resolution and prevention agents share the existing six-call case ceiling and single-worker queue. Prevention gets at most one remaining call after an approved case. Later payment checks are local and consume no Gemini calls. Model choice, versions, validated tool arguments, public purposes and results are visible in **Agent activity**.
