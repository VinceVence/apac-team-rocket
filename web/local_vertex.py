"""Run Pallet Town locally with Vertex and the existing shared cloud spend ledger.

Requires the hosted service to be disabled (manual scaling 0). Never creates a
fresh paid ledger, changes cloud resources, retries a model, or raises dollar caps.
"""
import argparse
import os
import signal
import tempfile
from pathlib import Path

from cloud_data import CloudData
from server import make_server
from settings import DAILY_MODEL_USD, CASE_USD, TOTAL_MODEL_USD, DAILY_MODEL_CALLS, MAX_CASE_CALLS

PROJECT='minttown-apac-2026'


def require_paused(service):
    scaling=service.get('scaling',{})
    if service.get('reconciling') or scaling.get('scalingMode')!='MANUAL' or scaling.get('manualInstanceCount',0)!=0:
        raise ValueError('Pause the hosted service with manual scaling 0 before using its ledger locally.')
    if any(t.get('tag') for t in service.get('traffic',[])+service.get('trafficStatuses',[])):
        raise ValueError('Tagged hosted revisions must also be disabled before local execution.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',required=True,help='Explicitly enable bounded Vertex investigations.')
    parser.add_argument('--port',type=int,default=3000)
    args=parser.parse_args()
    if os.environ.get('GOOGLE_CLOUD_PROJECT')!=PROJECT:parser.error('Load the dedicated project ADC environment first.')
    cloud=CloudData(PROJECT,PROJECT+'-demo-state','minttown_demo')
    response=cloud.session.get(f'https://run.googleapis.com/v2/projects/{PROJECT}/locations/us-central1/services/minttown',timeout=20)
    response.raise_for_status();require_paused(response.json())
    with tempfile.TemporaryDirectory(prefix='pallet-vertex-') as folder:
        path=Path(folder)/'shared.sqlite3';cloud.restore(path)
        if cloud.generation=='0' or not path.exists():raise ValueError('The existing shared ledger is missing. Refusing a new paid budget.')
        for name in ('MINTTOWN_LIVE','MINTTOWN_FRAUD_LIVE','MINTTOWN_CLOUD_LIVE'):os.environ[name]='1'
        os.environ['PALLET_WAREHOUSE_ENABLED']='1'
        server=make_server(args.port,path,cloud=cloud,bind_host='127.0.0.1')
        server.warehouse.provision()
        def terminate(*_):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,terminate)
        print(f'Pallet Town: http://127.0.0.1:{args.port} · Vertex AI · shared ledger · Cloud Run paused',flush=True)
        print(f'${DAILY_MODEL_USD:g}/UTC day · ${CASE_USD:g}/case · ${TOTAL_MODEL_USD:g} lifetime · {DAILY_MODEL_CALLS} calls/day · {MAX_CASE_CALLS}/case · no retries',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close();server.lab.db.close()


if __name__=='__main__':main()
