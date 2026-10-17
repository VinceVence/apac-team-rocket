// Receipt-driven customer UI. Mutations are injected by the current-world app; replay stays read-only.
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
  const base={moment,replay:!!demo.replay,sceneId:demo.scene_id,mode:demo.replay?'Recorded demo':'Synthetic demo',customerId:source?.customer_id||customer,
    message:messageOf(source)||report?.message||null,amount:source?.amount_minor,payee:source?.to_account,
    eventId:source?.id,settled:source?.status==='settled',reportId:report?.id||demo.focus_report_id};
  if(moment==='repeat')return {...base,customerId:'C002',message:base.message,
    amount:undefined,payee:undefined,eventId:undefined,preview:true};
  if(moment==='protected')return {...base,customerId:held?.customer_id||'C002',message:messageOf(held)||null,
    amount:held?.amount_minor,payee:held?.to_account,eventId:held?.id,held:!!held,workflow:!demo.replay?(data.resident_requests||[]).find(r=>r.event_id===held?.id):null,changedRecipient:!!held&&!!source?.to_account&&held.to_account!==source.to_account,
    reason:matchedRule?.explanation||held?.reason||held?.metadata?.prevention_reason||null,
    ruleName:matchedRule?.name,verification:playbook?.verification_question||'Did you verify this request using a contact you found independently?',
    counterexample:playbook?.counterexample||null,ruleId:matchedRule?.id,
    attribution:relatedHold?.rule_ids?.length?'From your Mint Town safeguard, learned from a reviewed case.':'From your Mint Town recipient watch, based on an analyst-reviewed case.'};
  if(moment==='payment-sent')return {...base,customerId:sent?.customer_id||'C002',amount:sent?.amount_minor,
    payee:sent?.to_account,eventId:sent?.id,message:messageOf(sent)||null,settled:!!sent};
  return base;
}

export function residentActions(story){
  if(story.replay||!story.held||!story.eventId||!story.sceneId)return [];
  const w=story.workflow||{},actions=[];
  if(w.payment_status!=='cancelled'){
    actions.push('cancel');if(!w.verification_status||w.verification_status==='none')actions.push('verify');
  }
  if(!w.support_status||w.support_status==='none')actions.push('support');
  return actions;
}

export function residentActionPayload(story,action,note,requestId){
  if(!residentActions(story).includes(action))throw Error('This action is unavailable. Refresh the payment status.');
  return {scene_id:story.sceneId,event_id:story.eventId,expected_revision:story.workflow?.revision||0,request_id:requestId,action,note};
}

export function renderResidentPhone(parent,story,{onAction,onRefresh}={}){
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
      const actions=el('div',undefined,'phone-actions');card.append(actions);
      function drawActions(){
        actions.replaceChildren();const w=story.workflow||{};
        const cancelled=w.payment_status==='cancelled';
        card.querySelector('h3').textContent=cancelled?'Payment request cancelled':'We paused this payment';
        card.querySelector('.phone-result-icon').textContent=cancelled?'✓':'Ⅱ';
        card.querySelector(':scope > p').textContent=cancelled?'No money was debited. This request is closed.':'No money was debited. Verify independently.';
        question.hidden=cancelled;
        const status=el('div',undefined,'phone-advice');status.setAttribute('role','status');
        if(w.payment_status==='cancelled')status.append(el('strong','Cancelled · no money sent'),el('p','This request is closed. The original hold receipt is preserved.'));
        if(w.verification_status==='pending')status.append(el('strong','Verification submitted'),el('p','Waiting for analyst review. Your payment remains held.'));
        if(w.verification_status==='reviewed')status.append(el('strong','Verification reviewed'));
        if(w.support_status!=='none'&&w.support_status)status.append(el('strong',w.ticket_id),el('p',w.support_status==='open'?'Support ticket saved in the simulation’s analyst queue.':'Support ticket closed by the demo analyst.'));
        if(w.analyst_note)status.append(el('strong','Analyst response'),el('p',w.analyst_note));
        if(status.childNodes.length)actions.append(status);
        if(story.replay||!onAction){actions.append(el('small','Recorded view · customer actions are available in a current-world demo.','phone-action-note'));return}
        for(const action of residentActions(story)){
          const label={cancel:'Cancel payment',verify:'Submit verification',support:'Contact Mint Town support'}[action];
          const button=el('button',label,action==='cancel'?'primary-button':'phone-text-button');button.type='button';
          button.onclick=()=>showForm(action);actions.append(button);
        }
        if(onRefresh){const refresh=el('button','Refresh payment status','phone-text-button');refresh.type='button';refresh.onclick=async()=>{refresh.disabled=true;try{story={...story,workflow:await onRefresh(story.eventId)};drawActions()}catch(e){refresh.textContent=e.message;refresh.disabled=false}};actions.append(refresh)}
        actions.append(el('small','Synthetic wallet · requests are saved for the demo analyst. Verification does not release money.','phone-action-note'));
      }
      function showForm(action){
        actions.querySelector('form')?.remove();
        const form=el('form',undefined,'phone-action-form');
        const label=el('label',action==='verify'?'How did you independently verify this request?':action==='support'?'What do you need help with?':'Cancel this payment request?');
        const input=el('textarea');input.rows=3;input.maxLength=600;input.minLength=10;input.required=true;
        if(action!=='cancel'){label.append(input);form.append(label,el('small','Use fictional details. Never enter a PIN, OTP or password.'))}
        else form.append(label,el('p','No money will be sent. You can still contact support.'));
        const submit=el('button',action==='cancel'?'Confirm cancellation':'Send request','primary-button');submit.type='submit';
        const back=el('button','Back','phone-text-button');back.type='button';back.onclick=()=>{form.remove();actions.querySelector('button')?.focus()};
        const notice=el('p',undefined,'phone-form-error');notice.setAttribute('role','alert');
        form.append(submit,back,notice);actions.append(form);(action==='cancel'?submit:input).focus();
        form.onsubmit=async event=>{
          event.preventDefault();if(!form.reportValidity())return;
          const payload=residentActionPayload(story,action,action==='cancel'?'':input.value.trim(),crypto.randomUUID());
          actions.querySelectorAll('button,textarea').forEach(n=>n.disabled=true);notice.textContent='Saving…';
          try{story={...story,workflow:await onAction(payload)};drawActions();actions.querySelector('[role="status"]')?.scrollIntoView({block:'nearest'});screen.focus({preventScroll:true})}
          catch(e){notice.textContent=e.message+' Check the current status before trying again.';actions.querySelectorAll('button,textarea').forEach(n=>n.disabled=false)}
        };
      }
      drawActions();
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
