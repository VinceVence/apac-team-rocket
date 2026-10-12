import {createTown} from './town.js';
import {createFraudUI} from './fraud-ui.js';

const $=id=>document.getElementById(id);
const drawTown=createTown($('town-map'));
const money=n=>'₱'+(n/100).toLocaleString('en-PH',{maximumFractionDigits:2});
const state={data:null,view:'world',busy:false,playing:false,speed:1,timer:null,stepping:false,customerId:null,hosted:false};
const labels={world:'town',resolution:'scam-desk'};

async function api(path,body){
  const options=body?{method:'POST',headers:{'Content-Type':'application/json','X-MintTown-Token':state.data.csrf_token},body:JSON.stringify(body)}:{};
  const response=await fetch(path,options),result=await response.json();
  if(!response.ok)throw Error(result.error||'The local service could not complete the request.');
  return result;
}
function error(message){$('app-error').textContent=message||'';$('app-error').hidden=!message}
function setBusy(on){
  state.busy=on;
  document.querySelectorAll('[data-view],#world-report,#step-world,#play-world').forEach(node=>node.disabled=on);
}
function setMenu(open){
  $('mint-town').classList.toggle('parameters-open',open);$('sidebar-backdrop').hidden=!open;
  $('open-menu').setAttribute('aria-expanded',String(open));if(open)$('close-menu').focus();
}
function renderWorld(){
  const w=state.data.world;
  $('world-time').textContent=w.day+' · '+String(w.hour).padStart(2,'0')+':00';
  $('map-date').textContent=$('world-time').textContent;
  $('ledger-health').textContent=state.data.ledger_balanced?'Ledger balanced':'Ledger needs review';
  $('provider-label').textContent=state.data.budget.live_enabled?'Offline investigation tools':'Gemini off · $0';
  $('world-events').replaceChildren();
  for(const event of state.data.events.filter(e=>['payment','payment_blocked','payment_declined'].includes(e.kind)).slice(0,5)){
    const row=document.createElement('div'),body=document.createElement('div'),name=document.createElement('strong'),copy=document.createElement('small'),amount=document.createElement('span');
    row.className='world-event '+event.status;name.textContent=state.data.customers.find(c=>c.id===event.customer_id)?.name||'Customer';
    copy.textContent=event.status+' · '+event.occurred_at;amount.textContent=money(event.amount_minor);
    body.append(name,copy);row.append(body,amount);$('world-events').append(row);
  }
  drawTown(state.data.customers,state.customerId,state.customerId?'fraud':'world');
}
async function refresh(){state.data=await api('/api/state');renderWorld()}
async function cloudStatus(){
  const cloud=await api('/api/cloud');$('cloud-data-panel').hidden=!cloud.enabled;
  if(cloud.enabled){
    state.hosted=true;
    $('deployment-label').textContent='Cloud demo';
    $('cloud-data-status').textContent=`${cloud.daily_exports}/${cloud.daily_export_limit} batches today · ${cloud.pending_events.toLocaleString()} events awaiting export`;
    const pending=!!sessionStorage.getItem('minttown-export-request');
    $('cloud-export').textContent=pending?'Check export status':'Export next batch';
    $('cloud-export').disabled=!cloud.healthy||(cloud.daily_exports>=cloud.daily_export_limit&&!pending);
  }
}
function setPlaying(on){
  on=on&&!document.hidden&&state.view==='world';state.playing=on;clearTimeout(state.timer);state.timer=null;
  drawTown.setRunning(on);$('mint-town').classList.toggle('is-running',on);
  $('play-world').textContent=on?'Pause world':'Run world';$('running-label').textContent=on?'Running':'Paused';
  if(on)scheduleStep();
}
function scheduleStep(){clearTimeout(state.timer);if(state.playing)state.timer=setTimeout(stepWorld,Math.max(1100,3000/state.speed))}
async function stepWorld(){
  if(state.stepping||state.busy)return;state.stepping=true;error('');
  try{
    const result=await api('/api/world/step',{expected_tick:state.data.world.tick,activity:Number($('activity').value),scenario:'none'});
    await refresh();drawTown.motion(result.motions);
  }catch(e){error(e.message);setPlaying(false)}
  finally{state.stepping=false;if(state.playing)scheduleStep()}
}
const fraudUI=createFraudUI({$,api,state,setPlaying,setBusy,refresh,error,focusCustomer:cid=>{state.customerId=cid;renderWorld()}});
async function showView(view){
  state.view=view in labels?view:'resolution';setPlaying(false);error('');setMenu(false);
  $('view-title').textContent=labels[state.view];document.title='MintTown · '+labels[state.view];
  history.replaceState(null,'',state.view==='world'?location.pathname:'#scam-resolution');
  document.querySelectorAll('[data-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.view===state.view)));
  $('case-view').hidden=state.view!=='world';$('fraud-view').hidden=state.view!=='resolution';
  $('town-settings').hidden=state.view!=='world';$('world-controls').hidden=state.view!=='world';$('world-time').hidden=state.view!=='world';
  document.querySelector('.lab-content').scrollTop=0;document.scrollingElement.scrollTop=0;
  try{if(state.view==='resolution')await fraudUI.load();else renderWorld()}catch(e){error(e.message)}
}
$('open-menu').onclick=()=>setMenu(true);$('close-menu').onclick=()=>{setMenu(false);$('open-menu').focus()};$('sidebar-backdrop').onclick=()=>setMenu(false);
window.addEventListener('keydown',e=>{if(e.key==='Escape')setMenu(false)});
document.addEventListener('visibilitychange',()=>{if(document.hidden)setPlaying(false)});
for(const button of document.querySelectorAll('[data-view]'))button.onclick=()=>showView(button.dataset.view);
for(const button of document.querySelectorAll('[data-speed]'))button.onclick=()=>{
  state.speed=Number(button.dataset.speed);drawTown.setSpeed(state.speed);$('speed-label').textContent=state.speed+'×';
  document.querySelectorAll('[data-speed]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));if(state.playing)scheduleStep();
};
$('activity').oninput=()=>{$('activity-value').textContent=$('activity').value};
$('play-world').onclick=()=>{if(!state.busy&&!state.stepping)setPlaying(!state.playing)};
$('step-world').onclick=()=>{setPlaying(false);stepWorld()};
$('world-report').onclick=async()=>{if(state.busy||state.stepping)return;await showView('resolution');await fraudUI.demo('first')};
$('cloud-export').onclick=async()=>{
  if(state.busy||state.stepping)return;setPlaying(false);setBusy(true);$('cloud-export').disabled=true;error('');
  $('cloud-export-result').textContent='Saving a bounded batch…';
  try{
    const requestId=sessionStorage.getItem('minttown-export-request')||crypto.randomUUID();
    sessionStorage.setItem('minttown-export-request',requestId);
    const result=await api('/api/cloud/export',{request_id:requestId});
    if(['completed','failed'].includes(result.status))sessionStorage.removeItem('minttown-export-request');
    $('cloud-export-result').textContent=result.row_count?`${result.row_count.toLocaleString()} records · ${result.status} · ${result.remaining_events.toLocaleString()} events remaining`:'All events exported. No new load job needed.';
  }
  catch(e){error(e.message);$('cloud-export-result').textContent='Export could not be confirmed.'}
  finally{setBusy(false);await cloudStatus().catch(e=>error(e.message))}
};
window.addEventListener('hashchange',()=>showView(!location.hash||location.hash==='#live-world'?'world':'resolution'));
try{
  await refresh();$('loading-state').hidden=true;
  await cloudStatus();
  await showView(!location.hash||location.hash==='#live-world'?'world':'resolution');
  await document.fonts.ready;renderWorld();
}catch(e){$('loading-state').hidden=true;error('Cannot reach MintTown. Start the local server and refresh. '+e.message)}
