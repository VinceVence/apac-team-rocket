export function createFraudUI({$,api,state,setPlaying,setBusy,refresh,error,focusCustomer}){
  let dashboard=null,report=null,working=false;
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node};
  const money=value=>'₱'+(value/100).toLocaleString('en-PH',{maximumFractionDigits:2});
  const names={reported:'Report received',investigating:'Investigation in progress',awaiting_review:'Analyst review',awaiting_customer:'Waiting for customer',needs_review:'Manual review needed',resolved:'Resolution recorded'};
  function actions(){
    const confirmed=$('fraud-disposition').value==='confirmed_scam';
    $('fraud-publish').disabled=!confirmed;$('fraud-lesson').disabled=!confirmed;$('fraud-question').disabled=!confirmed;
    if(!confirmed){$('fraud-publish').checked=false;$('fraud-action').value='support_followup'}
    $('fraud-action').querySelector('[value=request_recall]').disabled=!confirmed;
  }
  function transactions(){
    $('fraud-event').replaceChildren();
    for(const t of dashboard.transactions.filter(t=>t.customer_id===$('fraud-customer').value))$('fraud-event').add(new Option(`${money(t.amount_minor)} → ${t.to_account} · ${t.id}`,t.id));
    $('fraud-submit-report').disabled=!$('fraud-event').value;
  }
  function renderMemory(){
    $('fraud-memory-count').textContent=dashboard.memories.length+' approved';$('fraud-memory-list').replaceChildren();
    $('fraud-memory-panel').hidden=!dashboard.memories.length;
    for(const m of dashboard.memories){
      const row=el('article',undefined,'fraud-memory');row.append(el('strong',m.id),el('p',m.lesson),el('small',`Source ${m.source_report_id} · review ${m.review_id}`));
      row.append(el('p','Ask next: '+m.next_question),el('small',m.validation.passed?'Recipient watch active · review flags only':'Watch withheld.'));
      const open=el('button','Open reviewed case','text-button');open.type='button';open.onclick=()=>perform(()=>select(m.source_report_id));row.append(open);$('fraud-memory-list').append(row);
    }
  }
  function render(){
    $('fraud-select').replaceChildren();for(const r of dashboard.reports)$('fraud-select').add(new Option(`${r.name} · ${names[r.status]} · ${r.id}`,r.id));
    if(report)$('fraud-select').value=report.id;
    $('fraud-history').hidden=dashboard.reports.length<2;
    $('fraud-select').disabled=!dashboard.reports.length;$('fraud-repeat').disabled=!dashboard.memories.length;
    $('fraud-repeat').hidden=!dashboard.memories.length;
    $('fraud-first').classList.toggle('primary-button',!report);$('fraud-first').classList.toggle('text-button',!!report);
    $('fraud-repeat').classList.toggle('primary-button',report?.status==='resolved');$('fraud-repeat').classList.toggle('text-button',report?.status!=='resolved');
    $('fraud-empty').hidden=!!report;$('fraud-case').hidden=!report;renderMemory();
    const selected=$('fraud-customer').value;$('fraud-customer').replaceChildren();
    for(const c of dashboard.customers)$('fraud-customer').add(new Option(c.id+' · '+c.name,c.id));
    if(selected)$('fraud-customer').value=selected;transactions();
    $('fraud-runtime-label').textContent='ADK · fake model';
    $('fraud-provider-note').textContent='No live AI calls';
    if(!report)return;
    let run=report.investigation;if(run?.report_revision!==report.revision)run=null;
    const reviewed=report.status==='resolved';
    const stopped=run&&['failed','budget_exhausted','interrupted'].includes(run.status);
    const adk=run?.context.controller==='adk';
    $('fraud-runtime-label').textContent=adk?(run.provider==='fake'?'ADK · fake model':'ADK · Gemini'):run?.trace.length?'Saved fixed rehearsal':'ADK · fake model';
    $('fraud-provider-note').textContent=run?.provider==='gemini'?'Metered Vertex AI':'No live AI calls';
    $('fraud-agent-budget').hidden=!run?.budget;
    if(run?.budget){const b=run.budget;$('fraud-agent-budget').textContent=`${b.case_calls}/${b.max_case_calls} generations · $${b.actual_usd.toFixed(4)} actual`+(b.simulated?` · $${b.estimated_usd.toFixed(4)} simulated / $${(b.case_limit_microusd/1e6).toFixed(2)} case cap`:'')}
    $('fraud-agent-stop').hidden=!stopped;$('fraud-agent-stop').textContent=run?.context.stop_reason||'The previous request was interrupted. Its cost reservation was retained.';
    $('fraud-agent-handoff').hidden=!stopped;
    $('fraud-agent-question').hidden=run?.status!=='awaiting_customer';$('fraud-agent-question').textContent=run?.context.pending_question||'';
    $('fraud-case-title').textContent=report.customer.name+' · '+names[report.status];
    $('fraud-case-meta').textContent=report.transactions.map(t=>money(t.amount_minor)+' → '+t.to_account).join(' · ');
    $('fraud-story').textContent=report.story;$('fraud-message').textContent=report.message||'No message transcript provided.';
    $('fraud-replies').replaceChildren();for(const a of report.answers)$('fraud-replies').append(el('p','Customer follow-up: '+a.text));
    const flags=report.transactions.flatMap(t=>t.metadata.review_flags||[]);
    $('fraud-early-warning').hidden=!flags.length;$('fraud-early-warning').textContent=flags.length?'Flagged before the report: this recipient appears in a reviewed scam case.':'';
    $('fraud-run').hidden=reviewed||report.status==='awaiting_customer'||!!stopped;
    $('fraud-step').hidden=$('fraud-run').hidden||run?.status==='awaiting_review';$('fraud-run').textContent=run?.status==='awaiting_review'?'Recheck evidence':run?'Continue':'Investigate';
    $('fraud-run').classList.toggle('primary-button',run?.status!=='awaiting_review');$('fraud-run').classList.toggle('text-button',run?.status==='awaiting_review');
    $('fraud-tools').hidden=!run?.trace.length;$('fraud-tool-count').textContent=run?.trace.length?run.trace.length+' tools completed':'';
    $('fraud-trace').replaceChildren();
    for(const t of run?.trace||[]){
      const li=el('li'),icon=el('span',String(t.step),'agent-avatar'),body=el('div');
      body.append(el('strong',t.tool.replaceAll('_',' ')),el('p',t.summary));
      const details=el('details',undefined,'world-details');details.append(el('summary','Tool result and sources'));
      details.append(el('pre',JSON.stringify(t.output,null,2),'science-evidence'));body.append(details);li.append(icon,body);$('fraud-trace').append(li);
    }
    $('fraud-trace-empty').hidden=!!run?.trace.length;
    $('fraud-context').hidden=!run?.context.memories?.length;
    $('fraud-context').textContent=run?.context.memories?.length
      ?`Retrieved reviewed context from ${run.context.memories.map(m=>m.source_report_id).join(', ')}.`
      :'';
    $('fraud-packet').hidden=!run?.recommendation;$('fraud-review-form').hidden=run?.status!=='awaiting_review';
    if(run?.recommendation){
      const p=run.recommendation;$('fraud-recommendation').textContent=p.summary;
      $('fraud-assessment').textContent=p.disposition==='suspected_scam'?'Possible scam':p.disposition==='likely_legitimate'?'Scam not established':'More context needed';
      $('fraud-next-question').hidden=!p.questions.length;$('fraud-next-question').textContent='Ask next: '+p.questions.join(' ');
      $('fraud-questions').replaceChildren();for(const q of p.uncertainties)$('fraud-questions').append(el('li',q));
      $('fraud-citations').textContent='Ledger evidence: '+p.evidence_ids.join(', ')+(p.memory_ids.length?' · Reviewed memory: '+p.memory_ids.join(', '):'');
      $('fraud-lesson').value=p.suggested_lesson;$('fraud-question').value=p.suggested_question;
      $('fraud-disposition').value=p.disposition==='suspected_scam'?'confirmed_scam':p.disposition==='likely_legitimate'?'not_scam':'needs_information';
      $('fraud-action').value=p.suggested_action;$('fraud-publish').checked=p.disposition==='suspected_scam';actions();
    }
    $('fraud-resolution').hidden=!report.reviews.length;
    if(report.reviews.length){const latest=report.reviews[0];$('fraud-resolution-copy').textContent=latest.resolution.customer_message;$('fraud-receipt').textContent=latest.resolution.action.replaceAll('_',' ')+' · '+latest.resolution.receipt_id+' · Simulated service receipt. No funds refunded.'}
    $('fraud-reply-form').hidden=report.status!=='awaiting_customer';
    const stage=reviewed?(dashboard.memories.some(m=>m.source_report_id===report.id)?4:3):report.status==='awaiting_review'?2:run?1:0;
    document.querySelectorAll('[data-fraud-stage]').forEach((node,i)=>{node.classList.toggle('done',i<stage);node.classList.toggle('current',i===stage);if(i===stage)node.setAttribute('aria-current','step');else node.removeAttribute('aria-current')});
  }
  async function load(){dashboard=await api('/api/fraud-desk');if(report)report=await api('/api/fraud-desk/reports/'+report.id);else if(dashboard.reports.length)report=await api('/api/fraud-desk/reports/'+dashboard.reports[0].id);render()}
  async function select(id){report=await api('/api/fraud-desk/reports/'+encodeURIComponent(id));$('fraud-note').value='';render();focusCustomer(report.customer_id)}
  async function perform(fn){
    if(working||state.busy||state.stepping)return;let succeeded=false;working=true;setPlaying(false);setBusy(true);error('');$('fraud-status').textContent='Working locally…';
    const controls=[...$('fraud-view').querySelectorAll('button,input,select,textarea')],disabled=controls.map(n=>n.disabled);controls.forEach(n=>n.disabled=true);
    try{await fn();await refresh();await load();succeeded=true;$('fraud-status').textContent='Saved'}catch(e){error(e.message);$('fraud-status').textContent='Not saved'}
    finally{working=false;setBusy(false);controls.forEach((n,i)=>n.disabled=disabled[i]);if(succeeded)render()}
  }
  async function demo(scenario){await perform(async()=>{report=await api('/api/fraud-desk/demo',{scenario,request_id:crypto.randomUUID()});$('fraud-note').value='';focusCustomer(report.customer_id);$('fraud-new-report').open=false;$('fraud-tools').open=false})}
  async function investigate(all){await perform(async()=>{
    const savedReplay=report.investigation?.trace.length&&report.investigation.context.controller!=='adk';
    const base=savedReplay?'/api/fraud-desk':'/api/fraud-agent';
    let run=await api(base+(savedReplay?'/investigate':'/start'),{report_id:report.id});
    for(let i=0;i<(all?(run.budget?.max_case_calls||6):1)&&run.status==='running';i++){
      run=await api(base+'/step',{run_id:run.id,expected_step:run.step});report.investigation=run;
      $('fraud-status').textContent=`${run.step} tool results saved`;
    }
    if(!all)$('fraud-tools').open=true;
  })}
  $('fraud-first').onclick=()=>demo('first');$('fraud-repeat').onclick=()=>demo('repeat');$('fraud-benign').onclick=()=>demo('benign');
  $('fraud-select').onchange=e=>perform(()=>select(e.target.value));$('fraud-run').onclick=()=>investigate(true);$('fraud-step').onclick=()=>investigate(false);
  $('fraud-disposition').onchange=actions;$('fraud-customer').onchange=transactions;
  $('fraud-agent-handoff').onclick=()=>perform(async()=>{report=await api('/api/fraud-agent/handoff',{run_id:report.investigation.id})});
  $('fraud-review-form').onsubmit=e=>{e.preventDefault();perform(async()=>{
    report=await api('/api/fraud-desk/review',{report_id:report.id,investigation_id:report.investigation.id,disposition:$('fraud-disposition').value,action:$('fraud-action').value,note:$('fraud-note').value,publish_memory:$('fraud-publish').checked,lesson:$('fraud-lesson').value,next_question:$('fraud-question').value});
  })};
  $('fraud-reply-form').onsubmit=e=>{e.preventDefault();perform(async()=>{report=await api('/api/fraud-desk/reply',{report_id:report.id,answer:$('fraud-reply').value,expected_revision:report.revision});$('fraud-reply').value=''})};
  $('fraud-report-form').onsubmit=e=>{e.preventDefault();perform(async()=>{report=await api('/api/fraud-desk/report',{customer_id:$('fraud-customer').value,story:$('fraud-report-story').value,message:$('fraud-report-message').value,event_ids:[$('fraud-event').value],request_id:crypto.randomUUID()});$('fraud-new-report').open=false;focusCustomer(report.customer_id)})};
  return {load,demo};
}
