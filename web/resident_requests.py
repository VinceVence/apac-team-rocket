"""Customer follow-up for simulated holds; never releases money or calls a model."""
import hashlib
import json
import re
import uuid

from lab import LabError, encoded, now


class ResidentRequests:
    def __init__(self, lab):
        self.lab = lab
        lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS resident_requests(
          event_id TEXT PRIMARY KEY REFERENCES financial_events(id),
          ticket_id TEXT NOT NULL UNIQUE, scene_id TEXT NOT NULL, customer_id TEXT NOT NULL,
          payment_status TEXT NOT NULL DEFAULT 'held',
          verification_status TEXT NOT NULL DEFAULT 'none', verification_note TEXT NOT NULL DEFAULT '',
          support_status TEXT NOT NULL DEFAULT 'none', support_note TEXT NOT NULL DEFAULT '',
          analyst_note TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS resident_request_actions(
          request_id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES resident_requests(event_id),
          payload_hash TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
          note TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')

    def dashboard(self):
        with self.lab.lock:
            return self.lab.rows('''SELECT r.*,e.amount_minor FROM resident_requests r
                JOIN financial_events e ON e.id=r.event_id
                ORDER BY (r.verification_status='pending' OR r.support_status='open') DESC,
                r.updated_at DESC,r.event_id LIMIT 100''')

    def act(self, body, *, analyst=False):
        required = {'scene_id', 'event_id', 'expected_revision', 'request_id', 'action', 'note'}
        if set(body) != required or any(not isinstance(body[k], str) for k in required-{'expected_revision'}):
            raise LabError('Use a current payment and complete request fields.')
        if type(body['expected_revision']) is not int or body['expected_revision'] < 0:
            raise LabError('Use the current request revision.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', body['request_id']):
            raise LabError('Use a unique request identifier.')
        action, note = body['action'], body['note'].strip()
        allowed = ('keep_held', 'cancel') if analyst else ('cancel', 'verify', 'support')
        if action not in allowed or len(note) > 600 or (action != 'cancel' or analyst) and len(note) < 10:
            raise LabError('Choose an allowed action and include 10–600 characters for review. Do not include secrets.')
        if len(body['event_id']) > 160 or len(body['scene_id']) > 80:
            raise LabError('Invalid payment reference.')
        actor = 'demo_analyst' if analyst else 'resident'
        fingerprint = hashlib.sha256(encoded({**body, 'actor': actor}).encode()).hexdigest()
        with self.lab.lock, self.lab.db:
            scene = self.lab.db.execute('SELECT scene_id FROM demo_scene WHERE id=1').fetchone()[0]
            if body['scene_id'] != scene:
                raise LabError('This scene has changed. Refresh before submitting.', 409)
            event = self.lab.db.execute('SELECT * FROM financial_events WHERE id=?', (body['event_id'],)).fetchone()
            if not event or event['kind'] != 'payment_blocked' or event['status'] != 'blocked' or json.loads(event['metadata']).get('prevention_tool') != 'payments.hold_transfer':
                raise LabError('Choose a recorded prevention hold in this scene.', 409)
            if self.lab.db.execute('SELECT 1 FROM ledger_entries WHERE event_id=?', (event['id'],)).fetchone():
                raise LabError('This payment has ledger entries and cannot use the hold workflow.', 409)
            previous = self.lab.db.execute('SELECT * FROM resident_request_actions WHERE request_id=?', (body['request_id'],)).fetchone()
            if previous:
                if previous['payload_hash'] != fingerprint:
                    raise LabError('This request identifier was already used for another action.', 409)
                return self.detail(event['id'])
            saved = self.lab.db.execute('SELECT * FROM resident_requests WHERE event_id=?', (event['id'],)).fetchone()
            if body['expected_revision'] != (saved['revision'] if saved else 0):
                raise LabError('This request changed. Refresh its status before submitting.', 409)
            stamp = now()
            if not saved:
                self.lab.db.execute('''INSERT INTO resident_requests
                    (event_id,ticket_id,scene_id,customer_id,created_at,updated_at) VALUES(?,?,?,?,?,?)''',
                    (event['id'], 'HELP-'+uuid.uuid4().hex[:10], scene, event['customer_id'], stamp, stamp))
            current = self.detail(event['id'])
            if analyst:
                if current['verification_status'] != 'pending' and current['support_status'] != 'open':
                    raise LabError('There is no pending customer request to review.', 409)
                self.lab.db.execute('''UPDATE resident_requests SET analyst_note=?,
                    payment_status=CASE WHEN ?='cancel' THEN 'cancelled' ELSE payment_status END,
                    verification_status=CASE WHEN verification_status='pending' THEN 'reviewed' ELSE verification_status END,
                    support_status=CASE WHEN support_status='open' THEN 'closed' ELSE support_status END WHERE event_id=?''',
                    (note, action, event['id']))
            elif action == 'cancel':
                if current['payment_status'] == 'cancelled':
                    raise LabError('This payment request is already cancelled.', 409)
                self.lab.db.execute("UPDATE resident_requests SET payment_status='cancelled',verification_status=CASE WHEN verification_status='pending' THEN 'withdrawn' ELSE verification_status END WHERE event_id=?", (event['id'],))
            elif action == 'verify':
                if current['payment_status'] == 'cancelled' or current['verification_status'] != 'none':
                    raise LabError('Verification is already submitted or this request is cancelled.', 409)
                self.lab.db.execute("UPDATE resident_requests SET verification_status='pending',verification_note=? WHERE event_id=?", (note, event['id']))
            else:
                if current['support_status'] != 'none':
                    raise LabError('A support ticket already exists for this payment.', 409)
                self.lab.db.execute("UPDATE resident_requests SET support_status='open',support_note=? WHERE event_id=?", (note, event['id']))
            self.lab.db.execute('UPDATE resident_requests SET revision=revision+1,updated_at=? WHERE event_id=?', (stamp, event['id']))
            self.lab.db.execute('INSERT INTO resident_request_actions VALUES(?,?,?,?,?,?,?)',
                                (body['request_id'], event['id'], fingerprint, actor, action, note, stamp))
            return self.detail(event['id'])

    def detail(self, event_id):
        return dict(self.lab.db.execute('SELECT r.*,e.amount_minor FROM resident_requests r JOIN financial_events e ON e.id=r.event_id WHERE r.event_id=?', (event_id,)).fetchone())
