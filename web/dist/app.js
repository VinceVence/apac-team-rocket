import {createTown} from './town.js';
import {createFraudUI} from './fraud-ui.js';
import {createRiskUI} from './risk-ui.js';
import {createDemoGuide} from './demo-guide.js';
import {createRecordedDemo} from './demo-replay.js';
import {showEvaluation} from './evaluation-ui.js';
import {mountAgentIcons,cleanText,agentIcon,featuredIncident} from './agent-ui.js';
import {residentLabel,residentAlerts} from './resident-sprites.js';
mountAgentIcons();
showEvaluation(document.getElementById('evaluation-panel')).catch(()=>{});
const $=id=>document.getElementById(id),drawTown=createTown($('town-map'));
const state={data:null,view:'world',busy:false,playing:false,speed:1,stepping:false,customerId:null,hosted:false};
const money=n=>'₱'+(n/100).toLocaleString('en-PH',{maximumFractionDigits:0});
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
let pollTimer=null,lastTick=-1,lastIncident=null,lastScene=null,guide=null;
async function api(path,body){
  if(state.replay)return state.replay.api(path,body);
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-MintTown-Token':state.data.csrf_token},body:JSON.stringify(body)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Request could not be completed.');return result;
}
function error(message){$('app-error').textContent=cleanText(message||'');$('app-error').hidden=!message}
function setBusy(on){state.busy=on;document.querySelectorAll('[data-view]').forEach(b=>b.disabled=on);renderRunControls()}
function renderRunControls(){
  const demo=state.data?.demo;if(!demo)return;
  $('run-demo').disabled=state.busy;
  $('restart-world').disabled=state.busy||!!demo.restart_blocked;
  $('restart-world').title=demo.restart_blocked?'Wait for the current agent work to finish.':'Archive this scene and start an empty simulation. Usage limits stay unchanged.';
  $('play-world').disabled=state.busy||(!demo.running&&!demo.continuous&&!!demo.restart_blocked);
  $('play-world').textContent=demo.running?'Ⅱ Pause simulation':demo.continuous?'▶ Resume simulation':'▶ Run simulation';
  $('play-world').title=demo.running?'Pause payments; active investigations can finish.':demo.continuous?'Resume this world with its cases and safeguards.':'Start an empty world. Payments continue while agents investigate.';
  $('run-demo').title='Run the complete demo. Saved Gemini playback is available when live work cannot start.';
}
const sidebarMobile=matchMedia('(max-width:1000px)');let menuOpen=false,sidebarCollapsed=false;
try{sidebarCollapsed=localStorage.getItem('minttown-sidebar-collapsed')==='true'}catch{}
function renderSidebar(){
  const mobile=sidebarMobile.matches,open=mobile?menuOpen:!sidebarCollapsed;
  $('mint-town').classList.toggle('parameters-open',mobile&&open);
  $('mint-town').classList.toggle('sidebar-collapsed',!mobile&&sidebarCollapsed);
  $('sidebar-backdrop').hidden=!(mobile&&open);
  $('open-menu').setAttribute('aria-expanded',String(open));
  const label=open?'Collapse sidebar':'Expand sidebar';$('open-menu').setAttribute('aria-label',label);$('open-menu').title=label;
  $('sidebar-chevron').setAttribute('d',open?'m17 9-3 3 3 3':'m14 9 3 3-3 3');
  requestAnimationFrame(positionFraudAlert);
}
function setMenu(open){menuOpen=open;renderSidebar()}
function toggleSidebar(){
  if(sidebarMobile.matches)menuOpen=!menuOpen;
  else{sidebarCollapsed=!sidebarCollapsed;try{localStorage.setItem('minttown-sidebar-collapsed',String(sidebarCollapsed))}catch{}}
  renderSidebar();
}
sidebarMobile.addEventListener('change',()=>{menuOpen=false;renderSidebar()});renderSidebar();
function incidentCopy(i){return i.status==='passed'?'Legitimate payment completed':i.status==='blocked'?'Held before debit by approved knowledge':i.status==='budget_limited'?'Investigation allowance reached':i.report_status==='resolved'?'Analyst reviewed':i.report_status==='awaiting_review'?'Ready for analyst review':i.report_status==='awaiting_customer'?'Waiting for a customer reply':i.status==='needs_review'||i.report_status==='needs_review'?'Needs manual review':i.report_status==='reported'?'Preparing case evidence':'Agent investigating'}
function renderWorld(){
  const d=state.data,w=d.world,demo=d.demo;
  if(lastScene&&lastScene!==demo.scene_id){state.customerId=null;state.focusReport=null;drawTown.reset();fraudUI.reset();lastTick=-1}
  lastScene=demo.scene_id;
  const phase=demo.phase||'world',stage={world:0,complaint:1,investigation:2,followup:2,review:3,prevention:4,activate:4,ready:4,protected:5,attention:3}[phase]??0;
  const narrative={world:demo.running?'Payments are arriving. Watch for a resident asking for help.':'Press Run simulation. Start with zero transactions.',complaint:'A resident is calling for help. A scam report is being filed.',investigation:'The resident reported a scam. Follow the agent’s investigation.',followup:'The agent needs one customer answer before continuing.',review:'The resolution is ready for the human risk analyst.',prevention:'The prevention agent is learning from the reviewed case.',activate:'The safeguard passed replay. The analyst decides whether to enable it.',ready:'The safeguard is active. Test a similar request with a different recipient.',protected:'The similar request was held before debit. The legitimate payment passed.',attention:'This case needs manual attention. Open the saved evidence.'};
  $('demo-narrative').textContent=narrative[phase]||narrative.world;document.querySelector('.demo-story').hidden=!demo.guided||state.view!=='world';
  $('world-mode-label').textContent=demo.continuous?'Live simulation':demo.guided?'Guided demo':'Choose demo or simulation';
  document.querySelectorAll('[data-demo-stage]').forEach((n,i)=>{n.classList.toggle('current',i===stage);n.classList.toggle('done',i<stage);if(i===stage)n.setAttribute('aria-current','step');else n.removeAttribute('aria-current')});

  $('population-count').textContent=d.customers.length+' customers';
  const generated=d.environment_data;
  $('simulation-count').textContent=(generated?.counts.wallet_transactions||0).toLocaleString()+' transactions';
  $('environment-data-total').textContent=generated?`${generated.counts.wallet_transactions.toLocaleString()} transfers`:'';
  const publication=generated?.publication;
  $('environment-data-status').textContent=publication?.enabled?`${publication.dataset} · ${publication.latest?.status==='completed'?'saved':publication.latest?'publication needs review':'batched sync pending'}`:'Local generation · 100 customers';
  $('environment-data-tables').replaceChildren();
  for(const [table,count] of Object.entries(generated?.counts||{})){
    const row=node('div',undefined,'environment-data-row');row.append(node('span',table),node('strong',count.toLocaleString()));$('environment-data-tables').append(row);
  }
  const wh=d.warehouse;
  $('warehouse-note').textContent=publication?.enabled?(publication.latest?.status==='completed'?'BigQuery · 6 simulator tables':'BigQuery · batched sync pending'):wh?.latest_snapshot?`BigQuery · ${wh.latest_snapshot.row_count.toLocaleString()} rows · ${wh.table_count} tables`:wh?.enabled?'BigQuery · batched sync pending':'Local data · warehouse off';
  $('warehouse-tables').replaceChildren();
  const exportTables=publication?.enabled?Object.keys(generated.counts):wh?.tables||[];
  const exportCounts=publication?.enabled?publication.latest?.counts:wh?.latest_snapshot?.counts;
  for(const table of exportTables)$('warehouse-tables').append(node('li',table.replace('pallet_','').replaceAll('_',' ')+(exportCounts?' · '+(exportCounts[table]||0)+' rows':'')));
  state.playing=!!demo.running;$('mint-town').classList.toggle('is-running',state.playing);
  $('running-label').textContent=state.playing?'● Running':'Paused';renderRunControls();
  $('world-time').textContent=w.day+' · '+String(w.hour).padStart(2,'0')+':00';$('map-date').textContent=String(w.hour).padStart(2,'0')+':00';
  $('ledger-health').textContent=d.ledger_balanced?'Ledger balanced':'Ledger needs review';
  $('provider-label').textContent=demo.replay?'Recorded Gemini replay':d.budget.live_enabled?'Live agents':'Local rehearsal';
  $('protected-count').textContent=demo.blocked_payments;$('knowledge-total').textContent=demo.knowledge_count;
  const pending=demo.incidents.filter(i=>i.report_id&&i.report_status!=='resolved').length;
  $('agent-badge').textContent=pending;$('agent-badge').hidden=!pending;
  $('world-note').textContent=demo.scene_blocked_reason||(!demo.running&&demo.start_blocked_reason)||(demo.calls_remaining===0?'Investigation allowance used. Approved knowledge still protects payments.':demo.running?'Each payment becomes a new transaction record.':demo.note==='Ready'?'100 residents. Opening wallet balances. No transactions yet.':demo.note);
  $('activity').disabled=state.playing;document.querySelectorAll('[data-speed]').forEach(b=>b.disabled=state.playing);
  const latest=featuredIncident(demo);$('world-alert').hidden=!latest;
  if(latest){const person=residentLabel(latest.customer_id);$('world-alert-title').textContent=latest.status==='blocked'?'A similar request was held.':latest.report_id?person+' filed a scam report':'Scam case not created';$('world-alert-copy').textContent=demo.scene_blocked_reason||incidentCopy(latest);$('world-report').textContent=latest.status==='blocked'?'View knowledge →':'Follow the investigation →';$('world-report').hidden=!latest.report_id&&latest.status!=='blocked'}
  $('world-alert').hidden=!demo.guided||!latest;
  renderNotifications(demo);
  $('world-events').replaceChildren();
  for(const i of demo.incidents.slice(0,3)){
    const row=node('div',undefined,'world-event '+(i.status==='blocked'?'blocked':'incident')),body=node('div');
    row.append(node('span',['blocked','passed'].includes(i.status)?'✓':'!','event-icon'));body.append(node('strong',i.title),node('small',incidentCopy(i)));
    if(i.report_id||i.status==='blocked'){const button=node('button',i.status==='blocked'?'View knowledge →':'Open investigation →','text-button');button.onclick=()=>openIncident(i);body.append(button)}row.append(body);$('world-events').append(row);
  }
  const payments=d.events.filter(e=>['payment','payment_blocked','payment_declined'].includes(e.kind)).slice(0,5);
  $('transaction-ticker').textContent=payments.length?residentLabel(payments[0].customer_id)+' · '+money(payments[0].amount_minor)+' '+(payments[0].status==='blocked'?'held':payments[0].status==='declined'?'declined':'paid'):'Waiting for the first payment';
  for(const e of payments){
    const name=residentLabel(e.customer_id);
    const row=node('div',undefined,'world-event '+e.status),body=node('div');row.append(node('span',e.status==='blocked'?'✓':'↗','event-icon'));
    body.append(node('strong',`${name} ${e.status==='blocked'?'was protected':e.status==='declined'?'payment declined':'paid '+money(e.amount_minor)}`),node('small',e.status==='blocked'?'Transfer held before settlement':({P2P_TRANSFER:'Person-to-person transfer',MERCHANT_QR:'Merchant QR payment',CASH_IN_AGENT:'Cash-in',CASH_OUT_AGENT:'Cash-out'}[e.metadata?.transaction_type]||e.metadata?.rail||'Wallet payment')));row.append(body);$('world-events').append(row);
  }
  drawTown.setAlerts(residentAlerts(demo));
  if(demo.focus_report_id&&demo.focus_report_id!==state.focusReport){state.focusReport=demo.focus_report_id;state.customerId=demo.focus_customer_id}
  drawTown(d.customers.map(p=>({...p,name:residentLabel(p.id)})),state.customerId);drawTown.setHour(w.hour);drawTown.setSpeed(state.playing?demo.speed:state.speed);
  drawTown.setVisible(state.view==='world'&&!document.hidden);drawTown.setRunning(state.playing);
  drawTown.motion(payments.slice(0,4).map(e=>({id:e.id,customer_id:e.customer_id,merchant:['m1','m2','m3'].includes(e.to_account)?e.to_account:'m4',receiver_customer_id:e.to_account?.endsWith(':wallet')?e.to_account.split(':')[0]:null,transaction_type:e.metadata?.transaction_type,amount_minor:e.amount_minor,status:e.status})),lastTick===-1);
  lastTick=w.tick;
  positionFraudAlert();
  renderResident();
  guide?.update();
}
function renderNotifications(demo){
  const notices=$('world-notifications');notices.replaceChildren();
  const held=demo.protection?.recent||[],reports=demo.incidents.filter(i=>i.report_id&&i.report_status!=='resolved');
  const items=[...reports.map(i=>({...i,copy:incidentCopy(i)})),...held.slice(0,1).map(i=>({...i,status:'blocked',copy:'Prevention held the transfer'}))].sort((a,b)=>b.created_at.localeCompare(a.created_at)).slice(0,2);
  for(const i of items){const safe=i.status==='blocked',b=node('button',undefined,'world-notification '+(safe?'safe':'report'));b.type='button';b.append(agentIcon(safe?'prevention':'resolution'));const text=node('span');text.append(node('strong',residentLabel(i.customer_id)+(safe?' protected':' filed a report')),node('small',i.copy),node('span',safe?'View protection →':'Watch agent →','notification-link'));b.append(text);b.onclick=()=>{guide.close();openIncident(safe?{...i,report_id:i.source_report_id}:i)};notices.append(b)}
  $('protection-total').textContent=demo.protection?.count||0;$('protection-empty').hidden=held.length>0;$('protection-events').replaceChildren();
  for(const i of held.slice(0,3)){const row=node('div',undefined,'protected-payment'),text=node('div');row.append(agentIcon('prevention'));text.append(node('strong',residentLabel(i.customer_id)+' · '+money(i.amount_minor)+' held'),node('small',i.rule_ids?.length?'Approved safeguard matched':'Reviewed recipient matched'));row.append(text);const open=node('button','View protection →','text-button');open.onclick=()=>{guide.close();openIncident({...i,status:'blocked',report_id:i.source_report_id})};row.append(open);$('protection-events').append(row)}
}
function positionFraudAlert(){
  const alarm=drawTown.alertBounds(),anchor=$('fraud-sprite-focus'),canvas=$('town-map');anchor.hidden=!alarm;
  if(alarm){const sx=canvas.clientWidth/canvas.width,sy=canvas.clientHeight/canvas.height;Object.assign(anchor.style,{left:(canvas.offsetLeft+alarm.x*sx)+'px',top:(canvas.offsetTop+alarm.y*sy)+'px',width:alarm.width*sx+'px',height:alarm.height*sy+'px'})}
}
window.addEventListener('resize',positionFraudAlert);
function renderResident(){
  const people=state.data.customers,picker=$('resident-picker');
  if(picker.options.length!==people.length+1){picker.replaceChildren(new Option('Choose a resident',''),...people.map(p=>new Option(residentLabel(p.id),p.id)))}
  picker.value=state.customerId||'';
  const person=people.find(p=>p.id===state.customerId);$('resident-card').hidden=!person;
  if(!person)return;
  $('resident-name').textContent=residentLabel(person.id);
  const incident=state.data.demo.incidents.find(i=>i.customer_id===person.id);
  const payment=state.data.events.find(e=>e.customer_id===person.id&&['payment','payment_blocked','payment_declined'].includes(e.kind));
  $('resident-note').textContent=incident?incidentCopy(incident):payment?`${payment.status==='settled'?'Latest payment':payment.status==='blocked'?'Payment held':'Payment declined'} · ${money(payment.amount_minor)}`:'Exploring the neighborhood';
  const held=state.data.demo.protection?.recent.find(p=>p.customer_id===person.id);
  $('resident-case').hidden=!incident?.report_id&&!held;
  $('resident-case').textContent=held?'View protection →':'Open their case →';
  $('resident-case').onclick=()=>{guide.close();openIncident(held?{...held,status:'blocked',report_id:held.source_report_id}:incident)};
}
function followResident(id){state.customerId=id||null;renderWorld()}
$('town-map').addEventListener('resident-select',event=>followResident(event.detail));
$('resident-picker').onchange=event=>followResident(event.target.value);
$('resident-close').onclick=()=>followResident(null);
async function refresh(){state.data=await api('/api/state');renderWorld();schedulePoll()}
function schedulePoll(){clearTimeout(pollTimer);if(state.replay||document.hidden||(!state.data?.demo.running&&!state.data?.demo.agent_busy&&!['complaint','investigation','prevention'].includes(state.data?.demo.phase)))return;pollTimer=setTimeout(async()=>{try{await refresh();const latest=state.data.demo.incidents[0]?.id;if(latest!==lastIncident&&state.view==='resolution')await fraudUI.load();lastIncident=latest}catch(e){error(e.message)}},3000)}
async function cloudStatus(){const c=await api('/api/cloud');state.hosted=!!c.enabled;$('cloud-data-panel').hidden=!c.enabled;if(c.enabled){$('deployment-label').textContent=c.execution==='local'?'Local simulation':'Cloud simulation';$('cloud-data-status').textContent=`${c.daily_exports} export batches today`;const pending=!!sessionStorage.getItem('minttown-export-request');$('cloud-export').textContent=pending?'Check export status':'Export next batch';$('cloud-export').disabled=!c.healthy||(c.daily_export_limit!==null&&c.daily_exports>=c.daily_export_limit&&!pending)}}
const fraudUI=createFraudUI({$,api,state,setPlaying:()=>{},setBusy,refresh,error,focusCustomer:cid=>{state.customerId=cid;renderWorld()},onRender:report=>guide?.update(report),onNavigate:()=>guide?.close()});
const riskUI=createRiskUI({$,state,error,onCases:()=>fraudUI.load(true)});
guide=createDemoGuide({state,error,onClose:()=>{if(state.replay){try{sessionStorage.setItem('minttown-guide-dismissed',state.replayReturnScene)}catch{}state.replay=null;fraudUI.reset();setBusy(true);refresh().then(()=>showView('world')).catch(e=>error(e.message)).finally(()=>setBusy(false))}},showWorld:customerId=>{if(customerId)state.customerId=customerId;return showView('world')},residentPosition:id=>drawTown.residentPosition(id),openCase:async()=>{if(!await openIncident({report_id:state.data.demo.focus_report_id}))throw Error('The saved case could not be opened. Refresh its status.');},demoAction:async action=>{if(action==='replay')return recordedDemo();await api('/api/world/demo-action',{expected_run:state.data.demo.run_id,report_id:state.data.demo.focus_report_id,action});await refresh();if(state.data.demo.focus_report_id)await fraudUI.load()}});
async function showView(view){if(state.view!==view)window.scrollTo({top:0,behavior:'instant'});state.view=['world','resolution','agents'].includes(view)?view:'world';setMenu(false);error('');$('mint-town').dataset.view=state.view;history.replaceState(null,'',state.view==='world'?location.pathname:state.view==='agents'?'#agents':location.hash==='#models'?'#models':'#agent');document.title='Mint Town · '+({world:'Environment',resolution:'Agent activity',agents:'Agents'}[state.view]);document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));$('case-view').hidden=state.view!=='world';$('fraud-view').hidden=state.view!=='resolution';$('agents-view').hidden=state.view!=='agents';renderWorld();document.querySelector('.demo-story').hidden=state.view!=='world'||!state.data.demo.guided;if(state.view==='resolution'){if(location.hash==='#models'||!$('risk-view').hidden)await riskUI.show(true);else await fraudUI.load(true)}else riskUI.pause()}
async function openIncident(i){try{await riskUI.show(false);await showView('resolution');if(i.report_id||state.data.demo.focus_report_id)await fraudUI.open(i.report_id||state.data.demo.focus_report_id);if(i.status==='blocked'){$('fraud-memory-panel').open=true;document.getElementById(i.report_id?'prevention-stage':'fraud-memory-panel').scrollIntoView({behavior:'smooth',block:'start'})}return true}catch(e){error(e.message);return false}}
$('open-menu').onclick=toggleSidebar;$('close-menu').onclick=()=>{setMenu(false);$('open-menu').focus()};$('sidebar-backdrop').onclick=()=>setMenu(false);window.addEventListener('keydown',e=>{if(e.key==='Escape')setMenu(false)});
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{guide.close();showView(b.dataset.view).catch(e=>error(e.message))};
for(const b of document.querySelectorAll('[data-speed]'))b.onclick=()=>{state.speed=Number(b.dataset.speed);$('speed-label').textContent=state.speed+'×';document.querySelectorAll('[data-speed]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)))};
$('activity').oninput=()=>{$('activity-value').textContent=$('activity').value};
async function runWorld(mode){
  if(state.busy||!state.data)return;setBusy(true);error('');guide.close();
  try{
    const demo=state.data.demo,pausing=mode==='simulation'&&demo.running;
    if(mode==='demo'&&(demo.start_blocked_reason||demo.restart_blocked||demo.running||demo.calls_remaining<6)){await recordedDemo();return}
    await api(pausing?'/api/world/stop':'/api/world/start',pausing?{expected_run:demo.run_id}:{expected_run:demo.run_id,activity:Number($('activity').value),speed:state.speed,fresh:mode==='demo'||!demo.continuous,mode});
    await refresh();if(!pausing)await showView('world');
  }catch(e){if(mode==='demo'){try{await recordedDemo()}catch(replayError){error(replayError.message)}}else error(e.message)}finally{setBusy(false)}
}
let recording=null;
async function recordedDemo(){
  if(!recording){const response=await fetch('/demo-recording.json');if(!response.ok)throw Error('The saved demo could not load. Refresh this page.');recording=await response.json()}
  clearTimeout(pollTimer);fraudUI.reset();if(!state.replay)state.replayReturnScene=state.data.demo.scene_id+':'+state.data.demo.run_id;state.replay=createRecordedDemo(recording,'REPLAY-'+crypto.randomUUID());
  state.data=state.replay.snapshot();state.focusReport=null;await showView('world');
}
$('play-world').onclick=()=>runWorld('simulation');
$('run-demo').onclick=()=>runWorld('demo');
let restartRun=null;
$('restart-world').onclick=()=>{guide.close();restartRun=state.data.demo.run_id;$('restart-dialog').returnValue='';$('restart-dialog').showModal()};
$('restart-dialog').addEventListener('close',async()=>{
  const expectedRun=restartRun;restartRun=null;
  if($('restart-dialog').returnValue!=='restart'||state.busy)return;
  setBusy(true);error('');
  try{
    await api('/api/world/restart',{expected_run:expectedRun,activity:Number($('activity').value),speed:state.speed});
    await refresh();await cloudStatus();await showView('world');
  }catch(e){error(e.message);await refresh().catch(()=>{})}finally{setBusy(false)}
});
$('world-report').onclick=()=>{const incident=featuredIncident(state.data.demo);if(incident)openIncident(incident)};
$('cloud-export').onclick=async()=>{if(state.busy)return;setBusy(true);$('cloud-export').disabled=true;try{const id=sessionStorage.getItem('minttown-export-request')||crypto.randomUUID();sessionStorage.setItem('minttown-export-request',id);const r=await api('/api/cloud/export',{request_id:id});if(['completed','failed'].includes(r.status))sessionStorage.removeItem('minttown-export-request');$('cloud-export-result').textContent=`${r.row_count.toLocaleString()} records · ${r.status}`}catch(e){error(e.message)}finally{setBusy(false);await cloudStatus().catch(e=>error(e.message))}};
document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(pollTimer);drawTown.setVisible(false)}else refresh().catch(e=>error(e.message))});
window.addEventListener('hashchange',()=>showView(!location.hash?'world':location.hash==='#agents'?'agents':'resolution').catch(e=>error(e.message)));
try{await refresh();await cloudStatus();$('loading-state').hidden=true;await showView(!location.hash?'world':location.hash==='#agents'?'agents':'resolution');await document.fonts.ready;renderWorld()}catch(e){$('loading-state').hidden=true;error('Cannot reach the simulation. '+e.message)}
