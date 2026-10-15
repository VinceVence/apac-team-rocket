import assert from 'node:assert/strict';
import {test} from 'node:test';
import {caseProgress,publicEvidence,cleanText,caseActivity} from './dist/agent-ui.js';

test('UI receipt projection removes provider and spending details without changing the record',()=>{
  const receipt={model:'gemini-3.5-flash-lite',budget:{total_usd:8},cost_usd:.01,source:'snapshot',result:{model_version:'v1',receipt_id:'r1',signal_score:0,missing_inputs:['device']}};
  const original=structuredClone(receipt),visible=publicEvidence(receipt);
  assert.deepEqual(visible,{source:'snapshot',result:{receipt_id:'r1',signal_score:0,missing_inputs:['device']}});
  assert.deepEqual(receipt,original);assert.equal(cleanText('gemini-3.5-flash-lite paused at $0.05'),'agent paused at configured limit');
});
test('tracker distinguishes investigation, human review and prevention failures',()=>{
  assert.equal(caseProgress({status:'investigating',investigation:{context:{execution:{status:'running'}}}}).working,true);
  const review=caseProgress({status:'awaiting_review',investigation:{status:'awaiting_review'}});
  assert.equal(review.current,1);assert.equal(review.statuses[1],'Your decision');
  const rejected=caseProgress({status:'resolved',reviews:[{}],prevention:{status:'rejected',rule:{status:'rejected'}}});
  assert.equal(rejected.current,2);assert.equal(rejected.statuses[2],'Needs revision');assert.equal(rejected.protected,false);
});
test('a saved review or different case is never presented as current payment protection',()=>{
  const r={id:'a',status:'resolved',reviews:[{}],prevention:{status:'awaiting_activation',rule:{status:'proposed'}}};
  assert.equal(caseProgress(r).statuses[2],'Ready to enable');
  r.prevention.rule.status='active';
  assert.equal(caseProgress(r,{focus_report_id:'b',phase:'protected'}).protected,false);
  assert.equal(caseProgress(r,{focus_report_id:'a',phase:'protected'}).protected,true);
});

test('watch the reported case before the worker or investigation exists',()=>{
  const report={id:'case',status:'reported',investigation:null,preparation:{status:'running',stage:'simulation_data',detail:'Saving case tables.'}};
  assert.equal(caseActivity(report).poll,true);assert.equal(caseActivity(report).stage,'evidence');
  assert.equal(caseActivity(report).action,null);
  delete report.preparation;
  assert.equal(caseActivity(report,{focus_report_id:'case'}).poll,true);
  assert.equal(caseActivity(report,{}).action,'start');
});

test('a preparation failure is visible and never starts or retries a model automatically',()=>{
  const report={id:'case',status:'reported',preparation:{status:'blocked',detail:'Snapshot needs operator review.'}};
  const a=caseActivity(report,{focus_report_id:'case'});
  assert.equal(a.active,false);assert.equal(a.poll,false);assert.equal(a.stage,'blocked');assert.equal(a.action,'refresh');
});

test('watch transitions from handoff to reserved generation and then human review',()=>{
  const report={id:'case',status:'investigating',investigation:{status:'running',context:{execution:{status:'queued'}}},decision_trail:[]};
  assert.equal(caseActivity(report).poll,true);
  report.investigation.context.execution.status='running';report.decision_trail=[{number:1,status:'reserved'}];
  assert.equal(caseActivity(report).completed.length,0);assert.equal(caseActivity(report).active,true);
  report.decision_trail=[{number:1,status:'completed',tool:'get_case_evidence',result:{transactions:[{}]}}];
  report.status='awaiting_review';report.investigation.status='awaiting_review';report.investigation.context.execution.status='awaiting_review';
  const a=caseActivity(report);assert.equal(a.poll,false);assert.equal(a.stage,'review');assert.equal(a.completed.length,1);
});
