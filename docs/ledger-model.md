# AE ledger model as an investigation tool

Karlo's `feature/custom-fraud-classifier` contribution (source `4858404`) is integrated into the current harness, without replacing the newer demo UI. His CPU gradient-boosted tree approach remains; export, feature timing, evaluation and deployment have been hardened.

## Flow

AE `minttown_simulated_env` → capped read-only export → one local CPU fit → data-only JSON artifact → Gemini selects `score_models` → immutable model receipt → analyst review.

`ledger_transaction_v1` version 2 uses `ledger-features-v2`: amount, payment type, channel, UTC hour, strictly earlier one-hour count, 24-hour spend, 30-day mean and count. Customer IDs define training scope; they are not predictor inputs. Mutable wallet balances/status, customer risk tiers, device trust proxies, demographics and label-derived risk fields are excluded. `is_fraud` is an offline target only.

New cases freeze these values from canonical transaction history inside the evidence snapshot. Inference never re-reads changing tables, makes a BigQuery query or calls an external endpoint. The model returns a version, artifact hash, input hash, scoped event IDs and limitations through the existing tool. Old snapshots lacking this contract return unavailable; they are not backfilled. These are case-time ledger observations, not a claim that a new BigQuery inference query ran.

## Measured result

One read-only BigQuery job exported **2,031 transactions / 100 customers**, scanning 8,120,327 bytes and billing 30 MiB under a 50 MiB ceiling. No source table was changed. Training used the existing local scikit-learn dependency: 32 trees, depth two, no BQML/Vertex training or dedicated serving endpoint.

Chronological train / validation / test: 1,219 / 406 / 406 rows. Timestamp ties stay together; the 0.70 threshold is selected only on validation. The sealed test contains 255 fraud examples and 151 legitimate examples:

| Test outcome | Count |
|---|---:|
| Fraud detected / missed | 20 / 235 |
| Legitimate flagged / allowed | 6 / 145 |
| Recall / false-positive rate | 7.84% / 3.97% |

JSON inference matches the fitted estimator within `1.12e-16`. The temporal splits share customers and use synthetic AE labels. This is a weak corroborating signal, **not production fraud accuracy**. A low score cannot clear a complaint. The model is investigation-only and cannot activate a payment safeguard. Its measured limitation is returned to Gemini with the receipt.

The useful demonstration is disagreement: a transaction may resemble ordinary wallet activity while a payment request contains deception. The agent must reconcile the ledger result, message evidence and customer testimony before presenting a resolution. Human-reviewed knowledge and replay-passed prevention remain separate.

## Run and deploy

Use your own ADC; no credential files belong in Git. The revised entry point is:

```sh
./scripts/retrain_and_deploy_ledger_model.sh --train-only
./scripts/retrain_and_deploy_ledger_model.sh --deploy-only
```

`--all` performs both on the first run. Export goes into ignored `output/ledger-training/`, not a tracked dataset. An existing export/deploy receipt stops accidental resubmission; inspect an uncertain job before taking further action. Reuse the completed CSV for local retraining with `web/train_ledger_classifier.py`; it does not query BigQuery again.

Deployment uses the configured `minttown-builder` identity and dedicated staging bucket, cached image layers, a ten-minute build ceiling and only the existing service. It checks that simulation/investigation work is idle, pauses the previous writer, and preserves every environment setting, access policy and spend counter. No new model endpoint is provisioned.

## Evaluation-period cost

Zero minimum / one maximum Cloud Run instance are retained. Idle demo phases no longer poll just because they are waiting for Next. Active simulation and investigation still refresh; hidden tabs stop polling. CPU remains available between HTTP requests because the existing world and agent workers run in background threads. Request-only CPU throttling would interrupt that architecture.

At Google's listed us-central1 instance-based rates, 1 vCPU + 1 GiB is approximately **$0.072 per allocated hour**, before free-tier credits, builds, storage and network charges. Continuous allocation for 48 hours would be about $3.46; scale-to-zero can reduce that. This is an estimate, not a budget guarantee. [Cloud Run pricing](https://cloud.google.com/run/pricing), [background execution and billing](https://docs.cloud.google.com/run/docs/configuring/billing-settings).

Verified controls remain $5/month native Cloud Run cap, $8/month native Vertex cap, the $20 cumulative project budget with a shutdown request at $16 reported spend, and application model limits of $2/day, $0.05/case, $8 lifetime and six calls/case. One paid call at a time, six-second spacing and no automatic retries remain. Caps can stop evaluator access and billing enforcement is delayed; availability is not unlimited.
