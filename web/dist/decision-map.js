// A view of public tool receipts. No generated explanations or private reasoning.
import {agentIcon,cleanText,pretty,toolLabels} from './agent-ui.js';
import {roleNames} from './harness-ui.js';

const text=value=>typeof value==='string'?cleanText(value):'';
export const manualInvestigation=run=>!!(run?.context?.manual_handoff||(run?.trace?.length&&run?.context?.controller!=='adk'));
export function decisionTrail(report){
  const run=report?.investigation,scope=run?.context?.snapshot_id||run?.snapshot?.id;
  const rows=report?.decision_trail?.length?report.decision_trail:
    run?.context?.controller==='adk'?(run.trace||[]).map(t=>({...t,number:t.step,purpose:t.summary,result:t.output,status:'completed'})):[];
  return rows.filter(t=>(!run?.id||!t.run_id||t.run_id===run.id)&&
    (!scope||t.status!=='completed'||t.provenance?.snapshot_id===scope));
}

export function decisionResult(turn){
  const r=turn?.result||{},facts=[];
  if(turn?.status!=='completed')return {facts,summary:turn?.status==='responded'?'Tool requested; its result is not recorded yet.':turn?.status==='failed'?text(turn.error)||'The request stopped. No result was recorded.':'Waiting for a recorded decision.',unknowns:[]};
  if(r.transactions){
    facts.push(`${r.transactions.length} payment${r.transactions.length===1?'':'s'} verified`);
    const source=r.warehouse?.source;
    if(source)facts.push(source.analytics_sync==='deferred'?'Frozen ledger · analytics sync deferred':source.analytics_sync==='matched_completed_publication'?'Matching publication reused':'Pinned customer history');
  }else if(r.receipts){
    for(const p of r.receipts.slice(0,2))facts.push(`${text(p.manifest?.name)||'Signal check'}: ${text(p.prediction?.result)||pretty(p.status)}`);
  }else if(r.matches)facts.push(`${r.matches.length} approved lesson${r.matches.length===1?'':'s'} found`);
  else if(r.related_transfers)facts.push(`${r.related_transfers.length} related transfer${r.related_transfers.length===1?'':'s'} found`);
  else if(r.models)facts.push(`${r.models.length} registered checks available`);
  else if(turn.tool==='delegate_question')facts.push(roleNames[r.role]||pretty(r.role)||'Scoped specialist requested');
  else if(turn.tool==='return_finding')facts.push(text(r.summary||r.finding?.summary)||pretty(r.assessment||r.finding?.assessment)||'Finding returned to the lead');
  else if(turn.tool==='ask_customer')facts.push(text(r.question));
  else if(['submit_case_resolution','submit_for_review'].includes(turn.tool))facts.push(r.status==='revision_required'?'Draft withheld by validation':'Proposal sent for analyst review');
  else if(r.features)facts.push(`${r.features.payment_count??'Unknown'} recorded payments in scope`);
  const unknowns=[...(r.uncertainties||r.finding?.uncertainties||r.recommendation?.uncertainties||[])];
  if(r.receipts)for(const p of r.receipts)if(p.missing_inputs?.length)unknowns.push('Missing inputs: '+[...new Set(p.missing_inputs.flatMap(i=>i.fields||[]))].map(pretty).join(', '));
  if(r.harness_judges?.passed===false)unknowns.push(...r.harness_judges.judges.flatMap(j=>j.blockers||[]));
  return {facts:facts.filter(Boolean),summary:text(turn.finding)||facts.filter(Boolean).join('. ')||'Tool receipt recorded.',unknowns:unknowns.map(text).filter(Boolean)};
}

export function decisionMap(report,selected=null){
  const run=report?.investigation,trail=decisionTrail(report),focus=selected===null?trail.at(-1):trail.find(t=>t.number===selected);
  const index=trail.indexOf(focus),next=trail[index+1],result=decisionResult(focus);
  const working=['running','stepping'].includes(run?.status),manual=manualInvestigation(run);
  const phase=focus?.status==='completed'?'recorded':focus?.status==='responded'?'executing':focus?.status==='failed'?'stopped':working?'choosing':'waiting';
  const origin=focus?.provider||run?.provider||run?.context?.provider;
  const live=working&&(selected===null||(focus===trail.at(-1)&&focus?.status!=='completed'));
  let nextAction=next?.tool?'Next recorded choice: '+(toolLabels[next.tool]||pretty(next.tool)):
    working?'The agent will choose after reading the result.':report?.status==='awaiting_customer'?'Waiting for the customer’s answer.':
    manual?'Saved evidence goes to a manual review.':run?.recommendation?'Next: Fraud Analyst review.':'Waiting for a recorded agent action.';
  if(['failed','interrupted','budget_exhausted'].includes(run?.status))nextAction='Investigation stopped. No automatic retry.';
  return {phase,live,manual,selected:focus?.number??null,
    badge:report?.presentation_mode==='replay'?'Recorded Gemini replay':origin==='gemini'?(live?'Live agent':'Recorded live decision'):origin==='fake'?'Offline rehearsal':manual?'Manual evidence review':'Waiting for investigator',
    actor:!focus&&manual?'Fraud Analyst':roleNames[focus?.role]||'Resolution agent',actorIcon:!focus&&manual?'human':focus?.role&& !['resolution','case_lead'].includes(focus.role)?'specialist':'resolution',
    tool:focus?.tool||null,toolLabel:focus?.tool?(toolLabels[focus.tool]||pretty(focus.tool)):working?'Choosing a tool':'No tool chosen yet',
    reason:text(focus?.purpose)||'No public decision summary has been recorded yet.',
    result,nextAction,completed:trail.filter(t=>t.status==='completed').length,
    trail:trail.map(t=>({number:t.number,label:t.tool?(toolLabels[t.tool]||pretty(t.tool)):'Choosing next action',status:t.status,selected:t===focus})),
    receipt:focus?.turn_id||null,snapshot:focus?.provenance?.snapshot_id||null};
}

const el=(tag,value,cls)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=value;if(cls)n.className=cls;return n};
export function renderDecisionMap(root,report,{selected=null,compact=false,onSelect}={}){
  const d=decisionMap(report,selected);root.replaceChildren();root.classList.add('decision-map');root.classList.toggle('decision-map-compact',compact);root.dataset.phase=d.phase;
  const header=el('header',undefined,'decision-map-heading'),title=el('div');title.append(agentIcon('resolution'),el('strong','Agent decision map'));
  header.append(title,el('span',d.badge,'decision-origin'));root.append(header);
  if(onSelect&&selected!==null){const follow=el('button','Follow latest','text-button');follow.type='button';follow.onclick=()=>onSelect(null);header.append(follow)}
  const path=el('ol',undefined,'decision-path');path.setAttribute('aria-label','Actual tool choices in recorded order');
  for(const step of d.trail){const li=el('li',undefined,step.selected?'selected':'');const n=el(onSelect?'button':'span',step.label);if(onSelect){n.type='button';n.onclick=()=>onSelect(step.number)}if(step.selected)n.setAttribute('aria-current','step');li.append(n);path.append(li)}
  if(d.trail.length)root.append(path);
  const loop=el('div',undefined,'decision-loop');loop.setAttribute('role','group');loop.setAttribute('aria-label',`${d.actor} chooses ${d.toolLabel}, then reads the recorded result`);
  function node(role,label,caption,cls){const n=el('section',undefined,'decision-node '+cls);n.append(agentIcon(role),el('strong',label));if(caption)n.append(el('small',caption));return n}
  const actor=node(d.actorIcon,d.actor,{choosing:'Choosing the next action',recorded:'Decision recorded',executing:'Tool requested',stopped:'Request stopped',waiting:d.manual?'Manual evidence review':'Waiting for evidence'}[d.phase],'decision-actor');
  if(d.phase==='choosing'&&d.live)actor.classList.add('is-working');
  const tool=node(['delegate_question','return_finding'].includes(d.tool)?'specialist':d.tool?.includes('submit')?'judge':'knowledge',d.toolLabel,
    d.phase==='executing'?'Request validated · running':d.tool?'Selected by the agent':'Waiting for a choice','decision-tool');
  if(d.tool)tool.append(el('code',d.tool,'decision-tool-name'));
  if(d.phase==='executing'&&d.live)tool.classList.add('is-working');
  const outcome=node(d.tool==='return_finding'?'resolution':'judge',d.phase==='stopped'?'No result recorded':d.phase!=='recorded'?'Awaiting result':d.tool==='return_finding'?'Back to the lead':'Recorded result',null,'decision-outcome');
  const facts=el('ul');for(const fact of (d.result.facts.length?d.result.facts:[d.result.summary]).slice(0,2)){const li=el('li',fact.length>110?fact.slice(0,107)+'…':fact);li.setAttribute('aria-label',fact);facts.append(li)}outcome.append(facts);
  for(const n of [actor,el('span','→','decision-arrow'),tool,el('span','→','decision-arrow'),outcome])loop.append(n);root.append(loop);
  const feedback=el('div',undefined,'decision-feedback');
  feedback.innerHTML='<svg viewBox="0 0 800 45" preserveAspectRatio="none" aria-hidden="true"><path d="M714 1V20Q714 35 698 35H104Q88 35 88 20V6m-5 7 5-7 5 7" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>';
  feedback.append(el('span',d.phase==='stopped'?'No result to continue from':d.tool==='return_finding'?'The lead receives the specialist’s finding':d.phase==='recorded'?'Result returned to the agent':d.phase==='executing'?'Waiting for the tool result':'The next tool is not predetermined'));root.append(feedback);
  if(!compact){const why=el('div',undefined,'decision-reason');why.append(el('small','Agent’s stated reason'),el('p',d.reason));root.append(why)}
  if(d.result.unknowns.length){const unknown=el('p',undefined,'decision-unknown');unknown.append(el('strong','Still unverified: '),document.createTextNode(d.result.unknowns[0]));root.append(unknown)}
  root.append(el('p',d.nextAction,'decision-next'));
  return d;
}
