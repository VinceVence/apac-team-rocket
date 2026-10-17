import {WIDTH,HEIGHT,paintTown,paintWater} from './town-art.js';
import {drawResident} from './resident-sprites.js';

// Decorative preview only: no API, financial events, agent jobs or shared state.
export function previewPhase(seconds){
  const t=((seconds%24)+24)%24;
  return t<8?{id:'day',text:'A normal day in Mint Town'}:t<13?{id:'report',text:'One resident reports a scam'}:t<18?{id:'review',text:'Evidence becomes a case for review'}:{id:'protect',text:'A related request is held before payment'};
}
export function createLandingWorld(canvas,section,label){
  canvas.width=WIDTH;canvas.height=HEIGHT;
  const ctx=canvas.getContext('2d'),background=document.createElement('canvas');
  background.width=WIDTH;background.height=HEIGHT;paintTown(background.getContext('2d'));
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  let raf=0,last=0,elapsed=0,previousPhase='',destroyed=false;
  const visible=()=>!destroyed&&!section.hidden&&!document.hidden;
  const bubble=(text,x,y,color='#2e694f',fill='#fff8de')=>{
    ctx.font='600 13px "DM Sans",sans-serif';ctx.textAlign='center';const w=ctx.measureText(text).width+22;
    ctx.fillStyle='#294c3428';ctx.beginPath();ctx.roundRect(x-w/2+2,y-21+2,w,29,8);ctx.fill();
    ctx.fillStyle=fill;ctx.beginPath();ctx.roundRect(x-w/2,y-21,w,29,8);ctx.fill();ctx.fillStyle=color;ctx.fillText(text,x,y-2);
  };
  function paint(){
    const phase=previewPhase(motion.matches?0:elapsed),t=elapsed;
    if(phase.id!==previousPhase){label.textContent=phase.text;section.dataset.preview=phase.id;previousPhase=phase.id}
    ctx.imageSmoothingEnabled=false;ctx.drawImage(background,0,0);paintWater(ctx,t*1000,!motion.matches);
    const actors=Array.from({length:18},(_,i)=>{
      const d=(i*91+t*17)%1200;
      const p=d<375?{x:315+d,y:260,dir:'right'}:d<600?{x:690,y:260+d-375,dir:'down'}:d<975?{x:690-(d-600),y:485,dir:'left'}:{x:315,y:485-(d-975),dir:'up'};
      return {id:'C'+String(i+3).padStart(3,'0'),...p};
    });
    actors.push({id:'C001',x:600,y:485,dir:'down'},{id:'C002',x:315,y:310,dir:'down'});
    for(const a of actors.sort((a,b)=>a.y-b.y)){
      const alarm=a.id==='C001'&&phase.id==='report';
      const jump=alarm&&!motion.matches?Math.max(0,Math.sin(t*10))*12:0;
      drawResident(ctx,a.x,a.y-25-jump,a.id,a.dir,Math.floor(t*7+Number(a.id.slice(1)))%4,false,alarm);
    }
    if(phase.id==='day'){bubble('Coffee · ₱65',150,246);if(t%8>2)bubble('Groceries · ₱120',480,462)}
    if(phase.id==='report'){
      const y=420-Math.max(0,Math.sin(t*10))*10;
      ctx.fillStyle='#b95135';ctx.beginPath();ctx.arc(600,y,15,0,Math.PI*2);ctx.fill();
      ctx.fillStyle='#fff7db';ctx.font='700 22px "DM Sans",sans-serif';ctx.textAlign='center';ctx.fillText('!',600,y+8);
      bubble('Resident 1 needs help',600,y-32,'#8d3e2f','#fff0da');
    }
    if(phase.id==='review')bubble('Report → evidence → review',480,227);
    if(phase.id==='protect'){
      ctx.fillStyle='#2f7655';ctx.strokeStyle='#eff9dc';ctx.lineWidth=2;
      ctx.beginPath();ctx.moveTo(297,244);ctx.lineTo(333,244);ctx.lineTo(330,268);ctx.lineTo(315,280);ctx.lineTo(300,268);ctx.closePath();ctx.fill();ctx.stroke();
      ctx.fillStyle='#fff9df';ctx.font='700 24px "DM Sans",sans-serif';ctx.textAlign='center';ctx.fillText('✓',315,269);
      bubble('Payment protected',315,224,'#245f42','#e4f5d3');bubble('Coffee · paid',150,246);
    }
  }
  function frame(now){raf=0;if(!visible()||motion.matches)return;const dt=last?Math.min((now-last)/1000,.1):0;last=now;elapsed+=dt;paint();raf=requestAnimationFrame(frame)}
  function sync(){cancelAnimationFrame(raf);raf=0;last=0;if(!visible())return;paint();if(!motion.matches)raf=requestAnimationFrame(frame)}
  const observer=new MutationObserver(sync);observer.observe(section,{attributes:true,attributeFilter:['hidden']});
  document.addEventListener('visibilitychange',sync);motion.addEventListener('change',sync);
  document.fonts?.ready.then(()=>{if(!destroyed){paintTown(background.getContext('2d'));sync()}});
  sync();
  return {destroy(){destroyed=true;cancelAnimationFrame(raf);observer.disconnect();document.removeEventListener('visibilitychange',sync);motion.removeEventListener('change',sync)}};
}
