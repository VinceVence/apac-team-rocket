// Case state and public receipts only; never model chain-of-thought.
export const roleNames={resolution:'Case lead',case_lead:'Case lead',transaction_specialist:'Transactions',device_specialist:'Device & identity',scam_specialist:'Scam context',resolution_critic:'Resolution critic'};
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
export function renderHarness(harness){
  const panel=document.getElementById('harness-panel');panel.hidden=!harness?.enabled;if(!harness?.enabled)return;
  panel.replaceChildren();const head=el('div',undefined,'harness-heading');
  head.append(el('strong','Investigation team'),el('span',`${harness.shared_budget?.case_calls||0}/6 shared calls · checkpoint ${harness.checkpoint.step}`));panel.append(head);
  const flow=el('div',undefined,'harness-flow'),task=harness.tasks[0];
  for(const [title,detail,active] of [['Case lead','Chooses evidence & models',harness.active_role==='case_lead'],
    [task?roleNames[task.role]:'Specialist on demand',task?task.status.replaceAll('_',' '):'Only when useful',!!task&&harness.active_role===task.role],
    ['Harness judges','Evidence · models · resolution',false],['Risk analyst','Approves the resolution',harness.active_role==='risk_analyst']]){
    const node=el('div',undefined,'harness-role'+(active?' active':''));node.append(el('span',title),el('small',detail));flow.append(node);
  }
  panel.append(flow);
  if(task){const question=el('p',task.question,'harness-question');panel.append(question);if(task.finding)panel.append(el('p',`${roleNames[task.role]}: ${task.finding.summary}`,'harness-finding'))}
  const latest=harness.checks.find(c=>c.judges.some(j=>j.judge==='resolution')),strip=el('div',undefined,'harness-judges');
  for(const name of ['evidence','models','resolution']){
    const check=latest?.judges.find(j=>j.judge===name),state=check?(check.skipped?'not used':check.passed?'passed':'blocked'):'pending';
    strip.append(el('span',`${{evidence:'Evidence',models:'Model contracts',resolution:'Resolution'}[name]} · ${state}`,'judge-pill '+state));
  }
  panel.append(strip);
  const details=el('details',undefined,'world-details harness-details');details.append(el('summary','Judge checks & model receipts'));
  details.append(el('p','Local checks enforce scope, provenance and specific unsafe claims. They do not establish fraud or replace analyst approval.','surface-note'));
  for(const check of harness.checks){
    const item=el('div',undefined,'harness-verdict');item.append(el('strong',check.mode==='manual_handoff_checks'?'Manual evidence ready for the analyst':check.passed?'Draft passed the checks':'Draft or tool action withheld'));
    for(const judge of check.judges){item.append(el('small',`${judge.name}: ${judge.skipped?'previous model inferences discarded':judge.passed?'passed':judge.blockers.join(' ')}`))}details.append(item);
  }
  for(const r of harness.model_receipts){
    const item=el('div',undefined,'harness-receipt');item.append(el('strong',`${r.manifest.name} · ${r.model_version}`),el('p',r.target),el('small',`${r.status.replaceAll('_',' ')} · ${r.score_kind.replaceAll('_',' ')} · never a fraud probability`));
    if(r.prediction?.signal_score!==null&&r.prediction?.signal_score!==undefined)item.append(el('small',`Signal ${r.prediction.signal_score.toFixed(2)} · ${r.prediction.result}`));
    if(r.missing_inputs.length)item.append(el('small','Missing: '+[...new Set(r.missing_inputs.flatMap(x=>x.fields))].join(', ')));
    item.append(el('small',`${r.receipt_id} · ${r.snapshot_id}`));details.append(item);
  }
  panel.append(details);
}
