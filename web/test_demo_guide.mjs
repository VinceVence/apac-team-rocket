import assert from 'node:assert/strict';
import {test} from 'node:test';
import {demoBeats} from './dist/demo-guide.js';

const demo={guided:true,run_id:1,scene_id:'first',focus_report_id:'case',phase:'investigation'};
const report={id:'case',status:'investigating',reviews:[],decision_trail:[],investigation:{status:'running'}};
const turn=(number,tool,role='resolution')=>({number,tool,role,status:'completed',purpose:'Check the recorded evidence.'});

test('guide follows actual tool order and does not invent a specialist',()=>{
  const r={...report,decision_trail:[turn(1,'get_case_evidence'),turn(2,'ask_customer')],status:'awaiting_customer',investigation:{status:'awaiting_customer',context:{pending_question:'Did you verify the caller?'}}};
  const beats=demoBeats(demo,r);
  assert.deepEqual(beats.map(b=>b.id),['world','complaint','report','turn-1','turn-2','reply']);
  assert.equal(beats.at(-1).copy,'Did you verify the caller?');
  assert.equal(beats.some(b=>b.id==='review'),false);
});

test('fast completed runs retain each tool, the specialist and judge rejection',()=>{
  const r={...report,decision_trail:[turn(1,'score_models'),turn(2,'delegate_question'),turn(3,'return_finding','device_specialist')],harness:{checks:[{passed:false,judges:[{judge:'resolution',passed:false,blockers:['Unsupported recovery']}]}]},investigation:{status:'budget_exhausted'}};
  const beats=demoBeats(demo,r);
  assert.equal(beats.find(b=>b.id==='turn-3').who,'Device & identity');
  assert.equal(beats.find(b=>b.id==='judges').title,'The judges withheld this draft');
  assert.equal(beats.at(-1).id,'stopped');
  assert.equal(beats.some(b=>b.id==='review'||b.id==='knowledge'),false);
});

test('knowledge and protection require observed review and backend state',()=>{
  const r={...report,status:'resolved',reviews:[{id:'human-review'}],approved_lesson:{id:'memory'},prevention:{status:'awaiting_activation',rule:{status:'proposed',replay:{passed:true}}}};
  const beats=demoBeats(demo,r);
  assert.deepEqual(beats.slice(-4).map(b=>b.id),['review','knowledge','prevention','activate']);
  r.prevention.rule.status='active';
  assert.equal(demoBeats(demo,r).at(-1).id,'protect');
  assert.equal(demoBeats({...demo,phase:'protected'},r).at(-1).id,'protected');
  assert.equal(demoBeats(demo,{...report,status:'resolved',reviews:[{}]}).some(b=>b.id==='knowledge'),false);
  assert.equal(demoBeats(demo,{...r,approved_lesson:{lifecycle:{active:false}}}).some(b=>b.id==='knowledge'),false);
});

test('fresh scenes and foreign cases do not carry old investigation facts',()=>{
  assert.deepEqual(demoBeats({...demo,focus_report_id:null,run_id:2,scene_id:'new'},report).map(b=>b.id),['world']);
  assert.deepEqual(demoBeats(demo,{...report,id:'different-case'}).map(b=>b.id),['world','complaint']);
  assert.deepEqual(demoBeats({guided:false},report),[]);
});

test('reserved and failed requests are not presented as completed tools',()=>{
  const r={...report,decision_trail:[{...turn(1,'score_models'),status:'reserved'},{...turn(2,'return_finding'),status:'failed'}]};
  assert.equal(demoBeats(demo,r).some(b=>b.tool),false);
});
