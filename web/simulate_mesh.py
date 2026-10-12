"""Rehearse the five BFSI playbooks over HTTP; no browser or paid API calls."""
import json
import time
from pathlib import Path

from simulate import sandbox


def main():
    started = time.perf_counter(); results = []
    for playbook in ('fraud-response', 'cashflow-care', 'retention-science', 'savings-science', 'macro-policy'):
        with sandbox() as (server, call, initial):
            if playbook == 'macro-policy':
                for tick in range(6): call('/api/world/step', {'expected_tick': tick, 'activity': 3, 'scenario': 'demand' if tick == 0 else 'none'})
            catalogue = call('/api/mesh')
            request = {'playbook_id': playbook, 'mode': 'baseline', 'request_id': 'headless-' + playbook}
            if playbook == 'fraud-response': request['case_id'] = 'F001'
            if playbook == 'cashflow-care': request['case_id'] = 'I001'
            run = call('/api/mesh/start', request)
            while run['status'] == 'running': run = call('/api/mesh/runs/' + run['id'] + '/step', {'expected_step': run['step']})
            assert run['status'] == ('withheld' if playbook == 'savings-science' else 'completed'), run.get('error')
            state = call('/api/state'); assert state['ledger_balanced'] and state['budget']['calls_today'] == 0
            results.append({'playbook': playbook, 'runtime': catalogue['runtime'], 'run': run, 'ledger_balanced': True, 'gemini_calls': 0})
            print(playbook + ': ' + run['status'] + ', ' + str(run['step']) + ' turns, ' + catalogue['runtime']['label'], flush=True)
    report = {'elapsed_seconds': round(time.perf_counter() - started, 3), 'runs': results,
              'mode': 'Local rehearsal; real service tools and Google ADK when installed; no live Gemini evaluation.'}
    output = Path(__file__).resolve().parent / 'reports' / 'latest-mesh.json'
    output.parent.mkdir(exist_ok=True); output.write_text(json.dumps(report, indent=2) + '\n')
    print(str(output) + ' · ' + str(report['elapsed_seconds']) + ' seconds', flush=True)


if __name__ == '__main__': main()
