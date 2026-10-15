import {drawResident,appearance,alarmMotion,protectionMotion} from './resident-sprites.js';
import {WIDTH,HEIGHT,PLACES,NODES,EDGES,paintTown,paintWater} from './town-art.js';

// Route residents along the street graph, including the path around the fountain.
export function streetRoute(from,to){
  const nearest=p=>NODES.reduce((best,n,i)=>Math.hypot(n.x-p.x,n.y-p.y)<Math.hypot(NODES[best].x-p.x,NODES[best].y-p.y)?i:best,0);
  const start=nearest(from),end=nearest(to),dist=NODES.map(()=>Infinity),prev=NODES.map(()=>null),open=new Set(NODES.map((_,i)=>i));dist[start]=0;
  while(open.size){
    const node=[...open].reduce((a,b)=>dist[a]<dist[b]?a:b);open.delete(node);if(node===end)break;
    for(const [a,b] of EDGES){const next=a===node?b:b===node?a:null;if(next===null||!open.has(next))continue;
      const score=dist[node]+Math.hypot(NODES[node].x-NODES[next].x,NODES[node].y-NODES[next].y);
      if(score<dist[next]){dist[next]=score;prev[next]=node}
    }
  }
  const path=[];for(let i=end;i!==null;i=prev[i])path.unshift({...NODES[i]});
  if(Math.hypot(path.at(-1).x-to.x,path.at(-1).y-to.y)>1)path.push({...to});
  return path.filter((p,i)=>i||Math.hypot(p.x-from.x,p.y-from.y)>2);
}

export function createTown(canvas){
  canvas.width=WIDTH;canvas.height=HEIGHT;
  const ctx=canvas.getContext('2d'),actors=new Map(),seen=new Set(),alarmStarts=new Map(),safetyStarts=new Map(),alertIds=new Map();
  const media=matchMedia('(prefers-reduced-motion: reduce)');let reduced=media.matches;
  let people=[],population=[],recent=[],selected=null,hovered=null,alerts=new Map(),running=false,speed=1,raf=0,last=0,background=null,fx=[],expiryTimer=null;
  let hour=9,centered=null,visible=true;
  const animating=()=>visible&&!reduced&&(running||[...alarmStarts.values()].some(t=>performance.now()-t<8000)||[...safetyStarts.values()].some(t=>performance.now()-t<6500)||fx.some(f=>performance.now()-f.start<2200));
  function syncAnimation(){if(animating()){if(!raf){last=0;raf=requestAnimationFrame(frame)}}else{cancelAnimationFrame(raf);raf=0;last=0}}
  function scenery(){background=document.createElement('canvas');background.width=WIDTH;background.height=HEIGHT;paintTown(background.getContext('2d'))}
  function capsule(text,x,y,color='#395d50',fill='#fff9e7'){
    ctx.font='700 12px "DM Sans",sans-serif';const width=ctx.measureText(text).width+20;
    x=Math.max(width/2+4,Math.min(WIDTH-width/2-4,x));y=Math.max(25,y);
    ctx.fillStyle='#2e4e3a22';ctx.beginPath();ctx.roundRect(x-width/2+2,y-17,width,24,6);ctx.fill();
    ctx.fillStyle=fill;ctx.beginPath();ctx.roundRect(x-width/2,y-20,width,24,6);ctx.fill();
    ctx.fillStyle=color;ctx.textAlign='center';ctx.fillText(text,x,y-4);
  }
  function paint(time=performance.now()){
    if(!background)scenery();ctx.clearRect(0,0,WIDTH,HEIGHT);ctx.imageSmoothingEnabled=false;ctx.drawImage(background,0,0);paintWater(ctx,time,running&&!reduced);
    for(const p of [...people].sort((a,b)=>actors.get(a.id).y-actors.get(b.id).y)){
      const a=actors.get(p.id);if(!a)continue;
      if(selected===p.id||hovered===p.id){ctx.strokeStyle=selected===p.id?'#f8f4c4':'#e9f2c49c';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(a.x,a.y+1,15,6,0,0,Math.PI*2);ctx.stroke()}
      const moving=running&&a.path.length&&!reduced,frame=moving?Math.floor(time/140+Number(p.id.slice(1)))%4:0;
      const alarm=alerts.get(p.id)==='!',motion=alarmMotion(time-(alarmStarts.get(p.id)??-Infinity),reduced);
      if(alarm){ctx.fillStyle='#5d694b55';ctx.beginPath();ctx.ellipse(a.x,a.y+1,11,4,0,0,Math.PI*2);ctx.fill()}
      drawResident(ctx,a.x,a.y-25-(alarm?motion.jump:0),p.id,alarm?'down':a.direction,frame,!!a.payment&&a.until>time,alarm);
    }
    // Simulated afternoon light; time is the world's clock, not the viewer's clock.
    if(hour>=17||hour<7){ctx.fillStyle=hour>=19||hour<6?'#27395b42':'#d9a57818';ctx.fillRect(0,0,WIDTH,HEIGHT)}
    for(const p of people){
      const a=actors.get(p.id),mark=alerts.get(p.id);
      if(mark){
        const motion=alarmMotion(time-(alarmStarts.get(p.id)??-Infinity),reduced),safe=protectionMotion(time-(safetyStarts.get(p.id)??-Infinity),reduced),y=a.y-58-(mark==='!'?motion.jump:safe.lift);
        ctx.fillStyle=mark==='!'?'#b95135':'#397b5b';ctx.strokeStyle='#fff5d9';ctx.lineWidth=2.5;
        ctx.beginPath();if(mark==='!')ctx.arc(a.x,y,12,0,Math.PI*2);else{ctx.moveTo(a.x-13,y-11);ctx.lineTo(a.x+13,y-11);ctx.lineTo(a.x+11,y+6);ctx.lineTo(a.x,y+16);ctx.lineTo(a.x-11,y+6);ctx.closePath()}ctx.fill();ctx.stroke();
        ctx.fillStyle='#fff9e8';ctx.font='700 19px "DM Sans",sans-serif';ctx.textAlign='center';ctx.fillText(mark,a.x,y+7);
        if(mark==='!')capsule(motion.active?'HELP! My money!':'Scam report filed',a.x,a.y-91-motion.jump,'#8c3c29','#fff0cf');
        else{capsule(safe.active?'SAFE! Scam stopped':'Payment protected',a.x,a.y-94-safe.lift,'#245c40','#dff5d4');if(safe.active){ctx.strokeStyle='#86c58c';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(a.x,a.y+2,18+safe.lift,6+safe.lift/2,0,0,Math.PI*2);ctx.stroke()}}
      }else if(a.payment&&a.until>time)capsule(a.payment,a.x,a.y-49);
    }
    fx=fx.filter(f=>time-f.start<2200);
    if(!reduced)for(const f of fx){
      const t=(time-f.start)/2200,alpha=Math.max(0,1-t);ctx.globalAlpha=alpha;
      if(f.to){ctx.strokeStyle=f.held?'#bd7453':'#d7edaf';ctx.lineWidth=2;ctx.setLineDash([5,6]);ctx.beginPath();ctx.moveTo(f.x,f.y-12);ctx.quadraticCurveTo((f.x+f.to.x)/2,Math.min(f.y,f.to.y)-80,f.to.x,f.to.y-12);ctx.stroke();ctx.setLineDash([])}
      ctx.strokeStyle=f.held?'#ce855c':'#fff0b3';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(f.x,f.y,12+t*25,5+t*11,0,0,Math.PI*2);ctx.stroke();ctx.globalAlpha=1;
    }
    if(hovered){const p=people.find(p=>p.id===hovered),a=actors.get(hovered);if(p&&a)capsule(p.name,a.x,a.y-(alerts.has(p.id)?80:51))}
  }
  function frame(time){
    raf=0;if(!animating()){paint(time);return}
    const dt=Math.min((time-(last||time))/1000,.045);last=time;
    for(const [i,p] of people.entries()){
      if(!running||alerts.get(p.id)==='!')continue;
      const a=actors.get(p.id);if(!a.path.length&&time>a.until){
        const target=a.home||NODES[(a.wander++*7+i*3)%NODES.length];a.path=streetRoute(a,target);a.until=time+1800+i*53;
      }
      const target=a.path[0];if(!target)continue;
      const dx=target.x-a.x,dy=target.y-a.y,d=Math.hypot(dx,dy),step=dt*(43+i%6*3)*Math.min(speed,2);
      a.direction=Math.abs(dx)>Math.abs(dy)?(dx<0?'left':'right'):(dy<0?'up':'down');
      if(d<=step){a.x=target.x;a.y=target.y;a.path.shift();if(!a.path.length)a.until=time+1800+i*61}
      else{a.x+=dx/d*step;a.y+=dy/d*step}
    }
    paint(time);if(animating())raf=requestAnimationFrame(frame);
  }
  function draw(list,focus){
    population=list.slice(0,100);selected=focus;
    const ids=[...new Set([...alerts.keys(),focus,...recent,...population.filter(p=>appearance(p.id).role!=='resident').map(p=>p.id),...population.map(p=>p.id)].filter(Boolean))].slice(0,28);
    people=ids.map(id=>population.find(p=>p.id===id)).filter(Boolean);
    for(const [i,p] of people.entries())if(!actors.has(p.id)){
      const role=appearance(p.id).role,place=role==='merchant'?PLACES[100-Number(p.id.slice(1))]:role==='cashier'?PLACES[4]:null;
      const edge=EDGES[(i*7)%EDGES.length],a=NODES[edge[0]],b=NODES[edge[1]],fraction=.2+(i%5)*.14;
      const spot=place?place.entry:{x:a.x+(b.x-a.x)*fraction,y:a.y+(b.y-a.y)*fraction};
      actors.set(p.id,{x:spot.x,y:spot.y,home:place?.entry,direction:'down',path:[],until:performance.now()+i*123,payment:null,wander:1});
    }
    const viewport=canvas.parentElement;
    if(selected!==centered&&selected&&viewport?.clientWidth){
      const a=actors.get(selected);
      if(a)viewport.scrollTo({left:Math.max(0,a.x/WIDTH*canvas.clientWidth-viewport.clientWidth/2),behavior:reduced?'instant':'smooth'});
      centered=selected;
    }
    paint();
  }
  draw.motion=(events,initial=false)=>{
    const incoming=events.filter(e=>!e.id||!seen.has(e.id));for(const e of incoming)if(e.id)seen.add(e.id);
    while(seen.size>180)seen.delete(seen.values().next().value);
    if(initial||!incoming.length)return;
    recent=[...new Set([...incoming.flatMap(e=>[e.customer_id,e.receiver_customer_id]),...recent].filter(Boolean))].slice(0,12);draw(population,selected);
    for(const e of incoming){
      const a=actors.get(e.customer_id);if(!a)continue;const other=actors.get(e.receiver_customer_id);
      const place=e.transaction_type?.startsWith('CASH_')?PLACES[4]:PLACES.find(p=>p.id===e.merchant)||PLACES[3];
      const target=e.transaction_type==='P2P_TRANSFER'&&other?{x:other.x,y:other.y}:place.entry;
      const held=e.status==='blocked'||e.status==='declined';a.path=held?[]:streetRoute(a,target);
      const label={P2P_TRANSFER:'Sent',MERCHANT_QR:'QR',CASH_IN_AGENT:'Cash in',CASH_OUT_AGENT:'Cash out'}[e.transaction_type]||'Paid';
      a.payment=held?(e.status==='blocked'?'Payment held':'Declined'):`${label} ₱${Math.round(e.amount_minor/100).toLocaleString('en-PH')}`;a.until=performance.now()+3000;
      fx.push({x:a.x,y:a.y,to:e.transaction_type==='P2P_TRANSFER'&&other?{x:other.x,y:other.y}:null,held,start:performance.now()});
      if(reduced&&!held){a.x=target.x;a.y=target.y;a.path=[]}
    }
    fx=fx.slice(-12);clearTimeout(expiryTimer);expiryTimer=setTimeout(()=>paint(),3100);paint();syncAnimation();
  };
  draw.setRunning=on=>{running=on;syncAnimation();paint()};
  draw.setVisible=on=>{visible=on;syncAnimation()};
  draw.setSpeed=value=>{speed=value};draw.setHour=value=>{hour=value;paint()};
  draw.setAlerts=value=>{const next=new Map(value.map(v=>[v.customer_id,v.mark]));for(const v of value){const id=v.customer_id;if(alertIds.get(id)!==(v.id||v.mark)){if(v.mark==='!')alarmStarts.set(id,performance.now());else safetyStarts.set(id,performance.now());alertIds.set(id,v.id||v.mark)}}for(const id of alarmStarts.keys())if(next.get(id)!=='!')alarmStarts.delete(id);for(const id of safetyStarts.keys())if(next.get(id)!=='✓')safetyStarts.delete(id);for(const id of alertIds.keys())if(!next.has(id))alertIds.delete(id);alerts=next;draw(population,selected);syncAnimation()};
  draw.alertBounds=()=>{const id=[...alerts].find(([,mark])=>mark==='!')?.[0],a=actors.get(id);return a?{x:Math.max(0,a.x-102),y:Math.max(0,a.y-142),width:204,height:155}:null};
  draw.reset=()=>{clearTimeout(expiryTimer);cancelAnimationFrame(raf);raf=0;running=false;actors.clear();alerts.clear();alarmStarts.clear();safetyStarts.clear();alertIds.clear();seen.clear();recent=[];people=[];selected=hovered=centered=null;fx=[];last=0;paint()};
  const personAt=event=>{
    const bounds=canvas.getBoundingClientRect(),x=(event.clientX-bounds.left)/bounds.width*WIDTH,y=(event.clientY-bounds.top)/bounds.height*HEIGHT;
    return [...people].reverse().find(p=>{const a=actors.get(p.id);return Math.abs(x-a.x)<17&&y>a.y-40&&y<a.y+6})?.id||null;
  };
  canvas.addEventListener('pointermove',e=>{const id=personAt(e);if(id!==hovered){hovered=id;canvas.style.cursor=id?'pointer':'default';paint()}});
  canvas.addEventListener('pointerleave',()=>{hovered=null;paint()});
  canvas.addEventListener('click',e=>{const id=personAt(e);if(id)canvas.dispatchEvent(new CustomEvent('resident-select',{detail:id}))});
  media.addEventListener('change',e=>{reduced=e.matches;syncAnimation();paint()});
  document.fonts.ready.then(()=>{background=null;paint()});
  return draw;
}
