import {renderDecisionMap} from './decision-map.js';
import {renderHarness,roleNames} from './harness-ui.js';
import {agentIcon,pretty,toolLabels,cleanText,publicEvidence,publicEventText,caseEventAliases,renderCaseTracker,caseActivity,renderPreventionFlow,demoAnalystState} from './agent-ui.js';
export function createFraudUI({$,api,state,setPlaying,setBusy,refresh,error,focusCustomer,onRender=()=>{},onNavigate=()=>{}}){
  let dashboard=null,report=null,working=false,starting=false,pollTimer=null,pollKey='',pollDelay=1500,pollRun='',pollStarted=0,pollProblem='';
  let mappedCase=null,selectedDecision=null;
  const learning=()=>['queued','running'].includes(report?.prevention?.status);
  const running=()=>learning()||caseActivity(report,state.data?.demo).poll;
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
    for(const [index,t] of dashboard.transactions.filter(t=>t.customer_id===$('fraud-customer').value).entries())$('fraud-event').add(new Option(`${money(t.amount_minor)} → ${t.to_account} · Transfer ${index+1}`,t.id));
    $('fraud-submit-report').disabled=!$('fraud-event').value;
  }
  function renderMemory(){
    $('fraud-memory-count').textContent=dashboard.memories.filter(m=>m.lifecycle?.active!==false).length+' active';$('fraud-memory-list').replaceChildren();
    $('fraud-memory-panel').hidden=false;
    for(const m of dashboard.memories){
      const inactive=m.lifecycle?.active===false,title=dashboard.reports.find(r=>r.id===m.source_report_id)?.scenario_title||'Reviewed payment case';
      const row=el('article',undefined,'fraud-memory'+(inactive?' inactive':'')),head=el('header'),heading=el('div');
      heading.append(el('h3',title),el('small',`${m.pattern.evidence_ids.length} transfer${m.pattern.evidence_ids.length===1?'':'s'} reviewed`));head.append(agentIcon('knowledge'),heading,el('span',inactive?(m.lifecycle.revoked_at?'Revoked':'Expired'):'Approved','lesson-state'));row.append(head);
      const cues=el('div',undefined,'signal-chips');for(const cue of (m.pattern.cues||[]).slice(0,3))cues.append(el('span',pretty(cue)));row.append(cues);
      row.append(el('p',cleanText(m.lesson).length>150?cleanText(m.lesson).slice(0,147)+'…':cleanText(m.lesson),'lesson-summary'));
      const sources=el('details',undefined,'world-details');sources.append(el('summary','Lesson details'),el('p',cleanText(m.lesson)),el('p','Ask next: '+cleanText(m.next_question)),el('small',`${m.id} · ${m.source_report_id}`));row.append(sources);
      if(m.playbook){const p=m.playbook;row.append(el('p','ACE playbook · '+p.id,'playbook-label'));sources.append(el('h4','Reusable investigation strategy'),el('p',p.payload.strategy),el('p','Counterexample: '+p.payload.counterexample),el('p','Ask: '+p.payload.verification_question),el('small',`${p.feedback.helpful} later reviews agreed · ${p.feedback.harmful} disagreed`));}
      if(m.lifecycle){sources.append(el('p','Applicability: '+m.lifecycle.applicability.requirement),el('p','Counterexamples: '+m.lifecycle.counterexamples.join(' ')),el('small','Expires '+m.lifecycle.expires_at));}
      const buttons=el('div',undefined,'lesson-actions'),open=el('button','Open reviewed case →','secondary-button');open.type='button';open.onclick=async()=>{onNavigate();await perform(()=>select(m.source_report_id));if(report?.id===m.source_report_id)$('human-review-stage').scrollIntoView({behavior:'smooth',block:'start'})};buttons.append(open);
      if(!inactive){const revoke=el('button','Revoke','revoke-button');revoke.type='button';revoke.onclick=()=>{onNavigate();buttons.hidden=true;const confirm=el('div',undefined,'revoke-confirm');confirm.append(el('p','Revoke this lesson and disable its linked safeguards?'));const yes=el('button','Revoke lesson','revoke-button'),cancel=el('button','Cancel','text-button');yes.type=cancel.type='button';cancel.onclick=()=>{confirm.remove();buttons.hidden=false;revoke.focus()};yes.onclick=()=>perform(async()=>{await api('/api/fraud-desk/revoke-memory',{memory_id:m.id,reason:'Analyst revoked this lesson pending a fresh evidence review.'});await load();await refresh()});confirm.append(yes,cancel);row.append(confirm);cancel.focus()};buttons.append(revoke)}
      row.append(buttons);
      $('fraud-memory-list').append(row);
    }
    if(!dashboard.memories.length)$('fraud-memory-list').append(el('p','Reviewed lessons appear here after analyst approval.','stage-placeholder'));
  }
  function renderPrevention(){
    const job=report?.prevention,eligible=report?.status==='resolved'&&dashboard.memories.some(m=>m.source_report_id===report.id);
    $('prevention-panel').hidden=!eligible&&!job;$('prevention-placeholder').hidden=eligible||!!job;if(!eligible&&!job)return;
    const rule=job?.rule,active=rule?.status==='active';
    const rejected=job?.status==='rejected'||rule?.replay?.passed===false;
    const failed=job&&['failed','interrupted','budget_exhausted'].includes(job.status);renderPreventionFlow(job);
    $('prevention-title').textContent=active?'Payment protection is active':failed?'Learning needs attention':rejected?'This safeguard needs revision':rule?'A safeguard is ready for review':'Learn from the approved case';
    $('prevention-status').textContent=active?'Matching requests pause before debit.':failed?'The reviewed lesson is saved. No request will be retried automatically.':rejected?'The replay found a problem. This candidate stays inactive.':rule?'Check the replay results, then decide whether to enable it.':learning()?'Checking a candidate against similar scams and legitimate payments…':'The reviewed lesson is ready for the prevention agent.';
    $('prevention-panel').classList.toggle('rejected',rejected);
    $('prevention-learn').hidden=!!job&&job.status!=='ready';
    $('prevention-rule').hidden=!rule;
    $('prevention-signals').replaceChildren();
    for(const signal of rule?.signals||[])$('prevention-signals').append(el('li',pretty(signal)));
    $('prevention-test-summary').replaceChildren();
    if(job?.playbook){const p=job.playbook,delta=el('section',undefined,'playbook-delta');delta.append(el('h3',p.status==='active'?'Reviewed playbook ready for reuse':'Case reflection → proposed playbook'),el('p',p.payload.strategy),el('small','Independent check: '+p.payload.verification_question));$('prevention-test-summary').append(delta)}
    if(rule){for(const [value,label,bad] of [[`${rule.replay.changed_recipient_matches} / ${rule.replay.source_variants}`,'similar requests held',rule.replay.changed_recipient_matches<rule.replay.source_variants],[`${rule.replay.false_flags} / ${rule.replay.legitimate_controls}`,'legitimate payments held',rule.replay.false_flags>0]]){const metric=el('div',undefined,'replay-metric'+(bad?' warning':''));metric.append(el('strong',String(value)),el('span',label));$('prevention-test-summary').append(metric)}$('prevention-test-summary').append(el('small','Synthetic replay · not real-world accuracy','replay-note'))}
    const paired=rule?.replay?.paired;
    if(paired?.available){
      const comparison=el('section',undefined,'policy-comparison');comparison.append(el('h3','Before → after this safeguard'));
      const metrics=el('div',undefined,'policy-comparison-metrics');
      for(const [value,label] of [[`${paired.before_stopped} → ${paired.after_stopped} / ${paired.scam_variants}`,'scam variants held'],[`${paired.before_false_holds} → ${paired.after_false_holds} / ${paired.legitimate_controls}`,'legitimate requests held']]){const item=el('div');item.append(el('strong',value),el('span',label));metrics.append(item)}
      comparison.append(metrics,el('p',`Rejected comparison: holding every new recipient flags ${paired.rejected_baseline.false_holds} of ${paired.rejected_baseline.controls} legitimate controls.`,'surface-note'));
      for(const reason of paired.reasons)comparison.append(el('p',reason,'risk-reason'));
      const details=el('details',undefined,'world-details');details.append(el('summary','Inspect matched requests'));
      for(const item of paired.cases){const row=el('div',undefined,'policy-comparison-row');row.append(el('span',pretty(item.name)),el('strong',item.before+' → '+item.after));details.append(row)}
      comparison.append(details);$('prevention-test-summary').append(comparison);
    }
    $('prevention-activate').hidden=!rule||!rule.replay.passed||active;
    $('prevention-disable').hidden=!active;
    $('prevention-prove').hidden=!active||!state.data?.demo.guided||state.data?.demo.focus_report_id!==report.id;
    $('prevention-trace').textContent=job?JSON.stringify(publicEvidence({actions:job.trace,review_id:job.review_id,source:job.source.feature_provenance,replay:rule?.replay,rule_id:rule?.id,expires_at:rule?.expires_at},caseEventAliases(report)),null,2):'No safeguard has been proposed.';
  }
  function render(){
    const analyst=demoAnalystState(report);
    const eventAliases=caseEventAliases(report);
    $('demo-analyst-approve').disabled=!analyst.enabled||!!state.replay;$('demo-analyst-approve').textContent=analyst.label;
    $('demo-analyst-case').textContent=report?report.scenario_title+' · '+report.id:'Open a completed case.';
    $('demo-analyst-status').textContent=report?analyst.detail:'';
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
    $('fraud-provider-note').textContent=report?.investigation?.provider==='gemini'?'Live investigation':'Offline rehearsal';
    renderPrevention();renderHarness(report?.harness,eventAliases);document.querySelector('.demo-story').hidden=true;if(!report)return;
    let run=report.investigation;if(run?.report_revision!==report.revision)run=null;
    if(starting&&!run&&!report.preparation)report.preparation={status:'running',stage:'request',detail:'Sending the investigation request.'};
    const reviewed=report.status==='resolved';
    const warnings=report.validation_warnings||[];$('fraud-unit-warning').hidden=!warnings.length;$('fraud-unit-warning').textContent=warnings.join(' ');$('fraud-approve').disabled=!!warnings.length;
    const resumable=report.harness?.can_resume===true;
    const stopped=run&&['failed','budget_exhausted','interrupted'].includes(run.status)&&!resumable;
    const adk=run?.context.controller==='adk';
    const activity=caseActivity(report,state.data?.demo),automatic=running();
    if(learning())$('fraud-status').textContent='Prevention agent is learning from the approved resolution…';
    else if(automatic)$('fraud-status').textContent=activity.title;
    else $('fraud-status').textContent=names[report.status]||'Review the saved investigation.';
    $('fraud-provider-note').textContent=report.presentation_mode==='replay'?'Recorded Gemini replay':(run?run.provider==='gemini':dashboard.agent_runtime?.live_enabled)?'Live investigation':'Offline rehearsal';
    const progress=renderCaseTracker(report,state.data?.demo,onNavigate);
    $('fraud-snapshot').hidden=!run?.snapshot;
    if(run?.snapshot)$('fraud-snapshot').textContent=`Frozen evidence · simulation date ${run.snapshot.as_of} · ${run.snapshot.id}. ${report.preparation?.detail||''}`;
    $('fraud-agent-stop').hidden=!stopped;$('fraud-agent-stop').textContent=run?.status==='budget_exhausted'?'The investigation reached its safety limit. An analyst can continue from the saved evidence.':run?.status==='interrupted'?'The investigation was interrupted. Review the saved evidence before continuing.':cleanText(run?.context.stop_reason||'The investigation needs manual attention.');
    $('fraud-agent-handoff').hidden=!stopped;
    $('fraud-agent-question').hidden=run?.status!=='awaiting_customer';$('fraud-agent-question').textContent=run?.context.pending_question||'';
    $('fraud-case-title').textContent=report.scenario_title||(report.transactions.length===1?'Reported transfer':'Reported transfers');
    $('fraud-case-meta').textContent=`${report.transactions.length} payment${report.transactions.length===1?'':'s'} · ${money(report.transactions.reduce((sum,t)=>sum+t.amount_minor,0))} total`;
    $('fraud-story').textContent=report.story;$('fraud-message').textContent=report.message||'No message transcript provided.';
    $('fraud-replies').replaceChildren();for(const a of report.answers)$('fraud-replies').append(el('p','Customer follow-up: '+a.text));
    const flags=report.transactions.flatMap(t=>t.metadata.review_flags||[]);
    $('fraud-early-warning').hidden=!flags.length;$('fraud-early-warning').textContent=flags.length?'Flagged before the report: this recipient appears in a reviewed scam case.':'';
    $('fraud-run').hidden=reviewed||report.status==='awaiting_customer'||!!stopped||automatic||run?.status==='awaiting_review'||activity.stage==='blocked'&&!resumable&&activity.action!=='start';
    $('fraud-step').hidden=state.hosted||$('fraud-run').hidden||run?.status==='awaiting_review';$('fraud-run').textContent=activity.stage==='blocked'&&!run?'Prepare & investigate':resumable?'Resume saved work':run?.status==='awaiting_review'?'Recheck evidence':run?'Continue':'Investigate';
    $('fraud-run').classList.toggle('primary-button',run?.status!=='awaiting_review');$('fraud-run').classList.toggle('text-button',run?.status==='awaiting_review');
    const trail=report.decision_trail?.length?report.decision_trail:(run?.trace||[]).map(t=>({number:t.step,tool:t.tool,purpose:t.summary,finding:t.finding,result:t.output,provenance:t.provenance,status:'completed'}));
    $('fraud-tools').hidden=!trail.length;$('fraud-tool-count').textContent=trail.length?trail.filter(t=>t.status==='completed').length+' checks recorded':'';
    const existing=[...$('fraud-trace').querySelectorAll('details.decision-step')],opened=new Set(existing.filter(n=>n.open).map(n=>n.id)),known=new Set(existing.map(n=>n.id));
    $('fraud-trace').replaceChildren();
    for(const t of trail){
      const li=el('li'),step=el('details',undefined,'decision-step'),summary=el('summary'),icon=el('span',String(t.number),'agent-avatar'),body=el('div',undefined,'decision-body');step.id='guide-turn-'+t.number;
      step.open=(!known.has('guide-turn-'+trail.at(-1)?.number)?t===trail.at(-1):opened.has(step.id));
      summary.append(icon,el('strong',t.tool?(toolLabels[t.tool]||pretty(t.tool)):t.status==='reserved'?'Choosing the next check…':'Request stopped'),el('span',t.status==='completed'?'Done':t.status==='reserved'?'Working':'Needs attention','check-status'));step.append(summary);
      const role=t.role&&t.role!=='resolution'?roleNames[t.role]||pretty(t.role):'Resolution agent',byline=el('div',undefined,'tool-byline');byline.append(agentIcon(t.role&&t.role!=='resolution'?'specialist':'resolution'),el('small',role));body.append(byline);
      const result=t.result||{},brief=['get_transactions','get_case_evidence'].includes(t.tool)?`Verified ${result.transactions?.length||0} reported payments.`:t.tool==='search_reviewed_cases'?`Found ${result.matches?.length||0} approved lessons.`:t.tool==='trace_recipient'?`Found ${result.related_transfers?.length||0} transfers to this recipient.`:t.tool==='ask_customer'?result.question:['submit_for_review','submit_case_resolution'].includes(t.tool)?(result.status==='revision_required'?'Judges withheld the draft.': 'Sent the proposed resolution for analyst review.'):t.finding;
      if(t.purpose)body.append(el('p',publicEventText(t.purpose,eventAliases),'decision-purpose'));
      if(t.status==='completed')body.append(el('span','Tool input validated','tool-validation'));
      if(t.tool==='run_fraud_detectors'||t.tool==='score_models'){
        const models=el('div',undefined,'detector-results');
        const predictions=t.tool==='score_models'?(result.receipts||[]).map(r=>({name:r.manifest.name,version:r.model_version,kind:r.score_kind.replaceAll('_',' '),signal_score:r.prediction?.signal_score??null,result:r.status==='not_available'?'Not available':r.prediction?.result||r.status})):(result.detectors||[]);
        for(const d of predictions){const card=el('section',undefined,'detector-result'),head=el('header');const label=/device/i.test(d.name)?'Device activity':/message|intent|request/i.test(d.name)?'Payment request':'Payment pattern';head.append(el('strong',label),el('span',d.result));card.append(head);if(d.signal_score!==null){const meter=el('meter');meter.min=0;meter.max=1;meter.value=d.signal_score;meter.setAttribute('aria-label',label+' signal score');card.append(meter)}card.append(el('small','Signal strength · not a fraud probability'));models.append(card)}
        body.append(models);
      }else if(brief)body.append(el('p',publicEventText(brief,eventAliases)));
      const behavior=result.warehouse?.source||(['get_customer_features'].includes(t.tool)?result.source:null);
      if(behavior?.analytics_sync)body.append(el('p',behavior.analytics_sync==='matched_completed_publication'?'Customer behavior: matching published data reused.':'Customer behavior: frozen ledger evidence. BigQuery sync is deferred.','surface-note'));
      if(t.error)body.append(el('p',publicEventText(t.error,eventAliases)));
      const details=el('details',undefined,'world-details');details.append(el('summary','Evidence sources & result'));
      details.append(el('pre',JSON.stringify(publicEvidence({purpose:t.purpose,finding:t.finding,status:t.status,sources:t.provenance,result:t.result},eventAliases),null,2),'science-evidence'));body.append(details);step.append(body);li.append(step);$('fraud-trace').append(li);
    }
    $('fraud-trace-empty').hidden=!!trail.length;
    $('fraud-context').hidden=!run?.context.memories?.length;
    $('fraud-context').textContent=run?.context.memories?.length
      ?'Using a lesson from an approved case.'
      :'';
    $('fraud-packet').hidden=!run?.recommendation;$('fraud-review-form').hidden=run?.status!=='awaiting_review';
    if(run?.recommendation){
      const p=run.recommendation;$('fraud-recommendation').textContent=publicEventText(p.summary,eventAliases);
      $('fraud-assessment').textContent=p.suggested_action==='request_recall'?'Request a recall.':p.disposition==='likely_legitimate'?'Reassure the customer.':'Ask for more evidence.';
      $('fraud-next-question').hidden=!p.questions.length;$('fraud-next-question').textContent=publicEventText('Ask next: '+p.questions.join(' '),eventAliases);
      $('fraud-questions').replaceChildren();for(const q of p.uncertainties)$('fraud-questions').append(el('li',publicEventText(q,eventAliases)));
      $('fraud-citations').textContent=publicEventText('Ledger evidence: '+p.evidence_ids.join(', ')+(p.memory_ids.length?' · Reviewed memory: '+p.memory_ids.join(', '):''),eventAliases);
      $('fraud-lesson').value=p.suggested_lesson;$('fraud-question').value=p.suggested_question;
      $('fraud-disposition').value=p.disposition==='suspected_scam'?'confirmed_scam':p.disposition==='likely_legitimate'?'not_scam':'needs_information';
      $('fraud-action').value=p.suggested_action;$('fraud-publish').checked=p.disposition==='suspected_scam';actions();
    }
    $('fraud-resolution').hidden=!report.reviews.length;
    $('human-review-empty').hidden=run?.status==='awaiting_review'||!!report.reviews.length;
    if(report.reviews.length){const latest=report.reviews[0];$('fraud-resolution-copy').textContent=report.demo_analyst?.assumption?'Demo Fraud Analyst approval recorded. This simulates human review; no funds were recovered.':latest.resolution.customer_message;$('fraud-receipt').textContent=latest.resolution.action.replaceAll('_',' ')+' · '+latest.resolution.receipt_id+' · Simulated service receipt. No funds refunded.'}
    $('fraud-reply-form').hidden=report.status!=='awaiting_customer';
    const stage=reviewed?(dashboard.memories.some(m=>m.source_report_id===report.id)?4:3):report.status==='awaiting_review'?2:run?1:0;
    document.querySelectorAll('[data-fraud-stage]').forEach((node,i)=>{node.classList.toggle('done',i<stage);node.classList.toggle('current',i===stage);if(i===stage)node.setAttribute('aria-current','step');else node.removeAttribute('aria-current')});
    const mappingKey=`${report.id}:${run?.id||''}:${report.revision}`;
    if(mappedCase!==mappingKey){mappedCase=mappingKey;selectedDecision=null}
    renderDecisionMap($('agent-live-panel'),report,{selected:selectedDecision,onSelect:number=>{selectedDecision=number;render()}});
    $('fraud-poll-note').hidden=!pollProblem;$('fraud-poll-note').textContent=pollProblem;
    $('fraud-refresh').hidden=!pollProblem&&activity.stage!=='blocked';
    if(working){$('fraud-view').querySelectorAll('button,input,select,textarea').forEach(n=>n.disabled=true);$('fraud-refresh').disabled=false}
    schedulePoll();
    onRender({...report,approved_lesson:dashboard.memories.find(m=>m.source_report_id===report.id)});
  }
  function schedulePoll(){
    clearTimeout(pollTimer);
    if(!running()||document.hidden||state.view!=='resolution')return;
    const run=learning()?report.prevention:report.investigation,watch=learning()?run.id:report.id+':'+report.revision;
    const key=run?`${run.id}:${run.step??run.model_calls}:${run.status}`:`${report.id}:${report.preparation?.stage}:${report.preparation?.status}`;
    if(pollRun!==watch){pollRun=watch;pollStarted=Date.now()}
    if(Date.now()-pollStarted>300000){pollProblem='Status updates paused. Refresh to reconnect to the saved case.';$('fraud-poll-note').textContent=pollProblem;$('fraud-poll-note').hidden=false;$('fraud-refresh').hidden=false;return}
    pollDelay=key===pollKey?Math.min(5000,pollDelay*1.5):1500;pollKey=key;
    pollTimer=setTimeout(async()=>{
      const id=report.id;
      try{
        const next=await api('/api/fraud-desk/reports/'+encodeURIComponent(id));
        if(report?.id!==id)return;
        report=next;pollProblem='';render();
        if(!running()){$('fraud-status').textContent=names[report.status]||'Investigation paused';await refresh();await load()}
      }catch(e){pollProblem='Status could not be refreshed. The investigation may still be running; refresh its saved progress.';$('fraud-poll-note').textContent=pollProblem;$('fraud-poll-note').hidden=false;$('fraud-refresh').hidden=false;error(e.message)}
    },pollDelay);
  }
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(pollTimer);else if(state.view==='resolution')load().catch(e=>error(e.message))});
  async function load(latest=false){dashboard=await api('/api/fraud-desk');if(latest&&dashboard.reports.length)report=await api('/api/fraud-desk/reports/'+dashboard.reports[0].id);else if(report)report=await api('/api/fraud-desk/reports/'+report.id);else if(dashboard.reports.length)report=await api('/api/fraud-desk/reports/'+dashboard.reports[0].id);render()}
  async function select(id){pollRun='';report=await api('/api/fraud-desk/reports/'+encodeURIComponent(id));$('fraud-note').value='Reviewed the synthetic report and its transaction evidence.';render();focusCustomer(report.customer_id)}
  async function perform(fn){
    if(working||state.busy||state.stepping)return;let succeeded=false;working=true;setPlaying(false);setBusy(true);error('');$('fraud-status').textContent='Working locally…';
    const controls=[...$('fraud-view').querySelectorAll('button,input,select,textarea'),$('demo-analyst-approve')],disabled=controls.map(n=>n.disabled);controls.forEach(n=>n.disabled=true);
    try{await fn();await refresh();await load();succeeded=true;$('fraud-status').textContent='Saved'}catch(e){error(e.message);$('fraud-status').textContent='Not saved'}
    finally{working=false;setBusy(false);controls.forEach((n,i)=>n.disabled=disabled[i]);if(succeeded)render()}
  }
  async function demo(scenario){await perform(async()=>{report=await api('/api/fraud-desk/demo',{scenario,request_id:crypto.randomUUID()});$('fraud-note').value='Reviewed the synthetic report and its transaction evidence.';focusCustomer(report.customer_id);$('fraud-new-report').open=false;$('fraud-tools').open=true})}
  async function investigate(all){if(working||state.busy)return;starting=true;render();try{await perform(async()=>{
    const savedReplay=report.investigation?.trace.length&&report.investigation.context.controller!=='adk';
    const base=savedReplay?'/api/fraud-desk':'/api/fraud-agent';
    let run=await api(base+(savedReplay?'/investigate':'/start'),savedReplay?{report_id:report.id}:{report_id:report.id,mode:report.investigation?.context.provider||(dashboard.agent_runtime?.live_enabled?'gemini':'fake'),automatic:all});
    if(savedReplay||!all){
      for(let i=0;i<(all?6:1)&&run.status==='running';i++)run=await api(base+'/step',{run_id:run.id,expected_step:run.step});
    }
    report.investigation=run;$('fraud-tools').open=true;
  })}finally{starting=false;if(report?.preparation?.stage==='request')report.preparation=null;render()}}
  $('fraud-create-scenario').onclick=()=>demo($('fraud-scenario').value+($('fraud-control').checked?'.control':''));
  $('fraud-first').onclick=()=>demo('first');$('fraud-repeat').onclick=()=>demo('repeat');$('fraud-benign').onclick=()=>demo('benign');
  $('fraud-select').onchange=e=>perform(()=>select(e.target.value));$('fraud-run').onclick=()=>investigate(true);$('fraud-step').onclick=()=>investigate(false);
  $('fraud-refresh').onclick=async()=>{pollRun='';pollProblem='';try{await refresh();await load()}catch(e){error(e.message)}};
  $('fraud-disposition').onchange=actions;$('fraud-customer').onchange=transactions;
  $('fraud-agent-handoff').onclick=()=>perform(async()=>{report=await api('/api/fraud-agent/handoff',{run_id:report.investigation.id})});
  $('demo-analyst-approve').onclick=()=>perform(async()=>{report=await api('/api/world/demo-approve',{expected_run:state.data.demo.run_id,report_id:report.id,investigation_id:report.investigation.id})});
  $('fraud-review-form').onsubmit=e=>{e.preventDefault();perform(async()=>{
    report=await api('/api/fraud-desk/review',{report_id:report.id,investigation_id:report.investigation.id,disposition:$('fraud-disposition').value,action:$('fraud-action').value,note:$('fraud-note').value,publish_memory:$('fraud-publish').checked,lesson:$('fraud-lesson').value,next_question:$('fraud-question').value});
  })};
  $('prevention-learn').onclick=()=>perform(async()=>{await api('/api/prevention/learn',{report_id:report.id})});
  $('prevention-activate').onclick=()=>perform(async()=>{await api('/api/prevention/activate',{rule_id:report.prevention.rule.id,enabled:true})});
  $('prevention-disable').onclick=()=>perform(async()=>{await api('/api/prevention/activate',{rule_id:report.prevention.rule.id,enabled:false})});
  $('prevention-prove').onclick=()=>perform(async()=>{await api('/api/world/prove',{expected_run:state.data.demo.run_id});location.hash='';});
  $('fraud-reply-form').onsubmit=e=>{e.preventDefault();perform(async()=>{report=await api('/api/fraud-desk/reply',{report_id:report.id,answer:$('fraud-reply').value,expected_revision:report.revision});$('fraud-reply').value='';if(report.auto_resume_error)error(report.auto_resume_error)})};
  $('fraud-report-form').onsubmit=e=>{e.preventDefault();perform(async()=>{report=await api('/api/fraud-desk/report',{customer_id:$('fraud-customer').value,story:$('fraud-report-story').value,message:$('fraud-report-message').value,event_ids:[$('fraud-event').value],request_id:crypto.randomUUID()});$('fraud-new-report').open=false;focusCustomer(report.customer_id)})};
  return {load,demo,open:select,startInvestigation:()=>investigate(true),reset:()=>{clearTimeout(pollTimer);report=null;dashboard=null;pollRun='';pollKey='';pollProblem='';$('demo-analyst-approve').disabled=true;$('demo-analyst-case').textContent='Open a completed case.';$('demo-analyst-status').textContent=''}};
}
