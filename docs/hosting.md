# Public demo and cost protection

Public URL: https://minttown-1040017899050.us-central1.run.app/

This release serves the saved Pallet Town investigations. New Gemini calls are disabled by all three live flags, and the public runtime service account has no Vertex prediction permission. The environment, saved evidence, analyst review and simulated prevention remain available. Any newly generated offline investigation is labelled as fake; saved Gemini traces retain their original provider and usage.

The Vertex API is also disabled following the shutdown test. Re-enabling it requires an owner to review the budget first.

The local shared-ledger process must remain stopped while Cloud Run serves this database. The cloud deployment keeps one maximum instance, zero minimum instances and the existing global request, report, warehouse and model limits. All data is synthetic. Public visitors share the same demo, including case approvals; do not enter real customer information.

## Cost controls

- Existing native spend caps remain **$1/month for Vertex AI** and **$1/month for Cloud Run**, scoped to this project. These can stop the demo before the project-wide guard triggers.
- The application retains **$0.10/UTC day, $0.02/case, $1 lifetime, six calls/case**, and no automatic model retries.
- A separate **$10 cumulative project budget**, starting October 1, 2026 with no end date, sends budget messages to `pallet-cost-guard`. It does not reset each month and excludes credits from cost calculations.
- Eventarc delivers those messages to the `pallet-cost-guard` workflow. At **$8 reported cost**, the workflow requests that Vertex AI be disabled and the `minttown` Cloud Run service be paused with manual scaling zero.
- The workflow checks the exact budget ID, billing account, schema, USD currency and configured amount. Its service account has the required shutdown permissions, including permission to act as this demo's runtime account when pausing Cloud Run. It cannot enable services or modify billing. It has no model calls or repeated shutdown submissions; status polling is bounded to 15 reads of the same operation.

The workflow source is [deploy/cost-guard.yaml](../deploy/cost-guard.yaml). It disables the Vertex API and pauses the demo; it does not delete datasets, model artifacts, or the project. Existing fixed resources and unrelated services can still incur charges. Budget notifications and native caps can be delayed, and in-flight usage can finish. **These controls cannot guarantee an absolute $10 final bill.** The $8 trigger provides headroom, not a prepaid balance.

Google references: [native spend caps](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps), [budget notification format](https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications), and [service disabling](https://docs.cloud.google.com/service-usage/docs/reference/rest/v1/services/disable).

## Team development

Gab and Jansen use their supplied Google accounts. Their scoped access covers Cloud Run development, the existing BigQuery dataset and query jobs, the existing container repository, logs, and Vertex prediction. They can act as the app runtime service account to deploy containers. Billing administration, IAM administration, service enablement, Vertex training/endpoint creation and Cloud Build job creation are not granted.

Build containers locally and push them to the existing Artifact Registry repository. Use your own Google credentials. Never copy the owner's ADC file or put credentials in source control. Enabling live inference or restoring Vertex after a shutdown is an owner operation; it requires reviewing both the cumulative budget and the app's existing spend ledger.

Detailed deployment, IAM and shutdown-test receipts remain in ignored `output/google-cloud/`. The saved-case walkthrough is [demo-script.md](demo-script.md).

## Verified shutdown behavior

On October 13, 2026, below-threshold and unrelated-budget messages were checked, followed by a synthetic $8 message sent through the real Pub/Sub → Eventarc → Workflows path. The completed test confirmed `aiplatform.googleapis.com` was `DISABLED` and the demo was at manual scaling zero. This was a control test, not a claim that spending had reached $8. The demo was then reopened with Vertex still disabled.

The test exposed an oversized Service Usage metadata response and missing shutdown-status permissions. The final workflow requests only the response fields it needs and confirms the shutdown operations before reporting success. Failed test receipts remain available alongside the successful receipt.
