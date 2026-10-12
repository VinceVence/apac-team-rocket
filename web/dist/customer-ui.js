export function createCustomerUI({$,api,state,setPlaying,setBusy,refresh,error,runTeam}){
  let data=null;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  const pct=n=>n==null?'Withheld':(n*100).toFixed(1)+'%';
  const metrics=[['churn_score','Disengagement risk'],['response_score','Campaign engagement'],['savings_score','Savings affinity'],['budgeting_score','Budgeting affinity'],['qr_score','QR affinity'],['rewards_score','Rewards affinity'],['repeat_spend_score','Repeat spending'],['capacity_band','Spending-capacity proxy']];
  function person(){
    const cid=$('dna-customer').value,p=data.profiles.find(p=>p.id===cid),dna=data.dna.find(d=>d.customer_id===cid);if(!p)return;
    $('dna-name').textContent=p.name;$('dna-profile').textContent=p.profile.age_band+' · '+p.profile.region+' · '+p.profile.occupation+' · household of '+p.profile.household_size;
    $('dna-preferences').textContent='Goal: '+p.profile.goal+' · preferred channel: '+p.profile.preferred_channel+' · marketing '+(p.profile.marketing_consent?'opted in':'opted out');
    $('dna-tags').textContent=dna?dna.tags.join(' · '):'Run the customer team to build and publish Customer DNA.';
    $('dna-scores').replaceChildren();for(const [key,label] of metrics){const cell=el('div',undefined,'dna-score');cell.append(el('span',label),el('strong',dna?(key==='capacity_band'?(dna[key]||'Withheld'):pct(dna[key])):'Not published'));$('dna-scores').append(cell)}
    $('dna-lineage').textContent=dna?'As of '+dna.as_of+' · '+Object.keys(dna.model_versions).length+' qualified models · remaining columns are withheld.':'No published model scores for this customer.';
  }
  function render(){
    const p=data.pipeline;$('customer-population').textContent=data.customers+' synthetic customers · '+data.marketing_consent+' marketing opt-ins';
    $('customer-layers').replaceChildren();for(const [label,value,caption] of [['Bronze',data.tables.bronze_interactions,'Raw keyed interactions'],['Silver',data.tables.silver_interactions,'Clean event records'],['Gold',data.tables.gold_customer_features,'One feature row per customer'],['Customer DNA',data.tables.gold_customer_dna,'Versioned predictive columns']]){const c=el('div');c.append(el('span',label),el('strong',value.toLocaleString()),el('small',caption));$('customer-layers').append(c)}
    $('customer-quality').textContent=p?'Last build: '+p.as_of+' · '+p.rejected_rows+' rejected raw rows · '+(p.quality_passed?'quality checks passed':'quality needs review'):'Bronze is ready. The data engineer has not materialized silver and gold yet.';
    $('customer-models').replaceChildren();for(const m of data.models.slice().reverse()){const tr=el('tr');for(const v of [m.title,m.fitted?'Fitted':'Needs data',m.eligible?'Qualified':'Withheld',m.auc==null?(m.accuracy==null?'—':'Accuracy '+pct(m.accuracy)):'AUC '+m.auc,m.holdout_rows])tr.append(el('td',String(v)));$('customer-models').append(tr)}
    $('customer-model-note').textContent=data.models.filter(m=>!m.eligible).map(m=>m.title+': '+m.gate_reasons.join(' ')).join(' ');
    const selected=$('dna-customer').value;$('dna-customer').replaceChildren();for(const p of data.profiles)$('dna-customer').add(new Option(p.id+' · '+p.name,p.id));if(selected)$('dna-customer').value=selected;person();
    $('customer-events').replaceChildren();for(const event of data.events.slice(0,8)){const tr=el('tr');for(const v of [event.customer_id,event.event_date,event.kind,event.product||'—'])tr.append(el('td',v));$('customer-events').append(tr)}
    $('customer-campaigns').replaceChildren();
    if(!data.campaigns.length)$('customer-campaigns').append(el('p','The marketing agent can inspect an audience and launch a randomized in-app pilot after Customer DNA is published.','surface-note'));
    for(const c of data.campaigns){
      const section=el('article',undefined,'customer-campaign'),report=c.report;
      section.append(el('strong',c.config.strategy.replaceAll('_',' ')+' · '+c.status),el('p',c.id+' · '+c.assignments.length+' customers · outcomes due '+c.due_on));
      if(c.status==='completed')section.append(el('p','Activation: message '+pct(report.message_rate)+' vs control '+pct(report.control_rate)+' · difference '+(report.difference*100).toFixed(1)+' percentage points.'),el('p',report.conclusion));
      else section.append(el('p','Message and control arms are waiting for observed outcomes. No effectiveness claim yet.'));
      const details=el('details',undefined,'world-details');details.append(el('summary','Personalized message previews'));
      for(const a of c.assignments.filter(a=>a.arm==='message').slice(0,5)){const row=el('div',undefined,'customer-message');row.append(el('small',a.customer_id+' · '+a.product),el('p',a.message));details.append(row)}
      section.append(details);$('customer-campaigns').append(section);
    }
    $('customer-advance').disabled=!data.campaigns.some(c=>c.status==='running');
  }
  async function load(){data=await api('/api/customer-data');render()}
  $('dna-customer').onchange=person;$('customer-run-team').onclick=runTeam;
  $('customer-advance').onclick=async()=>{if(state.busy||state.stepping)return;setPlaying(false);setBusy(true);error('');$('customer-advance').disabled=true;$('customer-advance').textContent='Simulating seven days…';try{await api('/api/customer-data/advance',{expected_tick:state.data.world.tick,days:7,activity:Number($('activity').value)});await refresh();await load()}catch(e){error(e.message);await refresh().catch(()=>{})}finally{setBusy(false);$('customer-advance').textContent='Simulate 7 days';if(data)render()}};
  for(const b of document.querySelectorAll('[data-customer-tab]'))b.onclick=()=>{for(const x of document.querySelectorAll('[data-customer-tab]'))x.setAttribute('aria-selected',String(x===b));for(const p of document.querySelectorAll('[data-customer-panel]'))p.hidden=p.dataset.customerPanel!==b.dataset.customerTab};
  return {load};
}
