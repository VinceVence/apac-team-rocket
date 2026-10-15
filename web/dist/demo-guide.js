import {roleNames} from './harness-ui.js';
import {cleanText,toolLabels,caseActivity} from './agent-ui.js';

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
  const trail=report.decision_trail?.length?report.decision_trail:(report.investigation?.trace||[]).map(t=>({...t,number:t.step,status:'completed',purpose:t.summary,result:t.output}));
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
  if(activity.action==='start')add('start','resolution','#fraud-run','Start the investigation','The agent will choose its checks and return a proposal for human review.',{who:'Resolution agent',manual:true,action:'start',next:report.harness?.can_resume?'Resume saved work':'Start investigation'});
  else if(activity.stage==='blocked')add('stopped','resolution','#agent-live-panel',activity.title,activity.detail,{who:'Needs attention',manual:true,action:'refresh',next:'Refresh status'});
  if(report.status==='awaiting_customer')add('reply','resolution','#fraud-reply-form','The customer needs to answer',short(run?.context?.pending_question)||'A missing fact prevents the agent from continuing.',{who:'Customer follow-up',manual:true,wait:'Answer in the highlighted form'});
  if(report.status==='awaiting_review')add('review','resolution','#fraud-review-form','Now the risk analyst decides','Check the proposal, choose a decision, then use Approve & learn if justified. The guide cannot approve for you.',{who:'Human decision',manual:true,wait:'Approve using the highlighted form'});
  if(report.reviews?.length){
    add('review','resolution','#fraud-resolution','The analyst recorded a resolution','The saved resolution and service receipt show what the analyst authorized.',{who:'Human decision'});
    if(report.approved_lesson&&report.approved_lesson.lifecycle?.active!==false)add('knowledge','resolution','#fraud-memory-panel','Reviewed knowledge can be reused','The approved lesson is now available to later investigations. Applicability, expiry and revocation still apply.',{who:'Shared knowledge'});
  }
  const job=report.prevention,rule=job?.rule;
  if(job){
    const terminal=['rejected','failed','budget_exhausted','interrupted','deferred'].includes(job.status);
    add('prevention','resolution','#prevention-panel',terminal?'This safeguard stays inactive':rule?'A candidate safeguard was tested':'Learn a safeguard from the case',terminal?'The candidate was rejected, deferred, or stopped. Inspect the recorded result; no request is retried automatically.':rule?'Replay checks the proposed signals against a changed recipient and legitimate controls. It does not prove real-world accuracy.':'The prevention agent uses the approved case to propose a safeguard for future payments.',{who:'Prevention agent',manual:terminal,done:terminal,wait:terminal?'Review the highlighted result':'Following the prevention agent'});
    if(rule?.status==='proposed'&&rule.replay?.passed)add('activate','resolution','#prevention-rule','Activation is a separate decision','Inspect the signals and replay. Enable the safeguard only if those checks justify it.',{who:'Human decision',manual:true,wait:'Enable using the highlighted control'});
    if(rule?.status==='active')add('protect','resolution','#prevention-rule','Try the next suspicious payment','Use Test a similar payment. The local safeguard checks before debit; the check runs locally.',{who:'Payment safeguard',manual:true,wait:'Use Test a similar payment'});
  }
  if(demo.phase==='protected')add('protected','world','#world-alert','The later scam was held','The changed-recipient attempt was held before debit. The legitimate control payment passed. The check runs locally.',{who:'Protection verified',done:true});
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

export function createDemoGuide({state,openCase,showWorld,error,startInvestigation,refreshCase}){
  const root=document.createElement('div');root.id='demo-guide';root.hidden=true;
  root.innerHTML='<div class="guide-focus" aria-hidden="true"></div><aside class="guide-caption" role="region" aria-label="Demo guide"><header><span class="guide-who"></span><button type="button" class="guide-close" aria-label="Close demo guide">×</button></header><div aria-live="polite" aria-atomic="true"><h2></h2><p class="guide-copy"></p><p class="guide-detail"></p></div><footer><span class="guide-progress"></span><button type="button" class="guide-back">Back</button><button type="button" class="primary-button guide-next">Next</button></footer><small class="guide-wait"></small></aside>';
  document.body.append(root);
  const $=s=>root.querySelector(s),card=$('.guide-caption'),ring=$('.guide-focus');
  let scene=null,report=null,active=false,beats=[],current='world',target=null,frame=0,entering=false;
  let priorFocus=null;const seen=new Set();
  const saved=(key,value)=>{try{if(value===undefined)return sessionStorage.getItem(key);sessionStorage.setItem(key,value)}catch{}return null};
  function close(){active=false;root.hidden=true;document.body.classList.remove('guide-open');saved('minttown-guide-dismissed',scene);if(root.contains(document.activeElement)){const focus=priorFocus?.isConnected&&!priorFocus.disabled?priorFocus:document.getElementById('play-world');focus?.focus()}priorFocus=null}
  function layout(){
    if(!active||!target?.isConnected||!target.getClientRects().length){ring.hidden=true;return}
    const r=target.getBoundingClientRect(),w=innerWidth,h=innerHeight,pad=7;
    const left=Math.max(8,r.left-pad),top=Math.max(8,r.top-pad),right=Math.min(w-8,r.right+pad),bottom=Math.min(h-8,r.bottom+pad);
    ring.hidden=bottom<=top||right<=left;
    Object.assign(ring.style,{left:left+'px',top:top+'px',width:Math.max(0,right-left)+'px',height:Math.max(0,bottom-top)+'px'});
    const cw=card.offsetWidth,ch=card.offsetHeight,gap=18;
    let x=Math.max(12,w-cw-20),y=Math.max(12,h-ch-18);
    if(w>=850&&left>=cw+gap+16){x=left-cw-gap;y=Math.min(Math.max(18,top),h-ch-18)}
    else if(w>=850&&w-right>=cw+gap+16){x=right+gap;y=Math.min(Math.max(18,top),h-ch-18)}
    else if(bottom+ch+gap<h)y=bottom+gap;
    else if(top>ch+gap+16)y=top-ch-gap;
    Object.assign(card.style,{left:Math.max(12,x)+'px',top:Math.max(12,y)+'px'});
  }
  async function render(navigate=false){
    if(!active||!beats.length)return;
    const index=Math.max(0,beats.findIndex(b=>b.id===current)),b=beats[index];current=b.id;
    if(state.view!==b.view){
      if(!navigate){root.hidden=true;document.body.classList.remove('guide-open');return}
      entering=true;try{if(b.view==='world')await showWorld();else await openCase()}catch(e){close();error(e.message)}finally{entering=false}
      if(active)render(true);return;
    }
    target=document.querySelector(b.target);
    if(!target||target.closest('[hidden]')){root.hidden=true;document.body.classList.remove('guide-open');return}
    for(let p=target;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
    root.hidden=false;document.body.classList.add('guide-open');
    const nextStep=nextGuideStep(beats,current,seen),identity=[b.id,b.title,b.copy,b.detail,b.wait,beats.length,nextStep].join('|'),changed=root.dataset.beat!==identity;
    if(changed){
      root.dataset.beat=identity;$('.guide-who').textContent=b.who;$('.guide-caption h2').textContent=b.title;$('.guide-copy').textContent=b.copy;
      $('.guide-detail').textContent=b.tool?`${toolLabels[b.tool]||b.tool}${b.detail?' · '+b.detail:''}`:b.detail||'';$('.guide-detail').hidden=!b.tool&&!b.detail;
      $('.guide-progress').textContent=`${index+1} / ${beats.length}${!['protected'].includes(state.data.demo.phase)?' so far':''}`;
      $('.guide-back').disabled=index===0;const next=$('.guide-next');next.textContent=b.done?'Finish demo':b.action?b.next||'Continue':'Next';next.disabled=!nextStep&&!b.done&&!b.action&&b.id!=='complaint';
      $('.guide-wait').textContent=b.manual?b.wait||'Choose the highlighted action':b.live?(nextStep?'New tool results are ready. Click Next to inspect them.':'Agent working · new steps appear as results arrive'):next.disabled?b.wait||'No further recorded steps':'Click Next when you are ready';
    }
    if(navigate){
      const r=target.getBoundingClientRect();
      if(r.top<100||r.bottom>innerHeight-card.offsetHeight-36){const top=scrollY+r.top-(innerWidth<1200?24:110);window.scrollTo({top:Math.max(0,top),behavior:'instant'})}
      if(priorFocus&&root.contains(document.activeElement)||!priorFocus){$('.guide-close').focus({preventScroll:true})}
    }
    seen.add(current);layout();
  }
  function update(nextReport){
    const demo=state.data?.demo;if(!demo?.guided){if(active)close();return;}
    const key=demo.scene_id+':'+demo.run_id;
    if(scene!==key){scene=key;report=null;current='world';beats=[];seen.clear();priorFocus=document.activeElement;active=!!demo.running&&saved('minttown-guide-dismissed')!==scene;root.dataset.beat=''}
    if(nextReport){report=nextReport;if(report.id!==demo.focus_report_id&&!entering){close();report=null;return}}
    if(report&&report.id!==demo.focus_report_id){report=null;if(state.view==='resolution')root.hidden=true}
    beats=keepReadingStep(beats,demoBeats(demo,report),current);
    if(!active)return;
    cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{if(!entering)render(current!==root.dataset.current);root.dataset.current=current});
  }
  async function advance(){
    const i=beats.findIndex(b=>b.id===current),b=beats[i];if(b?.done){close();return}
    if(b?.action){$('.guide-next').disabled=true;try{if(b.action==='start')await startInvestigation();else await refreshCase();update()}finally{$('.guide-next').disabled=false}return}
    if(b?.id==='complaint'&&!report){entering=true;try{await openCase()}catch(e){close();error(e.message)}finally{entering=false}beats=demoBeats(state.data.demo,report)}
    current=nextGuideStep(beats,current,seen)||current;render(true);
  }
  $('.guide-next').onclick=()=>advance().catch(e=>error(e.message));
  $('.guide-back').onclick=()=>{current=beats[Math.max(0,beats.findIndex(b=>b.id===current)-1)].id;render(true)};
  $('.guide-close').onclick=close;
  document.getElementById('fraud-select').addEventListener('change',close);
  document.getElementById('risk-models-tab').addEventListener('click',close);
  window.addEventListener('keydown',e=>{if(e.key==='Escape'&&active){close();if(priorFocus?.isConnected)priorFocus.focus({preventScroll:true})}});
  window.addEventListener('scroll',layout,{passive:true,capture:true});window.addEventListener('resize',()=>active?render(true):layout());
  new ResizeObserver(layout).observe(card);
  return {update,close};
}
