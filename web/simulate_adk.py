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
        # An isolated rehearsal gets enough simulated calls to include all three example cases.
        server.agents.config = Config(live=False, daily_calls=100)
        call('/api/world/step', {'expected_tick': initial['world']['tick'], 'activity': 2, 'scenario': 'none'})
        def investigate(report):
            run = call('/api/fraud-agent/start', {'report_id': report['id'], 'mode': 'fake'})
            for _ in range(7):
                if run['status'] != 'running': return run
                run = call('/api/fraud-agent/step', {'run_id': run['id'], 'expected_step': run['step']})
            raise AssertionError('Unbounded loop')
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
        resumed = investigate(updated)
        assert resumed['status'] == 'awaiting_review', resumed['context'].get('stop_reason')
        assert resumed['budget']['case_calls'] == 5
        benign = investigate(call('/api/fraud-desk/demo', {'scenario': 'benign', 'request_id': 'adk-benign'}))
        assert benign['status'] == 'awaiting_review' and benign['step'] == 2
        final = call('/api/state'); assert final['ledger_balanced'] and not final['budget']['live_enabled'] and final['budget']['calls_today'] == 0
        client.assert_not_called()
        result = {'mode': 'Real ADK runtime; injected fake model; no live reasoning evaluation',
                  'elapsed_seconds': round(time.perf_counter() - started, 3), 'runtime': server.fraud_agent.runtime(),
                  'first': before, 'second_paused': paused, 'second_after_reply': resumed, 'benign': benign,
                  'real_gemini_calls': 0, 'real_api_cost_usd': 0, 'ledger_balanced': True}
        output = Path(__file__).resolve().parent / 'reports' / 'latest-adk-investigation.json'
        output.parent.mkdir(exist_ok=True); output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'first_tools': [t['tool'] for t in before['trace']],
            'second_before_reply': [t['tool'] for t in paused['trace']],
            'model_question': paused['context']['pending_question'],
            'second_after_reply': [t['tool'] for t in resumed['trace']],
            'benign_tools': [t['tool'] for t in benign['trace']],
            'second_case_calls_before_after_reply': [paused['budget']['case_calls'], resumed['budget']['case_calls']],
            'real_gemini_calls': 0, 'real_api_cost_usd': 0, 'ledger_balanced': True,
            'report': str(output)}, indent=2))


if __name__ == '__main__': main()
