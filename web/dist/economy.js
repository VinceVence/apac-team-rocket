// A prefunded, single-currency simulation. All balances are integer centavos.
export const DISTRICTS = [
  {name:'Market quarter',x:0,y:0},
  {name:'Harbor district',x:768,y:0},
  {name:'Garden homes',x:0,y:480},
  {name:'Works district',x:768,y:480}
];
export const MERCHANTS = [
  ['Kape café',90,100,0,'#bf7459',0],['Sari-sari',319,78,0,'#647c9a',1],['Mercado',99,334,0,'#9b6985',1],
  ['Harbor grocer',858,100,1,'#658d79',1],['Ferry depot',1087,78,1,'#b29253',2],['Dockside kitchen',867,334,1,'#ad7864',0],
  ['Garden bakery',90,580,2,'#c18b69',0],['Amihan clinic',319,558,2,'#588a7d',3],['Corner books',99,814,2,'#897b9b',1],
  ['Bayani bikes',858,580,3,'#b29a50',2],['Workshop',1087,558,3,'#647c9a',2],['Rice cooperative',867,814,3,'#8f9562',1]
].map(([name,x,y,district,roof,kind])=>({name,x,y,district,roof,kind}));

const interest=(principal,bps,days=1)=>Math.floor((principal*bps*days+1825000)/3650000);
const validMoney=n=>Number.isSafeInteger(n)&&n>0&&n<=1000000000000;

export class Economy {
  constructor({seed=42,population=64,savingsBps=300,loanBps=1200}={}){
    if(!Number.isInteger(seed)||seed<0||seed>999999||!Number.isInteger(population)||population<8||population>256||population%8)throw Error('Invalid world setup');
    this.rngState=seed;this.seed=seed;this.tick=0;this.day=1;this.setRates(savingsBps,loanBps);
    this.accounts=new Map();this.events=[];this.people=[];this.loans=[];this.remittances=[];this.receipts=new Map();
    this.eventSeq=0;this.commandSeq=0;this.paymentCount=0;this.paymentVolume=0;this.interestPaid=0;this.feesEarned=0;this.wagesPaid=0;this.shortfalls=0;this.shockUntil=0;
    this.addAccount('bank','Bank treasury',200000000);
    this.addAccount('platform','Fintech operations',10000000);
    this.addAccount('escrow','Remittance escrow',0);
    MERCHANTS.forEach((m,i)=>this.addAccount('m:'+i,m.name,10000000));
    const first=['Ari','Bea','Carlo','Dani','Eli','Faye','Gab','Hana','Ivo','Jules','Kai','Lia','Mika','Nico','Oli','Pia'];
    const last=['Santos','Reyes','Cruz','Tan','Rivera','Lim','Navarro','Torres'];
    for(let i=0;i<population;i++){
      const owner=this,p={id:i,name:first[i%16]+' '+last[Math.floor(i/16)%8]+(i>=128?' '+(1+Math.floor(i/128)):''),district:i%4,employer:(i%4)*3+Math.floor(i/4)%3,
        wallet:'p:'+i+':wallet',savings:'p:'+i+':savings',weeklyWage:250000+Math.floor(this.random()*400000),essential:5000+Math.floor(this.random()*10000),
        creditLimit:0,creditDebt:0,creditInterest:0,creditDrawn:0,creditPaid:0,creditWrittenOff:0,creditPastDue:0,creditMissedSince:null,creditFrozen:false,loanId:null,
        get balance(){return owner.balance(this.wallet)}};
      p.creditLimit=p.weeklyWage;
      this.addAccount(p.wallet,p.name+' · wallet',500000+Math.floor(this.random()*1000000));
      this.addAccount(p.savings,p.name+' · savings',i%3===0?300000+Math.floor(this.random()*400000):0);
      this.people.push(p);
    }
    this.openingCash=this.totalCash();
    for(let i=0;i<12;i++)this.purchase();
  }
  random(){this.rngState=(Math.imul(1664525,this.rngState)+1013904223)>>>0;return this.rngState/4294967296}
  addAccount(id,name,balance){this.accounts.set(id,{name,balance})}
  balance(id){return this.accounts.get(id)?.balance??0}
  totalCash(){return [...this.accounts.values()].reduce((n,a)=>n+a.balance,0)}
  setRates(savingsBps,loanBps){
    if(!Number.isInteger(savingsBps)||savingsBps<0||savingsBps>1000||!Number.isInteger(loanBps)||loanBps<0||loanBps>3000)throw Error('Invalid simulation rates');
    this.savingsBps=savingsBps;this.loanBps=loanBps;
  }
  record(type,meta={}){
    const e={id:'E'+String(++this.eventSeq).padStart(5,'0'),tick:this.tick,day:this.day,type,rail:meta.rail||type,result:'Settled',amount:0,entries:[],cashMoved:0,...meta};
    this.events.push(e);return e;
  }
  post(type,legs,meta={}){
    const deltas=new Map();
    for(const leg of legs){
      if(!validMoney(leg.amount)||!this.accounts.has(leg.from)||!this.accounts.has(leg.to)||leg.from===leg.to)throw Error('Invalid financial posting');
      deltas.set(leg.from,(deltas.get(leg.from)||0)-leg.amount);deltas.set(leg.to,(deltas.get(leg.to)||0)+leg.amount);
    }
    for(const [id,delta] of deltas)if(!Number.isSafeInteger(this.balance(id)+delta)||this.balance(id)+delta<0)return this.record(type,{fromLabel:this.accounts.get(legs[0].from).name,toLabel:this.accounts.get(legs[0].to).name,...meta,ok:false,result:'Declined',detail:'Insufficient available funds'});
    for(const [id,delta] of deltas)this.accounts.get(id).balance+=delta;
    const e=this.record(type,{fromLabel:this.accounts.get(legs[0].from).name,toLabel:this.accounts.get(legs[0].to).name,...meta,ok:true,entries:[...deltas].map(([account,delta])=>({account,delta})),cashMoved:legs.reduce((n,l)=>n+l.amount,0)});
    if(type==='Payment'){this.paymentCount++;this.paymentVolume+=meta.amount}
    return e;
  }
  pay(person,merchant,amount,rail='Wallet',result='Settled'){
    const p=this.people[person],shop=MERCHANTS[merchant];
    if(!p||!shop||!validMoney(amount))throw Error('Invalid payment');
    const meta={person,merchant,amount,rail,fromLabel:p.name,toLabel:shop.name};
    if(result!=='Settled')return this.record('Payment',{...meta,result,ok:false});
    return this.post('Payment',[{from:p.wallet,to:'m:'+merchant,amount}],meta);
  }
  purchase(){
    const person=Math.floor(this.random()*this.people.length),p=this.people[person];
    const local=p.district*3+Math.floor(this.random()*3),merchant=this.random()<.8?local:Math.floor(this.random()*MERCHANTS.length);
    return this.pay(person,merchant,(30+Math.floor(this.random()*370))*100,['QR','Card','Wallet'][Math.floor(this.random()*3)]);
  }
  apply(action,input={},operationId){
    const id=operationId||'C'+(++this.commandSeq),signature=JSON.stringify([action,input.person??null,input.amount??null,action==='remit'?input.target:null,action==='cancelRemittance'?input.transfer:null]);
    if(this.receipts.has(id)){
      const old=this.receipts.get(id);
      if(old.signature!==signature)return {ok:false,message:'Operation ID was reused with different instructions.'};
      return {...old.result,replayed:true};
    }
    const p=this.people[input.person],amount=input.amount,start=this.events.length;
    let result;
    if(action==='incomeShock'){this.shockUntil=this.tick+14*24;this.record('Income shock',{result:'Scheduled',detail:'Wages reduced by 50% for 14 days',fromLabel:'Scenario',toLabel:'All employers'});result={ok:true,message:'A 14-day income shock is active. Scheduled wages are halved.'}}
    else if(action==='cancelRemittance')result=this.cancelRemittance(input.transfer);
    else if(!p||!validMoney(amount))result={ok:false,message:'Choose a resident and a positive amount in whole centavos.'};
    else if(action==='deposit'||action==='withdraw'){
      const from=action==='deposit'?p.wallet:p.savings,to=action==='deposit'?p.savings:p.wallet;
      const e=this.post(action==='deposit'?'Savings deposit':'Savings withdrawal',[{from,to,amount}],{person:p.id,amount});
      result={ok:e.ok,message:e.ok?(action==='deposit'?'Moved to savings. Interest is paid at each simulated day close.':'Moved from savings to the wallet.'):'Insufficient funds in the source account.'};
    }else if(action==='loan')result=this.openLoan(p,amount);
    else if(action==='repayLoan')result=this.repayLoan(p,amount,false);
    else if(action==='credit')result=this.drawCredit(p,amount);
    else if(action==='repayCredit')result=this.payCredit(p,amount);
    else if(action==='remit')result=this.sendRemittance(p,input.target,amount);
    else result={ok:false,message:'Unknown financial action.'};
    if(!result.ok&&this.events.length===start){const names={loan:'Loan application',repayLoan:'Loan repayment',credit:'Credit request',repayCredit:'Credit repayment',remit:'Remittance request',cancelRemittance:'Remittance cancellation',deposit:'Savings deposit',withdraw:'Savings withdrawal'};this.record(names[action]||'Policy decision',{person:p?.id,amount:validMoney(amount)?amount:0,result:'Declined',fromLabel:p?.name||'Operator',toLabel:'Policy service',detail:result.message})}
    for(let i=start;i<this.events.length;i++)this.events[i].operationId=id;
    this.receipts.set(id,{signature,result:{...result}});return result;
  }
  income(p){return Math.floor(p.weeklyWage*(this.tick<this.shockUntil ? 0.5 : 1))}
  openLoan(p,amount){
    const previous=this.loans.find(l=>l.id===p.loanId);
    if(previous&&previous.status!=='paid')return {ok:false,message:'The existing loan must be resolved before another is issued.'};
    if(p.creditPastDue||p.creditFrozen)return {ok:false,message:'Overdue credit requires review before a new loan.'};
    const weekly=Math.ceil(amount/4)+interest(amount,this.loanBps,7)+Math.ceil(p.creditDebt/10);
    if(amount>this.income(p)*3||weekly>Math.floor(this.income(p)*.35))return {ok:false,message:'Declined: scheduled weekly debt exceeds the simulated 35% income limit.'};
    const e=this.post('Loan disbursement',[{from:'bank',to:p.wallet,amount}],{person:p.id,amount,detail:'Four weekly installments'});
    if(!e.ok)return {ok:false,message:'The bank does not have enough lending capital.'};
    const loan={id:'L'+(this.loans.length+1),person:p.id,original:amount,outstanding:amount,repaid:0,writtenOff:0,rateBps:this.loanBps,status:'active',schedule:[]};
    for(let i=0;i<4;i++)loan.schedule.push({day:this.day+7*(i+1),principal:Math.floor(amount/4)+(i<amount%4?1:0),interest:0,assessed:false});
    e.loanId=loan.id;e.rateBps=loan.rateBps;this.loans.push(loan);p.loanId=loan.id;
    return {ok:true,message:'Loan funded by the bank treasury. First installment is due on day '+loan.schedule[0].day+'.'};
  }
  repayLoan(p,amount,dueOnly){
    const l=this.loans.find(l=>l.id===p.loanId);
    if(!l||!['active','arrears'].includes(l.status))return {ok:false,message:'No active installment loan.'};
    const rows=l.schedule.filter(r=>!dueOnly||r.day<=this.day);
    const owing=rows.reduce((n,r)=>n+r.principal+r.interest,0),payment=Math.min(amount,owing);
    if(payment<=0)return {ok:false,message:'No installment is due.'};
    const e=this.post('Loan repayment',[{from:p.wallet,to:'bank',amount:payment}],{person:p.id,amount:payment,detail:l.id});
    if(!e.ok)return {ok:false,message:'Insufficient wallet funds for that repayment.'};
    let remaining=payment,principalPaid=0;
    for(const r of rows){const n=Math.min(remaining,r.interest);r.interest-=n;remaining-=n}
    for(const r of rows){const n=Math.min(remaining,r.principal);r.principal-=n;remaining-=n;principalPaid+=n}
    e.loanId=l.id;e.principalMinor=principalPaid;e.interestMinor=payment-principalPaid;l.outstanding-=principalPaid;l.repaid+=principalPaid;this.updateLoan(l);
    return {ok:true,message:l.status==='paid'?'Loan paid in full.':'Repayment posted; principal and accrued interest updated.'};
  }
  updateLoan(l){
    const late=l.schedule.find(r=>r.day<=this.day&&(r.principal+r.interest)>0);
    if(l.outstanding===0&&l.schedule.every(r=>r.interest===0)){l.status='paid';return}
    l.status=late?'arrears':'active';
    if(late&&this.day-late.day>=28){
      const loss=l.outstanding;l.writtenOff+=loss;l.outstanding=0;l.status='written-off';
      l.schedule.forEach(r=>{r.principal=0;r.interest=0});
      this.record('Loan write-off',{person:l.person,amount:loss,result:'Written off',fromLabel:'Bank loan book',toLabel:this.people[l.person].name,detail:'Non-cash loss after 28 days past due'});
    }
  }
  drawCredit(p,amount){
    if(p.creditFrozen||p.creditPastDue)return {ok:false,message:'Credit is paused while an overdue balance needs review.'};
    if(p.creditDebt+amount>p.creditLimit)return {ok:false,message:'The purchase exceeds the available credit limit.'};
    const merchant=p.district*3;
    const e=this.post('Credit purchase',[{from:'bank',to:'m:'+merchant,amount}],{person:p.id,merchant,amount,fromLabel:p.name+' · credit line',toLabel:MERCHANTS[merchant].name});
    if(!e.ok)return {ok:false,message:'Bank treasury cannot fund this credit purchase.'};
    p.creditDebt+=amount;p.creditDrawn+=amount;
    return {ok:true,message:'Merchant paid by the bank. The amount is now revolving credit debt.'};
  }
  payCredit(p,amount){
    const payment=Math.min(amount,p.creditDebt+p.creditInterest);
    if(!payment)return {ok:false,message:'No credit balance to repay.'};
    const e=this.post('Credit repayment',[{from:p.wallet,to:'bank',amount:payment}],{person:p.id,amount:payment});
    if(!e.ok)return {ok:false,message:'Insufficient wallet funds for that repayment.'};
    const interestPaid=Math.min(payment,p.creditInterest),principal=payment-interestPaid;
    e.principalMinor=principal;e.interestMinor=interestPaid;p.creditInterest-=interestPaid;p.creditDebt-=principal;p.creditPaid+=principal;p.creditPastDue=Math.max(0,p.creditPastDue-payment);
    if(!p.creditPastDue)p.creditMissedSince=null;
    return {ok:true,message:'Credit repayment posted. Available credit has been restored.'};
  }
  sendRemittance(p,target,amount){
    const receiver=this.people[target];
    if(!receiver||receiver.id===p.id)return {ok:false,message:'Choose a different recipient.'};
    const fee=Math.max(1000,Math.floor((amount+50)/100)),gross=amount+fee;
    const e=this.post('Remittance sent',[{from:p.wallet,to:'escrow',amount:gross}],{person:p.id,amount,result:'Pending',toLabel:receiver.name,detail:'Fee reserved: '+fee+' centavos'});
    if(!e.ok)return {ok:false,message:'Wallet must cover the transfer plus its fee.'};
    const transfer={id:'R'+(this.remittances.length+1),from:p.id,to:target,amount,fee,dueDay:this.day+1,status:'pending'};
    e.transferId=transfer.id;e.feeMinor=fee;e.dueDay=transfer.dueDay;this.remittances.push(transfer);
    return {ok:true,message:'Transfer and fee reserved in escrow. Delivery on day '+transfer.dueDay+'.'};
  }
  cancelRemittance(id){
    const r=this.remittances.find(x=>x.id===id);
    if(!r||r.status!=='pending')return {ok:false,message:'Only a pending remittance can be cancelled.'};
    this.post('Remittance refund',[{from:'escrow',to:this.people[r.from].wallet,amount:r.amount+r.fee}],{person:r.from,amount:r.amount+r.fee,result:'Refunded'});
    r.status='cancelled';return {ok:true,message:'Pending transfer cancelled. Principal and reserved fee refunded.'};
  }
  step(activity=1){
    if(!Number.isInteger(activity)||activity<1||activity>8)throw Error('Invalid activity');
    this.tick++;const nextDay=1+Math.floor((this.tick+9)/24);
    if(nextDay!==this.day){this.day=nextDay;this.closeDay()}
    for(let i=0;i<activity;i++)this.purchase();
  }
  closeDay(){
    for(const r of this.remittances.filter(r=>r.status==='pending'&&r.dueDay<=this.day)){
      this.post('Remittance delivered',[{from:'escrow',to:this.people[r.to].wallet,amount:r.amount},{from:'escrow',to:'platform',amount:r.fee}],{person:r.to,amount:r.amount,fromLabel:this.people[r.from].name,toLabel:this.people[r.to].name,detail:'Fee earned: '+r.fee+' centavos',transferId:r.id,feeMinor:r.fee});
      r.status='delivered';this.feesEarned+=r.fee;
    }
    for(const p of this.people){
      if((this.day-1)%7===0){
        const wage=this.income(p);
        const e=this.post('Payroll',[{from:'m:'+p.employer,to:p.wallet,amount:wage}],{person:p.id,amount:wage});
        if(e.ok)this.wagesPaid+=wage;
      }
      const yieldAmount=interest(this.balance(p.savings),this.savingsBps);
      if(yieldAmount>0){const e=this.post('Savings interest',[{from:'bank',to:p.savings,amount:yieldAmount}],{person:p.id,amount:yieldAmount});if(e.ok)this.interestPaid+=yieldAmount}
      const need=this.post('Essential expense',[{from:p.wallet,to:'m:'+(p.district*3+1),amount:p.essential}],{person:p.id,amount:p.essential,merchant:p.district*3+1});
      if(!need.ok)this.shortfalls++;
      const l=this.loans.find(l=>l.id===p.loanId);
      if(l&&['active','arrears'].includes(l.status)){
        for(const r of l.schedule)if(r.day<=this.day&&!r.assessed){r.interest=interest(l.outstanding,l.rateBps,7);r.assessed=true;if(r.interest)this.record('Loan interest accrued',{person:p.id,loanId:l.id,amount:r.interest,rateBps:l.rateBps,result:'Accrued',fromLabel:'Bank loan book',toLabel:p.name,detail:'Non-cash interest assessment'})}
        const due=l.schedule.filter(r=>r.day<=this.day).reduce((n,r)=>n+r.principal+r.interest,0);
        const available=Math.max(0,p.balance-50000);
        if(due&&available)this.repayLoan(p,Math.min(due,available),true);
        this.updateLoan(l);
      }
      if((this.day-1)%7===0&&p.creditDebt){
        const newInterest=interest(p.creditDebt,2400,7);p.creditInterest+=newInterest;if(newInterest)this.record('Credit interest accrued',{person:p.id,amount:newInterest,rateBps:2400,result:'Accrued',fromLabel:'Bank credit book',toLabel:p.name,detail:'Non-cash interest assessment'});
        const due=Math.min(p.creditDebt,Math.ceil(p.creditDebt/10))+newInterest;
        p.creditPastDue=Math.min(p.creditDebt+p.creditInterest,p.creditPastDue+due);
        const available=Math.max(0,p.balance-50000);
        if(available)this.payCredit(p,Math.min(p.creditPastDue,available));
        if(p.creditPastDue&&p.creditMissedSince===null)p.creditMissedSince=this.day;
      }
      if(p.creditMissedSince!==null&&this.day-p.creditMissedSince>=28){
        const loss=p.creditDebt;p.creditWrittenOff+=loss;p.creditDebt=0;p.creditInterest=0;p.creditPastDue=0;p.creditFrozen=true;p.creditMissedSince=null;
        this.record('Credit write-off',{person:p.id,amount:loss,result:'Written off',fromLabel:'Bank credit book',toLabel:p.name,detail:'Non-cash loss'});
      }
    }
  }
  metrics(){
    return {savings:this.people.reduce((n,p)=>n+this.balance(p.savings),0),wallets:this.people.reduce((n,p)=>n+p.balance,0),loanPrincipal:this.loans.reduce((n,l)=>n+l.outstanding,0),creditPrincipal:this.people.reduce((n,p)=>n+p.creditDebt,0),loanLosses:this.loans.reduce((n,l)=>n+l.writtenOff,0)+this.people.reduce((n,p)=>n+p.creditWrittenOff,0),bankCash:this.balance('bank'),pendingRemittances:this.remittances.filter(r=>r.status==='pending').length,escrow:this.balance('escrow')};
  }
  check(){
    const cash=this.totalCash()===this.openingCash;
    const nonnegative=[...this.accounts.values()].every(a=>Number.isSafeInteger(a.balance)&&a.balance>=0);
    const loans=this.loans.every(l=>l.original===l.outstanding+l.repaid+l.writtenOff&&l.outstanding>=0&&l.schedule.every(r=>r.principal>=0&&r.interest>=0));
    const credit=this.people.every(p=>p.creditDrawn===p.creditDebt+p.creditPaid+p.creditWrittenOff&&p.creditDebt>=0);
    const escrow=this.balance('escrow')===this.remittances.filter(r=>r.status==='pending').reduce((n,r)=>n+r.amount+r.fee,0);
    const journal=this.events.every(e=>e.entries.every(x=>Number.isSafeInteger(x.delta))&&e.entries.reduce((n,x)=>n+x.delta,0)===0);
    return {ok:cash&&nonnegative&&loans&&credit&&escrow&&journal,cash,nonnegative,loans,credit,escrow,journal};
  }
}
