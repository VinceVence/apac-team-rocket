"""Run the simulated-env training export query and write CSV."""
import argparse
import csv
from pathlib import Path

from google.cloud import bigquery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument(
        '--sql',
        type=Path,
        default=Path(__file__).resolve().parents[1] / 'sql' / 'ledger_fraud_export_simulated_env.sql',
    )
    args = parser.parse_args()
    client = bigquery.Client(project='minttown-apac-2026')
    query = args.sql.read_text()
    rows = client.query(query).result()
    fieldnames = [field.name for field in rows.schema]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        count = 0
        for row in rows:
            writer.writerow(dict(row.items()))
            count += 1
    print(f'Wrote {count} rows to {args.output}')


if __name__ == '__main__':
    main()
