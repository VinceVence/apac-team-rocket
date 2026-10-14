"""Generate a fresh offline AE-schema dataset. No BigQuery or Gemini calls."""
import argparse
import tempfile
from pathlib import Path

from agents import Config
from server import make_server
from lab import encoded


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('output/environment-data'))
    parser.add_argument('--steps',type=int,choices=range(1,25),default=24)
    parser.add_argument('--scenario',choices=('phishing','payment_burst','invoice_redirect','task_scam','investment_scam'))
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='minttown-ae-export-') as folder:
        server=make_server(0,Path(folder)/'world.db',Config(live=False))
        try:
            for step in range(args.steps):server.world.advance(step,activity=4)
            if args.scenario:server.fraud_desk.demo(args.scenario,'offline-export')
            print(encoded(server.environment_data.export(args.output)))
        finally:server.server_close();server.lab.db.close()


if __name__=='__main__':main()
