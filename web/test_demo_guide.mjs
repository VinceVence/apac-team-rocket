import assert from 'node:assert/strict';
import {test} from 'node:test';
import {demoBeats,keepReadingStep,nextGuideStep,demoPhase,demoPhases,investigationProgress,liveDemoState,classifierReceipts,classifierInterpretation} from './dist/demo-guide.js';

const demo={guided:true,run_id:1,scene_id:'first',focus_report_id:'case',phase:'investigation'};
const report={id:'case',status:'investigating',reviews:[],decision_trail:[],investigation:{status:'running'}};
const turn=(number,tool,role='resolution')=>({number,tool,role,status:'completed',purpose:'Check the recorded evidence.'});

const modelTurn=()=>({...turn(2,'score_models'),result:{receipts:[{receipt_id:'receipt',model_id:'ledger_transaction_v1',score_kind:'uncalibrated_model_score',manifest:{name:'AE ledger behavior classifier'},status:'scored',event_ids:['event'],prediction:{available:true,signal_score:.585159,threshold:.7},missing_inputs:[]}]}});

test('classifier screens show the real call, threshold and cited interpretation before review',()=>{
  const r={...report,status:'awaiting_review',decision_trail:[turn(1,'get_case_evidence'),modelTurn(),turn(3,'submit_case_resolution')],
    investigation:{status:'awaiting_review',recommendation:{summary:'The complaint requires verification despite a low model signal.',uncertainties:['Identity remains unverified.']}},
    harness:{checks:[{passed:true,receipt_ids:['receipt'],judges:[{judge:'resolution',passed:true}]}]}};
  const beats=demoBeats(demo,r),ids=beats.map(b=>b.id);
  assert.equal(beats.find(b=>b.id==='turn-2').title,'Check the payment');
  assert.ok(ids.indexOf('classifier-result-2-0')>ids.indexOf('turn-2'));
  assert.ok(ids.indexOf('classifier-result-2-0')<ids.indexOf('turn-3'));
  assert.ok(ids.indexOf('classifier-use')<ids.indexOf('review'));
  const result=classifierReceipts(modelTurn())[0];assert.equal(result.score,.585159);assert.equal(result.threshold,.7);assert.equal(result.verdict,'Below threshold');
  assert.equal(classifierInterpretation(r).rows[0].cited,true);
  assert.equal(classifierInterpretation(r).summary,r.investigation.recommendation.summary);
});

test('rule checks, failed calls and unavailable classifier inputs are not invented successful ML results',()=>{
  const t=modelTurn();t.result.receipts[0].score_kind='rule_signal';assert.deepEqual(classifierReceipts(t),[]);
  t.result.receipts[0].score_kind='uncalibrated_model_score';t.status='reserved';assert.deepEqual(classifierReceipts(t),[]);
  t.status='completed';t.result.receipts[0].status='not_available';t.result.receipts[0].prediction.available=false;
  const r=classifierReceipts(t)[0];assert.equal(r.score,null);assert.equal(r.verdict,'Unavailable');
});

test('live Next cannot skip unread classifier results or interpretation',()=>{
  const beats=[{id:'turn-2'},{id:'classifier-result-2-0'},{id:'classifier-use'},{id:'live'},{id:'review'}];
  const seen=new Set(['turn-2','live']);assert.equal(nextGuideStep(beats,'live',seen),'classifier-result-2-0');
  seen.add('classifier-result-2-0');assert.equal(nextGuideStep(beats,'live',seen),'classifier-use');
});

test('a currently rejected interpretation never offers assumed approval after an older passing check',()=>{
  const r={...report,status:'awaiting_review',investigation:{status:'awaiting_review',recommendation:{summary:'Models note elevated risk.'}},decision_trail:[modelTurn()],
    harness:{checks:[{passed:false,judges:[{judge:'models',passed:false,blockers:['Below threshold.']},{judge:'resolution',passed:true}]},{passed:true,judges:[{judge:'resolution',passed:true}]}]}};
  const beats=demoBeats(demo,r);assert.equal(beats.at(-1).action,undefined);assert.equal(beats.at(-1).exit,true);
  assert.equal(beats.some(b=>b.action==='review'),false);assert.equal(classifierInterpretation(r).blocked,true);
});

test('evidence preparation is a live data handoff, not an invented agent decision',()=>{
  const r={id:'case',status:'reported',investigation:null,preparation:{status:'running',stage:'ledger_snapshot',detail:'Freezing payments.'}};
  const state=liveDemoState(r,demo);
  assert.equal(state.who,'Data pipeline');assert.equal(state.live,true);
  assert.equal(state.copy,'Freezing payments.');assert.match(state.detail,/after.*evidence/);
  assert.equal(liveDemoState(report,demo).who,'Resolution agent');
});

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
  assert.equal(beats.at(-1).id,'stopped');assert.equal(beats.at(-1).action,undefined);assert.equal(beats.at(-1).exit,true);
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

test('rejected report admission explains the stop without promising a scam or investigation',()=>{
  const beats=demoBeats({...demo,focus_report_id:null,running:false,scene_blocked_reason:'Daily scam-report allowance reached.'},null);
  assert.equal(beats.length,1);assert.equal(beats[0].action,null);assert.equal(beats[0].exit,true);assert.match(beats[0].title,/paused/);
  assert.match(beats[0].copy,/allowance reached/);assert.equal(beats[0].done,undefined);
  assert.equal(beats[0].wait,'No investigation ran');
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

test('a rejected candidate stays inactive without switching to a recording',()=>{
  const beats=demoBeats(demo,{...report,status:'resolved',reviews:[{}],prevention:{status:'rejected',rule:{status:'rejected',replay:{passed:false}}}});
  assert.equal(beats.at(-1).id,'prevention');assert.equal(beats.at(-1).action,undefined);assert.equal(beats.at(-1).exit,true);assert.match(beats.at(-1).copy,/review/);
});


test('phase progress is stable even when new tool steps arrive',()=>{
  assert.deepEqual(demoPhases,['World','Report','Investigate','Review','Learn','Protect']);
  for(const id of ['live','turn-1','turn-5','judges','proposal'])assert.equal(demoPhase(id),2);
  assert.equal(demoPhase('repeat'),5);assert.equal(demoPhase('protected'),5);
});

test('live progress reports real completed tools and the pending choice separately',()=>{
  const r={...report,investigation:{status:'running',context:{execution:{status:'running'}}},decision_trail:[turn(1,'get_case_evidence'),turn(2,'score_models'),{number:3,status:'reserved'}]};
  const p=investigationProgress(r,demo);
  assert.equal(p.completedCount,2);assert.equal(p.rows.at(-1).status,'active');
  assert.equal(p.rows.at(-1).label,'Choosing the next check');
  const done=investigationProgress({...r,status:'awaiting_review',decision_trail:[...r.decision_trail.slice(0,2),turn(3,'submit_case_resolution')]},demo);
  assert.equal(done.active,false);assert.equal(done.title,'Investigation complete');
  assert.equal(done.rows.at(-1).label,'Resolution ready for review');
});

test('completed live progress never skips unread checks that arrived before it',()=>{
  const previous=[{id:'report'},{id:'turn-1'},{id:'turn-2'},{id:'live',live:true}];
  const latest=[{id:'report'},{id:'turn-1'},{id:'turn-2'},{id:'turn-3'},{id:'review'}];
  const beats=keepReadingStep(previous,latest,'live');
  assert.equal(nextGuideStep(beats,'live',new Set(['report','live'])),'turn-1');
  assert.equal(nextGuideStep(beats,'live',new Set(['report','live','turn-1','turn-2'])),'turn-3');
});

test('the similar attempt and blocked outcome use the environment view',()=>{
  const r={...report,status:'resolved',reviews:[{}],approved_lesson:{id:'lesson'}};
  const beats=demoBeats({...demo,phase:'protected',presentation_actions:{learn:{},activate:{mode:'behavioral_safeguard'}}},r);
  assert.equal(beats.find(b=>b.id==='repeat').view,'world');
  assert.equal(beats.at(-1).view,'world');
});

 test('Run demo and the final tutorial button open the same presentation-only entry',async()=>{const fs=await import('node:fs/promises');const source=await fs.readFile(new URL('./dist/app.js',import.meta.url),'utf8');assert.match(source,/\$\('run-demo'\)\.onclick=startWalkthrough/);assert.match(source,/startDemo:startWalkthrough/);const start=source.slice(source.indexOf('async function startWalkthrough('),source.indexOf('let recording=null'));assert.match(start,/recordedDemo\(\)/);assert.doesNotMatch(start,/api\(|runWorld\(|refresh\(/);});
