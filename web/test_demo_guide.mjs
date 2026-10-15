import assert from 'node:assert/strict';
import {test} from 'node:test';
import {demoBeats,keepReadingStep,nextGuideStep} from './dist/demo-guide.js';

const demo={guided:true,run_id:1,scene_id:'first',focus_report_id:'case',phase:'investigation'};
const report={id:'case',status:'investigating',reviews:[],decision_trail:[],investigation:{status:'running'}};
const turn=(number,tool,role='resolution')=>({number,tool,role,status:'completed',purpose:'Check the recorded evidence.'});

test('guide follows actual tool order and does not invent a specialist',()=>{
  const r={...report,decision_trail:[turn(1,'get_case_evidence'),turn(2,'ask_customer')],status:'awaiting_customer',investigation:{status:'awaiting_customer',context:{pending_question:'Did you verify the caller?'}}};
  const beats=demoBeats(demo,r);
  assert.deepEqual(beats.map(b=>b.id),['world','complaint','report','turn-1','turn-2','reply']);
  assert.equal(beats.at(-1).action,'answer');
  assert.equal(beats.some(b=>b.id==='review'),false);
});

test('fast completed runs retain each tool, the specialist and judge rejection',()=>{
  const r={...report,decision_trail:[turn(1,'score_models'),turn(2,'delegate_question'),turn(3,'return_finding','device_specialist')],harness:{checks:[{passed:false,judges:[{judge:'resolution',passed:false,blockers:['Unsupported recovery']}]}]},investigation:{status:'budget_exhausted'}};
  const beats=demoBeats(demo,r);
  assert.equal(beats.find(b=>b.id==='turn-3').who,'Device & identity');
  assert.equal(beats.find(b=>b.id==='judges').title,'The judges withheld this draft');
  assert.equal(beats.at(-1).id,'review');assert.equal(beats.at(-1).action,'review');
  assert.equal(beats.some(b=>b.id==='knowledge'),false);
});

test('knowledge and protection require observed review and backend state',()=>{
  const r={...report,status:'resolved',reviews:[{id:'human-review'}],approved_lesson:{id:'memory'},prevention:{status:'awaiting_activation',rule:{status:'proposed',replay:{passed:true}}}};
  const beats=demoBeats(demo,r);
  assert.deepEqual(beats.slice(-3).map(b=>b.id),['review','knowledge','prevention']);assert.equal(beats.at(-1).action,'activate');
  r.prevention.rule.status='active';
  assert.equal(demoBeats({...demo,presentation_actions:{learn:{},activate:{}}},r).at(-1).id,'repeat');
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

test('guide shows live preparation instead of ending at the complaint',()=>{
  const r={...report,status:'reported',investigation:null,preparation:{status:'running',stage:'simulation_data',detail:'Saving snapshots.'}};
  const beats=demoBeats(demo,r);
  assert.equal(beats.at(-1).id,'live');assert.equal(beats.at(-1).target,'#agent-live-panel');
  assert.equal(beats.some(b=>b.action==='start'),false);
});

test('new results preserve the step being read until Next is clicked',()=>{
  const waiting=[{id:'world'},{id:'complaint'},{id:'report'},{id:'live',live:true,target:'#agent-live-panel',copy:'Reading the evidence.'}];
  const ready=[{id:'world'},{id:'complaint'},{id:'report'},{id:'turn-1'},{id:'review',manual:true}];
  const retained=keepReadingStep(waiting,ready,'live');
  assert.equal(retained.find(b=>b.id==='live').copy,'Reading the evidence.');
  assert.equal(nextGuideStep(retained,'live'),'turn-1');
  assert.equal(nextGuideStep(retained,'review'),null);
  assert.equal(nextGuideStep(keepReadingStep(waiting,ready,'world'),'world'),'complaint');
});

test('Next from live activity visits unread tools instead of skipping to review',()=>{
  const steps=[{id:'report'},{id:'turn-1'},{id:'turn-2'},{id:'live',live:true},{id:'review',manual:true}];
  assert.equal(nextGuideStep(steps,'live',new Set(['report','turn-1','live'])),'turn-2');
  assert.equal(nextGuideStep(steps,'live',new Set(['turn-1','turn-2','live'])),'review');
  const replied=keepReadingStep([{id:'report'},{id:'reply',target:'#fraud-reply-form'}],[{id:'report'},{id:'turn-3'}],'reply');
  assert.equal(replied[1].target,'#agent-live-panel');assert.equal(nextGuideStep(replied,'reply'),'turn-3');
});

test('a rejected candidate stays inactive while Next can use reviewed-recipient protection',()=>{
  const beats=demoBeats(demo,{...report,status:'resolved',reviews:[{}],prevention:{status:'rejected',rule:{status:'rejected',replay:{passed:false}}}});
  assert.equal(beats.at(-1).id,'prevention');assert.equal(beats.at(-1).action,'activate');assert.match(beats.at(-1).copy,/unapproved|unavailable|did not pass/);
});
