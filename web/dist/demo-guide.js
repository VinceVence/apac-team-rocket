import {roleNames} from './harness-ui.js';
import {cleanText,toolLabels} from './agent-ui.js';

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
  const run=report.investigation,checks=report.harness?.checks||[];
  const judged=checks.find(c=>c.judges?.some(j=>j.judge==='resolution'));
  if(judged)add('judges','resolution','.harness-judges',judged.passed?'The draft passed local checks':'The judges withheld this draft',judged.passed?'Evidence, model contracts and resolution claims passed the checks. An analyst still makes the decision.':'A contract or claim failed validation. The draft cannot proceed as an approved resolution.',{who:'Harness judges',detail:short(judged.judges.filter(j=>!j.passed).flatMap(j=>j.blockers||[]).join(' '))});
  if(run?.recommendation)add('proposal','resolution','#fraud-packet','Read the proposed resolution','Review the suggested action, cited evidence and what remains uncertain.',{who:'Resolution agent',next:'Show analyst review'});
  if(report.status==='awaiting_customer')add('reply','resolution','#fraud-reply-form','The customer needs to answer',short(run?.context?.pending_question)||'A missing fact prevents the agent from continuing.',{who:'Customer follow-up',wait:'Waiting for a reply'});
  if(['failed','budget_exhausted','interrupted'].includes(run?.status))add('stopped','resolution','#fraud-agent-stop','The investigation paused safely','Check the saved evidence and stop reason. The guide does not retry model calls or bypass limits.',{who:'Manual attention',wait:'Use the case controls'});
  if(report.status==='awaiting_review')add('review','resolution','#fraud-review-form','Now the risk analyst decides','Check the proposal, choose a decision, then use Approve & learn if justified. The guide cannot approve for you.',{who:'Human decision',wait:'Waiting for your review'});
  if(report.reviews?.length){
    add('review','resolution','#fraud-resolution','The analyst recorded a resolution','The saved resolution and service receipt show what the analyst authorized.',{who:'Human decision'});
    if(report.approved_lesson&&report.approved_lesson.lifecycle?.active!==false)add('knowledge','resolution','#fraud-memory-panel','Reviewed knowledge can be reused','The approved lesson is now available to later investigations. Applicability, expiry and revocation still apply.',{who:'Shared knowledge'});
  }
  const job=report.prevention,rule=job?.rule;
  if(job){
    add('prevention','resolution','#prevention-panel',rule?'A candidate safeguard was tested':'Learn a safeguard from the case',rule?'Replay checks the proposed signals against a changed recipient and legitimate controls. It does not prove real-world accuracy.':'The prevention agent uses the approved case to propose a safeguard for future payments.',{who:'Prevention agent',wait:['failed','budget_exhausted'].includes(job.status)?'Use the case controls':'Waiting for a safeguard'});
    if(rule?.status==='proposed'&&rule.replay?.passed)add('activate','resolution','#prevention-rule','Activation is a separate decision','Inspect the signals and replay. Enable the safeguard only if those checks justify it.',{who:'Human decision',wait:'Waiting for activation'});
    if(rule?.status==='active')add('protect','resolution','#prevention-rule','Try the next suspicious payment','Use Test a similar payment. The local safeguard checks before debit; the check runs locally.',{who:'Payment safeguard',wait:'Use Test a similar payment'});
  }
  if(demo.phase==='protected')add('protected','world','#world-alert','The later scam was held','The changed-recipient attempt was held before debit. The legitimate control payment passed. The check runs locally.',{who:'Protection verified',done:true});
  return beats;
}

export function createDemoGuide({state,openCase,showWorld,error}){
  const root=document.createElement('div');root.id='demo-guide';root.hidden=true;
  root.innerHTML='<div class="guide-focus" aria-hidden="true"></div><aside class="guide-caption" role="region" aria-label="Demo guide"><header><span class="guide-who"></span><button type="button" class="guide-close" aria-label="Close demo guide">×</button></header><div aria-live="polite" aria-atomic="true"><h2></h2><p class="guide-copy"></p><p class="guide-detail"></p></div><footer><span class="guide-progress"></span><button type="button" class="guide-back">Back</button><button type="button" class="primary-button guide-next">Next</button></footer><small class="guide-wait"></small></aside>';
  document.body.append(root);
  const $=s=>root.querySelector(s),card=$('.guide-caption'),ring=$('.guide-focus'),toggle=document.getElementById('demo-guide-toggle');
  let scene=null,report=null,active=false,beats=[],current='world',target=null,frame=0,entering=false,autoWorld=true;
  let priorFocus=null;
  const saved=(key,value)=>{try{if(value===undefined)return sessionStorage.getItem(key);sessionStorage.setItem(key,value)}catch{}return null};
  function close(){active=false;root.hidden=true;document.body.classList.remove('guide-open');toggle.textContent='Guide demo';saved('minttown-guide-dismissed',scene);if(root.contains(document.activeElement))toggle.focus();else priorFocus=null}
  function start(){if(!state.data?.demo.guided)return;active=true;current='world';autoWorld=!state.data.demo.focus_report_id;priorFocus=document.activeElement;saved('minttown-guide-dismissed','');update();render(true)}
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
    root.hidden=false;document.body.classList.add('guide-open');toggle.textContent='Hide guide';
    const identity=[b.id,b.title,b.copy,b.detail,b.wait,beats.length].join('|'),changed=root.dataset.beat!==identity;
    if(changed){
      root.dataset.beat=identity;$('.guide-who').textContent=b.who;$('.guide-caption h2').textContent=b.title;$('.guide-copy').textContent=b.copy;
      $('.guide-detail').textContent=b.tool?`${toolLabels[b.tool]||b.tool}${b.detail?' · '+b.detail:''}`:b.detail||'';$('.guide-detail').hidden=!b.tool&&!b.detail;
      $('.guide-progress').textContent=`${index+1} / ${beats.length}${!['protected'].includes(state.data.demo.phase)?' so far':''}`;
      $('.guide-back').disabled=index===0;const next=$('.guide-next');next.textContent=b.done?'Finish guide':b.next||'Next';next.disabled=index===beats.length-1&&!b.done&&b.id!=='complaint';
      $('.guide-wait').textContent=next.disabled?b.wait||'Waiting for the next recorded action':'Esc to close · approvals stay manual';
    }
    if(navigate){
      const r=target.getBoundingClientRect();
      if(r.top<100||r.bottom>innerHeight-card.offsetHeight-36){const top=scrollY+r.top-(innerWidth<1200?24:110);window.scrollTo({top:Math.max(0,top),behavior:'instant'})}
      if(priorFocus&&root.contains(document.activeElement)||!priorFocus){$('.guide-close').focus({preventScroll:true})}
    }
    layout();
  }
  function update(nextReport){
    const demo=state.data?.demo;if(!demo?.guided)return;
    const key=demo.scene_id+':'+demo.run_id;
    if(scene!==key){scene=key;report=null;current='world';autoWorld=true;active=!!demo.running&&saved('minttown-guide-dismissed')!==scene;root.dataset.beat=''}
    if(nextReport){report=nextReport;if(report.id!==demo.focus_report_id&&!entering){close();report=null;return}}
    if(report&&report.id!==demo.focus_report_id){report=null;if(state.view==='resolution')root.hidden=true}
    beats=demoBeats(demo,report);toggle.hidden=false;
    if(!active)return;
    // Advance waiting states only after the backend supplies the next fact.
    if(current==='world'&&autoWorld&&demo.focus_report_id){current='complaint';autoWorld=false}
    if(state.view==='resolution'&&report&&current==='complaint'&&!entering)current='report';
    if(current==='reply'&&report?.status!=='awaiting_customer')current=beats.some(b=>b.id==='proposal')?'proposal':beats.at(-1).id;
    if(current==='review'&&report?.status==='resolved')current=beats.some(b=>b.id==='knowledge')?'knowledge':'review';
    if(current==='activate'&&report?.prevention?.rule?.status==='active')current='protect';
    if(current==='protect'&&demo.phase==='protected')current='protected';
    if(!beats.some(b=>b.id===current))current=beats.at(-1)?.id||'world';
    cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{if(!entering)render(current!==root.dataset.current);root.dataset.current=current});
  }
  $('.guide-next').onclick=async()=>{
    const i=beats.findIndex(b=>b.id===current),b=beats[i];if(b?.done){close();return}
    if(b?.id==='complaint'&&!report){entering=true;try{await openCase()}catch(e){close();error(e.message)}finally{entering=false}beats=demoBeats(state.data.demo,report)}
    current=beats[i+1]?.id||current;render(true);
  };
  $('.guide-back').onclick=()=>{current=beats[Math.max(0,beats.findIndex(b=>b.id===current)-1)].id;render(true)};
  $('.guide-close').onclick=close;toggle.onclick=()=>active?close():start();
  document.getElementById('fraud-select').addEventListener('change',close);
  document.getElementById('risk-models-tab').addEventListener('click',close);
  window.addEventListener('keydown',e=>{if(e.key==='Escape'&&active){close();if(priorFocus?.isConnected)priorFocus.focus({preventScroll:true})}});
  window.addEventListener('scroll',layout,{passive:true,capture:true});window.addEventListener('resize',()=>active?render(true):layout());
  new ResizeObserver(layout).observe(card);
  return {update,start,close};
}
