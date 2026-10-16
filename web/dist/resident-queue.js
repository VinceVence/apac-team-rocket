import {formatPesos} from './resident-phone.js';
import {residentLabel} from './resident-sprites.js';

// The demo's explicit analyst controls, separate from resident assertions.
export function renderResidentQueue(parent,requests,{sceneId,replay,onReview,onRefresh}){
  parent.hidden=!!replay;
  if(replay)return;
  const key=JSON.stringify([sceneId,requests]);if(parent.dataset.receipts===key)return;
  parent.dataset.receipts=key;parent.replaceChildren();
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  const head=el('header'),title=el('div');title.append(el('span','Fraud Analyst · simulation','eyebrow'),el('h2','Customer follow-up'));
  const refresh=el('button','Refresh requests','text-button');refresh.type='button';
  const notice=el('p');notice.setAttribute('role','status');
  refresh.onclick=async()=>{refresh.disabled=true;try{await onRefresh();notice.textContent='Status updated.'}catch(e){notice.textContent=e.message}finally{refresh.disabled=false}};
  head.append(title,refresh);parent.append(head,el('p','Review resident verification and support requests. These controls save a demo analyst response; they cannot release a payment.'),notice);
  if(!requests.length){parent.append(el('p','No customer follow-up requests yet.'));return}
  for(const request of requests){
    const item=el('article',undefined,'resident-request'),pending=request.verification_status==='pending'||request.support_status==='open';
    item.append(el('h3',residentLabel(request.customer_id)+' · '+formatPesos(request.amount_minor)),el('small',request.ticket_id+' · '+(request.payment_status==='cancelled'?'Cancelled':'Held before debit')));
    for(const [label,text] of [['Verification',request.verification_note],['Support',request.support_note],['Analyst response',request.analyst_note]]){
      if(text){const row=el('div');row.append(el('strong',label),el('p',text));item.append(row)}
    }
    if(pending){
      const form=el('form'),label=el('label','Analyst response'),note=el('textarea');note.rows=2;note.required=true;note.minLength=10;note.maxLength=600;label.append(note);
      const choices=el('label','Outcome'),select=el('select');
      for(const [value,text] of [['keep_held',request.payment_status==='cancelled'?'Close support; keep cancelled':'Keep payment held'],['cancel','Cancel payment request']]){const option=el('option',text);option.value=value;select.append(option)}choices.append(select);
      const submit=el('button','Save demo analyst review','primary-button');submit.type='submit';const error=el('p');error.setAttribute('role','alert');
      form.append(label,choices,submit,error);form.onsubmit=async event=>{
        event.preventDefault();if(!form.reportValidity())return;submit.disabled=true;
        try{await onReview({scene_id:sceneId,event_id:request.event_id,expected_revision:request.revision,request_id:crypto.randomUUID(),action:select.value,note:note.value.trim()})}
        catch(e){error.textContent=e.message+' Refresh requests to check the saved status.';submit.disabled=false}
      };item.append(form);
    }else item.append(el('p','No pending follow-up.'));
    parent.append(item);
  }
}
