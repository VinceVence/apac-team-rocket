"""Real HTTP + ADK, injected fake choices, no Gemini client or paid API calls."""
import json
import time
from pathlib import Path
from unittest.mock import patch

from agents import Config
from fraud_desk import LESSON, QUESTION
from simulate import sandbox


def main():
    started = time.perf_counter()
    with sandbox() as (server, call, initial), patch('google.genai.Client.__init__', side_effect=AssertionError('No live client in this rehearsal')) as client:
        # Exercise a smaller 10-call limit while retaining the normal dollar caps.
        server.agents.config = Config(live=False,daily_calls=10)
        call('/api/world/step', {'expected_tick': initial['world']['tick'], 'activity': 2, 'scenario': 'none'})
        def wait_for_case(report_id):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                detail = call('/api/fraud-desk/reports/' + report_id)
                run = detail['investigation']
                if run and run['context'].get('execution', {}).get('status') not in ('queued','running'):
                    return run
                time.sleep(.03)
            raise AssertionError('Automatic runner did not stop')
        def investigate(report):
            run = call('/api/fraud-agent/start', {'report_id': report['id'], 'mode': 'fake'})
            assert run['context']['execution']['mode'] == 'automatic'
            # No client-side /step calls: the server keeps investigating independently.
            return wait_for_case(report['id'])
        first = call('/api/fraud-desk/demo', {'scenario': 'first', 'request_id': 'adk-first'})
        before = investigate(first); assert before['status'] == 'awaiting_review', before['context'].get('stop_reason')
        call('/api/fraud-desk/review', {'report_id': first['id'], 'investigation_id': before['id'],
            'disposition': 'confirmed_scam', 'action': 'request_recall',
            'note': 'Demo analyst verified the impersonation report and transaction references.',
            'publish_memory': True, 'lesson': LESSON, 'next_question': QUESTION})
        second = call('/api/fraud-desk/demo', {'scenario': 'repeat', 'request_id': 'adk-second'})
        paused = investigate(second)
        assert paused['status'] == 'awaiting_customer', paused['context'].get('stop_reason')
        assert paused['context']['pending_question'] == QUESTION
        updated = call('/api/fraud-desk/reply', {'report_id': second['id'], 'expected_revision': second['revision'],
                                               'answer': 'Yes. The caller said to keep this secret from bank staff.'})
        resumed = wait_for_case(updated['id'])
        assert resumed['status'] == 'awaiting_review', resumed['context'].get('stop_reason')
        assert resumed['budget']['case_calls'] == 5
        trail = call('/api/fraud-desk/reports/' + second['id'])['decision_trail']
        assert len(trail) == 5 and [t['revision'] for t in trail] == [1,1,1,2,2]
        assert all(t['purpose'] and t['finding'] and t['provenance']['snapshot_id'] for t in trail)
        stopped = investigate(call('/api/fraud-desk/demo', {'scenario': 'benign', 'request_id': 'adk-daily-cap'}))
        assert stopped['status'] == 'budget_exhausted' and stopped['budget']['case_calls'] == 0
        assert stopped['budget']['daily_calls'] == stopped['budget']['daily_call_limit'] == 10
        # An independent fake-only database demonstrates the benign branch without resetting a ledger.
        with sandbox() as (clean_server, clean_call, _):
            clean = clean_call('/api/fraud-desk/demo', {'scenario': 'benign', 'request_id': 'adk-benign'})
            clean_call('/api/fraud-agent/start', {'report_id': clean['id']})
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                benign = clean_call('/api/fraud-desk/reports/' + clean['id'])['investigation']
                if benign['status'] == 'awaiting_review': break
                time.sleep(.03)
            assert benign['status'] == 'awaiting_review' and benign['step'] == 2
        final = call('/api/state'); assert final['ledger_balanced'] and not final['budget']['live_enabled'] and final['budget']['calls_today'] == 0
        client.assert_not_called()
        result = {'mode': 'Real ADK runtime; injected fake model; no live reasoning evaluation',
                  'elapsed_seconds': round(time.perf_counter() - started, 3), 'runtime': server.fraud_agent.runtime(),
                  'first': before, 'second_paused': paused, 'second_after_reply': resumed, 'second_decision_trail': trail,
                  'daily_limit_stop': stopped, 'benign_in_separate_database': benign, 'automatic_runner': True,
                  'real_gemini_calls': 0, 'real_api_cost_usd': 0, 'ledger_balanced': True}
        output = Path(__file__).resolve().parent / 'reports' / 'latest-adk-investigation.json'
        output.parent.mkdir(exist_ok=True); output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'first_tools': [t['tool'] for t in before['trace']],
            'second_before_reply': [t['tool'] for t in paused['trace']],
            'model_question': paused['context']['pending_question'],
            'second_after_reply': [t['tool'] for t in resumed['trace']],
            'benign_tools': [t['tool'] for t in benign['trace']],
            'second_case_calls_before_after_reply': [paused['budget']['case_calls'], resumed['budget']['case_calls']],
            'automatic_runner': True, 'client_step_requests': 0, 'daily_limit_stop': stopped['context']['stop_reason'],
            'case_trail_across_replies': [t['tool'] for t in trail],
            'real_gemini_calls': 0, 'real_api_cost_usd': 0, 'ledger_balanced': True,
            'report': str(output)}, indent=2))


if __name__ == '__main__': main()
