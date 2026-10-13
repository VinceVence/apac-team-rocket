export function createFraudUI({$,api,state,setPlaying,setBusy,refresh,error,focusCustomer}){
  let dashboard=null,report=null,working=false,pollTimer=null,pollKey='',pollDelay=1500,pollRun='',pollStarted=0;
  const learning=()=>['queued','running'].includes(report?.prevention?.status);
  const running=()=>learning()||['queued','running'].includes(report?.investigation?.context.execution?.status);
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
    $('fraud-memory-panel').hidden=false;
    for(const m of dashboard.memories){
      const row=el('article',undefined,'fraud-memory');row.append(el('strong','Reviewed scam pattern'),el('p',m.lesson),el('small',m.validation.passed?'Protection active · matching recipients are held':'Protection withheld'));
      const sources=el('details',undefined,'world-details');sources.append(el('summary','Sources & follow-up question'),el('p',m.next_question),el('small',`${m.id} · ${m.source_report_id} · ${m.review_id}`));row.append(sources);
      const open=el('button','Open reviewed case','text-button');open.type='button';open.onclick=()=>perform(()=>select(m.source_report_id));row.append(open);$('fraud-memory-list').append(row);
    }
  }
  function renderPrevention(){
    const job=report?.prevention,eligible=report?.status==='resolved'&&dashboard.memories.some(m=>m.source_report_id===report.id);
    $('prevention-panel').hidden=!eligible&&!job;if(!eligible&&!job)return;
    const rule=job?.rule,active=rule?.status==='active';
    $('prevention-title').textContent=rule?.name||'Learn from this resolution.';
    $('prevention-status').textContent=job?`${job.model} · ${job.model_calls} model call · ${active?'safeguard active':job.status.replaceAll('_',' ')}${job.error?' — '+job.error:''}`:'The approved case is ready for the prevention learner.';
    $('prevention-learn').hidden=!!job&&job.status!=='ready';
    $('prevention-rule').hidden=!rule;
    $('prevention-signals').replaceChildren();
    for(const signal of rule?.signals||[])$('prevention-signals').append(el('li',signal.replaceAll('_',' ')));
    $('prevention-test-summary').textContent=rule?`${rule.replay.changed_recipient_matches} changed-recipient match · ${rule.replay.false_flags} flags across ${rule.replay.legitimate_controls} legitimate controls. Synthetic checks, not measured fraud accuracy.`:'';
    $('prevention-activate').hidden=!rule||!rule.replay.passed||active;
    $('prevention-disable').hidden=!active;
    $('prevention-prove').hidden=!active||!state.data?.demo.guided||state.data?.demo.focus_report_id!==report.id;
    $('prevention-trace').textContent=job?JSON.stringify({actions:job.trace,review_id:job.review_id,source:job.source.feature_provenance,case_calls:job.budget.case_calls,case_limit:job.budget.max_case_calls,replay:rule?.replay,rule_id:rule?.id,expires_at:rule?.expires_at},null,2):'No model call has been made.';
  }
  function render(){
    $('fraud-select').replaceChildren();for(const r of dashboard.reports)$('fraud-select').add(new Option(`${r.scenario_title||r.name} · ${names[r.status]}`,r.id));
    if(report)$('fraud-select').value=report.id;
    $('fraud-history').hidden=dashboard.reports.length<2;
    $('fraud-select').disabled=!dashboard.reports.length;$('fraud-repeat').disabled=!dashboard.memories.length;
    $('fraud-repeat').hidden=!dashboard.memories.length;
    $('fraud-first').classList.toggle('primary-button',!report);$('fraud-first').classList.toggle('text-button',!!report);
    $('fraud-repeat').classList.toggle('primary-button',report?.status==='resolved');$('fraud-repeat').classList.toggle('text-button',report?.status!=='resolved');
    $('fraud-empty').hidden=!!report;$('fraud-case').hidden=!report;renderMemory();
    const chosen=$('fraud-scenario').value;$('fraud-scenario').replaceChildren();
    for(const s of dashboard.scenarios||[])$('fraud-scenario').add(new Option(s.title,s.id));
    if(chosen)$('fraud-scenario').value=chosen;
    const selected=$('fraud-customer').value;$('fraud-customer').replaceChildren();
    for(const c of dashboard.customers)$('fraud-customer').add(new Option(c.id+' · '+c.name,c.id));
    if(selected)$('fraud-customer').value=selected;transactions();
    $('fraud-runtime-label').textContent='Resolution agent · ADK';
    $('fraud-provider-note').textContent=report?.investigation?.provider==='gemini'?'Gemini 3.5 Flash-Lite':'FakeInvestigator · no AI calls';
    renderPrevention();if(!report)return;
    let run=report.investigation;if(run?.report_revision!==report.revision)run=null;
    const reviewed=report.status==='resolved';
    const warnings=report.validation_warnings||[];$('fraud-unit-warning').hidden=!warnings.length;$('fraud-unit-warning').textContent=warnings.join(' ');$('fraud-approve').disabled=!!warnings.length;
    const stopped=run&&['failed','budget_exhausted','interrupted'].includes(run.status);
    const adk=run?.context.controller==='adk';
    const automatic=running();
    if(learning())$('fraud-status').textContent='Prevention agent is learning from the approved resolution…';
    else if(automatic)$('fraud-status').textContent=run.context.execution.status==='queued'?'Queued for investigation…':'Investigating in background…';
    $('fraud-runtime-label').textContent='Resolution agent · ADK';
    $('fraud-provider-note').textContent=run?.provider==='gemini'?'Gemini 3.5 Flash-Lite':'FakeInvestigator · no AI calls';
    $('fraud-agent-budget').hidden=!run?.budget;
    if(run?.budget){const b=run.budget;$('fraud-agent-budget').textContent=`${b.case_calls}/${b.max_case_calls} generations · $${b.actual_usd.toFixed(4)} actual`+(b.simulated?` · $${b.estimated_usd.toFixed(4)} simulated / $${(b.case_limit_microusd/1e6).toFixed(2)} case cap`:'')}
    $('fraud-snapshot').hidden=!run?.snapshot;
    if(run?.snapshot)$('fraud-snapshot').textContent=`Frozen evidence · simulation date ${run.snapshot.as_of} · ${run.snapshot.id}`;
    $('fraud-agent-stop').hidden=!stopped;$('fraud-agent-stop').textContent=run?.context.stop_reason||'The previous request was interrupted. Its cost reservation was retained.';
    $('fraud-agent-handoff').hidden=!stopped;
    $('fraud-agent-question').hidden=run?.status!=='awaiting_customer';$('fraud-agent-question').textContent=run?.context.pending_question||'';
    $('fraud-case-title').textContent=report.scenario_title||(report.transactions.length===1?'Reported transfer':'Reported transfers');
    $('fraud-case-meta').textContent=`${report.transactions.length} payment${report.transactions.length===1?'':'s'} · ${money(report.transactions.reduce((sum,t)=>sum+t.amount_minor,0))} total`;
    $('fraud-story').textContent=report.story;$('fraud-message').textContent=report.message||'No message transcript provided.';
    $('fraud-replies').replaceChildren();for(const a of report.answers)$('fraud-replies').append(el('p','Customer follow-up: '+a.text));
    const flags=report.transactions.flatMap(t=>t.metadata.review_flags||[]);
    $('fraud-early-warning').hidden=!flags.length;$('fraud-early-warning').textContent=flags.length?'Flagged before the report: this recipient appears in a reviewed scam case.':'';
    $('fraud-run').hidden=reviewed||report.status==='awaiting_customer'||!!stopped||automatic||run?.status==='awaiting_review';
    $('fraud-step').hidden=state.hosted||$('fraud-run').hidden||run?.status==='awaiting_review';$('fraud-run').textContent=run?.status==='awaiting_review'?'Recheck evidence':run?'Continue':'Investigate';
    $('fraud-run').classList.toggle('primary-button',run?.status!=='awaiting_review');$('fraud-run').classList.toggle('text-button',run?.status==='awaiting_review');
    const trail=report.decision_trail?.length?report.decision_trail:(run?.trace||[]).map(t=>({number:t.step,tool:t.tool,purpose:t.summary,finding:t.finding,result:t.output,provenance:t.provenance,status:'completed'}));
    $('fraud-tools').hidden=!trail.length;$('fraud-tool-count').textContent=trail.length?trail.length+' model turns':'';
    $('fraud-trace').replaceChildren();
    for(const t of trail){
      const li=el('li'),icon=el('span',String(t.number),'agent-avatar'),body=el('div');
      body.append(el('strong',t.tool?t.tool.replaceAll('_',' '):t.status==='reserved'?'Choosing a tool…':'Model request stopped'));
      const result=t.result||{},brief=t.tool==='get_transactions'?`Verified ${result.transactions?.length||0} reported payments.`:t.tool==='search_reviewed_cases'?`Found ${result.matches?.length||0} approved lessons.`:t.tool==='trace_recipient'?`Found ${result.related_transfers?.length||0} transfers to this recipient.`:t.tool==='ask_customer'?result.question:t.tool==='submit_for_review'?'Sent the proposed resolution for analyst review.':t.finding;
      if(t.purpose)body.append(el('p',t.purpose,'decision-purpose'));
      if(t.status==='completed')body.append(el('span','Tool input validated','tool-validation'));
      if(t.tool==='run_fraud_detectors'){
        const models=el('div',undefined,'detector-results');
        for(const d of result.detectors||[]){const card=el('section',undefined,'detector-result'),head=el('header');head.append(el('strong',d.name+' v'+d.version),el('span',d.result));card.append(head);if(d.signal_score!==null){const meter=el('meter');meter.min=0;meter.max=1;meter.value=d.signal_score;meter.setAttribute('aria-label',d.name+' signal score');card.append(meter)}card.append(el('small',d.kind+' · signal score, not fraud probability'));models.append(card)}
        body.append(models);
      }else if(brief)body.append(el('p',brief));
      if(t.error)body.append(el('p',t.error));
      const details=el('details',undefined,'world-details');details.append(el('summary','Evidence sources & result'));
      details.append(el('pre',JSON.stringify({purpose:t.purpose,finding:t.finding,model:t.provider==='fake'?'FakeInvestigator':'Gemini 3.5 Flash-Lite',status:t.status,cost_usd:t.committed_usd,simulated:t.provider==='fake',sources:t.provenance,result:t.result},null,2),'science-evidence'));body.append(details);li.append(icon,body);$('fraud-trace').append(li);
    }
    $('fraud-trace-empty').hidden=!!trail.length;
    $('fraud-context').hidden=!run?.context.memories?.length;
    $('fraud-context').textContent=run?.context.memories?.length
      ?'Using a lesson from an approved case.'
      :'';
    $('fraud-packet').hidden=!run?.recommendation;$('fraud-review-form').hidden=run?.status!=='awaiting_review';
    if(run?.recommendation){
      const p=run.recommendation;$('fraud-recommendation').textContent=p.summary;
      $('fraud-assessment').textContent=p.suggested_action==='request_recall'?'Request a recall.':p.disposition==='likely_legitimate'?'Reassure the customer.':'Ask for more evidence.';
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
    schedulePoll();
  }
  function schedulePoll(){
    clearTimeout(pollTimer);
    if(!running()||document.hidden||state.view!=='resolution')return;
    const run=learning()?report.prevention:report.investigation,key=`${run.id}:${run.step??run.model_calls}:${run.status}`;
    if(pollRun!==run.id){pollRun=run.id;pollStarted=Date.now()}
    if(Date.now()-pollStarted>210000){$('fraud-status').textContent='Progress polling stopped. Reopen the case to check its saved status.';return}
    pollDelay=key===pollKey?Math.min(5000,pollDelay*1.5):1500;pollKey=key;
    pollTimer=setTimeout(async()=>{
      if(working||state.busy){schedulePoll();return}
      const id=report.id;
      try{
        const next=await api('/api/fraud-desk/reports/'+encodeURIComponent(id));
        if(report.id!==id)return;
        report=next;render();
        if(!running()){$('fraud-status').textContent=names[report.status]||'Investigation paused';await refresh();await load()}
      }catch(e){error(e.message);$('fraud-status').textContent='Progress unavailable. Reopen the case to reconnect.'}
    },pollDelay);
  }
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(pollTimer);else if(state.view==='resolution')load().catch(e=>error(e.message))});
  async function load(latest=false){dashboard=await api('/api/fraud-desk');if(latest&&dashboard.reports.length)report=await api('/api/fraud-desk/reports/'+dashboard.reports[0].id);else if(report)report=await api('/api/fraud-desk/reports/'+report.id);else if(dashboard.reports.length)report=await api('/api/fraud-desk/reports/'+dashboard.reports[0].id);render()}
  async function select(id){pollRun='';report=await api('/api/fraud-desk/reports/'+encodeURIComponent(id));$('fraud-note').value='Reviewed the synthetic report and its transaction evidence.';render();focusCustomer(report.customer_id)}
  async function perform(fn){
    if(working||state.busy||state.stepping)return;let succeeded=false;working=true;setPlaying(false);setBusy(true);error('');$('fraud-status').textContent='Working locally…';
    const controls=[...$('fraud-view').querySelectorAll('button,input,select,textarea')],disabled=controls.map(n=>n.disabled);controls.forEach(n=>n.disabled=true);
    try{await fn();await refresh();await load();succeeded=true;$('fraud-status').textContent='Saved'}catch(e){error(e.message);$('fraud-status').textContent='Not saved'}
    finally{working=false;setBusy(false);controls.forEach((n,i)=>n.disabled=disabled[i]);if(succeeded)render()}
  }
  async function demo(scenario){await perform(async()=>{report=await api('/api/fraud-desk/demo',{scenario,request_id:crypto.randomUUID()});$('fraud-note').value='Reviewed the synthetic report and its transaction evidence.';focusCustomer(report.customer_id);$('fraud-new-report').open=false;$('fraud-tools').open=true})}
  async function investigate(all){await perform(async()=>{
    const savedReplay=report.investigation?.trace.length&&report.investigation.context.controller!=='adk';
    const base=savedReplay?'/api/fraud-desk':'/api/fraud-agent';
    let run=await api(base+(savedReplay?'/investigate':'/start'),savedReplay?{report_id:report.id}:{report_id:report.id,mode:report.investigation?.context.provider||(dashboard.agent_runtime?.live_enabled?'gemini':'fake'),automatic:all});
    if(savedReplay||!all){
      for(let i=0;i<(all?6:1)&&run.status==='running';i++)run=await api(base+'/step',{run_id:run.id,expected_step:run.step});
    }
    report.investigation=run;$('fraud-tools').open=true;
  })}
  $('fraud-create-scenario').onclick=()=>demo($('fraud-scenario').value+($('fraud-control').checked?'.control':''));
  $('fraud-first').onclick=()=>demo('first');$('fraud-repeat').onclick=()=>demo('repeat');$('fraud-benign').onclick=()=>demo('benign');
  $('fraud-select').onchange=e=>perform(()=>select(e.target.value));$('fraud-run').onclick=()=>investigate(true);$('fraud-step').onclick=()=>investigate(false);
  $('fraud-disposition').onchange=actions;$('fraud-customer').onchange=transactions;
  $('fraud-agent-handoff').onclick=()=>perform(async()=>{report=await api('/api/fraud-agent/handoff',{run_id:report.investigation.id})});
  $('fraud-review-form').onsubmit=e=>{e.preventDefault();perform(async()=>{
    report=await api('/api/fraud-desk/review',{report_id:report.id,investigation_id:report.investigation.id,disposition:$('fraud-disposition').value,action:$('fraud-action').value,note:$('fraud-note').value,publish_memory:$('fraud-publish').checked,lesson:$('fraud-lesson').value,next_question:$('fraud-question').value});
  })};
  $('prevention-learn').onclick=()=>perform(async()=>{await api('/api/prevention/learn',{report_id:report.id})});
  $('prevention-activate').onclick=()=>perform(async()=>{await api('/api/prevention/activate',{rule_id:report.prevention.rule.id,enabled:true})});
  $('prevention-disable').onclick=()=>perform(async()=>{await api('/api/prevention/activate',{rule_id:report.prevention.rule.id,enabled:false})});
  $('prevention-prove').onclick=()=>perform(async()=>{await api('/api/world/prove',{expected_run:state.data.demo.run_id});location.hash='';});
  $('fraud-reply-form').onsubmit=e=>{e.preventDefault();perform(async()=>{report=await api('/api/fraud-desk/reply',{report_id:report.id,answer:$('fraud-reply').value,expected_revision:report.revision});$('fraud-reply').value='';if(report.auto_resume_error)error(report.auto_resume_error)})};
  $('fraud-report-form').onsubmit=e=>{e.preventDefault();perform(async()=>{report=await api('/api/fraud-desk/report',{customer_id:$('fraud-customer').value,story:$('fraud-report-story').value,message:$('fraud-report-message').value,event_ids:[$('fraud-event').value],request_id:crypto.randomUUID()});$('fraud-new-report').open=false;focusCustomer(report.customer_id)})};
  return {load,demo,open:select,reset:()=>{clearTimeout(pollTimer);report=null;dashboard=null;pollRun='';pollKey=''}};
}
