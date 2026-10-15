import {roleNames} from './harness-ui.js';
import {cleanText,toolLabels,caseActivity,agentIcon,pretty} from './agent-ui.js';

const toolCopy={
  get_case_evidence:['Check the case records','The agent retrieves this customer’s recorded payments and frozen evidence.'],
  get_transactions:['Verify the reported transfers','The agent checks the complaint against recorded transactions.'],
  get_customer_features:['Look at the customer’s history','The agent retrieves the customer’s scoped behavior features.'],
  compare_behavior:['Compare everyday behavior','The agent checks how these payments differ from the customer’s history.'],
  trace_recipient:['Follow the recipient','The agent checks related transfers for a possible connection.'],
  list_eligible_models:['Choose an eligible detector','The agent checks which registered tools fit the available evidence.'],
  score_models:['Test the relevant signals','Chosen detectors return versioned results. Missing evidence stays unavailable; rule scores are not fraud probabilities.'],
  run_fraud_detectors:['Test the relevant signals','The agent calls registered detectors. Their signals support investigation, not a final verdict.'],
  search_reviewed_cases:['Look for an approved lesson','The agent checks applicable knowledge from earlier analyst-reviewed cases.'],
  delegate_question:['Ask a specialist','The lead sends one scoped question and its evidence to a specialist. The finding returns to the lead.'],
  return_finding:['Bring the finding back','The specialist returns its evidence and uncertainty to the case lead.'],
  ask_customer:['Ask for missing information','The agent chose a customer follow-up instead of guessing.'],
  submit_case_resolution:['Propose a resolution','The lead submits its findings to local judges before human review.'],
  submit_for_review:['Propose a resolution','The agent proposes an action with evidence and uncertainty for the analyst.'],
};
const short=text=>typeof text==='string'?cleanText(text).slice(0,180):'';

// Presentation of saved facts only. No fixed tool route, requests or mutations.
export function demoBeats(demo,report){
  if(!demo?.guided)return [];
  const beats=[],add=(id,view,target,title,copy,extra={})=>beats.push({id,view,target,title,copy,...extra});
  add('world','world','.map-shell','Everyday payments become evidence','Start with zero transactions. Watch numbered residents make payments before someone calls for help.',{who:'Live world',wait:'Waiting for a report'});
  if(!demo.focus_report_id)return beats;
  add('complaint','world',(demo.incidents||[]).some(i=>i.report_id===demo.focus_report_id&&i.report_status!=='resolved')?'#fraud-sprite-focus':'#world-alert','A customer reports a scam','This resident is calling for help and has filed a scam report. Follow the investigation to see what the agent checks.',{who:'Customer',next:'Follow investigation'});
  if(report?.id!==demo.focus_report_id)return beats;
  add('report','resolution','.report-details','Start with the customer’s account','This report is a claim to investigate. The agent must compare it with independent records.',{who:'Customer report'});
  const trail=report.decision_trail?.length?report.decision_trail:(report.investigation?.context?.controller==='adk'?report.investigation.trace||[]:[]).map(t=>({...t,number:t.step,status:'completed',purpose:t.summary,result:t.output}));
  for(const t of trail.filter(t=>t.tool&&t.status==='completed')){
    const [title,copy]=toolCopy[t.tool]||['Inspect the tool result','The recorded tool receipt shows what the agent requested and what it found.'];
    add('turn-'+t.number,'resolution',`#guide-turn-${t.number}`,title,copy,{who:roleNames[t.role]||'Resolution agent',tool:t.tool,detail:short(t.purpose)});
  }
  const activity=caseActivity(report,demo);
  if(activity.active)add('live','resolution','#agent-live-panel',activity.title,activity.detail,{who:activity.stage==='evidence'?'Evidence handoff':'Resolution agent',live:true,wait:'Following live progress'});
  const run=report.investigation,checks=report.harness?.checks||[];
  const judged=checks.find(c=>c.judges?.some(j=>j.judge==='resolution'));
  if(judged)add('judges','resolution','.harness-judges',judged.passed?'The draft passed local checks':'The judges withheld this draft',judged.passed?'Evidence, model contracts and resolution claims passed the checks. An analyst still makes the decision.':'A contract or claim failed validation. The draft cannot proceed as an approved resolution.',{who:'Harness judges',detail:short(judged.judges.filter(j=>!j.passed).flatMap(j=>j.blockers||[]).join(' '))});
  if(run?.recommendation)add('proposal','resolution','#fraud-packet','Read the proposed resolution','Review the suggested action, cited evidence and what remains uncertain.',{who:'Resolution agent',next:'Show analyst review'});
  const actions=demo.presentation_actions||{};
  if(report.status==='awaiting_customer')add('reply','resolution','#agent-live-panel','The customer provides more context','Next supplies the known answer from this synthetic customer so the agent can continue.',{who:'Demo customer',action:'answer'});
  else if(!activity.active&&report.status!=='resolved')add('review','resolution','#human-review-stage','Assume the analyst approves','For this demo, approval is assumed after reviewing the recorded transfer and scam request. Next saves the resolution and publishes its lesson.',{who:'Demo analyst',action:'review',detail:activity.stage==='blocked'?'The model draft stopped. The saved evidence goes to the simulated analyst; no model retry.':''});
  if(report.status==='resolved'){
    add('review','resolution','#human-review-stage','The demo analyst approved','The synthetic review is recorded. No refund or recovery is being claimed.',{who:'Demo analyst'});
    if(report.approved_lesson&&report.approved_lesson.lifecycle?.active!==false)add('knowledge','resolution','#fraud-memory-panel','The resolution becomes knowledge','The approved lesson and recipient can now inform the prevention agent.',{who:'Shared knowledge',action:actions.learn?null:'learn'});
  }
  const job=report.prevention,rule=job?.rule;
  if(actions.learn||job){
    const working=['ready','queued','running'].includes(job?.status),passed=rule?.replay?.passed;
    add('prevention','resolution','#prevention-panel',working?'The prevention agent tests the lesson':passed?'Prepare the next payment check':'Use the approved recipient watch',working?'The learner checks a narrow candidate against similar requests and legitimate controls.':passed?'The candidate passed synthetic replay. Next applies the assumed demo analyst activation.':'A broader candidate is unavailable or did not pass. The approved recipient watch still checks the next payment locally.',{who:'Prevention',live:working,action:!working&&!actions.activate?'activate':null});
  }
  if(actions.activate)add('repeat','world','.map-shell','A similar scam happens again','Another resident receives a suspicious request. Next sends the attempt through the actual payment check before any debit.',{who:'Next payment',action:demo.phase==='protected'?null:'prove'});
  if(demo.phase==='protected')add('protected','world','.map-shell','The scam was stopped before debit','The suspicious transfer was held. A legitimate control payment completed. The payment gateway used approved knowledge without another model call.',{who:'Protection verified',done:true});
  return beats;
}

// New receipts can arrive while someone reads. Preserve their current step;
// navigation belongs exclusively to Next/Back, never polling or a timer.
export function keepReadingStep(previous,latest,current){
  if(latest.some(b=>b.id===current))return latest;
  const index=previous.findIndex(b=>b.id===current),old=previous[index];if(!old)return latest;
  const before=previous.slice(0,index).reverse().find(b=>latest.some(n=>n.id===b.id));
  const at=before?latest.findIndex(b=>b.id===before.id)+1:0;
  const target=['reply','start','stopped'].includes(current)?'#agent-live-panel':old.target;
  return [...latest.slice(0,at),{...old,target,action:null,manual:false,live:false,wait:'The result is ready. Click Next when you are ready.'},...latest.slice(at)];
}
export function nextGuideStep(beats,current,seen=new Set()){
  const i=beats.findIndex(b=>b.id===current),b=beats[i];
  if(b?.live){const unread=beats.find(n=>n.id.startsWith('turn-')&&!seen.has(n.id));if(unread)return unread.id}
  return beats[i+1]?.id||null;
}

export function createDemoGuide({state,openCase,showWorld,error,demoAction}){
  const root=document.createElement('div');root.id='demo-guide';root.hidden=true;root.setAttribute('role','dialog');root.setAttribute('aria-modal','true');root.setAttribute('aria-label','Guided fraud demo');
  root.innerHTML='<section class="demo-presentation"><header class="demo-stage-header"><span class="demo-stage-brand">Mint Town <small>Guided demo</small></span><nav class="demo-stage-track" aria-label="Demo flow"></nav><button type="button" class="guide-close" aria-label="Exit demo">×</button></header><div class="demo-stage-main"><section class="demo-visual" aria-label="Current demo scene"></section><aside class="guide-caption" role="region" aria-label="Demo guide"><span class="guide-who"></span><h2></h2><p class="guide-copy"></p><p class="guide-detail"></p><p class="guide-error" role="alert" hidden></p><footer><span class="guide-progress"></span><button type="button" class="guide-back">Back</button><button type="button" class="primary-button guide-next">Next</button></footer><small class="guide-wait"></small></aside></div></section>';
  document.body.append(root);
  const $=s=>root.querySelector(s),app=document.getElementById('mint-town'),visual=$('.demo-visual'),seen=new Set();
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  const money=n=>'₱'+(n/100).toLocaleString('en-PH',{maximumFractionDigits:0});
  let scene=null,report=null,active=false,beats=[],current='world',busy=false,entering=false,priorFocus=null,canvasFrame=0,worldCanvas=null,lastPaint=0;
  const saved=(key,value)=>{try{if(value===undefined)return sessionStorage.getItem(key);sessionStorage.setItem(key,value)}catch{}return null};
  function close(){active=false;root.hidden=true;app.inert=false;document.body.classList.remove('guide-open');cancelAnimationFrame(canvasFrame);worldCanvas=null;saved('minttown-guide-dismissed',scene);const focus=priorFocus?.isConnected&&!priorFocus.disabled?priorFocus:document.getElementById('play-world');focus?.focus();priorFocus=null}
  function sceneCanvas(){worldCanvas=el('canvas',undefined,'demo-world-canvas');worldCanvas.width=960;worldCanvas.height=600;worldCanvas.setAttribute('aria-label','Live Mint Town residents and recorded payment alerts');visual.append(worldCanvas);copyWorld()}
  function copyWorld(time=0){cancelAnimationFrame(canvasFrame);if(!active||!worldCanvas)return;if(time-lastPaint>32||!time){const source=document.getElementById('town-map');worldCanvas.getContext('2d').drawImage(source,0,0,960,600);lastPaint=time}canvasFrame=requestAnimationFrame(copyWorld)}
  function card(role,title,copy){const c=el('div',undefined,'demo-focus-card');c.append(agentIcon(role),el('h3',title));if(copy)c.append(el('p',short(copy)));visual.append(c);return c}
  function facts(parent,items){const list=el('div',undefined,'demo-facts');for(const [label,value] of items.slice(0,3)){const row=el('div');row.append(el('small',label),el('strong',String(value)));list.append(row)}parent.append(list)}
  function chips(parent,items){const c=el('div',undefined,'signal-chips');for(const value of items.slice(0,4))c.append(el('span',pretty(value)));parent.append(c)}
  function paint(b){
    cancelAnimationFrame(canvasFrame);worldCanvas=null;visual.replaceChildren();
    const d=state.data.demo,run=report?.investigation,job=report?.prevention,rule=job?.rule,actions=d.presentation_actions||{},tx=report?.transactions||[],total=tx.reduce((s,t)=>s+t.amount_minor,0);
    if(['world','complaint','protected'].includes(b.id)){
      const heading=el('div',undefined,'demo-scene-label');heading.append(agentIcon(b.id==='protected'?'prevention':b.id==='complaint'?'human':'knowledge'),el('strong',b.id==='protected'?'The next payment was protected':b.id==='complaint'?'Resident '+Number((d.focus_customer_id||'C001').slice(1))+' asks for help':'Watch the town transact'));visual.append(heading);sceneCanvas();
      const results=el('div',undefined,'demo-world-results');
      if(b.id==='protected')facts(results,[['Suspicious payment','Held before debit'],['Legitimate payment','Completed'],['Check location','Local payment gateway']]);
      else facts(results,[['Residents',state.data.customers?.length||100],['Transactions',state.data.environment_data?.counts.wallet_transactions||0],['Scam report',d.focus_report_id?'Filed':'Not yet']]);visual.append(results);return;
    }
    if(b.id==='report'){const c=card('human','Resident '+Number((report?.customer_id||'C001').slice(1)),report?.story);facts(c,[['Reported transfer',money(total)],['Recorded payments',tx.length],['Claim','Bank impersonation']]);return}
    if(b.id.startsWith('turn-')){
      const t=report?.decision_trail?.find(t=>'turn-'+t.number===b.id)||{};const c=card(t.role?.includes('specialist')?'specialist':'resolution',toolLabels[t.tool]||b.title,t.purpose);const output=t.result||{};
      const route=el('div',undefined,'demo-tool-route');for(const [icon,label] of [['resolution','Agent chooses'],['knowledge','Tool checks'],['judge','Receipt saved']]){const n=el('div');n.append(agentIcon(icon),el('span',label));route.append(n)}c.append(route);
      if(output.transactions)facts(c,[['Payments verified',output.transactions.length],['Amount',money(total)],['History',output.warehouse?.features?.baseline_days===0?'No prior baseline':'Scoped to this customer']]);
      else if(output.receipts){const signals=output.receipts.flatMap(r=>r.prediction?.predictions?.flatMap(p=>p.matched_features||[])||[]);chips(c,[...new Set(signals)]);facts(c,[['Detector receipts',output.receipts.length],['Interpretation','Investigation signals'],['Decision','Not proof of fraud']])}
      else if(output.models)facts(c,[['Registered checks',output.models.length],['Selection','Chosen for this evidence'],['Inputs','Case-bound features']]);
      else if(t.tool==='delegate_question'||t.tool==='return_finding')facts(c,[['Handoff','Scoped evidence'],['Finding',output.assessment||'Returned to the lead'],['Authority','Cannot approve']]);
      else facts(c,[['Result',output.status||'Recorded'],['Scope','This customer’s case'],['Next','Review the evidence']]);return;
    }
    if(b.id==='live'){const c=card('resolution','Investigation in progress','The agent chooses its next tool. Completed receipts appear as they are recorded.');c.classList.add('demo-working');facts(c,[['Evidence','Saved'],['Tools completed',report?.decision_trail?.filter(t=>t.status==='completed').length||0],['Next','Waiting for a recorded result']]);return}
    if(b.id==='judges'){const c=card('judge',b.title,'Local checks validate evidence, tool contracts and the proposed action.');const checks=report?.harness?.checks?.at(-1)?.judges||[];facts(c,checks.map(j=>[pretty(j.judge),j.passed?'Passed':'Needs review']));return}
    if(b.id==='proposal'){const c=card('resolution','Proposed resolution',run?.recommendation?.summary);facts(c,[['Action',pretty(run?.recommendation?.suggested_action)],['Evidence',tx.length+' payment(s)'],['Recovery','Not guaranteed']]);return}
    if(b.id==='reply'){card('human','The demo customer answers',run?.context?.pending_question);return}
    if(b.id==='review'){
      const c=card('human',report?.status==='resolved'?'Demo analyst approved':'Assume analyst approval','For this synthetic demo, the risk analyst verifies the report and approves a recall request. Next saves the reviewed lesson.');facts(c,[['Review','Synthetic demo assumption'],['Evidence',tx.length+' recorded payment(s)'],['Money recovered','No recovery claimed']]);
      const stopped=run?.context?.manual_handoff||['failed','interrupted','budget_exhausted'].includes(run?.status);if(stopped)c.append(el('p','The automated draft stopped. The demo analyst uses the saved evidence; no model request is retried.','demo-disclosure'));return;
    }
    if(b.id==='knowledge'){const c=card('knowledge','Reviewed case → shared knowledge',report?.approved_lesson?.lesson||'A familiar device does not rule out a deceptive payment request. Verify urgent safe-account requests independently.');chips(c,['safe_account_request','secrecy_request']);facts(c,[['Source','Demo analyst resolution'],['Scope','Reviewed recipient + case signals'],['Use','Check future payments']]);return}
    if(b.id==='prevention'){
      const waiting=['ready','queued','running'].includes(job?.status),passed=rule?.replay?.passed;const c=card('prevention',waiting?'Prevention agent is testing':passed?'A narrow safeguard is ready':'Reviewed recipient watch is ready',waiting?'The approved lesson is being tested against similar requests and legitimate payments.':passed?'Combine the reviewed signals before a future payment is debited.':'The approved recipient is watched locally. A broader unapproved candidate is not used.');if(waiting)c.classList.add('demo-working');if(passed)chips(c,rule.signals);
      facts(c,passed?[['Similar request',rule.replay.changed_recipient_matches?'Matched':'Not matched'],['Legitimate controls',rule.replay.false_flags+' held / '+rule.replay.legitimate_controls],['Activation','Assumed demo analyst approval']]:[['Knowledge','Approved recipient'],['Broader candidate',job?'Not activated':'Not requested'],['Payment check','Local; no model call']]);return;
    }
    if(b.id==='repeat'){const changed=actions.activate?.mode==='behavioral_safeguard',c=card('prevention','A similar request arrives',changed?'Another resident is asked to move money to a safe account, using a different recipient.':'Another resident is asked to pay the previously reviewed recipient.');const pair=el('div',undefined,'demo-resident-pair');for(const [n,label] of [['1','Earlier case'],['2','New payment']]){const actor=el('div');actor.append(agentIcon('human'),el('strong','Resident '+n),el('small',label));pair.append(actor)}c.append(pair);facts(c,[['Amount','₱900'],['Protection',changed?'Reviewed behavior signals':'Approved recipient watch'],['Next','Verify before debit']]);return}
    card('resolution',b.title,b.copy);
  }
  function render(){
    if(!active||!beats.length)return;const i=beats.findIndex(b=>b.id===current),b=beats[i];if(!b)return;
    root.hidden=false;app.inert=true;document.body.classList.add('guide-open');
    $('.guide-who').textContent=b.who;$('.guide-caption h2').textContent=b.title;$('.guide-copy').textContent=b.copy;$('.guide-detail').textContent=b.detail||'';$('.guide-detail').hidden=!b.detail;
    $('.guide-progress').textContent=(i+1)+' / '+beats.length;const next=nextGuideStep(beats,current,seen);$('.guide-next').textContent=busy?'Working…':b.done?'Finish demo':'Next';$('.guide-next').disabled=busy||(!next&&!b.action&&!b.done&&b.id!=='complaint');$('.guide-back').disabled=busy||i===0;
    $('.guide-wait').textContent=b.done?'Finish returns to the town.':$('.guide-next').disabled&&b.id==='world'?'World running · the first report will appear shortly.':b.live?'Live results continue here. Next is available when the next result is ready.':b.action==='review'?'Next records the assumed demo approval.':b.action==='activate'?'Next enables only the reviewed protection.':'Read at your pace. Click Next to continue.';
    const stages=['World','Case','Investigate','Approve','Learn','Protect'],stage=b.id==='world'?0:['complaint','report'].includes(b.id)?1:b.id==='review'?3:['knowledge','prevention'].includes(b.id)?4:['repeat','protected'].includes(b.id)?5:2;
    $('.demo-stage-track').replaceChildren();stages.forEach((label,n)=>{const v=el('span',label,n===stage?'current':n<stage?'complete':'');$('.demo-stage-track').append(v)});
    paint(b);seen.add(current);if(!root.contains(document.activeElement))($('.guide-next').disabled?$('.guide-close'):$('.guide-next')).focus({preventScroll:true});
  }
  function update(nextReport){
    const d=state.data?.demo;if(!d?.guided){if(active)close();return}
    const key=d.scene_id+':'+d.run_id;if(scene!==key){scene=key;report=null;beats=[];current='world';seen.clear();priorFocus=document.activeElement;active=!!(d.running||d.focus_report_id)&&d.phase!=='protected'&&saved('minttown-guide-dismissed')!==scene}
    if(nextReport){if(nextReport.id!==d.focus_report_id&&!entering){close();return}report=nextReport}
    if(report?.id!==d.focus_report_id)report=null;
    beats=keepReadingStep(beats,demoBeats(d,report),current);if(active&&!entering)render();
  }
  async function advance(){
    if(busy)return;const b=beats.find(b=>b.id===current);if(b?.done){close();return}
    busy=true;$('.guide-error').hidden=true;render();
    try{
      if(b?.action)await demoAction(b.action);
      if(b?.id==='complaint'&&!report){entering=true;try{await openCase()}finally{entering=false}beats=demoBeats(state.data.demo,report)}
      const target=nextGuideStep(beats,current,seen);if(target){current=target;const next=beats.find(n=>n.id===current);if(next.view!==state.view){entering=true;try{if(next.view==='world')await showWorld();else await openCase()}finally{entering=false}}}
    }catch(e){$('.guide-error').textContent=cleanText(e.message);$('.guide-error').hidden=false}
    finally{busy=false;render();$('.guide-next').focus({preventScroll:true})}
  }
  $('.guide-next').onclick=advance;
  $('.guide-back').onclick=async()=>{if(busy)return;current=beats[Math.max(0,beats.findIndex(b=>b.id===current)-1)].id;const b=beats.find(b=>b.id===current);if(b.view!==state.view){entering=true;try{if(b.view==='world')await showWorld();else await openCase()}finally{entering=false}}render()};
  $('.guide-close').onclick=close;
  window.addEventListener('wheel',e=>{if(active)e.preventDefault()},{passive:false});window.addEventListener('touchmove',e=>{if(active)e.preventDefault()},{passive:false});
  window.addEventListener('keydown',e=>{if(!active)return;if(e.key==='Escape'){e.preventDefault();close();return}if(['PageDown','PageUp','Home','End','ArrowDown','ArrowUp',' '].includes(e.key)){e.preventDefault();return}if(e.key==='Tab'){const buttons=[...root.querySelectorAll('button:not(:disabled)')];e.preventDefault();const i=buttons.indexOf(document.activeElement);buttons[(i+(e.shiftKey?-1:1)+buttons.length)%buttons.length]?.focus()}});
  document.getElementById('fraud-select').addEventListener('change',close);document.getElementById('risk-models-tab').addEventListener('click',close);
  return {update,close};
}
