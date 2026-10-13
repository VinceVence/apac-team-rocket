import {createTown} from './town.js';
import {createFraudUI} from './fraud-ui.js';
const $=id=>document.getElementById(id),drawTown=createTown($('town-map'));
const state={data:null,view:'world',busy:false,playing:false,speed:1,stepping:false,customerId:null,hosted:false};
const money=n=>'₱'+(n/100).toLocaleString('en-PH',{maximumFractionDigits:0});
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
let pollTimer=null,lastTick=-1,lastIncident=null,lastScene=null;
async function api(path,body){
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-MintTown-Token':state.data.csrf_token},body:JSON.stringify(body)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Request could not be completed.');return result;
}
function error(message){$('app-error').textContent=message||'';$('app-error').hidden=!message}
function setBusy(on){state.busy=on;document.querySelectorAll('[data-view],#play-world').forEach(b=>b.disabled=on)}
function setMenu(open){$('mint-town').classList.toggle('parameters-open',open);$('sidebar-backdrop').hidden=!open;$('open-menu').setAttribute('aria-expanded',String(open))}
function incidentCopy(i){return i.status==='passed'?'Legitimate payment completed · no model call':i.status==='blocked'?(i.title.includes('changed recipient')?'New recipient · held for verification':'Held by approved knowledge'):i.status==='budget_limited'?'Investigation allowance reached':i.report_status==='resolved'?'Reviewed · protection active':i.report_status==='awaiting_review'?'Ready for analyst review':i.report_status==='awaiting_customer'?'Waiting for a customer reply':i.report_status==='needs_review'?'Needs manual review':'Agent investigating'}
function renderWorld(){
  const d=state.data,w=d.world,demo=d.demo;
  if(lastScene&&lastScene!==demo.scene_id){state.customerId=null;drawTown.reset();fraudUI.reset();lastTick=-1}
  lastScene=demo.scene_id;
  const phase=demo.phase||'world',stage={world:0,complaint:1,investigation:2,followup:2,review:3,prevention:4,activate:4,ready:4,protected:5,attention:3}[phase]??0;
  const narrative={world:demo.running?'Customers are transacting. Watch for a customer alert.':'Start a fresh world. Prior cases are archived; spend limits stay counted.',complaint:'The customer filed a complaint. Evidence is being frozen for investigation.',investigation:'A customer filed a scam report. Follow the agent’s validated checks.',followup:'The agent needs one customer answer before continuing.',review:'The resolution is ready for the human risk analyst.',prevention:'The prevention agent is learning from the reviewed case.',activate:'The safeguard passed replay. The analyst decides whether to enable it.',ready:'The safeguard is active. Test a similar request with a different recipient.',protected:'The similar request was held before debit. The legitimate payment passed.',attention:'This case needs manual attention. Open the saved evidence.'};
  $('demo-narrative').textContent=narrative[phase]||narrative.world;
  document.querySelectorAll('[data-demo-stage]').forEach((n,i)=>{n.classList.toggle('current',i===stage);n.classList.toggle('done',i<stage);if(i===stage)n.setAttribute('aria-current','step');else n.removeAttribute('aria-current')});

  $('population-count').textContent=d.customers.length+' customers';
  const wh=d.warehouse;
  $('warehouse-note').textContent=wh?.latest_snapshot?`BigQuery · ${wh.latest_snapshot.row_count.toLocaleString()} rows · ${wh.table_count} tables`:wh?.enabled?'BigQuery ready · publishes before investigation':'Local data · warehouse off';
  $('warehouse-tables').replaceChildren();
  for(const table of wh?.tables||[])$('warehouse-tables').append(node('li',table.replace('pallet_','').replaceAll('_',' ')+(wh.latest_snapshot?' · '+(wh.latest_snapshot.counts[table]||0)+' rows':'')));
  state.playing=!!demo.running;$('mint-town').classList.toggle('is-running',state.playing);
  $('running-label').textContent=state.playing?'● Running':'Paused';$('play-world').textContent=state.playing?'Ⅱ Pause world':phase==='ready'?'Test protection →':['complaint','investigation','followup','review','prevention','activate','attention'].includes(phase)?'Follow the case →':phase==='protected'?'▶ Run new world':'▶ Run world';
  $('world-time').textContent=w.day+' · '+String(w.hour).padStart(2,'0')+':00';$('map-date').textContent=String(w.hour).padStart(2,'0')+':00';
  $('ledger-health').textContent=d.ledger_balanced?'Ledger balanced':'Ledger needs review';
  $('provider-label').textContent=d.budget.live_enabled?'Gemini · live':'Gemini off';
  $('protected-count').textContent=demo.blocked_payments;$('knowledge-total').textContent=demo.knowledge_count;
  const pending=demo.incidents.filter(i=>i.report_id&&i.report_status!=='resolved').length;
  $('agent-badge').textContent=pending;$('agent-badge').hidden=!pending;
  $('world-note').textContent=demo.calls_remaining===0?'Investigation allowance used. Approved knowledge still protects payments.':demo.running?'The world keeps running while you view the agent.':demo.note==='Ready'?'Start a fresh scene with seeded customer history.':demo.note;
  $('activity').disabled=state.playing;document.querySelectorAll('[data-speed]').forEach(b=>b.disabled=state.playing);
  const latest=phase==='protected'?(demo.incidents.find(i=>i.status==='blocked')||demo.incidents[0]):demo.incidents[0];$('world-alert').hidden=!latest;
  if(latest){const person=d.customers.find(c=>c.id===latest.customer_id)?.name||'A customer';$('world-alert-title').textContent=latest.status==='blocked'?'A similar request was held.':latest.report_id?person+' filed a scam report':latest.title;$('world-alert-copy').textContent=incidentCopy(latest);$('world-report').textContent=latest.status==='blocked'?'View knowledge →':'View agent →'}
  $('world-events').replaceChildren();
  for(const i of demo.incidents.slice(0,3)){
    const row=node('div',undefined,'world-event '+(i.status==='blocked'?'blocked':'incident')),body=node('div');
    row.append(node('span',['blocked','passed'].includes(i.status)?'✓':'!','event-icon'));body.append(node('strong',i.title),node('small',incidentCopy(i)));
    if(i.status!=='passed'){const button=node('button',i.status==='blocked'?'View knowledge →':'Open investigation →','text-button');button.onclick=()=>openIncident(i);body.append(button)}row.append(body);$('world-events').append(row);
  }
  const payments=d.events.filter(e=>['payment','payment_blocked','payment_declined'].includes(e.kind)).slice(0,5);
  for(const e of payments){
    const name=d.customers.find(c=>c.id===e.customer_id)?.name||'Customer';
    const row=node('div',undefined,'world-event '+e.status),body=node('div');row.append(node('span',e.status==='blocked'?'✓':'↗','event-icon'));
    body.append(node('strong',`${name} ${e.status==='blocked'?'was protected':e.status==='declined'?'payment declined':'paid '+money(e.amount_minor)}`),node('small',e.status==='blocked'?'Transfer held before settlement':e.metadata?.rail||'Wallet payment'));row.append(body);$('world-events').append(row);
  }
  drawTown.setAlerts(demo.incidents.filter(i=>i.status==='blocked'||(i.report_id&&i.report_status!=='resolved')).map(i=>({customer_id:i.customer_id,mark:i.status==='blocked'?'✓':'!'})));
  drawTown(d.customers,state.customerId,state.customerId?'fraud':'world');drawTown.setSpeed(state.playing?demo.speed:state.speed);
  drawTown.setRunning(state.playing&&state.view==='world'&&!document.hidden);
  if(w.tick!==lastTick&&lastTick!==-1)drawTown.motion(payments.slice(0,4).map(e=>({customer_id:e.customer_id,merchant:['m1','m2','m3'].includes(e.to_account)?e.to_account:'m4',amount_minor:e.amount_minor,status:e.status})));
  lastTick=w.tick;
}
async function refresh(){state.data=await api('/api/state');renderWorld();schedulePoll()}
function schedulePoll(){clearTimeout(pollTimer);if(document.hidden||(!state.data?.demo.running&&!['complaint','investigation','prevention'].includes(state.data?.demo.phase)))return;pollTimer=setTimeout(async()=>{try{await refresh();const latest=state.data.demo.incidents[0]?.id;if(latest!==lastIncident&&state.view==='resolution')await fraudUI.load();lastIncident=latest}catch(e){error(e.message)}},3000)}
async function cloudStatus(){const c=await api('/api/cloud');state.hosted=!!c.enabled;$('cloud-data-panel').hidden=!c.enabled;if(c.enabled){$('deployment-label').textContent=c.execution==='local'?'Local · Vertex AI':'Cloud simulation';$('cloud-data-status').textContent=`${c.daily_exports}/${c.daily_export_limit} exports today`;const pending=!!sessionStorage.getItem('minttown-export-request');$('cloud-export').textContent=pending?'Check export status':'Export next batch';$('cloud-export').disabled=!c.healthy||(c.daily_exports>=c.daily_export_limit&&!pending)}}
const fraudUI=createFraudUI({$,api,state,setPlaying:()=>{},setBusy,refresh,error,focusCustomer:cid=>{state.customerId=cid;renderWorld()}});
async function showView(view){state.view=['world','resolution','agents'].includes(view)?view:'world';setMenu(false);error('');history.replaceState(null,'',state.view==='world'?location.pathname:state.view==='agents'?'#agents':'#agent');document.title='Pallet Town · '+({world:'Environment',resolution:'Agent activity',agents:'Agents'}[state.view]);document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));$('case-view').hidden=state.view!=='world';$('fraud-view').hidden=state.view!=='resolution';$('agents-view').hidden=state.view!=='agents';renderWorld();if(state.view==='resolution')await fraudUI.load(true)}
async function openIncident(i){try{await showView('resolution');if(i.report_id||state.data.demo.focus_report_id)await fraudUI.open(i.report_id||state.data.demo.focus_report_id);if(i.status==='blocked')$('fraud-memory-panel').open=true}catch(e){error(e.message)}}
$('open-menu').onclick=()=>setMenu(true);$('close-menu').onclick=()=>setMenu(false);$('sidebar-backdrop').onclick=()=>setMenu(false);window.addEventListener('keydown',e=>{if(e.key==='Escape')setMenu(false)});
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>showView(b.dataset.view).catch(e=>error(e.message));
for(const b of document.querySelectorAll('[data-speed]'))b.onclick=()=>{state.speed=Number(b.dataset.speed);$('speed-label').textContent=state.speed+'×';document.querySelectorAll('[data-speed]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)))};
$('activity').oninput=()=>{$('activity-value').textContent=$('activity').value};
$('play-world').onclick=async()=>{if(state.busy)return;setBusy(true);error('');try{const demo=state.data.demo;if(!demo.running&&demo.phase==='ready'){await api('/api/world/prove',{expected_run:demo.run_id});await refresh()}else if(!demo.running&&['complaint','investigation','followup','review','prevention','activate','attention'].includes(demo.phase)){await showView('resolution');if(demo.focus_report_id)await fraudUI.open(demo.focus_report_id)}else{await api(demo.running?'/api/world/stop':'/api/world/start',demo.running?{expected_run:demo.run_id}:{expected_run:demo.run_id,activity:Number($('activity').value),speed:state.speed,fresh:true});await refresh()}}catch(e){error(e.message)}finally{setBusy(false)}};
$('world-report').onclick=()=>openIncident(state.data.demo.incidents[0]);
$('cloud-export').onclick=async()=>{if(state.busy)return;setBusy(true);$('cloud-export').disabled=true;try{const id=sessionStorage.getItem('minttown-export-request')||crypto.randomUUID();sessionStorage.setItem('minttown-export-request',id);const r=await api('/api/cloud/export',{request_id:id});if(['completed','failed'].includes(r.status))sessionStorage.removeItem('minttown-export-request');$('cloud-export-result').textContent=`${r.row_count.toLocaleString()} records · ${r.status}`}catch(e){error(e.message)}finally{setBusy(false);await cloudStatus().catch(e=>error(e.message))}};
document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(pollTimer);drawTown.setRunning(false)}else refresh().catch(e=>error(e.message))});
window.addEventListener('hashchange',()=>showView(!location.hash?'world':location.hash==='#agents'?'agents':'resolution').catch(e=>error(e.message)));
try{await refresh();await cloudStatus();$('loading-state').hidden=true;await showView(!location.hash?'world':location.hash==='#agents'?'agents':'resolution');await document.fonts.ready;renderWorld()}catch(e){$('loading-state').hidden=true;error('Cannot reach the simulation. '+e.message)}
