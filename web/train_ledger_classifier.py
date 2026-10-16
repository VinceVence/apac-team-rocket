"""Train Karlo's bounded tree classifier locally from the capped AE export; no BQML."""
import argparse
import hashlib
import json
from pathlib import Path
from ledger_fraud_features import load_bigquery_csv
from ledger_fraud_models import train_rows

ROOT = Path(__file__).with_name('model_artifacts')


def build(rows, destination=ROOT, *, training_source=None):
    artifact, evaluation = train_rows(rows)
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination/'ledger_transaction_v1.json'
    body = json.dumps(artifact, sort_keys=True, indent=2, allow_nan=False)+'\n'
    model_path.write_text(body)
    evaluation.update(source=training_source or 'AE synthetic BigQuery export', feature_version=artifact['feature_version'],
                      excluded_predictor_inputs=['is_fraud','scam_type','risk_score','risk_factors','current_balance','daily_spent','wallet_status','risk_tier','trust_score','demographics'])
    (destination/'ledger_transaction_evaluation.json').write_text(json.dumps(evaluation, indent=2)+'\n')
    entry = {'model_id':'ledger_transaction_v1','version':'2.0','name':'AE ledger behavior classifier',
             'task':'Compare transaction amount, channel, type and prior wallet activity with AE-labelled fraud patterns',
             'positive_class':'AE generator-labelled fraudulent transfer','release_status':'synthetic_advisory_only',
             'training_cutoff':evaluation['partitions']['train']['end'], 'eligible_population':'Settled synthetic wallet transfers with frozen ledger-features-v2',
             'file':model_path.name,'artifact_sha256':hashlib.sha256(body.encode()).hexdigest(),
             'evaluation_reference':'web/model_artifacts/ledger_transaction_evaluation.json',
             'limitation':f"Synthetic temporal test: {evaluation['test']['tp']}/{evaluation['test']['tp']+evaluation['test']['fn']} fraud detected; {evaluation['test']['fp']}/{evaluation['test']['fp']+evaluation['test']['tn']} legitimate flagged. Low scores cannot clear a complaint. Uncalibrated; not approved to block."}
    catalog_path = destination/'catalog.json'
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {'models':[]}
    catalog['models'] = [e for e in catalog['models'] if e['model_id'] != entry['model_id']]+[entry]
    catalog_path.write_text(json.dumps(catalog, indent=2)+'\n')
    return evaluation, entry


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bigquery-csv',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT)
    args=parser.parse_args()
    evaluation,_=build(load_bigquery_csv(args.bigquery_csv),args.output,training_source='minttown-apac-2026.minttown_simulated_env; 100 customers; read-only bounded export')
    print(json.dumps(evaluation,indent=2))
