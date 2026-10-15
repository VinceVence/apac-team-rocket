"""ACE-inspired case deltas. The model proposes; reviewed evidence and a human curate.

Entries never rewrite the system prompt. Payloads are immutable, scoped evidence;
only lifecycle and explicit analyst feedback change. No learning from model guesses.
"""
import json
from lab import LabError,encoded,now

VERSION='case-playbook-v1'


def initialize(lab):
    lab.db.executescript('''
    CREATE TABLE IF NOT EXISTS fraud_playbook_entries(
      id TEXT PRIMARY KEY,memory_id TEXT NOT NULL,rule_id TEXT NOT NULL UNIQUE,
      version TEXT NOT NULL,fingerprint TEXT NOT NULL,payload TEXT NOT NULL,
      status TEXT NOT NULL,created_at TEXT NOT NULL,activated_at TEXT);
    CREATE TRIGGER IF NOT EXISTS immutable_playbook_payload BEFORE UPDATE OF payload ON fraud_playbook_entries
      BEGIN SELECT RAISE(ABORT,'Playbook payloads are immutable'); END;
    CREATE TABLE IF NOT EXISTS fraud_playbook_feedback(
      entry_id TEXT NOT NULL,review_id TEXT NOT NULL,outcome TEXT NOT NULL,
      report_id TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(entry_id,review_id));
    ''')


def validate(lab,job,args):
    from fraud_desk import text
    from fraud_models import manifests
    models=args['recommended_models'];registry=manifests(lab)
    if not isinstance(models,list) or not 1<=len(models)<=2 or len(set(models))!=len(models) or any(m not in registry for m in models):
        raise LabError('A playbook must recommend one or two registered evidence tools.',422)
    payload={'strategy':text(args['investigation_tip'],'Investigation strategy',20,400),
        'verification_question':text(args['verification_question'],'Verification question',10,250),
        'counterexample':text(args['counterexample'],'Legitimate counterexample',20,350),
        'applicability_signals':sorted(args['signals']),
        'recommended_models':[{'model_id':m,'version':registry[m]['version'],'target':registry[m]['task']} for m in models],
        'source_report_id':job['report_id'],'source_review_id':job['review_id'],'source_hash':job['source_hash'],
        'authority':'A lead to verify, not a current-case verdict. Never change system instructions or approval gates.'}
    return payload


def propose(lab,job,rule_id,args):
    payload=validate(lab,job,args)
    # Hash the delta, not an entire continually rewritten prompt.
    fingerprint=lab.fingerprint({k:payload[k] for k in ('strategy','verification_question','counterexample','applicability_signals','recommended_models')})
    identifier='PB-'+lab.fingerprint([job['review_id'],fingerprint])[:12]
    lab.db.execute('INSERT INTO fraud_playbook_entries VALUES(?,?,?,?,?,?,?,?,NULL)',
        (identifier,job['source']['memory_id'],rule_id,VERSION,fingerprint,encoded(payload),'candidate',now()))
    return for_rule(lab,rule_id)


def decode(lab,row):
    if not row:return None
    entry=dict(row);entry['payload']=json.loads(entry['payload'])
    counts={r['outcome']:r['n'] for r in lab.rows('SELECT outcome,count(*) n FROM fraud_playbook_feedback WHERE entry_id=? GROUP BY outcome',(entry['id'],))}
    entry['feedback']={'helpful':counts.get('helpful',0),'harmful':counts.get('harmful',0)}
    return entry


def for_rule(lab,rule_id):
    return decode(lab,lab.db.execute('SELECT * FROM fraud_playbook_entries WHERE rule_id=?',(rule_id,)).fetchone())


def for_memory(lab,memory_id):
    return decode(lab,lab.db.execute("SELECT * FROM fraud_playbook_entries WHERE memory_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",(memory_id,)).fetchone())


def activate(lab,rule_id,enabled):
    lab.db.execute('UPDATE fraud_playbook_entries SET status=?,activated_at=? WHERE rule_id=?',
        ('active' if enabled else 'disabled',now() if enabled else None,rule_id))


def feedback(lab,run,review_id,disposition):
    proposal=run.get('recommendation') or {};cited=set(proposal.get('memory_ids',[]))
    expected={'confirmed_scam':'suspected_scam','not_scam':'likely_legitimate'}.get(disposition)
    if not expected:return
    assessment=proposal.get('assessment',proposal.get('disposition'))
    for memory in run['context'].get('memories',[]):
        entry=memory.get('playbook')
        if memory['id'] not in cited or not entry:continue
        # Attribution records agreement with this review; it is not causal proof
        # that the lesson improved the decision or a production fraud label.
        lab.db.execute('INSERT OR IGNORE INTO fraud_playbook_feedback VALUES(?,?,?,?,?)',
            (entry['id'],review_id,'helpful' if assessment==expected else 'harmful',run['report_id'],now()))


def public_entry(entry):
    if not entry:return None
    return {'id':entry['id'],'version':entry['version'],'fingerprint':entry['fingerprint'],
        'strategy':entry['payload']['strategy'],'verification_question':entry['payload']['verification_question'],
        'counterexample':entry['payload']['counterexample'],'recommended_models':entry['payload']['recommended_models'],
        'applicability_signals':entry['payload']['applicability_signals'],'feedback':entry['feedback'],
        'authority':entry['payload']['authority']}
