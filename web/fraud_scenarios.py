"""Five synthetic, source-grounded cases. Expected outcomes never enter model context."""
import uuid

from lab import LabError, encoded

SCENARIOS = {
    'phishing': {
        'title':'Bank impersonation', 'customer':'C001', 'payee':'external:r-1041', 'count':1, 'amount':90000,
        'focus':'Recorded authorization does not establish informed intent.',
        'source_url':'https://consumer.ftc.gov/consumer-alerts/2024/03/never-move-your-money-protect-it-thats-scam',
        'device_known':True, 'authorization_verified':True,
        'story':'A caller claiming to be bank support told me to transfer money to a safe account immediately. I approved it on my phone. The caller then disappeared. I am worried about my savings.',
        'message':'Bank security: urgently move funds to the safe account. Keep it secret from branch staff.',
        'reply':'The caller claimed to be bank support, supplied the recipient, and said to keep it secret. I did not independently contact the bank.',
        'control_story':'I moved money to my own savings account using my usual phone. I independently opened my banking app. Nobody called or asked me to protect my money. I recognize the transfer.',
        'control_message':'Your scheduled savings transfer was received.',
        'control_reply':'I own both accounts and initiated this transfer. There was no caller, security warning, or request to keep it secret.',
    },
    'payment_burst': {
        'title':'Account takeover', 'customer':'C004', 'payee':'external:r-2198', 'count':3, 'amount':14000,
        'focus':'A burst is a signal; device records and customer intent distinguish takeover from normal spending.',
        'source_url':'https://www.ic3.gov/PSA/2025/PSA251125',
        'device_known':False, 'authorization_verified':False,
        'story':'Someone claiming to be bank support urgently asked for a login code to protect my money. Three unrecognized payments then left my wallet within seconds. I received a password reset notice and saw an unknown device. I did not authorize these transfers and still have my phone.',
        'message':'Security notice: password reset completed and a new device signed in.',
        'reply':'I did not reset my password, enroll a device, or approve the payments. Nobody else has permission to use my wallet.',
        'control_story':'I made three quick purchases at a market on my usual phone. I recognize the merchant and received my items. The repeated notifications worried me, but all purchases appear on my receipts.',
        'control_message':'Three purchases were authorized on your registered device.',
        'control_reply':'I made all three purchases, recognize the merchant, and received my items. My device has not changed.',
    },
    'invoice_redirect': {
        'title':'Invoice redirection', 'customer':'C006', 'payee':'external:r-3072', 'count':1, 'amount':110000,
        'focus':'Check a changed beneficiary independently; a successful PIN is not supplier verification.',
        'source_url':'https://www.fbi.gov/how-we-can-help-you/common-frauds-and-scams/business-email-compromise',
        'device_known':True, 'authorization_verified':True,
        'story':'An email in our supplier conversation said the invoice must be paid to a new account immediately. I paid from my usual device. The supplier called using our saved number and said its payment details had not changed and it had received nothing.',
        'message':'Updated invoice: our account has changed. Pay the new beneficiary today. Do not call the office because the finance team is unavailable.',
        'reply':'The saved supplier phone contact confirmed the bank details had not changed. I still have the original invoice and the email with the replacement beneficiary.',
        'control_story':'Our supplier changed its bank account. Before paying, I independently called its long-standing phone number and verified the new details. I recognize the merchant and received my items and a payment receipt.',
        'control_message':'Updated invoice and beneficiary details, independently confirmed through the saved supplier contact.',
        'control_reply':'I used the saved phone number from before the email, verified the change, and received the goods and receipt.',
    },
    'task_scam': {
        'title':'Task / job scam', 'customer':'C007', 'payee':'external:r-4083', 'count':3, 'amount':25000,
        'amounts':(15000,25000,50000),
        'focus':'Distinguish pay-to-unlock earnings from payment for a genuine service.',
        'source_url':'https://consumer.ftc.gov/consumer-alerts/2024/11/task-scams-create-illusion-making-money',
        'device_known':True, 'authorization_verified':True,
        'story':'A recruiter offered paid product-rating tasks. The site displayed commissions but required progressively larger deposits to unlock earnings. I made three deposits and now cannot withdraw my commission unless I pay again.',
        'message':'Your task balance is negative. Recharge immediately to unlock earnings and withdraw your commission. One final deposit completes the job.',
        'reply':'I had to pay my own money to withdraw supposed wages. No commission reached my bank account, and the site demands another deposit.',
        'control_story':'I bought three optional training lessons from an established school. I recognize the merchant and received my items: course access and invoices. No job, commission, or earnings withdrawal was promised.',
        'control_message':'Your training course payments were received. No employment or income is guaranteed.',
        'control_reply':'These were course purchases, not deposits to release wages. I received all lessons and was never promised a job.',
    },
    'investment_scam': {
        'title':'Investment / advance-fee scam', 'customer':'C008', 'payee':'external:r-5094', 'count':2, 'amount':60000,
        'amounts':(80000,20000),
        'focus':'Separate an investment loss from guaranteed-return claims and demands for a withdrawal fee.',
        'source_url':'https://consumer.ftc.gov/articles/investment-scams',
        'device_known':True, 'authorization_verified':True,
        'story':'Someone on social media promised guaranteed returns through an investment app. After I deposited money it displayed a profit. To withdraw, support demanded a separate withdrawal tax. I paid it, but they still refuse to release my investment and now want another fee.',
        'message':'Guaranteed returns. Send a separate withdrawal tax payment today to release your investment profits. Further fees may apply.',
        'reply':'No withdrawal arrived. The same contact controls support and keeps asking for new payments outside the app before releasing funds.',
        'control_story':'I made two voluntary contributions through my established investment provider. My investment fell in value. I verified the statement through the provider independently; there were no guaranteed returns and no separate payment required to withdraw.',
        'control_message':'Your portfolio value can rise or fall. The statement lists your contributions and disclosed account fees.',
        'control_reply':'This is a market loss shown on a statement, not an unrecognized transfer. I verified the provider independently and can withdraw without making a new deposit.',
    },
}


def catalogue():
    return [{'id':key,**{k:spec[k] for k in ('title','focus','source_url')}} for key,spec in SCENARIOS.items()]


def create_scenario(desk, scenario, request_id):
    control=scenario.endswith('.control');key=scenario.removesuffix('.control')
    if key not in SCENARIOS:raise LabError('Choose a scenario from the catalogue.')
    spec=SCENARIOS[key];payload={'scenario':scenario}
    with desk.lab.lock,desk.lab.db:
        previous=desk.existing_request(request_id,payload)
        if previous:return previous
        cid=spec['customer'];payee='m1' if control else spec['payee']
        amounts=spec.get('amounts',(spec['amount'],)*spec['count'])
        balance=desk.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(cid+':wallet',)).fetchone()[0]
        if balance<sum(amounts):raise LabError('Insufficient simulator funds for this complete case fixture.',409)
        desk.lab.db.execute('INSERT OR IGNORE INTO accounts(id,label,kind,opening_minor,balance_minor) VALUES(?,?,?,0,0)',
                            (payee,'Synthetic transfer recipient','counterparty'))
        events=[]
        for n,amount in enumerate(amounts):
            eid='reported-payment-'+uuid.uuid4().hex[:12];events.append(eid)
            metadata={'device_id':'device-'+cid if control or spec['device_known'] else 'unrecognized-device',
                      'device_known':True if control else spec['device_known'],
                      'authorization_verified':True if control else spec['authorization_verified'],
                      'authorized_payee':payee,'rail':'Wallet','review_flags':desk.screen(cid,payee)}
            desk.lab.post(eid,cid,'payment',amount,desk.lab.clock_day,cid+':wallet',payee,metadata)
            desk.lab.db.execute('UPDATE financial_events SET occurred_at=? WHERE id=?',
                (desk.lab.clock_day+'T10:%02d:%02dZ'%(0 if key=='payment_burst' else n,n*4 if key=='payment_burst' else 0),eid))
        prefix='control_' if control else ''
        return desk._create(cid,spec[prefix+'story'],spec[prefix+'message'],events,request_id,encoded(payload))
