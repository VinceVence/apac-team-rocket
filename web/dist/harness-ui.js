// Case state and public receipts only; never model chain-of-thought.
import {agentIcon,publicEventText} from './agent-ui.js';
export const roleNames={resolution:'Resolution agent',case_lead:'Resolution agent',transaction_specialist:'Transactions',device_specialist:'Device & identity',scam_specialist:'Scam context',resolution_critic:'Resolution critic'};
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
export function renderHarness(harness,aliases){
  const panel=document.getElementById('harness-panel');panel.hidden=!harness?.enabled;if(!harness?.enabled)return;
  panel.replaceChildren();const head=el('div',undefined,'harness-heading');
  head.append(agentIcon('judge'),el('strong','Validation checks'));panel.append(head);
  const task=harness.tasks[0];
  const latest=harness.checks.find(c=>c.judges.some(j=>j.judge==='resolution')),strip=el('div',undefined,'harness-judges');
  for(const name of ['evidence','models','resolution']){
    const check=latest?.judges.find(j=>j.judge===name),state=check?(check.skipped?'not used':check.passed?'passed':'blocked'):'pending';
    strip.append(el('span',`${{evidence:'Evidence',models:'Detector inputs',resolution:'Resolution'}[name]} · ${state}`,'judge-pill '+state));
  }
  panel.append(strip);
  const details=el('details',undefined,'world-details harness-details');details.append(el('summary','Specialist findings & validation details'));
  if(task){details.append(el('p',roleNames[task.role]+': '+publicEventText(task.question,aliases),'harness-question'));if(task.finding)details.append(el('p',publicEventText(task.finding.summary,aliases),'harness-finding'))}
  details.append(el('p','These checks support human review. They do not establish fraud.','surface-note'));
  for(const check of harness.checks){
    const item=el('div',undefined,'harness-verdict');item.append(el('strong',check.mode==='manual_handoff_checks'?'Manual evidence ready for the analyst':check.passed?'Draft passed the checks':'Draft or tool action withheld'));
    for(const judge of check.judges){item.append(el('small',publicEventText(`${judge.name}: ${judge.skipped?'previous inferences discarded':judge.passed?'passed':judge.blockers.join(' ')}`,aliases)))}details.append(item);
  }
  for(const r of harness.model_receipts){
    const item=el('div',undefined,'harness-receipt');item.append(el('strong','Evidence check · '+r.status.replaceAll('_',' ')),el('p',r.target),el('small','Signal score · not a fraud probability'));
    if(r.prediction?.signal_score!==null&&r.prediction?.signal_score!==undefined)item.append(el('small',`Signal ${r.prediction.signal_score.toFixed(2)} · ${r.prediction.result}`));
    if(r.missing_inputs.length)item.append(el('small','Missing: '+[...new Set(r.missing_inputs.flatMap(x=>x.fields))].join(', ')));
    item.append(el('small',`${r.receipt_id} · ${r.snapshot_id}`));details.append(item);
  }
  panel.append(details);
}
