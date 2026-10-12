import {createTown} from './town.js';
import {createFraudUI} from './fraud-ui.js';
const $=id=>document.getElementById(id),drawTown=createTown($('town-map'));
const state={data:null,view:'world',busy:false,playing:false,speed:1,stepping:false,customerId:null,hosted:false};
const money=n=>'₱'+(n/100).toLocaleString('en-PH',{maximumFractionDigits:0});
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
let pollTimer=null,lastTick=-1,lastIncident=null;
async function api(path,body){
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-MintTown-Token':state.data.csrf_token},body:JSON.stringify(body)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Request could not be completed.');return result;
}
function error(message){$('app-error').textContent=message||'';$('app-error').hidden=!message}
function setBusy(on){state.busy=on;document.querySelectorAll('[data-view],#play-world').forEach(b=>b.disabled=on)}
function setMenu(open){$('mint-town').classList.toggle('parameters-open',open);$('sidebar-backdrop').hidden=!open;$('open-menu').setAttribute('aria-expanded',String(open))}
function incidentCopy(i){return i.status==='blocked'?'Held by approved knowledge':i.status==='budget_limited'?'Investigation allowance reached':i.report_status==='resolved'?'Reviewed · protection active':i.report_status==='awaiting_review'?'Ready for analyst review':i.report_status==='awaiting_customer'?'Waiting for a customer reply':i.report_status==='needs_review'?'Needs manual review':'Agent investigating'}
function renderWorld(){
  const d=state.data,w=d.world,demo=d.demo;
  state.playing=!!demo.running;$('mint-town').classList.toggle('is-running',state.playing);
  $('running-label').textContent=state.playing?'● Running':'Paused';$('play-world').textContent=state.playing?'Ⅱ Pause world':'▶ Run world';
  $('world-time').textContent=w.day+' · '+String(w.hour).padStart(2,'0')+':00';$('map-date').textContent=String(w.hour).padStart(2,'0')+':00';
  $('ledger-health').textContent=d.ledger_balanced?'Ledger balanced':'Ledger needs review';
  $('provider-label').textContent=d.budget.live_enabled?'Gemini · live':'Gemini off';
  $('protected-count').textContent=demo.blocked_payments;$('knowledge-total').textContent=demo.knowledge_count;
  const pending=demo.incidents.filter(i=>i.report_id&&i.report_status!=='resolved').length;
  $('agent-badge').textContent=pending;$('agent-badge').hidden=!pending;
  $('world-note').textContent=demo.calls_remaining===0?'Investigation allowance used. Approved knowledge still protects payments.':demo.running?'The world keeps running while you view the agent.':demo.note==='Ready'?'Run a 24-hour episode. Scams trigger investigations automatically.':demo.note;
  $('activity').disabled=state.playing;document.querySelectorAll('[data-speed]').forEach(b=>b.disabled=state.playing);
  const latest=demo.incidents[0];$('world-alert').hidden=!latest;
  if(latest){$('world-alert-title').textContent=latest.status==='blocked'?'A related scam was blocked.':latest.title;$('world-alert-copy').textContent=incidentCopy(latest);$('world-report').textContent=latest.status==='blocked'?'View knowledge →':'View agent →'}
  $('world-events').replaceChildren();
  for(const i of demo.incidents.slice(0,3)){
    const row=node('div',undefined,'world-event '+(i.status==='blocked'?'blocked':'incident')),body=node('div');
    row.append(node('span',i.status==='blocked'?'✓':'!','event-icon'));body.append(node('strong',i.title),node('small',incidentCopy(i)));
    const button=node('button',i.status==='blocked'?'View knowledge →':'Open investigation →','text-button');button.onclick=()=>openIncident(i);body.append(button);row.append(body);$('world-events').append(row);
  }
  const payments=d.events.filter(e=>['payment','payment_blocked','payment_declined'].includes(e.kind)).slice(0,5);
  for(const e of payments){
    const name=d.customers.find(c=>c.id===e.customer_id)?.name||'Customer';
    const row=node('div',undefined,'world-event '+e.status),body=node('div');row.append(node('span',e.status==='blocked'?'✓':'↗','event-icon'));
    body.append(node('strong',`${name} ${e.status==='blocked'?'was protected':e.status==='declined'?'payment declined':'paid '+money(e.amount_minor)}`),node('small',e.status==='blocked'?'Transfer held before settlement':e.metadata?.rail||'Wallet payment'));row.append(body);$('world-events').append(row);
  }
  drawTown(d.customers,state.customerId,state.customerId?'fraud':'world');drawTown.setSpeed(state.playing?demo.speed:state.speed);
  drawTown.setRunning(state.playing&&state.view==='world'&&!document.hidden);
  if(w.tick!==lastTick&&lastTick!==-1)drawTown.motion(payments.slice(0,4).map(e=>({customer_id:e.customer_id,merchant:['m1','m2','m3'].includes(e.to_account)?e.to_account:'m4',amount_minor:e.amount_minor,status:e.status})));
  lastTick=w.tick;
}
async function refresh(){state.data=await api('/api/state');renderWorld();schedulePoll()}
function schedulePoll(){clearTimeout(pollTimer);if(document.hidden||!state.data?.demo.running)return;pollTimer=setTimeout(async()=>{try{await refresh();const latest=state.data.demo.incidents[0]?.id;if(latest!==lastIncident&&state.view==='resolution')await fraudUI.load();lastIncident=latest}catch(e){error(e.message)}},3000)}
async function cloudStatus(){const c=await api('/api/cloud');state.hosted=!!c.enabled;$('cloud-data-panel').hidden=!c.enabled;if(c.enabled){$('deployment-label').textContent='Cloud simulation';$('cloud-data-status').textContent=`${c.daily_exports}/${c.daily_export_limit} exports today`;const pending=!!sessionStorage.getItem('minttown-export-request');$('cloud-export').textContent=pending?'Check export status':'Export next batch';$('cloud-export').disabled=!c.healthy||(c.daily_exports>=c.daily_export_limit&&!pending)}}
const fraudUI=createFraudUI({$,api,state,setPlaying:()=>{},setBusy,refresh,error,focusCustomer:cid=>{state.customerId=cid;renderWorld()}});
async function showView(view){state.view=view==='world'?'world':'resolution';setMenu(false);error('');history.replaceState(null,'',state.view==='world'?location.pathname:'#agent');document.title='MintTown · '+(state.view==='world'?'World':'Agent');document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));$('case-view').hidden=state.view!=='world';$('fraud-view').hidden=state.view!=='resolution';renderWorld();if(state.view==='resolution')await fraudUI.load(true)}
async function openIncident(i){try{await showView('resolution');if(i.report_id)await fraudUI.open(i.report_id);if(i.status==='blocked')$('fraud-memory-panel').open=true}catch(e){error(e.message)}}
$('open-menu').onclick=()=>setMenu(true);$('close-menu').onclick=()=>setMenu(false);$('sidebar-backdrop').onclick=()=>setMenu(false);window.addEventListener('keydown',e=>{if(e.key==='Escape')setMenu(false)});
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>showView(b.dataset.view).catch(e=>error(e.message));
for(const b of document.querySelectorAll('[data-speed]'))b.onclick=()=>{state.speed=Number(b.dataset.speed);$('speed-label').textContent=state.speed+'×';document.querySelectorAll('[data-speed]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)))};
$('activity').oninput=()=>{$('activity-value').textContent=$('activity').value};
$('play-world').onclick=async()=>{if(state.busy)return;setBusy(true);error('');try{const demo=state.data.demo;await api(demo.running?'/api/world/stop':'/api/world/start',demo.running?{expected_run:demo.run_id}:{expected_run:demo.run_id,activity:Number($('activity').value),speed:state.speed});await refresh()}catch(e){error(e.message)}finally{setBusy(false)}};
$('world-report').onclick=()=>openIncident(state.data.demo.incidents[0]);
$('cloud-export').onclick=async()=>{if(state.busy)return;setBusy(true);$('cloud-export').disabled=true;try{const id=sessionStorage.getItem('minttown-export-request')||crypto.randomUUID();sessionStorage.setItem('minttown-export-request',id);const r=await api('/api/cloud/export',{request_id:id});if(['completed','failed'].includes(r.status))sessionStorage.removeItem('minttown-export-request');$('cloud-export-result').textContent=`${r.row_count.toLocaleString()} records · ${r.status}`}catch(e){error(e.message)}finally{setBusy(false);await cloudStatus().catch(e=>error(e.message))}};
document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(pollTimer);drawTown.setRunning(false)}else refresh().catch(e=>error(e.message))});
window.addEventListener('hashchange',()=>showView(!location.hash?'world':'resolution').catch(e=>error(e.message)));
try{await refresh();await cloudStatus();$('loading-state').hidden=true;await showView(!location.hash?'world':'resolution');await document.fonts.ready;renderWorld()}catch(e){$('loading-state').hidden=true;error('Cannot reach the simulation. '+e.message)}
