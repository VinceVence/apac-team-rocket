"""Frozen synthetic request benchmark: distinct customers, periods and templates.

Labels are generator annotations, never agent predictions. This is a development
benchmark, not bank data or an estimate of production accuracy.
"""
import datetime as dt
import hashlib
import random
from risk_models import vector,VERSION

CORPUS_VERSION='request-corpus-v1'
BANK={
 'train':{
  'scam':[
   'Bank security here. Transfer your balance to a safe account immediately. Keep it secret from branch staff.',
   'Your account is under attack. Move funds to our secure account now and do not tell anyone.',
   'We protect your wallet. Send your savings to this temporary account and hide the reason from the teller.',
   'Finance changed our beneficiary account. Pay this new account today. Do not call the office.',
   'Use our replacement bank details for this invoice. The finance team is unavailable, so skip the callback.',
   'The supplier account has changed. Send the invoice payment here immediately without phoning our old contact.',
   'Recharge your task wallet to unlock earnings. You must deposit more money before you can withdraw.',
   'Pay a top-up today to unlock commissions. Your earned wages stay frozen until you deposit again.',
   'Your online job rewards are locked. Send an activation deposit now to release the earnings.',
   'Guaranteed returns await. Pay a withdrawal tax to this separate account to release your investment profits.',
   'Guaranteed profit is ready. Transfer the withdrawal fee first so we can release your funds.',
   'Your guaranteed investment payout is blocked. Send a separate unlocking fee to receive it.',
  ],
  'normal':[
   'I ordered these groceries and am paying the shop after receiving them.',
   'I chose to move money to my own savings account. Nobody contacted me or asked me to hide it.',
   'The supplier changed its bank account. I called the known office number and verified the new beneficiary.',
   'Security reminder: never send money to a safe account requested by a caller. Contact your bank directly.',
   'A disclosed withdrawal fee was deducted from my balance. There were no guaranteed returns or separate payment requests.',
   'I am paying an ordinary subscription that I recognized and authorized.',
   'My employer deposited my wages. I do not need to pay a deposit to withdraw earnings.',
   'This is the regular invoice to our verified supplier. I received the goods.',
   'My savings transfer was initiated by me using my known device.',
   'I verified the tuition bill with the school using the number on its official website.',
   'Our investment disclosure says returns are not guaranteed. Fees are deducted and no upfront payment is required.',
   'I contacted the merchant independently and confirmed this purchase.',
  ]},
 'validation':{
  'scam':[
   'A bank officer says transfer funds to a secure account right now and hide this from branch employees.',
   'Protect your balance: move it into our safe account immediately. Do not tell your family.',
   'Settle this invoice with the new beneficiary. Do not call to verify because the finance team is unavailable.',
   'Supplier update: new payment details today. Skip calling your regular contact and send the money now.',
   'Deposit another top-up to unlock your earnings. You cannot cash out until you recharge.',
   'Your commissions are ready but require a release deposit. Transfer more money first.',
   'Guaranteed profit can be withdrawn after you pay a separate withdrawal fee.',
   'Guaranteed returns are locked. Send a withdrawal tax to receive your investment payout.',
  ],
  'normal':[
   'I received the items and recognized the store before authorizing the payment.',
   'This safe account is my own savings account. I chose this transfer without any caller instructing me.',
   'I independently verified the new supplier bank details using our existing contact number.',
   'Do not transfer money into a safe account at the request of a stranger. This is a bank awareness message.',
   'The broker deducted a disclosed fee from my balance. It did not demand a separate transfer or promise guaranteed profit.',
   'I am paying the usual utility bill I checked in the official app.',
   'My salary has arrived. My employer does not ask for money to unlock it.',
   'We confirmed the invoice and replacement account in person with the supplier.',
  ]},
 'test':{
  'scam':[
   'To safeguard your deposits, transfer everything to the safe account we provide. Keep this secret from your branch.',
   'Urgent bank protection: move your balance to our secure account and do not tell anyone about the transfer.',
   'Pay the replacement beneficiary on this invoice. Do not call your established supplier contact.',
   'Use these new account details for payment. The finance office cannot take verification calls; pay immediately.',
   'Deposit more money to unlock commissions from your tasks. Your cash-out will stay blocked until then.',
   'Send a recharge payment first to release your wages from this online job.',
   'We guarantee your investment returns. To get the payout you must send an additional withdrawal fee.',
   'Your guaranteed profit is waiting. Make a separate transfer for withdrawal tax to release the investment.',
  ],
  'normal':[
   'The goods arrived and I approved the payment to the retailer I selected.',
   'Moving cash into a safe account that belongs to me was my own decision, with no contact from a supposed officer.',
   'Before paying the changed supplier account, I verified it using the phone number already in our records.',
   'Our bank never asks you to move funds to a safe account. Do not follow that instruction from callers.',
   'My broker charged the disclosed withdrawal fee against the balance and explicitly says returns are not guaranteed.',
   'I checked this electricity charge against my monthly bill in the provider app.',
   'The job pays wages directly; there is no deposit required to release them.',
   'The school independently confirmed both the tuition amount and the recipient account.',
  ]}}


def examples(customers):
    rows=[];starts={'train':'2026-07-01','validation':'2026-08-01','test':'2026-09-01'}
    for i,cid in enumerate(customers[:100]):
        split='train' if i<60 else 'validation' if i<80 else 'test';rng=random.Random(90971+i)
        for j in range(10):
            label=int(j in (0,3,6));kind=(i+j)%5;stamp=(dt.datetime.fromisoformat(starts[split]).replace(tzinfo=dt.timezone.utc)+dt.timedelta(days=j,hours=i%20)).isoformat()
            pool=BANK[split]['scam' if label else 'normal'];idx=(i//5+j)%len(pool)
            message=pool[idx]
            # Account-access cases differ through independently observed channel facts.
            if label and kind==4:message={'train':'A payment was initiated after a new device signed in.','validation':'A previously unseen device initiated the transfer.','test':'The transfer followed a login from a device not used before.'}[split]
            meta={'device_known':not(label and kind==4),'authorization_verified':not(label and kind==4),
                'payment_context':{'before_payment':True,'kind':'payment_request','message':message}}
            if not label and j==7:meta['device_known']=False
            if not label and j==8:meta['authorization_verified']=False
            amount=rng.randint(3000,150000);history=[{'occurred_at':(dt.datetime.fromisoformat(stamp)-dt.timedelta(days=d+1)).isoformat(),'amount_minor':rng.randint(5000,70000),'to_account':'merchant:known'} for d in range(12)]
            payee='new:request' if rng.random()<.65 else 'merchant:known'
            rows.append({'id':'REQUEST-'+cid+'-'+str(j),'customer_id':cid,'scene_id':CORPUS_VERSION,
                'event_id':'request-'+cid+'-'+str(j),'event_time':stamp,'available_at':stamp,
                'label_available_at':(dt.datetime.fromisoformat(stamp)+dt.timedelta(hours=24)).isoformat(),
                'label':label,'origin':'request_benchmark','split':split,'template_group':split+'-'+str(idx)+'-'+str(label)+'-'+str(kind==4),
                'request_text':message,'features':vector(meta,amount,history,payee,stamp),'feature_version':VERSION,
                'source_report_id':None,'review_id':None,'evidence_hash':hashlib.sha256((message+str(meta['device_known'])+str(meta['authorization_verified'])).encode()).hexdigest(),
                'quality_note':'Synthetic request corpus; disjoint customer, time and wording groups. Not production fraud outcomes.'})
    return rows
