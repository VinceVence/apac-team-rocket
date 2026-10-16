# Model tools: Karlo's handoff

The investigator calls `score_models` with registered model IDs and case-bound transaction IDs. Trusted code binds the customer, immutable evidence, feature versions and artifact digest. Models provide advisory evidence; they cannot approve cases or activate prevention.

The built-in `synthetic_triage_v1` is a real locally fitted logistic baseline, not Karlo's model. It uses generator labels, failed the final prevention gate and is explicitly investigation-only. Its scores are **not calibrated fraud probabilities**. Three existing predictor adapters remain labelled demo rules.

## Files to contribute

1. A data-only artifact under `web/model_artifacts/`. Current loader accepts standardized binary logistic regression or a bounded gradient-boosted tree ensemble. No pickle, dynamic code, external URL, GPU or always-on model endpoint.
2. A `catalog.json` entry with model ID/version, descriptive name, prediction target, positive-class meaning, release status, training/label cutoff, eligible population, artifact filename/SHA-256, evaluation reference and limitations. Follow the existing entry.
3. Evaluation with chronological/customer/template splits, no label-derived features, threshold selection using validation only, final confusion counts and negative controls. Document missingness and score interpretation. Include frozen input/output examples for parity testing.

Current artifact keys:

| Common | `kind`, `feature_version`, ordered `features`, `threshold` |
|---|---|
| Logistic | `coefficients`, scalar `intercept`, ordered `means`, positive `scales` |
| Boosted tree | scalar log-odds `initial_score`, `parameters.learning_rate`, up to 32 `trees`, each with `children_left`, `children_right`, `feature`, `threshold`, `value` arrays; at most 63 nodes/tree |

See `trained_models.py` for validation and `risk_models.py` for the exporter. All numeric parameters must be finite; JSON size is capped at 256 KiB. The container includes this directory. Every model call returns model/feature versions, manifest/input digests, scoped event IDs, source, missing inputs and score meaning.

## Feature boundary

The built-in adapter accepts only `risk-features-v1` fields from `risk_models.GROUPS`. It reads the vector recorded before payment, including spending history, recipient novelty and observed payment-request signals. Missing device/message/history inputs must remain missing. Neither a later complaint nor hidden `is_fraud`, `scam_type`, AE `risk_score`/`risk_factors`, demographics or outcome labels may enter this vector.

For a new feature set, add a versioned trusted builder and adapter with cutoff/availability checks and tests. Merely adding a catalog entry does not make a differently trained model compatible. BigQuery investigation aggregates are a separate contract in `case_features.py`; do not relabel them as prepayment observations.

Run the offline tests and compare JSON inference with the original estimator before merging. Registration enables investigation only. Promotion to payment serving requires a separate reviewed operating threshold, replay evidence, human activation and revocation path. Training and uploading an artifact never release it automatically.

## Ledger classifier (no BigQuery ML)

`ledger_transaction_v1` uses `ledger-features-v1` built from the AE ledger projection (`web/ledger_fraud_features.py`). Train locally:

```sh
uv run --locked python -B web/train_ledger_classifier.py
```

Optional: export rows with `sql/ledger_fraud_export.sql`, convert to the AE jsonl layout, then `uv run --locked python -B web/train_ledger_classifier.py --export path/to/export`. The agent calls it through `score_models` like the other registered predictors.

## Request-learning tools

`request_models.py` exports `request_logistic`: fixed word/character hashing blocks plus observed transaction features, bounded coefficients and a validation-selected threshold. `train_request_predictors.py` builds our two additional advisory tools. The model input is the recorded prepayment request, not the later complaint.

A three-role request study may register its validation-selected model via operator-only `POST /api/risk-lab/register` with `study_id`, `candidate_id`, and a review `note`. This creates an immutable, versioned investigation tool in the durable registry. It never approves payment release; a failed release gate stays failed. At most two reviewed request tools are active in this demo. See [learning loops](learning-loops.md).
