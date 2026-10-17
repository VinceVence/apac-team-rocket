import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createLandingWorld,previewPhase} from './dist/landing-world.js';

test('landing is a bounded illustrative cycle, separate from case execution',()=>{
 assert.deepEqual([0,9,14,20,24].map(previewPhase).map(p=>p.id),['day','report','review','protect','day']);
});
test('preview stops offscreen and with reduced motion without fetching or mutating the world',()=>{
 const keys=['document','matchMedia','MutationObserver','requestAnimationFrame','cancelAnimationFrame','fetch'];
 const original=Object.fromEntries(keys.map(k=>[k,globalThis[k]]));
 const queued=new Map(),events={};let n=0,observer,mediaChange;
 const ctx=new Proxy({measureText:t=>({width:t.length*7})},{get:(o,k)=>o[k]??(()=>{})});
 const canvas=()=>({width:0,height:0,getContext:()=>ctx});
 const section={hidden:false,dataset:{}},label={textContent:''};
 const motion={matches:false,addEventListener:(_,f)=>mediaChange=f,removeEventListener:()=>{}};
 globalThis.document={hidden:false,createElement:canvas,addEventListener:(k,f)=>events[k]=f,removeEventListener:k=>delete events[k]};
 globalThis.matchMedia=()=>motion;
 globalThis.MutationObserver=class{constructor(fn){observer=fn}observe(){}disconnect(){}};
 globalThis.requestAnimationFrame=fn=>{queued.set(++n,fn);return n};globalThis.cancelAnimationFrame=id=>queued.delete(id);
 globalThis.fetch=()=>{throw Error('Landing preview must not call a service')};
 try{
  const preview=createLandingWorld(canvas(),section,label);assert.equal(queued.size,1);
  section.hidden=true;observer();assert.equal(queued.size,0);
  section.hidden=false;observer();assert.equal(queued.size,1);
  document.hidden=true;events.visibilitychange();assert.equal(queued.size,0);
  document.hidden=false;motion.matches=true;mediaChange();assert.equal(queued.size,0);
  assert.equal(label.textContent,'A normal day in Mint Town');
  motion.matches=false;mediaChange();assert.equal(queued.size,1);preview.destroy();assert.equal(queued.size,0);
 }finally{for(const k of keys){if(original[k]===undefined)delete globalThis[k];else globalThis[k]=original[k]}}
});
