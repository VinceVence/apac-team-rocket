// Offline renderer contracts; no browser, model, cloud, or package install required.
import assert from 'node:assert/strict';
import {streetRoute,createTown} from './dist/town.js';
import {NODES,PLACES,WIDTH,HEIGHT} from './dist/town-art.js';
for(const from of NODES)for(const to of NODES){
  const path=[from,...streetRoute(from,to)];assert.deepEqual(path.at(-1),to);
  for(let i=1;i<path.length;i++){
    const a=path[i-1],b=path[i];assert(a.x===b.x||a.y===b.y,'Street route cuts diagonally');
    assert(b.x>=0&&b.x<=WIDTH&&b.y>=0&&b.y<=HEIGHT);
    for(let t=0;t<=1;t+=.05){const x=a.x+(b.x-a.x)*t,y=a.y+(b.y-a.y)*t;
      assert(!PLACES.some(p=>x>p.x-p.w/2-12&&x<p.x+p.w/2+12&&y>p.y&&y<p.y+116),'Route crosses a building');
      assert(Math.hypot(x-480,(y-296)*1.7)>38,'Route crosses fountain');
    }
  }
}
let frames=new Map(),next=0,mediaChange;
const ctx=new Proxy({measureText:text=>({width:text.length*7})},{get:(o,k)=>o[k]||(()=>{})});
globalThis.requestAnimationFrame=fn=>{frames.set(++next,fn);return next};
globalThis.cancelAnimationFrame=id=>frames.delete(id);
globalThis.matchMedia=()=>({matches:false,addEventListener:(_,fn)=>{mediaChange=fn}});
globalThis.document={createElement:()=>({getContext:()=>ctx}),fonts:{ready:Promise.resolve()}};
globalThis.CustomEvent=class{constructor(type,options){this.type=type;this.detail=options.detail}};
const handlers={},events=[],canvas={style:{},getContext:()=>ctx,addEventListener:(k,v)=>{handlers[k]=v},dispatchEvent:e=>events.push(e),getBoundingClientRect:()=>({left:0,top:0,width:WIDTH,height:HEIGHT})};
const draw=createTown(canvas),people=Array.from({length:100},(_,i)=>({id:'C'+String(i+1).padStart(3,'0'),name:'Resident '+(i+1)}));
draw(people,null);draw.setRunning(true);draw.setRunning(true);assert.equal(frames.size,1,'Duplicate animation loops');
const fn=[...frames.values()][0];frames.clear();fn(performance.now()+1000);assert.equal(frames.size,1);
draw.setRunning(false);assert.equal(frames.size,0,'Pause must stop animation');
handlers.click({clientX:150,clientY:240});assert.equal(events.at(-1)?.detail,'C100','Canvas resident picking');
draw.setRunning(true);mediaChange({matches:true});assert.equal(frames.size,0,'Reduced motion must stop animation');
draw.motion([{id:'settled',customer_id:'C001',merchant:'m1',amount_minor:10000,status:'settled',transaction_type:'MERCHANT_QR'}]);
draw.setAlerts([{customer_id:'C001',mark:'!'}]);draw.reset();draw.setRunning(false);await document.fonts.ready;
assert.equal(frames.size,0);
console.log('Passed: 400 street routes, animation lifecycle, reduced motion, resident picking and scene reset.');
