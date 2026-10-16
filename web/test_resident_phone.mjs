import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {residentPhoneStory,formatPesos} from './dist/resident-phone.js';
import {createRecordedDemo} from './dist/demo-replay.js';
import {demoBeats} from './dist/demo-guide.js';

const recording=JSON.parse(readFileSync(new URL('./dist/demo-recording.json',import.meta.url)));
function playback(actions=['payments','scam','investigate','review','learn','activate','prove']){
  const replay=createRecordedDemo(recording,'phone-test');for(const action of actions)replay.action(action);return replay;
}

test('customer scenes use the recorded request before the investigation starts',()=>{
  const replay=playback(['payments','scam']),data=replay.snapshot();
  const story=residentPhoneStory('message',data,null);
  assert.equal(story.message,recording.report.message);
  assert.equal(story.amount,recording.report.transactions[0].amount_minor);
  assert.equal(story.customerId,recording.report.customer_id);
  assert.equal(story.settled,true);
  assert.equal(replay.detail().investigation,null);
  assert.deepEqual(demoBeats(data.demo,null).map(b=>b.id),['world','payments','message','payment','complaint']);
});

test('a hold and legitimate success come from separate, case-linked payment receipts',()=>{
  const replay=playback(),data=replay.snapshot(),report=replay.detail();
  const hold=residentPhoneStory('protected',data,report),sent=residentPhoneStory('payment-sent',data,report);
  assert.equal(hold.held,true);assert.equal(hold.customerId,'C002');
  assert.equal(hold.payee,recording.proof.changed_recipient);
  assert.notEqual(hold.payee,recording.proof.source_recipient);
  assert.equal(hold.changedRecipient,true);
  assert.equal(hold.reason,report.prevention.rule.explanation);
  assert.equal(hold.ruleId,report.prevention.rule.id);
  assert.equal(sent.settled,true);assert.equal(sent.amount,5678);
  assert.notEqual(sent.eventId,hold.eventId);
  const beats=demoBeats(data.demo,report);
  assert.deepEqual(beats.slice(-2).map(b=>[b.id,!!b.done]),[['protected',false],['payment-sent',true]]);
});

test('missing evidence and foreign cases cannot supply message, hold or success',()=>{
  const replay=playback(),data=replay.snapshot();
  const foreign={...replay.detail(),id:'another-report',message:'Foreign message'};
  data.demo.focus_report_id='missing-report';data.demo.focus_customer_id='C099';
  assert.equal(residentPhoneStory('message',data,foreign).message,null);
  assert.equal(residentPhoneStory('protected',data,foreign).held,false);
  assert.equal(residentPhoneStory('payment-sent',data,foreign).settled,false);
  data.demo.focus_report_id=null;
  assert.equal(residentPhoneStory('protected',data,null).held,false);
});

test('only the matching active approved playbook supplies verification copy',()=>{
  const replay=playback(),data=replay.snapshot(),report=replay.detail();
  report.prevention.playbook={status:'active',rule_id:report.prevention.rule.id,payload:{verification_question:'Did you call the independently verified contact?',counterexample:'An independently initiated transfer may be legitimate.'}};
  assert.equal(residentPhoneStory('protected',data,report).verification,report.prevention.playbook.payload.verification_question);
  report.prevention.playbook.rule_id='foreign-rule';
  assert.notEqual(residentPhoneStory('protected',data,report).verification,report.prevention.playbook.payload.verification_question);
  report.prevention.rule.status='rejected';
  assert.equal(residentPhoneStory('protected',data,report).ruleId,undefined);
  assert.notEqual(residentPhoneStory('protected',data,report).reason,report.prevention.rule.explanation);
});

test('receipt watch fallback, missing control and synthetic truth do not invent outcomes',()=>{
  const replay=playback(),data=replay.snapshot(),report=replay.detail();
  data.demo.protection.recent[0].rule_ids=[];report.prevention=null;
  assert.match(residentPhoneStory('protected',data,report).attribution,/recipient watch/);
  data.events=data.events.filter(e=>e.kind!=='payment'||e.customer_id!=='C002');
  assert.equal(residentPhoneStory('payment-sent',data,report).settled,false);
  const before=residentPhoneStory('protected',data,report);
  for(const event of data.events)event.metadata={...event.metadata,is_fraud:true,scam_type:'hidden',risk_score:1};
  assert.deepEqual(residentPhoneStory('protected',data,report),before);
});

test('preview and navigation never change the saved record or make network calls',()=>{
  const replay=playback(),data=replay.snapshot(),report=replay.detail(),before=JSON.stringify({data,report});
  const old=globalThis.fetch;globalThis.fetch=()=>{throw Error('No network allowed')};
  try{for(const moment of ['message','payment','complaint','repeat','protected','payment-sent'])residentPhoneStory(moment,data,report)}finally{globalThis.fetch=old}
  assert.equal(JSON.stringify({data,report}),before);
  const preview=residentPhoneStory('repeat',data,report);
  assert.equal(preview.preview,true);assert.equal(preview.amount,undefined);assert.equal(preview.eventId,undefined);
});

test('a conflicting event cannot be presented as a held payment',()=>{
  const replay=playback(),data=replay.snapshot();
  const held=data.events.find(e=>e.id===data.demo.protection.recent[0].id);held.status='settled';
  assert.equal(residentPhoneStory('protected',data,replay.detail()).held,false);
});

test('peso amounts preserve centavos and reject absent amounts',()=>{
  assert.equal(formatPesos(5678),'₱56.78');assert.equal(formatPesos(90000),'₱900.00');
  for(const value of [null,undefined,NaN,-1,'90000'])assert.equal(formatPesos(value),'Amount unavailable');
});

test('replay never offers customer mutations even when current-world state is supplied',async()=>{
  const {residentActions,residentActionPayload}=await import('./dist/resident-phone.js');
  const replay=playback(),data=replay.snapshot();
  data.resident_requests=[{event_id:data.demo.protection.recent[0].id,payment_status:'cancelled',revision:9}];
  const story=residentPhoneStory('protected',data,replay.detail());
  assert.equal(story.workflow,null);assert.deepEqual(residentActions(story),[]);
  assert.throws(()=>residentActionPayload(story,'cancel','','one-request'),/unavailable/);
});

test('current-world actions carry the exact scene, held event and revision',async()=>{
  const {residentActions,residentActionPayload}=await import('./dist/resident-phone.js');
  const replay=playback(),data=replay.snapshot();data.demo.replay=false;
  const heldId=data.demo.protection.recent[0].id;
  data.resident_requests=[{event_id:'unrelated',revision:20},{event_id:heldId,revision:2,verification_status:'pending',support_status:'open',payment_status:'held'}];
  const story=residentPhoneStory('protected',data,replay.detail());
  assert.deepEqual(residentActions(story),['cancel']);
  assert.deepEqual(residentActionPayload(story,'cancel','','unique-request'),{scene_id:data.demo.scene_id,event_id:heldId,expected_revision:2,request_id:'unique-request',action:'cancel',note:''});
  story.workflow.payment_status='cancelled';assert.deepEqual(residentActions(story),[]);
  delete story.workflow;assert.deepEqual(residentActions(story),['cancel','verify','support']);
  story.held=false;assert.deepEqual(residentActions(story),[]);
});
