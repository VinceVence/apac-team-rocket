"""Offline customer workflow checks. A resident assertion never releases funds."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agents import Config
from demo_reset import initialize
from lab import Lab, LabError
from resident_requests import ResidentRequests
from server import make_server


class ResidentRequestChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'resident.db'
        self.lab = Lab(self.path, seed_history=False)
        initialize(self.lab)
        self.requests = ResidentRequests(self.lab)
        self.scene = self.lab.db.execute('SELECT scene_id FROM demo_scene').fetchone()[0]
        with self.lab.db:
            self.lab.event('held-1', 'C002', 'payment_blocked', 90000, '2026-10-16', 'blocked', 'C002:wallet', 'm1', {'prevention_tool': 'payments.hold_transfer'})
        self.accounts = self.lab.rows('SELECT * FROM accounts')
        self.events = self.lab.rows('SELECT * FROM financial_events')

    def tearDown(self):
        self.lab.db.close()
        self.temp.cleanup()

    def payload(self, action='verify', revision=0, **changes):
        return {'scene_id': self.scene, 'event_id': 'held-1', 'expected_revision': revision,
                'request_id': 'test-request-'+action+str(revision), 'action': action,
                'note': 'I used an independently found official contact.', **changes}

    def assert_no_debit(self):
        self.assertEqual(self.accounts, self.lab.rows('SELECT * FROM accounts'))
        self.assertEqual(self.events, self.lab.rows('SELECT * FROM financial_events'))
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM ledger_entries').fetchone()[0], 0)
        self.assertTrue(self.lab.integrity())

    def test_saved_verification_support_and_analyst_response_survive_reopen(self):
        first = self.requests.act(self.payload())
        self.assertEqual(first['customer_id'], 'C002')
        self.assertEqual(first['verification_status'], 'pending')
        self.assertEqual(first['payment_status'], 'held')
        support = self.requests.act(self.payload('support', 1))
        self.assertEqual(support['support_status'], 'open')
        self.assertEqual(first['ticket_id'], support['ticket_id'])
        reviewed = self.requests.act(self.payload('keep_held', 2, note='Independent evidence is insufficient. Keep held.'), analyst=True)
        self.assertEqual(reviewed['verification_status'], 'reviewed')
        self.assertEqual(reviewed['support_status'], 'closed')
        self.assertEqual(reviewed['payment_status'], 'held')
        self.assert_no_debit()
        self.lab.db.close()
        self.lab = Lab(self.path, seed_history=False)
        self.assertEqual(ResidentRequests(self.lab).dashboard()[0], reviewed)

    def test_cancel_is_terminal_and_withdraws_pending_verification(self):
        self.requests.act(self.payload())
        cancelled = self.requests.act(self.payload('cancel', 1, note=''))
        self.assertEqual(cancelled['payment_status'], 'cancelled')
        self.assertEqual(cancelled['verification_status'], 'withdrawn')
        with self.assertRaises(LabError):self.requests.act(self.payload('verify', 2))
        support = self.requests.act(self.payload('support', 2))
        reviewed = self.requests.act(self.payload('keep_held', 3), analyst=True)
        self.assertEqual(reviewed['payment_status'], 'cancelled')
        self.assertEqual(reviewed['support_status'], 'closed')
        self.assert_no_debit()

    def test_duplicate_delivery_is_idempotent_but_conflicting_payload_is_rejected(self):
        payload = self.payload()
        first = self.requests.act(payload)
        self.assertEqual(first, self.requests.act(payload))
        with self.assertRaises(LabError):self.requests.act({**payload, 'note': 'Changed evidence with the same request identifier.'})
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM resident_request_actions').fetchone()[0], 1)
        self.assert_no_debit()

    def test_concurrent_requests_cannot_overwrite_newer_state(self):
        def send(action):
            try:return self.requests.act(self.payload(action))
            except LabError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, ['verify', 'cancel']))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertIn(409, results)
        self.assert_no_debit()

    def test_invalid_scope_nonholds_extra_fields_and_release_are_rejected(self):
        for changes in [{'scene_id': 'old-scene'}, {'event_id': 'missing'}, {'expected_revision': 9},
                        {'expected_revision': True}, {'customer_id': 'C099'}, {'action': 'release'},
                        {'note': 'short'}, {'request_id': 'bad'}, {'note': 'x'*601}]:
            with self.subTest(changes=changes), self.assertRaises(LabError):
                self.requests.act(self.payload(**changes))
        with self.lab.db:
            self.lab.event('ordinary', 'C002', 'payment', 100, '2026-10-16', 'settled')
        with self.assertRaises(LabError):self.requests.act(self.payload(event_id='ordinary'))
        with self.assertRaises(LabError):self.requests.act(self.payload('keep_held'), analyst=True)
        self.assertEqual(self.requests.dashboard(), [])

    def test_analyst_cancel_is_audited_and_customer_cannot_review(self):
        self.requests.act(self.payload('support'))
        with self.assertRaises(LabError):self.requests.act(self.payload('keep_held', 1))
        result = self.requests.act(self.payload('cancel', 1), analyst=True)
        self.assertEqual(result['payment_status'], 'cancelled')
        self.assertEqual(result['support_status'], 'closed')
        self.assertEqual(self.lab.rows('SELECT actor FROM resident_request_actions')[-1]['actor'], 'demo_analyst')
        self.assert_no_debit()

    def test_http_csrf_hosted_allowlist_and_scene_reset(self):
        from demo_guard import DemoGuard
        server = make_server(0, Path(self.temp.name)/'http.db', Config(live=False), seed_history=False)
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        base = 'http://127.0.0.1:'+str(server.server_port)
        def read():
            with urllib.request.urlopen(base+'/api/state') as response:return json.load(response)
        try:
            state = read()
            with server.lab.lock, server.lab.db:
                server.lab.event('held-http', 'C002', 'payment_blocked', 90000, '2026-10-16', 'blocked', 'C002:wallet', 'm1', {'prevention_tool': 'payments.hold_transfer'})
            payload = self.payload('support', scene_id=state['demo']['scene_id'], event_id='held-http')
            request = urllib.request.Request(base+'/api/resident/action', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 403)
            request.add_header('X-MintTown-Token', state['csrf_token'])
            with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response)['support_status'], 'open')
            self.assertEqual(read()['resident_requests'][0]['customer_id'], 'C002')
            guard = DemoGuard(server.lab, lambda: None)
            for route in ('/api/resident/action', '/api/resident/review'):guard.allow('POST', route, payload)
            with server.lab.lock:
                server.world_demo.resetter.reset(10)
            self.assertEqual(server.resident_requests.dashboard(), [])
            with self.assertRaises(LabError):server.resident_requests.act(payload)
            self.assertTrue(list((Path(self.temp.name)/'archives').glob('*.sqlite3.gz')))
        finally:
            server.shutdown();server.server_close();server.lab.db.close();thread.join(2)
