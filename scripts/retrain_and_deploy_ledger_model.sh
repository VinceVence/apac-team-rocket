#!/usr/bin/env bash
# Retrain ledger_transaction_v1 from minttown_simulated_env, commit artifacts, deploy Cloud Run.
# Requires: gcloud ADC (gcloud auth application-default login), uv, project access.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PROJECT=minttown-apac-2026
REGION=us-central1
SERVICE=minttown
CSV="$ROOT/data/ledger_train_minttown_simulated_env.csv"
TAG="ledger-$(git rev-parse --short HEAD)-$(date -u +%Y%m%d%H%M%S)"

echo "==> Export training rows from BigQuery (minttown_simulated_env)"
uv run --locked --group training python -B web/fetch_ledger_training_csv.py --output "$CSV"

echo "==> Train CPU artifact (no BQML)"
uv run --locked python -B web/train_ledger_classifier.py --bigquery-csv "$CSV"

echo "==> Run contract tests"
uv run --locked python -B -m unittest web.test_ledger_fraud_models -v

echo "==> Cloud Build image :$TAG"
gcloud builds submit --project "$PROJECT" --config deploy/cloudbuild.yaml --substitutions=_TAG="$TAG"

echo "==> Deploy Cloud Run"
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --image "us-central1-docker.pkg.dev/$PROJECT/minttown/minttown:$TAG"

echo "Done. Model artifact: web/model_artifacts/ledger_transaction_v1.json"
echo "Hosted URL: https://minttown-1040017899050.us-central1.run.app/"
