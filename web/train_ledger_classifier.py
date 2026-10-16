"""Build ledger_transaction_v1.json locally. No BigQuery ML or cloud training."""
import argparse
import hashlib
import json
from pathlib import Path

from ledger_fraud_features import load_export_rows
from ledger_fraud_models import synthetic_training_rows, train_rows

ROOT = Path(__file__).with_name('model_artifacts')


def build(rows, destination=ROOT):
    artifact, evaluation = train_rows(rows)
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / 'ledger_transaction_v1.json'
    body = json.dumps(artifact, sort_keys=True, indent=2, allow_nan=False) + '\n'
    model_path.write_text(body)
    eval_path = destination / 'ledger_transaction_evaluation.json'
    evaluation.update({
        'source': 'CPU-trained on AE ledger rows; labels used only offline.',
        'feature_version': artifact['feature_version'],
        'excluded_predictor_inputs': ['is_fraud', 'scam_type', 'risk_score', 'risk_factors'],
    })
    eval_path.write_text(json.dumps(evaluation, indent=2) + '\n')
    entry = {
        'model_id': 'ledger_transaction_v1',
        'version': '1.0',
        'name': 'Ledger transaction classifier',
        'task': 'Observed wallet transfer patterns compared with generator-labelled fraud examples',
        'positive_class': 'Generator-labelled fraudulent transfer',
        'release_status': 'synthetic_advisory_only',
        'training_cutoff': '2026-10-06T23:59:59Z',
        'eligible_population': 'Case payments with a matching AE ledger projection',
        'file': model_path.name,
        'artifact_sha256': hashlib.sha256(body.encode()).hexdigest(),
        'evaluation_reference': 'web/model_artifacts/ledger_transaction_evaluation.json',
        'limitation': 'Advisory only; uncalibrated and not approved to block payments. Trained without BigQuery ML.',
    }
    catalog_path = destination / 'catalog.json'
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {'models': []}
    catalog['models'] = [m for m in catalog['models'] if m.get('model_id') != entry['model_id']] + [entry]
    catalog_path.write_text(json.dumps(catalog, indent=2) + '\n')
    return evaluation, entry


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, help='Environment export directory with *.jsonl tables')
    parser.add_argument('--output', type=Path, default=ROOT)
    args = parser.parse_args()
    training = load_export_rows(args.export) if args.export else synthetic_training_rows()
    summary, _ = build(training, args.output)
    print(json.dumps(summary))
