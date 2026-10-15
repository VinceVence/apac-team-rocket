// Saved offline evidence only. Opening this panel never starts a study or model.
export async function showEvaluation(root){
  const response=await fetch('evaluation-summary.json');if(!response.ok)return;
  const data=await response.json(),p=data.payments;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  root.replaceChildren();root.append(el('span','Saved evaluation · synthetic data','eyebrow'),el('h2','Evidence, including the misses'));
  const metrics=el('div',undefined,'evaluation-metrics');
  for(const [value,label,detail] of [
    [`${p.scams_before} → ${p.scams_after} / 50`,'Scams intercepted','Same payments, before and after learning'],
    [`${p.legitimate_settled} / 50`,'Legitimate payments completed',`${p.legitimate_held} held in this test bank`],
    [Object.values(data.investigations.arms).reduce((n,a)=>n+a.review_ready,0)+' / 24','Review packets ready','Fake-model execution checks; not AI accuracy']]){
    const item=el('article');item.append(el('strong',value),el('h3',label),el('p',detail));metrics.append(item);
  }
  root.append(metrics,el('p',data.scope,'surface-note'));
  const details=el('details',undefined,'world-details');details.append(el('summary','See failures, model results & comparison'));
  const table=el('table',undefined,'evaluation-table'),head=el('tr');for(const label of ['Scam family','Stopped / 10','Candidate'])head.append(el('th',label));table.append(head);
  for(const f of p.families){const row=el('tr');for(const text of [f.family.replaceAll('_',' '),String(f.scams_stopped),f.candidate_rejected?'Rejected':'Passed replay'])row.append(el('td',text));table.append(row)}
  details.append(table,el('p','Missed paraphrases and small-amount cases remain visible. The investment candidate was rejected because a legitimate control matched. Held payments had zero debit.'));
  const m=data.trained_model;details.append(el('h3','Learned predictor · advisory only'),el('p',`${m.test.caught} / ${m.test.positives} synthetic scams detected; ${m.test.false_holds} / ${m.test.negatives} legitimate examples flagged. ${m.prevention_gate_passed?'Passed the synthetic gate.':'Failed the prevention release gate.'} This is a locally trained baseline; Karlo’s reviewed artifact is still pending.`));
  details.append(el('h3','Single lead versus selective specialist'));
  for(const [name,a] of Object.entries(data.investigations.arms))details.append(el('p',`${name==='single'?'Single lead':'Selective specialist'}: ${a.review_ready}/${a.cases} review-ready; ${a.calls} fake generations. Same frozen payment evidence and limits.`));
  details.append(el('p','The extra role adds calls in this rehearsal. Live Gemini evaluation is required before claiming better decisions.','surface-note'));
  details.append(el('code',data.reproduce));root.append(details);root.hidden=false;
}
