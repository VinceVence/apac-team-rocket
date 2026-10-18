import {agentIcon} from './agent-ui.js';

export const TOUR_KEY='minttown-quick-tour-v1';
export function hasSeenTour(storage=()=>globalThis.localStorage){try{return storage()?.getItem(TOUR_KEY)==='seen'}catch{return false}}
export const TOUR_STEPS=[
  {title:'Payments become evidence',part:'Environment',nav:'World',target:'[data-view="world"]',copy:'A resident reports a scam. That report starts the case.'},
  {title:'Follow each decision',part:'Agent activity',nav:'Activity',target:'[data-view="resolution"]',copy:'See the tools, their findings and the resolution sent to the analyst.'},
  {title:'Two agents. One learning loop.',part:'Agents',nav:'Agents',target:'[data-view="agents"]',copy:'Resolution investigates. Prevention uses approved lessons to check later payments.'},
  {title:'Your controls',part:'Sidebar settings',nav:'Controls',target:'#open-menu',copy:'Keep speed, restart and demo approval in the sidebar.'},
  {title:'One case, step by step',part:'Ready',nav:'Demo',target:'#run-demo',copy:'Payments. Report. Investigation. Review. A safer next payment.'}
];

// Reading, skipping and replaying the introduction never dispatch demo actions.
export function createTourFlow({storage=()=>globalThis.localStorage,canOpen=()=>true,render,onClose,onStart}){
  let active=false,index=0;
  const markSeen=()=>{try{storage()?.setItem(TOUR_KEY,'seen')}catch{}};
  function open(automatic=false){
    if(active||!canOpen())return false;
    if(automatic&&hasSeenTour(storage))return false;
    active=true;index=0;render(index);return true;
  }
  function close(){if(!active)return;active=false;markSeen();onClose(false)}
  function next(){
    if(!active)return;
    if(index<TOUR_STEPS.length-1){index++;render(index);return}
    if(!canOpen())return;
    active=false;markSeen();onClose(true);onStart();
  }
  return {open,close,next,back(){if(active&&index>0){index--;render(index)}},goTo(value){if(active&&Number.isInteger(value)&&value>=0&&value<TOUR_STEPS.length){index=value;render(index)}},get active(){return active}};
}

export function createQuickTour({startDemo,canOpen,onDismiss=()=>{}}){
  const dialog=document.createElement('dialog');dialog.id='quick-tour';
  dialog.setAttribute('aria-labelledby','tour-title');dialog.setAttribute('aria-describedby','tour-copy');
  dialog.innerHTML='<header class="tour-header"><span><img src="/mark.svg" width="28" height="28" alt="">Mint Town <small>Quick tour</small></span><button class="tour-close icon-button" type="button" aria-label="Skip tour" title="Skip tour">×</button></header><div class="tour-content"><nav class="tour-map" aria-label="Tutorial sections"></nav><div class="tour-art" aria-hidden="true"></div><p class="tour-part"></p><h2 id="tour-title"></h2><p id="tour-copy"></p></div><footer class="tour-footer"><span class="tour-count" aria-live="polite"></span><button class="tour-back text-button" type="button">Back</button><button class="tour-next primary-button" type="button" autofocus>Next</button></footer>';
  document.body.append(dialog);
  const $=selector=>dialog.querySelector(selector),launcher=document.getElementById('open-tour');
  let priorFocus=null,highlight=null;
  const clearHighlight=()=>{highlight?.classList.remove('tour-target');highlight=null};
  const icon=(role,label)=>{const item=document.createElement('div');item.append(agentIcon(role));const name=document.createElement('span');name.textContent=label;item.append(name);return item};
  const flow=createTourFlow({canOpen,onStart:startDemo,onClose:starting=>{
    onDismiss(starting);
    clearHighlight();document.body.classList.remove('tour-open');dialog.close();
    if(!starting){const focus=priorFocus?.isConnected&&!priorFocus.disabled&&priorFocus.tabIndex>=0?priorFocus:launcher;focus?.focus({preventScroll:true})}
  },render:index=>{
    const step=TOUR_STEPS[index];clearHighlight();highlight=document.querySelector(step.target);highlight?.classList.add('tour-target');
    $('.tour-part').textContent=step.part;$('#tour-title').textContent=step.title;$('#tour-copy').textContent=step.copy;
    $('.tour-count').textContent=`${index+1} of ${TOUR_STEPS.length}`;
    $('.tour-back').disabled=index===0;$('.tour-next').textContent=index===TOUR_STEPS.length-1?'Start demo':'Next';
    [...dialog.querySelectorAll('.tour-map button')].forEach((tab,i)=>{tab.classList.toggle('current',i===index);if(i===index)tab.setAttribute('aria-current','step');else tab.removeAttribute('aria-current')});
    const art=$('.tour-art');art.replaceChildren();art.dataset.step=String(index);
    if(index===0){const payment=document.createElement('div'),symbol=document.createElement('span'),label=document.createElement('span');symbol.className='tour-currency';symbol.textContent='₱';label.textContent='Payment';payment.append(symbol,label);art.append(icon('human','Resident'),payment,icon('resolution','Report'))}
    else if(index===1)art.append(icon('resolution','Investigate'),icon('human','Review'),icon('prevention','Protect'));
    else if(index===2)art.append(icon('resolution','Resolution agent'),icon('prevention','Prevention agent'));
    else if(index===3){for(const [label,value] of [['World','Speed · restart'],['Fraud Analyst','Demo approval']]){const row=document.createElement('div');const name=document.createElement('strong');name.textContent=label;const detail=document.createElement('span');detail.textContent=value;row.append(name,detail);art.append(row)}}
    else art.append(icon('human','Report'),icon('resolution','Investigate'),icon('prevention','Protect'));
    if(!dialog.open){priorFocus=document.activeElement;document.body.classList.add('tour-open');dialog.showModal()}
    $('.tour-content').scrollTop=0;$('.tour-next').focus({preventScroll:true});
  }});
  for(const [i,step] of TOUR_STEPS.entries()){const button=document.createElement('button');button.type='button';button.textContent=step.nav;button.setAttribute('aria-label','Show '+step.part);button.onclick=()=>flow.goTo(i);$('.tour-map').append(button)}
  $('.tour-next').onclick=()=>flow.next();$('.tour-back').onclick=()=>flow.back();$('.tour-close').onclick=()=>flow.close();
  dialog.addEventListener('cancel',event=>{event.preventDefault();flow.close()});
  launcher.onclick=()=>flow.open();
  return {maybeOpen:()=>flow.open(true),open:()=>flow.open(),close:()=>flow.close()};
}
