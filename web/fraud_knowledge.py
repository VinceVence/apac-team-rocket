"""Scoped lifecycle for human-reviewed lessons; no automatic prompt rewriting."""
import datetime as dt
import json
import re
from lab import LabError,encoded,now

VERSION='reviewed-lesson-v1'


def initialize(lab):
    lab.db.execute('''CREATE TABLE IF NOT EXISTS fraud_lesson_controls(memory_id TEXT PRIMARY KEY,
      version TEXT NOT NULL,applicability TEXT NOT NULL,counterexamples TEXT NOT NULL,
      source_receipts TEXT NOT NULL,expires_at TEXT NOT NULL,revoked_at TEXT,revocation_reason TEXT)''')
    lab.db.commit()


def publish(lab,memory_id,pattern,run):
    source=[r['id'] for r in lab.rows('SELECT id FROM fraud_model_receipts WHERE report_id=? AND snapshot_hash=?',(run['report_id'],run['context'].get('snapshot_hash')))] if lab.db.execute("SELECT 1 FROM sqlite_master WHERE name='fraud_model_receipts'").fetchone() else []
    scope={'signals':pattern.get('cues',[]),'source_event_ids':pattern['evidence_ids'],
        'requirement':'Verify the current request and recipient; the previous case is a lead, not proof.'}
    counterexamples=['A normal purchase with independently verified recipient and delivered goods.',
        'A familiar device alone does not prove consent or rule out a deceptive request.']
    expiry=(dt.datetime.fromisoformat(now())+dt.timedelta(days=7)).isoformat()
    lab.db.execute('INSERT INTO fraud_lesson_controls VALUES(?,?,?,?,?,?,NULL,NULL)',
        (memory_id,VERSION,encoded(scope),encoded(counterexamples),encoded(source),expiry))


def lifecycle(lab,memory):
    row=lab.db.execute('SELECT * FROM fraud_lesson_controls WHERE memory_id=?',(memory['id'],)).fetchone()
    if row:
        data=dict(row)
        for k in ('applicability','counterexamples','source_receipts'):data[k]=json.loads(data[k])
    else:
        data={'version':'legacy-reviewed-recipient-v1','applicability':{'signals':memory['pattern'].get('cues',[]),'requirement':'Legacy reviewed recipient watch; verify applicability.'},
            'counterexamples':['Unrelated verified purchases.'],'source_receipts':[],
            'expires_at':(dt.datetime.fromisoformat(memory['created_at'])+dt.timedelta(days=7)).isoformat(),'revoked_at':None,'revocation_reason':None}
    data['active']=not data['revoked_at'] and data['expires_at']>now() and memory['validation'].get('passed') is True
    return data


def revoke(lab,memory_id,reason):
    if not isinstance(memory_id,str) or not isinstance(reason,str) or not 10<=len(reason.strip())<=500:raise LabError('Provide a lesson ID and a 10–500 character review reason.')
    row=lab.db.execute('SELECT * FROM scam_memories WHERE id=?',(memory_id,)).fetchone()
    if not row:raise LabError('Reviewed lesson not found.',404)
    memory=dict(row)
    for k in ('pattern','validation'):memory[k]=json.loads(memory[k])
    status=lifecycle(lab,memory)
    if status['revoked_at']:return status
    if not lab.db.execute('SELECT 1 FROM fraud_lesson_controls WHERE memory_id=?',(memory_id,)).fetchone():
        lab.db.execute('INSERT INTO fraud_lesson_controls VALUES(?,?,?,?,?,?,NULL,NULL)',
            (memory_id,status['version'],encoded(status['applicability']),encoded(status['counterexamples']),encoded(status['source_receipts']),status['expires_at']))
    lab.db.execute('UPDATE fraud_lesson_controls SET revoked_at=?,revocation_reason=? WHERE memory_id=?',(now(),reason.strip(),memory_id))
    if lab.db.execute("SELECT 1 FROM sqlite_master WHERE name='prevention_rules'").fetchone():
        lab.db.execute("UPDATE prevention_rules SET status='revoked' WHERE memory_id=?",(memory_id,))
    return lifecycle(lab,memory)


def redact(desk,memory):
    report=desk.report(memory['source_report_id']);name=desk.lab.db.execute('SELECT name FROM customers WHERE id=?',(report['customer_id'],)).fetchone()[0]
    controls=memory.get('lifecycle') or lifecycle(desk.lab,memory)
    clean=lambda value:re.sub(r'\bC\d{3}\b','[customer]',value.replace(name,'[prior customer]'))
    return {'id':memory['id'],'source_report_id':memory['source_report_id'],'review_id':memory['review_id'],
        'lesson':clean(memory['lesson']),'next_question':clean(memory['next_question']),
        'applicability':controls['applicability'],'counterexamples':controls['counterexamples'],
        'version':controls['version'],'expires_at':controls['expires_at']}
