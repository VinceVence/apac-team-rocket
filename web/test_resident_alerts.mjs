import assert from 'node:assert/strict';
import {test} from 'node:test';
import {alarmMotion,residentLabel} from './dist/resident-sprites.js';
import {demoBeats} from './dist/demo-guide.js';

test('residents have stable numbered labels',()=>{
  assert.equal(residentLabel('C001'),'Resident 1');assert.equal(residentLabel('C100'),'Resident 100');
});
test('the initial alarm jumps briefly, then settles without requiring world ticks',()=>{
  assert.ok(alarmMotion(250).jump>10);assert.ok(alarmMotion(1000).active);
  assert.deepEqual(alarmMotion(9000),{active:false,jump:0});
  assert.deepEqual(alarmMotion(250,true),{active:true,jump:0});
});
test('the guide highlights the reporting sprite, with a fallback for saved resolved cases',()=>{
  const demo={guided:true,focus_report_id:'case',incidents:[{report_id:'case',report_status:'awaiting_review'}]};
  assert.equal(demoBeats(demo,null)[1].target,'#fraud-sprite-focus');
  demo.incidents[0].report_status='resolved';
  assert.equal(demoBeats(demo,null)[1].target,'#world-alert');
});
