// Read-only playback of a saved Gemini case. No fetch, model, approval or payment writes.
const copy=value=>structuredClone(value);
const phases=['empty','payments','scam','investigate','review','learn','activate','prove'];
export function createRecordedDemo(recording,id){
  if(recording.schema!=='minttown-recorded-demo-v1'||recording.source.provider!=='gemini'||!recording.source.synthetic)throw Error('Invalid demo recording.');
  const original=recording.report;
  if(!original.decision_trail.some(t=>t.tool==='score_models'&&t.status==='completed'&&t.result?.receipts?.some(r=>r.score_kind==='uncalibrated_model_score')))throw Error('The recording needs a real trained-classifier receipt.');
  if(original.harness?.checks?.find(c=>c.judges?.some(j=>j.judge==='resolution'))?.passed!==true)throw Error('The recorded resolution did not pass its review checks.');
  if(!original.decision_trail.length||original.decision_trail.some(t=>t.provider!=='gemini'||t.status!=='completed')||!original.reviews.length||!original.prevention.rule.replay.passed||recording.proof.changed_recipient===recording.proof.source_recipient)throw Error('The recording lacks a completed investigation or changed-recipient proof.');
  let stage=0;
  function detail(){
    const r=copy(original);r.presentation_mode='replay';r.status=stage<3?'reported':stage<4?'awaiting_review':'resolved';
    if(stage<3){r.investigation=null;r.decision_trail=[];r.harness=null;r.preparation={status:'waiting',stage:'demo_investigation',detail:'Saved Gemini investigation ready to replay.'}}
    else{r.investigation.status='awaiting_review';r.preparation={status:'completed',stage:'recorded',detail:'Recorded Gemini case; no new investigation request.'}}
    if(stage<4){r.reviews=[];r.approved_lesson=null}
    if(stage<5)r.prevention=null;
    else if(stage<6)r.prevention.rule.status='proposed';
    return r;
  }
  function snapshot(){
    const d=copy(recording.state),r=detail(),events=stage<1?[]:copy(recording.normal_events);
    if(stage>=2)events.unshift(...copy(original.transactions));
    if(stage>=7)events.unshift(...copy(recording.proof_events));
    d.events=events;d.world.tick=events.length;d.world.hour=stage>=2?15:stage?12:9;
    d.environment_data.counts.wallet_transactions=events.length;d.environment_data.counts.scam_memory=stage>=4?1:0;
    const incidents=stage<2?[]:[{id:'replay-report',customer_id:r.customer_id,report_id:r.id,report_status:r.status,kind:'phishing',title:r.scenario_title,status:'investigating',created_at:r.created_at}];
    const held=recording.proof_events.find(e=>e.status==='blocked');
    const protection=stage>=7?{count:1,amount_minor:held.amount_minor,recent:[{...copy(held),source_report_id:r.id,rule_ids:[recording.source.rule_id],memory_ids:[recording.lesson.id],created_at:held.occurred_at}]}:{count:0,amount_minor:0,recent:[]};
    if(stage>=7)incidents.unshift({id:'replay-protected',customer_id:'C002',status:'blocked',created_at:held.occurred_at});
    d.demo={replay:true,replay_stage:phases[stage],recorded_at:recording.source.recorded_at,scene_id:id,run_id:1,guided:true,running:stage===0,continuous:false,agent_busy:false,restart_blocked:false,
      steps:events.length,speed:1,phase:stage>=7?'protected':stage>=6?'ready':stage>=4?'prevention':stage>=3?'review':stage>=2?'complaint':'world',
      focus_report_id:stage>=2?r.id:null,focus_customer_id:stage>=2?r.customer_id:null,incidents,protection,blocked_payments:protection.count,knowledge_count:stage>=4?1:0,
      calls_remaining:0,provider:'gemini',note:'Recorded Gemini replay. No current-world actions or paid calls.',
      presentation_actions:{...(stage>=5?{learn:{recorded:true}}:{}),...(stage>=6?{activate:{mode:'behavioral_safeguard',recorded:true}}:{})}};
    return d;
  }
  function action(name){
    const target=phases.indexOf(name);if(target<1)throw Error('Action is not part of this recording.');
    if(target<=stage)return; // Back/Next may revisit a saved result, never repeat work.
    if(target!==stage+1)throw Error('Read the preceding recorded step first.');stage=target;
  }
  return {snapshot,detail,action,api(path,body){
    if(body!==undefined){if(path==='/api/world/demo-action'){action(body.action);return {demo:snapshot().demo,report:detail()}}throw Error('Recorded demos cannot change the current world.');}
    if(path==='/api/state')return snapshot();
    if(path==='/api/fraud-desk/reports/'+original.id)return detail();
    if(path==='/api/fraud-desk')return {reports:stage>=2?[detail()]:[],memories:stage>=4?[copy(recording.lesson)]:[],customers:copy(recording.state.customers),transactions:stage>=2?copy(original.transactions):[],scenarios:[],agent_runtime:{live_enabled:false}};
    if(path==='/api/cloud')return {enabled:false};
    throw Error('This view is unavailable in the recorded demo.');
  }};
}
