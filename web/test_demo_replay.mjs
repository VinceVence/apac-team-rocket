import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {createRecordedDemo} from './dist/demo-replay.js';
import {demoBeats,nextGuideStep} from './dist/demo-guide.js';
import {decisionMap} from './dist/decision-map.js';
const recording=JSON.parse(readFileSync(new URL('./dist/demo-recording.json',import.meta.url)));
test('saved Gemini demo completes using Next only, without fetch or a paid call',()=>{
 const old=globalThis.fetch;globalThis.fetch=()=>{throw Error('Playback must never use the network')};
 try{
  const replay=createRecordedDemo(recording,'test'),seen=new Set();let current='world',completed=false;
  assert.equal(replay.snapshot().events.length,0);
  for(let n=0;n<30;n++){
   const state=replay.snapshot(),report=state.demo.focus_report_id?replay.detail():null;
   const b=demoBeats(state.demo,report).find(b=>b.id===current);assert.ok(b,current);seen.add(current);
   if(b.done){completed=true;break}
   if(b.action)replay.api('/api/world/demo-action',{action:b.action});
   const after=replay.snapshot();current=nextGuideStep(demoBeats(after.demo,after.demo.focus_report_id?replay.detail():null),current,seen);assert.ok(current,'Next must always have a destination');
  }
  assert.equal(completed,true);assert.equal(replay.snapshot().demo.blocked_payments,1);
  assert.notEqual(recording.proof.changed_recipient,recording.proof.source_recipient);
  assert.equal(recording.proof.wallet_debit_minor,0);assert.equal(recording.proof.legitimate_payment,'settled');
  assert.equal(replay.detail().investigation.provider,'gemini');assert.equal(decisionMap(replay.detail()).badge,'Recorded Gemini replay');
  assert.ok(seen.has('complaint')&&seen.has('turn-2')&&seen.has('review')&&seen.has('knowledge')&&seen.has('repeat'));
  assert.ok(seen.has('classifier-result-2-0')&&seen.has('classifier-use'));
 }finally{globalThis.fetch=old}
});
test('replay cannot substitute a rule-only recording for the promised classifier demonstration',()=>{
 const changed=structuredClone(recording);
 for(const t of changed.report.decision_trail)if(t.result?.receipts)t.result.receipts=t.result.receipts.filter(r=>r.score_kind!=='uncalibrated_model_score');
 assert.throws(()=>createRecordedDemo(changed,'missing-classifier'),/trained-classifier/);
});
test('a rejected recorded resolution cannot be presented as approved',()=>{
 const changed=structuredClone(recording);changed.report.harness.checks.unshift({passed:false,judges:[{judge:'resolution',passed:false}]});
 assert.throws(()=>createRecordedDemo(changed,'rejected'),/review checks/);
});
test('playback rejects mutations and preserves recorded receipts across restarts',()=>{
 const replay=createRecordedDemo(recording,'first');
 assert.throws(()=>replay.api('/api/fraud-desk/review',{}),/cannot change/);
 assert.throws(()=>replay.action('prove'),/preceding/);
 for(const action of ['payments','scam','investigate'])replay.action(action);
 assert.deepEqual(replay.detail().decision_trail,recording.report.decision_trail);
 assert.equal(createRecordedDemo(recording,'second').snapshot().events.length,0);
 assert.equal(recording.report.status,'resolved');
});
