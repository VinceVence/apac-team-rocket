import assert from 'node:assert/strict';
import {test} from 'node:test';
import {alarmMotion,protectionMotion,residentLabel,residentAlerts} from './dist/resident-sprites.js';
import {demoBeats} from './dist/demo-guide.js';

test('residents have stable numbered labels',()=>{
  assert.equal(residentLabel('C001'),'Resident 1');assert.equal(residentLabel('C100'),'Resident 100');
});
test('the initial alarm jumps briefly, then settles without requiring world ticks',()=>{
  assert.ok(alarmMotion(250).jump>10);assert.ok(alarmMotion(1000).active);
  assert.deepEqual(alarmMotion(9000),{active:false,jump:0});
  assert.deepEqual(alarmMotion(250,true),{active:true,jump:0});
});
test('protection animation settles and respects reduced motion',()=>{
  assert.ok(protectionMotion(200).lift>0);assert.deepEqual(protectionMotion(7000),{active:false,lift:0});
  assert.deepEqual(protectionMotion(200,true),{active:true,lift:0});
});
test('latest real hold gets a shield without old reports overwriting it',()=>{
  const incident={id:'report',customer_id:'C001',created_at:'2026-10-15T09:00:00Z',report_id:'case',report_status:'awaiting_review'};
  const hold={id:'held',customer_id:'C001',created_at:'2026-10-15T10:00:00Z'};
  assert.deepEqual(residentAlerts({incidents:[incident],protection:{recent:[hold]}}),[{customer_id:'C001',id:'held',mark:'✓'}]);
  assert.deepEqual(residentAlerts({incidents:[{...incident,report_status:'resolved'}],protection:{recent:[]}}),[]);
});
test('the guide highlights the reporting sprite, with a fallback for saved resolved cases',()=>{
  const demo={guided:true,focus_report_id:'case',incidents:[{report_id:'case',report_status:'awaiting_review'}]};
  assert.equal(demoBeats(demo,null).find(b=>b.id==='complaint').target,'#fraud-sprite-focus');
  demo.incidents[0].report_status='resolved';
  assert.equal(demoBeats(demo,null).find(b=>b.id==='complaint').target,'#world-alert');
});
