import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createTourFlow,hasSeenTour,TOUR_KEY,TOUR_STEPS} from './dist/quick-tour.js';

function setup({storage,ready=true}={}){
  const values=new Map(),steps=[],closed=[];let starts=0,available=ready;
  const store=storage||{getItem:key=>values.get(key),setItem:(key,value)=>values.set(key,value)};
  const flow=createTourFlow({storage:()=>store,canOpen:()=>available,render:index=>steps.push(index),onClose:starting=>closed.push(starting),onStart:()=>starts++});
  return {flow,values,steps,closed,get starts(){return starts},set ready(value){available=value}};
}

test('tour explains every tab and only starts the demo on the final explicit click',()=>{
  const t=setup();assert.equal(t.flow.open(true),true);
  assert.deepEqual(TOUR_STEPS.slice(0,3).map(s=>s.part),['Environment','Agent activity','Agents']);
  for(let i=1;i<TOUR_STEPS.length;i++){t.flow.next();assert.equal(t.starts,0)}
  t.flow.back();t.flow.next();assert.equal(t.starts,0);
  t.flow.next();assert.equal(t.starts,1);assert.deepEqual(t.closed,[true]);
  t.flow.next();assert.equal(t.starts,1,'double click after closing must not start a second demo');
});

test('skip remembers this browser, manual replay works, and navigation never starts a case',()=>{
  const t=setup();t.flow.open(true);t.flow.next();t.flow.back();t.flow.close();
  assert.equal(t.starts,0);assert.equal(t.values.get(TOUR_KEY),'seen');
  assert.equal(t.flow.open(true),false);assert.equal(t.flow.open(),true);
  assert.equal(t.steps.at(-1),0);t.flow.close();assert.equal(t.starts,0);
});

test('storage denial does not strand a visitor or run the demo',()=>{
  const t=setup({storage:{getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}}});
  assert.doesNotThrow(()=>{t.flow.open(true);t.flow.close()});assert.equal(t.starts,0);
});

test('first-visit detection gives the tour priority over a saved guided session',()=>{
  assert.equal(hasSeenTour(()=>({getItem:()=>null})),false);
  assert.equal(hasSeenTour(()=>({getItem:()=> 'seen'})),true);
  assert.equal(hasSeenTour(()=>{throw Error('unavailable')}),false);
});

test('an active demo or busy workspace cannot be interrupted or started twice',()=>{
  const t=setup({ready:false});assert.equal(t.flow.open(true),false);assert.deepEqual(t.steps,[]);
  t.ready=true;t.flow.open();assert.equal(t.flow.open(),false);
  for(let i=1;i<TOUR_STEPS.length;i++)t.flow.next();
  t.ready=false;t.flow.next();assert.equal(t.starts,0);assert.equal(t.flow.active,true);
  t.ready=true;t.flow.next();assert.equal(t.starts,1);
});
