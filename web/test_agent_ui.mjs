import assert from 'node:assert/strict';
import {test} from 'node:test';
import {caseProgress,publicEvidence,cleanText} from './dist/agent-ui.js';

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
