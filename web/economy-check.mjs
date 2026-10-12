import assert from 'node:assert/strict';
import {Economy} from './dist/economy.js';

const valid=w=>assert.deepEqual(w.check(),{ok:true,cash:true,nonnegative:true,loans:true,credit:true,escrow:true,journal:true});
const advance=(w,days)=>{for(let i=0;i<days*24;i++)w.step();valid(w)};
const w=new Economy(),p=w.people[0],start=p.balance,saved=w.balance(p.savings);
assert.equal(w.apply('deposit',{person:0,amount:200000},'deposit-1').ok,true);
assert.equal(p.balance,start-200000);assert.equal(w.balance(p.savings),saved+200000);
assert(w.apply('deposit',{amount:200000,person:0},'deposit-1').replayed);
assert.equal(p.balance,start-200000);
assert.equal(w.apply('deposit',{person:0,amount:100000},'deposit-1').ok,false);
assert(w.apply('withdraw',{person:0,amount:200000}).ok);assert.equal(p.balance,start);
assert.equal(w.apply('withdraw',{person:0,amount:999999999}).ok,false);
assert.equal(w.apply('deposit',{person:0,amount:1.5}).ok,false);
assert(w.apply('loan',{person:0,amount:200001},'loan-1').ok);
assert.equal(w.loans[0].schedule.reduce((n,r)=>n+r.principal,0),200001);
assert(w.apply('loan',{person:0,amount:200001},'loan-1').replayed);
assert.equal(w.loans.length,1);
assert.equal(w.apply('loan',{person:0,amount:200000}).ok,false);
assert.equal(w.events.at(-1).type,'Loan application');assert.equal(w.events.at(-1).result,'Declined');
assert(w.apply('credit',{person:0,amount:50000}).ok);
assert.equal(p.creditDebt,50000);
assert(w.apply('repayCredit',{person:0,amount:50000}).ok);assert.equal(p.creditDebt,0);
assert.equal(w.apply('credit',{person:0,amount:p.creditLimit+1}).ok,false);
const beforeSend=p.balance,target=w.people[1],beforeReceive=target.balance;
assert(w.apply('remit',{person:0,target:1,amount:50000},'remit-1').ok);
assert.equal(p.balance,beforeSend-51000);assert.equal(target.balance,beforeReceive);assert.equal(w.balance('escrow'),51000);
assert(w.apply('remit',{person:0,target:1,amount:50000},'remit-1').replayed);
assert.equal(w.remittances.length,1);
assert(w.apply('cancelRemittance',{transfer:'R1'}).ok);
assert.equal(p.balance,beforeSend);assert.equal(w.balance('escrow'),0);
assert.equal(w.apply('cancelRemittance',{transfer:'R1'}).ok,false);
assert(w.apply('remit',{person:0,target:1,amount:50000}).ok);
advance(w,1);assert.equal(w.remittances[1].status,'delivered');assert.equal(w.balance('escrow'),0);assert.equal(w.feesEarned,1000);
assert(w.interestPaid>0);
advance(w,28);assert.equal(w.loans[0].status,'paid');assert.equal(w.loans[0].outstanding,0);assert(w.wagesPaid>0);

const capacity=new Economy();
const bp=capacity.balance('bank');
capacity.post('Capital stress',[{from:'bank',to:'platform',amount:bp}]);
assert.equal(capacity.apply('loan',{person:0,amount:200000}).ok,false);
assert.equal(capacity.loans.length,0);advance(capacity,1);assert.equal(capacity.interestPaid,0);

const bad=new Economy(),borrower=bad.people[0];
assert(bad.apply('loan',{person:0,amount:200000}).ok);
bad.post('Liquidity stress',[{from:borrower.wallet,to:'bank',amount:borrower.balance}]);
// Unfundable scheduled wage is an explicit adverse fixture; no cash is fabricated.
borrower.weeklyWage=bad.openingCash*2;
advance(bad,40);assert.equal(bad.loans[0].status,'written-off');assert.equal(bad.loans[0].writtenOff,200000);

const creditBad=new Economy(),cp=creditBad.people[1];
assert(creditBad.apply('credit',{person:1,amount:50000}).ok);
creditBad.post('Liquidity stress',[{from:cp.wallet,to:'bank',amount:cp.balance}]);cp.weeklyWage=creditBad.openingCash*2;
advance(creditBad,40);assert(cp.creditFrozen);assert.equal(cp.creditWrittenOff,50000);

const a=new Economy({seed:93,population:256}),b=new Economy({seed:93,population:256});
for(let i=0;i<96;i++){a.step(4);b.step(4)}
assert.deepEqual([...a.accounts],[...b.accounts]);assert.deepEqual(a.events,b.events);valid(a);valid(b);
const wage=a.income(a.people[0]);a.apply('incomeShock');assert.equal(a.income(a.people[0]),Math.floor(wage/2));advance(a,14);assert.equal(a.income(a.people[0]),wage);
assert.throws(()=>new Economy({population:257}));assert.throws(()=>new Economy({savingsBps:9999}));
console.log('PASS: conserved cash/journals, savings, idempotency, loan schedule and write-off, credit lifecycle, remittance escrow/refund/delivery, treasury limits, payroll, interest, shock expiry and 256-resident replay.');
