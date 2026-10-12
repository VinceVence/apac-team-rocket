"""Rehearse report → investigation → human review → retrieved memory over real HTTP."""
import json
import time
from pathlib import Path

from fraud_desk import LESSON, QUESTION
from simulate import sandbox


def main():
    started = time.perf_counter()
    with sandbox() as (server, call, initial):
        def no_provider(*args): raise AssertionError('Fraud rehearsal must not call Gemini.')
        server.agents.transport = no_provider
        world = call('/api/world/step', {'expected_tick': initial['world']['tick'], 'activity': 2, 'scenario': 'none'})
        first = call('/api/fraud-desk/demo', {'scenario': 'first', 'request_id': 'http-first'})
        def investigate(report):
            run = call('/api/fraud-desk/investigate', {'report_id': report['id']})
            while run['status'] == 'running':
                run = call('/api/fraud-desk/step', {'run_id': run['id'], 'expected_step': run['step']})
            return run
        before = investigate(first)
        assert not before['context']['memories']
        assert not call('/api/fraud-desk')['memories']
        reviewed = call('/api/fraud-desk/review', {
            'report_id': first['id'], 'investigation_id': before['id'], 'disposition': 'confirmed_scam',
            'action': 'request_recall', 'note': 'Demo analyst verified the reported impersonation and transfer evidence.',
            'publish_memory': True, 'lesson': LESSON, 'next_question': QUESTION})
        second = call('/api/fraud-desk/demo', {'scenario': 'repeat', 'request_id': 'http-repeat'})
        after = investigate(second)
        assert after['context']['memories'][0]['source_report_id'] == first['id']
        assert after['trace'][3]['tool'] == 'compare_reviewed_pattern'
        assert second['transactions'][0]['metadata']['review_flags']
        benign = investigate(call('/api/fraud-desk/demo', {'scenario': 'benign', 'request_id': 'http-benign'}))
        assert not benign['context']['memories']
        final = call('/api/state')
        assert final['ledger_balanced'] and final['budget']['calls_today'] == 0 and not final['budget']['live_enabled']
        result = {'elapsed_seconds': round(time.perf_counter()-started, 3), 'world_tick': world['tick'],
                  'mode': 'Offline controller; no AI inference or model training', 'gemini_calls': 0,
                  'ledger_balanced': True, 'tables': len(final['tables']),
                  'first_investigation': before, 'analyst_review': reviewed['reviews'][0],
                  'second_investigation': after, 'early_review_flags': second['transactions'][0]['metadata']['review_flags'],
                  'benign_case_memory_matches': 0}
    output = Path(__file__).resolve().parent / 'reports' / 'latest-fraud-resolution.json'
    output.parent.mkdir(exist_ok=True); output.write_text(json.dumps(result, indent=2)+'\n')
    print('Passed: simulator → report → 5 tools → analyst review → saved memory → second investigation; benign control, balanced ledger, Gemini off.')
    print(str(output))


if __name__ == '__main__': main()
