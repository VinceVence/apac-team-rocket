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
export function caseProgress(report,demo={}){
  const run=report?.investigation,job=report?.prevention,reviewed=!!report?.reviews?.length&&report.status==='resolved';
  const stopped=['failed','interrupted','budget_exhausted'].includes(run?.status);
  const attention=stopped||report?.status==='needs_review';
  const current=reviewed?2:report?.status==='awaiting_review'||attention?1:0;
  const working=['queued','running'].includes(run?.context?.execution?.status);
  const learning=['queued','running'].includes(job?.status);
  const active=job?.rule?.status==='active',protectedCase=active&&demo.focus_report_id===report?.id&&demo.phase==='protected';
  const statuses=[reviewed||report?.status==='awaiting_review'?'Investigation complete':attention?'Needs attention':report?.status==='awaiting_customer'?'Waiting for customer':working?'Investigating':'Ready',
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
