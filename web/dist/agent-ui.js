const paths={
  resolution:'<path d="M12 10v-3m-2 0h4M6 13a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v7H6z"/><path d="M10 14v2m5-2v2M9 20v3m8-3v3"/><circle cx="22" cy="21" r="4"/><path d="m25 24 3 3"/>',
  prevention:'<path d="M16 5 6 9v7c0 6 10 11 10 11s10-5 10-11V9z"/><path d="m11 16 4 4 7-8"/>',
  human:'<circle cx="16" cy="10" r="5"/><path d="M6 27v-3a10 10 0 0 1 20 0v3M12 20l4 4 4-4"/>',
  specialist:'<circle cx="12" cy="12" r="5"/><path d="M3 27v-3a9 9 0 0 1 18 0v3m0-20a5 5 0 0 1 0 10m3 3a7 7 0 0 1 5 7"/>',
  judge:'<path d="M7 6h18v22H7zM11 6V3h10v3m-10 8 2 2 3-4m2 3h3m-10 7 2 2 3-4m2 3h3"/>',
  scientist:'<path d="M12 4h8m-6 0v8L6 25a2 2 0 0 0 2 3h16a2 2 0 0 0 2-3l-8-13V4M10 20h12"/><circle cx="17" cy="24" r="1"/>',
  knowledge:'<path d="M5 6h9l2 2 2-2h9v20h-9l-2 2-2-2H5zM16 8v20M8 11h5m-5 5h5m6-5h5m-5 5h5"/>',
};
export function agentIcon(role){
  const e=document.createElement('span');e.className='role-icon role-'+role;e.setAttribute('aria-hidden','true');
  e.innerHTML='<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+(paths[role]||paths.resolution)+'</svg>';return e;
}
export function mountAgentIcons(){document.querySelectorAll('[data-agent-icon]').forEach(n=>n.replaceChildren(agentIcon(n.dataset.agentIcon)))}
export const pretty=value=>String(value||'').replaceAll('_',' ').replace(/\b\w/,c=>c.toUpperCase());
export const toolLabels={get_case_evidence:'Verify the case records',get_transactions:'Verify the transfers',get_customer_features:'Check customer history',compare_behavior:'Compare spending patterns',trace_recipient:'Trace the recipient',list_eligible_models:'Choose relevant checks',score_models:'Check payment signals',run_fraud_detectors:'Check payment signals',search_reviewed_cases:'Find an approved lesson',get_complaint_guidance:'Check complaint guidance',delegate_question:'Ask a specialist',return_finding:'Specialist returns a finding',ask_customer:'Ask the customer',submit_case_resolution:'Propose a resolution',submit_for_review:'Propose a resolution'};

// UI projection only. Billing and original receipts remain unchanged on the server.
export function cleanText(value){return String(value??'').replace(/\b(?:gemini|gpt|claude|FakeInvestigator|FakePreventionLearner)[\w.:-]*/gi,'agent').replace(/\$\s*\d+(?:\.\d+)?(?:\s*USD)?/g,'configured limit')}
export function publicEvidence(value){
  if(Array.isArray(value))return value.map(publicEvidence);
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).filter(([k])=>!/(?:cost|budget|usd|microusd|tokens|provider|model|manifest|artifact|calls|reservation)/i.test(k)).map(([k,v])=>[k,publicEvidence(v)]));
  return typeof value==='string'?cleanText(value):value;
}
export function caseActivity(report,demo={}){
  const run=report?.investigation,prep=report?.preparation,execution=run?.context?.execution?.status;
  const trail=report?.decision_trail||[],completed=trail.filter(t=>t.status==='completed'&&t.tool),last=trail.at(-1);
  const base={completed,latest:last,poll:false,active:false,action:null,stage:'report'};
  if(report?.status==='resolved')return {...base,stage:'review',title:'Analyst resolution recorded',detail:'The reviewed case can inform prevention.'};
  if(report?.status==='awaiting_customer')return {...base,stage:'customer',title:'The agent needs a customer answer',detail:cleanText(run?.context?.pending_question||'Answer the saved follow-up question to continue.')};
  if(report?.status==='awaiting_review'||run?.recommendation)return {...base,stage:'review',title:'Ready for the risk analyst',detail:'The recorded checks and proposed resolution are ready below.'};
  if(['blocked','interrupted'].includes(prep?.status)&&!completed.length)return {...base,stage:'blocked',title:'Evidence preparation needs attention',detail:cleanText(prep.detail),action:'refresh'};
  if(['failed','budget_exhausted','interrupted'].includes(run?.status))return {...base,stage:'blocked',title:'Investigation paused for review',detail:'The saved evidence is available. No model request will be retried automatically.',action:report?.harness?.can_resume?'start':'refresh'};
  if(['queued','running'].includes(execution))return {...base,stage:'agent',active:true,poll:true,title:execution==='queued'?'Investigator queued':last?.status==='responded'?'Executing the chosen tool':'Resolution agent is working',detail:last?.status==='responded'&&last.tool?(toolLabels[last.tool]||pretty(last.tool)):completed.length?'Reviewing the last result and choosing the next check.':'Reading the complaint and choosing the first check.'};
  const incident=(demo.incidents||[]).find(i=>i.report_id===report?.id);
  if(!run&&incident?.status==='needs_review')return {...base,stage:'blocked',title:'The case needs attention',detail:cleanText(demo.note||'Evidence preparation stopped. Inspect the saved case.'),action:'refresh'};
  if(!run&&(prep?.status==='running'||(report?.status==='reported'&&demo.focus_report_id===report?.id)))return {...base,stage:'evidence',active:true,poll:true,title:prep?.stage==='simulation_data'?'Saving simulation data':prep?.stage==='dispatch'?'Handing evidence to the agent':'Preparing the case evidence',detail:cleanText(prep?.detail||'The report is saved. Transaction snapshots are being prepared before the investigator starts.')};
  return {...base,stage:'ready',title:'Ready to investigate',detail:'Start the investigation to let the agent choose its checks.',action:'start'};
}
export function renderAgentActivity(report,demo,onNavigate){
  const a=caseActivity(report,demo),root=document.getElementById('agent-live-panel');root.replaceChildren();root.dataset.stage=a.stage;root.classList.toggle('is-live',a.active);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  const head=el('header'),heading=el('div');heading.append(el('strong',a.title),el('p',a.detail));head.append(heading,el('span',a.active?'Live':a.completed.length?'Recorded activity':'Case status','activity-state'));root.append(head);
  const graph=el('div',undefined,'activity-route'),agentDone=['review','customer'].includes(a.stage);
  for(const [icon,label,state] of [['human','Report','complete'],['knowledge','Evidence',a.stage==='evidence'?'active':report.investigation?.snapshot?'complete':'pending'],['resolution','Agent',a.stage==='agent'?'active':agentDone?'complete':'pending'],['human','Review',report.status==='resolved'?'complete':a.stage==='review'?'active':'pending']]){
    const n=el('div',undefined,'activity-node '+state);n.append(agentIcon(icon),el('strong',label),el('small',state==='complete'?'Ready':state==='active'?(a.active?'Working':'Your turn'):'Next'));graph.append(n);
  }
  root.append(graph);
  const task=report.harness?.tasks?.[0];
  if(task){const handoff=el('div',undefined,'activity-delegation');handoff.append(agentIcon('specialist'),el('strong',pretty(task.role)),el('span',task.status==='completed'?'Finding returned to the lead':'Reviewing the delegated question'));root.append(handoff)}
  if(a.completed.length||a.stage==='agent'){
    const choices=el('div',undefined,'activity-choices');choices.append(el('small','Agent choices'));
    for(const t of a.completed){const b=el('button',`${t.number}. ${toolLabels[t.tool]||pretty(t.tool)}`,'activity-choice');b.type='button';b.onclick=()=>{onNavigate();const step=document.getElementById('guide-turn-'+t.number);if(step){step.open=true;step.scrollIntoView({behavior:'smooth',block:'start'})}};choices.append(b)}
    if(a.stage==='agent')choices.append(el('span',a.latest?.status==='responded'&&a.latest.tool?(toolLabels[a.latest.tool]||pretty(a.latest.tool)):'Choosing the next check…','activity-choice in-progress'));root.append(choices);
  }
  const result=a.completed.at(-1)?.result,proof=el('div',undefined,'activity-proof');
  const evidence=a.completed.find(t=>['get_case_evidence','get_transactions'].includes(t.tool))?.result?.transactions;
  if(evidence)proof.append(el('span',`${evidence.length} transfer${evidence.length===1?'':'s'} verified`));
  const signals=a.completed.filter(t=>['score_models','run_fraud_detectors'].includes(t.tool));
  if(signals.length)proof.append(el('span','Payment signals checked'));
  if(result?.status==='revision_required')proof.append(el('span','Draft withheld by checks','activity-warning'));
  if(report.investigation?.recommendation&&report.status!=='resolved')proof.append(el('span','Human approval required'));
  if(proof.childNodes.length)root.append(proof);
  return a;
}
export function renderPreventionFlow(job){
  const root=document.getElementById('prevention-flow'),rule=job?.rule,working=['queued','running'].includes(job?.status),failed=['failed','interrupted','budget_exhausted','rejected'].includes(job?.status);
  root.replaceChildren();root.classList.toggle('is-live',working);
  for(const [icon,label,state] of [['knowledge','Lesson','complete'],['prevention','Candidate',rule?'complete':failed?'blocked':working?'active':'pending'],['judge','Replay',rule?(rule.replay.passed?'complete':'blocked'):'pending'],['human','Activate',rule?.status==='active'?'complete':rule?.replay.passed?'active':'pending']]){
    const n=document.createElement('div');n.className='activity-node '+state;n.append(agentIcon(icon));const title=document.createElement('strong'),status=document.createElement('small');title.textContent=label;status.textContent=state==='complete'?'Ready':state==='blocked'?'Needs review':state==='active'?(working?'Working':'Your turn'):'Next';n.append(title,status);root.append(n);
  }
}
export function caseProgress(report,demo={}){
  const run=report?.investigation,job=report?.prevention,reviewed=!!report?.reviews?.length&&report.status==='resolved';
  const stopped=['failed','interrupted','budget_exhausted'].includes(run?.status);
  const attention=stopped||report?.status==='needs_review'||['blocked','interrupted'].includes(report?.preparation?.status);
  const current=reviewed?2:report?.status==='awaiting_review'||stopped||report?.status==='needs_review'?1:0;
  const working=caseActivity(report,demo).active;
  const learning=['queued','running'].includes(job?.status);
  const active=job?.rule?.status==='active',protectedCase=active&&demo.focus_report_id===report?.id&&demo.phase==='protected';
  const statuses=[reviewed||report?.status==='awaiting_review'?'Investigation complete':attention?'Needs attention':report?.status==='awaiting_customer'?'Waiting for customer':working?(run?'Investigating':'Preparing evidence'):'Ready',
    reviewed?'Reviewed':current===1?'Your decision':'Waiting for evidence',
    protectedCase?'Protection verified':active?'Safeguard active':job?.status==='rejected'?'Needs revision':learning?'Learning':job?.status==='awaiting_activation'?'Ready to enable':job&&['failed','interrupted','budget_exhausted'].includes(job.status)?'Needs attention':reviewed?'Ready to learn':'Waiting for review'];
  return {current,statuses,working:working||learning,protected:protectedCase};
}
export function renderCaseTracker(report,demo,onNavigate){
  const p=caseProgress(report,demo),root=document.getElementById('case-tracker');root.replaceChildren();
  const stages=[['resolution','Resolution agent','resolution-stage'],['human','Human review','human-review-stage'],['prevention','Prevention agent','prevention-stage']];
  stages.forEach(([role,label,id],i)=>{
    const button=document.createElement('button');button.type='button';button.className='case-step '+(i<p.current||p.protected?'complete':i===p.current?'current':'waiting');if(i===p.current)button.setAttribute('aria-current','step');
    button.append(agentIcon(role));const text=document.createElement('span'),name=document.createElement('strong'),status=document.createElement('small');name.textContent=label;status.textContent=p.statuses[i];text.append(name,status);button.append(text);
    button.onclick=()=>{onNavigate();document.getElementById(id).scrollIntoView({behavior:'smooth',block:'start'})};root.append(button);
  });
  root.classList.toggle('is-working',p.working);
  for(const [i,id] of ['resolution-stage','human-review-stage','prevention-stage'].entries())document.getElementById(id).classList.toggle('stage-current',i===p.current);
  document.getElementById('resolution-stage-status').textContent=p.statuses[0];document.getElementById('human-stage-status').textContent=p.statuses[1];document.getElementById('prevention-stage-status').textContent=p.statuses[2];
  return p;
}
