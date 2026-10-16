// Customer presentation only: recorded evidence in, no requests or payment mutations out.
import {residentLabel} from './resident-sprites.js';

export const formatPesos=minor=>Number.isSafeInteger(minor)&&minor>=0
  ?new Intl.NumberFormat('en-PH',{style:'currency',currency:'PHP',minimumFractionDigits:2}).format(minor/100):'Amount unavailable';
const messageOf=event=>event?.metadata?.payment_context?.message;
function eventIds(value){try{const ids=typeof value==='string'?JSON.parse(value):value;return Array.isArray(ids)?ids:[]}catch{return []}}

export function residentPhoneStory(moment,data,detail){
  const demo=data?.demo||{},report=detail?.id===demo.focus_report_id?detail:null;
  const events=data?.events||[],customer=demo.focus_customer_id;
  const incident=demo.incidents?.find(i=>i.report_id===demo.focus_report_id);
  const ids=eventIds(incident?.event_ids);
  const source=report?.transactions?.[0]||events.find(e=>e.customer_id===customer&&ids.includes(e.id));
  const relatedHold=demo.focus_report_id&&demo.protection?.recent?.find(e=>e.source_report_id===demo.focus_report_id);
  const heldEvent=relatedHold&&events.find(e=>e.id===relatedHold.id);
  const held=relatedHold&&(!heldEvent?relatedHold:heldEvent.kind==='payment_blocked'&&heldEvent.status==='blocked'&&heldEvent.customer_id===relatedHold.customer_id?heldEvent:null);
  const proof=demo.incidents?.find(i=>i.status==='passed'&&i.kind==='control');
  const proofIds=eventIds(proof?.event_ids);
  const sent=held&&events.find(e=>e.customer_id===held.customer_id&&e.kind==='payment'&&e.status==='settled'&&
    proofIds.includes(e.id));
  const rule=report?.prevention?.rule;
  const matchedRule=held&&rule?.status==='active'&&rule.replay?.passed&&relatedHold.rule_ids?.includes(rule.id)?rule:null;
  const entry=report?.prevention?.playbook;
  const playbook=matchedRule&&entry?.status==='active'&&entry.rule_id===matchedRule.id?entry.payload:null;
  const base={moment,mode:demo.replay?'Recorded demo':'Synthetic demo',customerId:source?.customer_id||customer,
    message:messageOf(source)||report?.message||null,amount:source?.amount_minor,payee:source?.to_account,
    eventId:source?.id,settled:source?.status==='settled',reportId:report?.id||demo.focus_report_id};
  if(moment==='repeat')return {...base,customerId:'C002',message:base.message,
    amount:undefined,payee:undefined,eventId:undefined,preview:true};
  if(moment==='protected')return {...base,customerId:held?.customer_id||'C002',message:messageOf(held)||null,
    amount:held?.amount_minor,payee:held?.to_account,eventId:held?.id,held:!!held,changedRecipient:!!held&&!!source?.to_account&&held.to_account!==source.to_account,
    reason:matchedRule?.explanation||held?.reason||held?.metadata?.prevention_reason||null,
    ruleName:matchedRule?.name,verification:playbook?.verification_question||'Did you verify this request using a contact you found independently?',
    counterexample:playbook?.counterexample||null,ruleId:matchedRule?.id,
    attribution:relatedHold?.rule_ids?.length?'From your Mint Town safeguard, learned from a reviewed case.':'From your Mint Town recipient watch, based on an analyst-reviewed case.'};
  if(moment==='payment-sent')return {...base,customerId:sent?.customer_id||'C002',amount:sent?.amount_minor,
    payee:sent?.to_account,eventId:sent?.id,message:messageOf(sent)||null,settled:!!sent};
  return base;
}

const advice={
  cancel:['Leave this request unpaid','Stop following the sender’s instructions. This payment remains held, with no money sent.'],
  verified:['Independent verification comes first','Use an official contact you found yourself, away from this message. A confirmation here does not release the payment.'],
  support:['Get help safely','Open support from your wallet’s official help menu. Never share your PIN, OTP or password. No support request has been sent from this demo.'],
};

export function renderResidentPhone(parent,story){
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  const phone=el('article',undefined,'resident-phone');phone.setAttribute('aria-label',residentLabel(story.customerId||'C001')+' phone');
  phone.dataset.moment=story.moment;
  const top=el('div',undefined,'phone-status');top.append(el('span','Mint Town'),el('span',story.mode));
  const header=el('header',undefined,'phone-header');header.append(el('span','M','phone-avatar'),el('div',residentLabel(story.customerId||'C001')),el('span','Wallet','phone-wallet-label'));
  const screen=el('div',undefined,'phone-screen');screen.tabIndex=0;screen.setAttribute('aria-label','Scrollable wallet screen');
  const message=()=>{const thread=el('section',undefined,'phone-thread');thread.append(el('small',story.preview?'Example from the reviewed request':'Incoming payment request · unverified sender'),el('p',story.message||'No message was recorded for this payment.','phone-message'));screen.append(thread)};
  const receipt=(title,status,copy)=>{
    const card=el('section',undefined,'phone-receipt '+status);card.append(el('span',status==='held'?'Ⅱ':status==='sent'?'✓':'↗','phone-result-icon'),el('h3',title));
    if(story.amount!==undefined)card.append(el('strong',formatPesos(story.amount),'phone-amount'));
    if(story.payee){
      const recipient=story.payee.startsWith('external:')?(story.changedRecipient?'a different external wallet':'an external wallet'):/^C\d{3}:wallet$/.test(story.payee)?residentLabel(story.payee.split(':')[0]):/^m\d+$/.test(story.payee)?'a town merchant':'the recorded recipient';
      card.append(el('small','To '+recipient,'phone-payee'));
    }
    card.append(el('p',copy));screen.append(card);return card;
  };
  if(story.moment==='protected'){
    if(!story.held)receipt('Waiting for the payment check','pending','A hold receipt has not arrived.');
    else{
      const card=receipt('We paused this payment','held','No money was debited. Verify independently.');
      const question=el('div',undefined,'phone-question');question.append(el('small','Before you continue'),el('p',story.verification));card.append(question);
      const why=el('details',undefined,'phone-why');why.append(el('summary','Why this was paused'),el('p',story.reason||'A reviewed payment safeguard requested verification.'));
      if(story.counterexample)why.append(el('p',story.counterexample));card.append(why);
      const actions=el('div',undefined,'phone-actions'),response=el('div',undefined,'phone-advice');response.hidden=true;response.setAttribute('role','status');
      for(const [action,label] of [['cancel','Cancel payment'],['verified','I verified through an official contact'],['support','Contact Mint Town support']]){
        const button=el('button',label,action==='cancel'?'primary-button':'phone-text-button');button.type='button';
        button.onclick=()=>{response.replaceChildren(el('strong',advice[action][0]),el('p',advice[action][1]),el('small','Demo guidance · the saved payment remains held.'));response.hidden=false};actions.append(button);
      }
      card.append(actions,response,el('small','Interactive demo guidance. These controls do not change a payment.','phone-action-note'));
      screen.append(el('p',story.attribution,'phone-attribution'));
    }
  }else if(story.moment==='payment-sent'){
    receipt(story.settled?'Payment sent':'Waiting for a payment receipt',story.settled?'sent':'pending',story.settled?'Your ordinary purchase completed. The safeguard allowed this payment.':'No completed control payment is recorded.');
    if(story.message)screen.append(el('p',story.message,'phone-purchase-note'));
  }else{
    message();
    if(story.moment==='payment')receipt(story.settled?'Payment sent':'Payment status unavailable',story.settled?'sent':'pending',story.settled?'This earlier transfer settled before the new safeguard was learned.':'Read the recorded payment status before drawing a conclusion.');
    if(story.moment==='complaint'||story.moment==='report'){
      const card=el('section',undefined,'phone-report');card.append(el('span','!','phone-report-icon'),el('h3','I think I was scammed'),el('p','The resident reported this transfer. The complaint is a claim for the agent to investigate.'),el('small',story.reportId?'Report saved · '+story.reportId:'Report details unavailable'));screen.append(card);
    }
    if(story.moment==='message'||story.moment==='repeat'){
      const note=el('div',undefined,'phone-request-note');note.append(el('small',story.preview?'A similar request · before the gateway check':'Before learning'),el('p',story.preview?'Next checks a similar attempt against the approved protection.':'Read the sender’s request. This scene shows the message before the resident’s later complaint.'));screen.append(note);
    }
  }
  const foot=el('footer',undefined,'phone-footer');foot.append(el('span',story.moment==='protected'?'Scroll for verification options ↓':story.eventId?'Recorded payment receipt':'Synthetic customer scene'),el('i',undefined,'phone-home'));
  phone.append(top,header,screen,foot);parent.append(phone);return phone;
}
