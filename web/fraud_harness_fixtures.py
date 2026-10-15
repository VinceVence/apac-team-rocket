"""Deterministic offline choices for exercising the real harness, not AI accuracy."""
import re
from fraud_desk import LESSON,QUESTION


def choose(packet):
    if packet['active_role']!='case_lead':
        missing=any(r['status'] in ('not_available','partial') for r in packet['model_receipts'])
        summaries={
            'transaction_specialist':'The transfer and recipient are recorded, but the supplier identity and changed payment instructions require an independent callback.',
            'device_specialist':'Device and authorization signals warrant checking account access. They do not identify who controlled the device; request independent login evidence.',
            'scam_specialist':'A familiar authorized device does not settle whether the payment request was deceptive. Keep the allegation separate from observed records.',
            'resolution_critic':'The records support a reviewable suspicion, not a guaranteed recovery or proven liability. Distinguish reported withdrawal demands from an ordinary investment loss.'}
        return 'return_finding',{'assessment':'inconclusive' if missing else 'supports',
            'summary':summaries[packet['active_role']],
            'evidence_ids':packet['event_ids'],'receipt_ids':[r['receipt_id'] for r in packet['model_receipts']],
            'uncertainties':['Caller identity and intent are not independently established.'],
            'next_question':'Did you verify the request using an independently obtained contact?',
            'purpose':'Check the proposed interpretation against its scoped evidence.'}
    observed={o['tool']:o['result'] for o in packet['observations']}
    if 'get_case_evidence' not in observed:return 'get_case_evidence',{'purpose':'Verify the reported transfer and its case-bound context.'}
    narrative=' '.join([packet['story'],packet['message_transcript']]+[a['text'] for a in packet['customer_replies']]).lower()
    device_issue=any(t.get('device_known') is False or t.get('authorization_recorded') is False for t in observed['get_case_evidence']['transactions'])
    suspected=device_issue or any(k in narrative for k in ('safe account','unlock earnings','unlock your earnings','withdrawal fee','withdrawal tax','do not call','new beneficiary'))
    legitimate=any(k in narrative for k in ('received my items','recognized the merchant','groceries','independently verified','verified with','legitimate')) and not suspected
    if 'score_models' not in observed:
        models=['device_integrity_v1','payment_velocity_v1'] if device_issue else ['device_integrity_v1','message_intent_v1']
        return 'score_models',{'model_ids':models,'event_ids':packet['event_ids'],'purpose':'Test the relevant device, transaction or payment-request signals.'}
    receipts=observed['score_models']['receipts'];ids=[r['receipt_id'] for r in receipts]
    if not suspected and not legitimate and not packet['customer_replies']:
        return 'ask_customer',{'question':'Who requested the payment, and did you receive the goods or verify the recipient independently?','purpose':'Resolve the missing transaction purpose before a conclusion.'}
    if suspected and packet.get('experiment_arm')!='single' and not packet.get('delegation_used') and packet['remaining_generations']>=4:
        role='device_specialist' if device_issue else 'transaction_specialist' if any(k in narrative for k in ('invoice','supplier')) else 'resolution_critic' if 'withdrawal tax' in narrative or 'withdrawal fee' in narrative else 'scam_specialist'
        return 'delegate_question',{'role':role,'question':{'device_specialist':'What does the observed device and authorization evidence establish, and which login facts are missing?', 'transaction_specialist':'Do the payment and recipient records establish the supplier identity, or is independent verification missing?', 'scam_specialist':'Does recorded authorization resolve the reported deception, and what legitimate alternatives remain?', 'resolution_critic':'Challenge the proposed suspicion: does this indicate investment deception or an ordinary loss, and what is unverified?'}[role],
            'evidence_ids':packet['event_ids'],'receipt_ids':ids,'purpose':'Get a scoped second interpretation of the unresolved mechanism.'}
    if packet.get('reviewed_memory_count') and 'search_reviewed_cases' not in observed and packet['remaining_generations']>=3:
        return 'search_reviewed_cases',{'query':'safe_account impersonation pressure secrecy','purpose':'Compare only analyst-reviewed lessons with this case.'}
    memories=observed.get('search_reviewed_cases',{}).get('matches',[])
    return 'submit_case_resolution',{'assessment':'suspected_scam' if suspected else 'likely_legitimate' if legitimate else 'needs_information',
        'summary':'Recorded transfers and the customer report warrant an analyst investigation. Authorization alone does not establish informed intent.' if suspected else 'The available records do not independently establish fraud; verify the customer account before deciding.',
        'evidence_ids':packet['event_ids'],'receipt_ids':ids,'memory_ids':[m['id'] for m in memories],
        'uncertainties':['Caller identity and testimony require independent verification.'],
        'questions':['Was the request verified through an independent official contact?'] if suspected else [],
        'action':'request_recall' if suspected else 'support_followup','customer_message':'Your report is ready for human review. Recovery is not guaranteed.',
        'lesson':LESSON,'followup_question':QUESTION,'purpose':'Present the scoped evidence, findings and limitations for human review.'}
