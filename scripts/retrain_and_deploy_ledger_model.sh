#!/usr/bin/env bash
# Karlo's AE export -> bounded CPU model -> contract checks -> existing Cloud Run service.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE="${1:---all}"
case "$MODE" in --all|--train-only|--deploy-only) ;; *) echo 'Use --all, --train-only or --deploy-only'; exit 2;; esac
CSV="$ROOT/output/ledger-training/ledger_train.csv"
if [ "$MODE" != '--deploy-only' ]; then
  uv run --locked python -B web/fetch_ledger_training_csv.py --output "$CSV"
  uv run --locked python -B web/train_ledger_classifier.py --bigquery-csv "$CSV"
fi
MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0 uv run --locked python -B -m unittest discover -s web -p 'test_ledger_fraud_models.py' -v
if [ "$MODE" != '--train-only' ]; then
  uv run --locked python -B scripts/deploy_ledger_model.py
fi
