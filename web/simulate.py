"""Offline, headless capability checks through the real local HTTP endpoints."""
import argparse
import collections
import datetime as dt
import json
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from agents import Config
from lab import LabError
from server import make_server


@contextmanager
def sandbox():
    """Ignore live-mode environment variables and never open the saved demo DB."""
    with tempfile.TemporaryDirectory(prefix='minttown-simulation-') as folder:
        server = make_server(0, Path(folder) / 'economy.db', Config(live=False))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        token = ''

        def call(path, body=None):
            request = urllib.request.Request(
                base + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type': 'application/json', 'X-MintTown-Token': token},
            )
            try:
                with client.open(request, timeout=60) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                raise LabError(path + ': ' + json.load(exc).get('error', str(exc)), exc.code) from None

        try:
            initial = call('/api/state')
            token = initial['csrf_token']
            yield server, call, initial
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            server.lab.db.close()


def run_scenario(name, hours, activity, shocks, automatic_policy=True, acceptance=False):
    started = time.perf_counter()
    checks, cases, policy_actions, daily_handoffs, timeline = [], [], [], [], []

    def verify(condition, description):
        if not condition:
            raise AssertionError(name + ': ' + description)
        if description not in checks:
            checks.append(description)

    with sandbox() as (server, call, initial):
        lab = server.lab
        initial_row = lab.db.execute('SELECT max(rowid) FROM financial_events').fetchone()[0]
        initial_cash = lab.db.execute('SELECT sum(balance_minor) FROM accounts').fetchone()[0]

        def route(case_id, expected=None):
            result = call('/api/analyze', {'case_id': case_id, 'mode': 'baseline'})
            run = result['run']
            action = run['decision']['action']
            if expected:
                verify(action == expected, expected + ' outcome from its matching evidence')
            cached = call('/api/analyze', {'case_id': case_id, 'mode': 'baseline'})
            verify(cached['cached'] and cached['run']['id'] == run['id'], 'Investigation cache reuses the recorded decision')
            endpoint = '/api/services/block-device' if action == 'reject' else '/api/apply'
            command = {'case_id': case_id, 'run_id': run['id']}
            balances = lab.rows('SELECT id,balance_minor,version FROM accounts ORDER BY id')
            try:
                receipt = call(endpoint, command)
            except LabError as exc:
                # Authorized payments can still lack funds. Verify the safe refusal;
                # other HTTP failures remain fatal instead of becoming a false pass.
                if action != 'release' or exc.status != 409 or 'Insufficient available funds' not in str(exc):
                    raise
                verify(balances == lab.rows('SELECT id,balance_minor,version FROM accounts ORDER BY id') and
                       lab.case(case_id)['status'] == 'open',
                       'Insufficient funds roll back the whole release and keep the case open')
                receipt = {'status': 'held_insufficient_funds', 'applied': False, 'reason': str(exc)}
            else:
                replay = call(endpoint, command)
                verify(not receipt['replayed'] and replay['replayed'], 'Applying the same decision twice is idempotent')
            cases.append({'case_id': case_id, 'kind': run['evidence']['kind'],
                          'action': action, 'execution': 'held' if receipt.get('applied') is False else 'applied',
                          'endpoint': endpoint, 'receipt': receipt})

        if acceptance:
            route('F002', 'release')
            route('F003', 'review')
            prediction = call('/api/models/churn/predict', {'customer_id': 'C001'})
            repeated = call('/api/models/churn/predict', {'customer_id': 'C001'})
            verify(0 <= prediction['probability'] <= 1, 'A deployed model returns a bounded prediction over HTTP')
            verify(repeated['cached'] and repeated['prediction_id'] == prediction['prediction_id'],
                   'Repeated scoring reuses the prediction and feature snapshot')

        for tick in range(hours):
            command = {'expected_tick': tick, 'activity': activity, 'scenario': shocks.get(tick, 'none')}
            result = call('/api/world/step', command)
            verify(result['tick'] == tick + 1 and not result['replayed'], 'Each requested hour advances exactly once')
            if tick == 0:
                count = lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0]
                replay = call('/api/world/step', command)
                verify(replay['replayed'] and replay['tick'] == 1 and
                       count == lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0],
                       'A duplicate world step cannot create duplicate transactions')
            for case_id in result['alerts']:
                expected = 'reject' if command['scenario'] == 'fraud' else 'insight' if command['scenario'] == 'income' else None
                route(case_id, expected)
            if automatic_policy and result['macro_due']:
                before = server.macro.policy()
                decision = call('/api/macro/review', {'mode': 'baseline'})['decision']
                receipt = call('/api/policy/apply', {'decision_id': decision['id']})
                verify(not receipt['replayed'], 'Fresh macro decisions apply through the policy endpoint')
                after = server.macro.policy()
                verify(abs(after['loan_bps'] - before['loan_bps']) <= 100 and
                       abs(after['reserve_bps'] - before['reserve_bps']) <= 500 and
                       abs(after['fee_bps'] - before['fee_bps']) <= 5,
                       'Macro changes stay inside their per-review bounds')
                policy_actions.append({'tick': tick + 1, 'stance': decision['recommendation']['stance'],
                                       'plan': decision['plan']})
            if result.get('day_closed'):
                verify('science_notice' not in result, 'Daily pipeline has no execution error')
                handoff = result.get('science_handoff', {})
                verify(handoff.get('status') == 'completed' and len(handoff.get('stages', [])) == 6,
                       'Day close completes all six recorded science stages')
                daily_handoffs.append(handoff)
            if result.get('day_closed') or (tick + 1) % 6 == 0:
                verify(lab.integrity(), 'Conserved cash, balanced journal and reconciled accounts')
                timeline.append({'metrics': server.macro.metrics(tick + 1),
                                 'policy': {k: server.macro.policy()[k] for k in ('loan_bps', 'reserve_bps', 'fee_bps')}})

        final = call('/api/state')
        science = call('/api/science')
        event_counts = {r['kind']: r['n'] for r in lab.rows(
            'SELECT kind,count(*) AS n FROM financial_events WHERE rowid>? GROUP BY kind', (initial_row,))}
        blocked_postings = lab.db.execute(
            "SELECT count(*) FROM ledger_entries l JOIN financial_events e ON l.event_id=e.id WHERE e.kind='payment_blocked'"
        ).fetchone()[0]
        verify(blocked_postings == 0, 'Blocked-device attempts never reach the financial journal')
        if acceptance and hours >= 5:
            verify(event_counts.get('payment_blocked', 0) > 0, 'A blocked device retries and is denied by the service')
        verify(final['ledger_balanced'] and initial_cash == lab.db.execute('SELECT sum(balance_minor) FROM accounts').fetchone()[0],
               'Total initialized cash is conserved through the entire scenario')
        verify(final['budget']['calls_today'] == 0 and final['budget']['committed_usd_total'] == 0,
               'No Gemini calls or API spending')
        verify(final['tables']['customers'] == 240 and len(final['tables']) == 30,
               'The full 240-customer, 30-table application is initialized')

        predictions = []
        for release in science['deployments']:
            if release['status'] == 'active':
                predictions.append(call('/api/models/' + release['kind'] + '/predict', {'customer_id': 'C001'}))
        latest_gates = [{'id': m['id'], 'eligible': m['release_gate']['eligible'],
                         'reasons': m['release_gate']['reasons']} for m in science['models']]
        settled = lab.db.execute(
            "SELECT count(*),coalesce(sum(amount_minor),0) FROM financial_events WHERE rowid>? AND kind='payment' AND status='settled'",
            (initial_row,)).fetchone()
        models = lab.rows('SELECT kind,count(*) AS versions FROM model_runs GROUP BY kind')
        report = {
            'name': name, 'mode': 'local baseline; live API disabled', 'policy_mode': 'automatic' if automatic_policy else 'fixed initial policy',
            'hours': hours, 'activity': activity, 'shocks': [{'at_hour': t + 1, 'kind': s} for t, s in shocks.items() if t < hours],
            'initial_day': initial['as_of'], 'final_day': final['as_of'], 'customer_count': 240,
            'initial_historical_events': initial['tables']['financial_events'], 'new_events': sum(event_counts.values()),
            'event_counts': event_counts, 'settled_payments': settled[0], 'settled_payment_value_minor': settled[1],
            'case_actions': dict(collections.Counter(c['action'] for c in cases)), 'cases': cases,
            'case_executions': dict(collections.Counter(c['execution'] for c in cases)),
            'checks_passed': checks, 'ledger_balanced': final['ledger_balanced'], 'cash_change_minor': 0,
            'gemini_calls': final['budget']['calls_today'], 'estimated_api_usd': final['budget']['committed_usd_total'],
            'policy_stances': dict(collections.Counter(p['stance'] for p in policy_actions)), 'policy_actions': policy_actions,
            'initial_macro': initial['macro'], 'final_macro': final['macro'], 'timeline': timeline,
            'science_runs': final['tables']['science_runs'], 'daily_handoffs': daily_handoffs,
            'model_versions': models, 'latest_candidate_gates': latest_gates,
            'deployments': [{k: d[k] for k in ('id', 'kind', 'model_id', 'status', 'predictions')} for d in science['deployments']],
            'saved_predictions': lab.db.execute('SELECT count(*) FROM prediction_logs').fetchone()[0],
            'sample_predictions': predictions, 'monitoring': science['monitoring'],
        }
    report['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    print(f"{name}: {hours} hours, {report['new_events']} new events, {len(checks)} checks passed in {report['elapsed_seconds']}s", flush=True)
    return report


def policy_comparison(runs):
    pairs = []
    for shock in ('demand', 'supply'):
        pair = {'shock': shock}
        for mode in ('automatic', 'fixed'):
            run = next(r for r in runs if r['name'] == shock + '-' + mode)
            metrics = run['final_macro']['metrics']
            indices = [run['initial_macro']['metrics']['price_index']] + [p['metrics']['price_index'] for p in run['timeline']]
            pair[mode] = {
                'final_price_index': metrics['price_index'], 'peak_price_index_at_6h_samples': max(indices),
                'settled_payments': run['settled_payments'], 'payment_value_minor': run['settled_payment_value_minor'],
                'businesses_insolvent': metrics['bankrupt_businesses'], 'loans_in_arrears': metrics['loans_in_arrears'],
                'liquid_gini': metrics['liquid_gini'], 'final_loan_apr_pct': run['final_macro']['policy']['loan_bps'] / 100,
            }
        pairs.append(pair)
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=14, help='Integrated scenario duration, 1–30 days (default: 14).')
    parser.add_argument('--activity', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--compare-policy', action='store_true', help='Also compare 72-hour demand/supply shocks with policy automatic vs fixed.')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'reports' / 'latest-simulation.json')
    args = parser.parse_args()
    if not 1 <= args.days <= 30:
        parser.error('--days must be between 1 and 30')
    start = time.perf_counter()
    # Same fixed world RNG and initial dataset in each isolated run. Policy changes can
    # change random-draw consumption; this is one scenario comparison, not a causal estimate.
    runs = [run_scenario('integrated', args.days * 24, args.activity,
                         {0: 'fraud', 1: 'demand', 24: 'income', 72: 'supply'}, acceptance=True)]
    if args.compare_policy:
        for shock in ('demand', 'supply'):
            for mode in ('automatic', 'fixed'):
                runs.append(run_scenario(shock + '-' + mode, 72, args.activity, {0: shock}, mode == 'automatic'))
    report = {
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'elapsed_seconds': round(time.perf_counter() - start, 3),
        'transport': 'real local HTTP API on temporary loopback ports; no browser',
        'database': 'fresh temporary database for each run; saved demo not touched',
        'seed': 'fixed world RNG: 42 + tick * 761; fixed historical cohort',
        'runs': runs, 'policy_comparisons': policy_comparison(runs) if args.compare_policy else [],
        'limitations': [
            'These checks verify application behavior on synthetic data, not real-world fraud or economic accuracy.',
            'Named roles execute bounded local code; optional Gemini reasoning is not exercised here.',
            'There is no live bank, MCP server, AlloyDB, Vertex AI or cloud deployment in this run.',
            'Policy comparisons use one fixed initialization per shock, not multiple-seed evidence of stabilization.',
            'Model performance needs delayed labels and sufficient examples of both outcomes.',
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Report: {args.output.resolve()}\nTotal: {report['elapsed_seconds']}s; API spend: $0", flush=True)


if __name__ == '__main__':
    main()
