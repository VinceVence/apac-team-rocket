import assert from 'node:assert/strict';
import {test} from 'node:test';
import {decisionMap,decisionResult,decisionTrail,manualInvestigation} from './dist/decision-map.js';
import {demoBeats,nextGuideStep,keepReadingStep} from './dist/demo-guide.js';

const turn=(number,tool,purpose,result={},extra={})=>({number,tool,purpose,result,status:'completed',provider:'gemini',finding:'A result was recorded.',...extra});
const report=trail=>({id:'case',status:'awaiting_review',decision_trail:trail,investigation:{status:'awaiting_review',provider:'gemini',context:{controller:'adk'},recommendation:{summary:'Review the evidence.'}}});

test('different recorded choices produce different routes and exact public reasons',()=>{
  const a=report([turn(1,'get_case_evidence','Verify the reported payments.',{transactions:[{}]}),turn(2,'score_models','Check device and request signals.'),turn(3,'submit_case_resolution','Send the supported findings for review.')]);
  const b=report([a.decision_trail[0],turn(2,'search_reviewed_cases','Look for a reviewed withdrawal-fee pattern.',{matches:[]}),turn(3,'trace_recipient','Check transfers to the reported recipient.',{related_transfers:[{},{}]})]);
  assert.notDeepEqual(decisionMap(a).trail,decisionMap(b).trail);
  assert.equal(decisionMap(b,2).reason,'Look for a reviewed withdrawal-fee pattern.');
  assert.deepEqual(decisionMap(b,2).result.facts,['0 approved lessons found']);
  assert.match(decisionMap(b,2).nextAction,/Trace the recipient/);
  assert.equal(decisionMap(a).live,false);assert.equal(decisionMap(a).badge,'Recorded live decision');
});

test('pending choices and requested tools never invent a result or rationale',()=>{
  const r={status:'investigating',investigation:{status:'stepping',provider:'gemini',context:{controller:'adk'}},decision_trail:[{number:1,status:'reserved',provider:'gemini'}]};
  let d=decisionMap(r);assert.equal(d.phase,'choosing');assert.equal(d.tool,null);assert.deepEqual(d.result.facts,[]);
  assert.match(d.reason,/No public decision summary/);assert.equal(d.live,true);
  r.decision_trail=[turn(1,'trace_recipient','Check the beneficiary trail.',{related_transfers:[{}]},{status:'responded'})];
  d=decisionMap(r);assert.equal(d.phase,'executing');assert.equal(d.reason,'Check the beneficiary trail.');assert.deepEqual(d.result.facts,[]);
  assert.match(d.result.summary,/not recorded yet/);
});

test('only current-run receipts with the pinned evidence version enter the diagram',()=>{
  const r=report([turn(1,'get_case_evidence','Old evidence.',{}, {run_id:'old',provenance:{snapshot_id:'old'}}),
    turn(2,'score_models','Stale evidence.',{}, {run_id:'current',provenance:{snapshot_id:'old'}}),
    turn(3,'get_case_evidence','Current evidence.',{}, {run_id:'current',provenance:{snapshot_id:'new'}})]);
  r.investigation.id='current';r.investigation.context.snapshot_id='new';
  assert.deepEqual(decisionTrail(r).map(t=>t.number),[3]);assert.equal(decisionMap(r).reason,'Current evidence.');
});

test('specialists, customer questions and judge rejection use actual receipts',()=>{
  const r=report([turn(1,'delegate_question','Ask a scoped device question.',{role:'device_specialist'}),
    turn(2,'return_finding','Return supported observations.',{finding:{summary:'Device ownership remains unverified.',uncertainties:['Login history is missing.']}},{role:'device_specialist'}),
    turn(3,'submit_case_resolution','Submit a cautious draft.',{status:'revision_required',harness_judges:{passed:false,judges:[{blockers:['Unsupported recovery claim.']}]}})]);
  assert.equal(decisionMap(r,2).actor,'Device & identity');assert.match(decisionMap(r,2).result.facts[0],/ownership/);
  assert.deepEqual(decisionMap(r,2).result.unknowns,['Login history is missing.']);
  assert.deepEqual(decisionMap(r,3).result.facts,['Draft withheld by validation']);
  assert.deepEqual(decisionMap(r,3).result.unknowns,['Unsupported recovery claim.']);
  const question=turn(4,'ask_customer','Resolve missing testimony.',{question:'Did you independently verify the supplier?'});
  assert.deepEqual(decisionResult(question).facts,['Did you independently verify the supplier?']);
});

test('failed, fake and manual paths are labelled honestly and do not expose hidden fields',()=>{
  const r=report([turn(1,'score_models','Check the observed signals.',{thoughts:'PRIVATE_SENTINEL'},{status:'failed',error:'Request stopped.',private_reasoning:'PRIVATE_SENTINEL'})]);
  r.investigation.status='failed';let d=decisionMap(r);
  assert.equal(d.phase,'stopped');assert.deepEqual(d.result.facts,[]);assert.match(d.nextAction,/No automatic retry/);
  assert.equal(JSON.stringify(d).includes('PRIVATE_SENTINEL'),false);
  r.decision_trail[0].provider='fake';assert.equal(decisionMap(r).badge,'Offline rehearsal');
  assert.equal(manualInvestigation({context:{manual_handoff:true}}),true);
  const manual={status:'awaiting_review',investigation:{status:'awaiting_review',context:{},trace:[{tool:'fixed_check'}]}};
  assert.equal(decisionTrail(manual).length,0);assert.equal(decisionMap(manual).badge,'Manual evidence review');assert.equal(decisionMap(manual).actor,'Fraud Analyst');
});

test('guided captions use the recorded purpose and Next keeps an unread decision',()=>{
  const demo={guided:true,focus_report_id:'case',phase:'investigation'};
  const r=report([turn(1,'get_case_evidence','Verify this exact reported transfer.',{transactions:[{}]})]);
  const beats=demoBeats(demo,r);
  assert.equal(beats.find(b=>b.id==='turn-1').copy,'Verify this exact reported transfer.');
  const previous=[{id:'report'},{id:'live',live:true}];
  const updated=keepReadingStep(previous,beats,'live');
  assert.equal(nextGuideStep(updated,'live',new Set(['live'])),'turn-1');
  r.investigation.context.manual_handoff=true;
  assert.equal(demoBeats(demo,r).find(b=>b.id==='proposal').who,'Demo analyst');
});

test('the report Next gate starts an investigation instead of allowing a scripted review',()=>{
  const d={guided:true,focus_report_id:'case',phase:'complaint'};
  const r={id:'case',status:'reported',investigation:null,preparation:{status:'waiting',stage:'demo_investigation'}};
  const beats=demoBeats(d,r);
  assert.equal(beats.at(-1).id,'report');assert.equal(beats.at(-1).action,'investigate');
  assert.equal(beats.some(b=>b.id==='review'||b.id==='live'),false);
});
