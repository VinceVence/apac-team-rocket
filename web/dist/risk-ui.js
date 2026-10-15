import {cleanText,publicEvidence,agentIcon} from './agent-ui.js';
export function createRiskUI({$,state,error,onCases}){
  let data=null,study=null,token='',busy=false,timer=null,selected='',visible=false,polls=0,initialized=false;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  const active=()=>study&&['queued','scientist','planned','training','refiner','refined','validator'].includes(study.status);
  const names={queued:'Queued',scientist:'Scientist choosing an experiment',planned:'Experiment planned',training:'Fitting models on the CPU',refiner:'Refiner examining validation errors',refined:'Targeted change selected',validator:'Validator checking results',needs_data:'More curated data needed',awaiting_model_review:'Candidate ready for human model review',rejected:'Payment release withheld',failed:'Study stopped',interrupted:'Study interrupted'};
  async function request(path='',body){
    const response=await fetch('/api/risk-lab'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-MintTown-Token':state.data.csrf_token,'X-MintTown-Operator':token},body:JSON.stringify(body)});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Research request failed.');return result;
  }
  function render(){
    if(!data)return;
    const source=$('risk-source').value,dataset=data.datasets[source];
    $('risk-dataset-stats').replaceChildren();
    for(const [value,label] of [[dataset.eligible_rows,'eligible examples'],[dataset.customers,'customers'],[dataset.excluded_count,'excluded examples']]){
      const box=el('div',undefined,'risk-stat');box.append(el('strong',String(value)),el('span',label));$('risk-dataset-stats').append(box);
    }
    $('risk-data-scope').textContent=dataset.scope;
    $('risk-quality').replaceChildren();
    for(const [split,value] of Object.entries(dataset.splits))$('risk-quality').append(el('p',`${split}: ${value.rows} examples · ${value.scams} scam labels · ${value.customers} customers`));
    for(const problem of [...dataset.problems,...dataset.excluded_examples.map(x=>x.reason)])$('risk-quality').append(el('p',problem,'risk-reason'));
    $('risk-case').replaceChildren();for(const c of data.reviewed_cases)$('risk-case').add(new Option(`${c.id} · ${c.disposition.replaceAll('_',' ')}`,c.id));
    $('risk-study-select').replaceChildren();for(const s of data.studies)$('risk-study-select').add(new Option(`${s.id} · ${names[s.status]||s.status}`,s.id));
    if(study)$('risk-study-select').value=study.id;
    $('risk-mode').textContent=study?.provider==='fake'?'Offline rehearsal':'Research workspace';
    $('risk-study-status').textContent=study?(names[study.status]||study.status)+' · '+(study.source==='reviewed'?'curated cases':study.source==='request_benchmark'?'MLE search & refinement':'synthetic benchmark')+(study.error?' — '+cleanText(study.error):''):'No saved experiments yet.';
    $('risk-hypothesis').textContent=study?.plan?.hypothesis||'The scientist chooses a hypothesis and model recipes after the dataset passes its checks.';
    $('risk-trail').replaceChildren();
    const timeline=study?.trace||[],roles=study?.source==='request_benchmark'?['scientist','refiner','validator']:['scientist','validator'];
    $('risk-trail').dataset.roleCount=String(roles.length);
    if(study)for(const role of roles){
      const at=timeline.findIndex(t=>t.role===role),t=timeline[at],row=el('li');
      row.append(agentIcon(role==='validator'?'judge':role==='refiner'?'specialist':'scientist'),el('strong',role),el('p',t?.purpose||'Waiting for this role.'));
      if(t){const end=timeline.findIndex((n,i)=>i>at&&n.role!=='training_tool'),receipts=timeline.slice(at,end<0?undefined:end),details=el('details',undefined,'world-details');details.append(el('summary','Tool receipts'));
        for(const receipt of receipts)details.append(el('p',receipt.tool.replaceAll('_',' ')+' · '+receipt.purpose));
        const change=receipts.find(r=>r.tool==='sealed_test')?.result;if(change)row.append(el('p',`${Math.round(change.validation_recall_delta*100)} points validation recall change · ${change.validation_false_hold_delta} additional legitimate flags`,'ablation-result'));
        row.append(details);
      }
      $('risk-trail').append(row);
    }
    $('risk-candidates').replaceChildren();
    for(const c of study?.candidates||[]){
      const card=el('article',undefined,'risk-candidate '+c.status),head=el('div',undefined,'risk-candidate-heading');
      head.append(el('h3',c.name),el('span',c.status==='eligible'?'Gate passed':c.status==='reference'?'Reference':'Rejected','risk-result'));card.append(head);
      const numbers=el('div',undefined,'risk-score-pair');
      for(const [value,total,label] of [[c.test.caught,c.test.positives,'scams detected'],[c.test.false_holds,c.test.negatives,'legitimate requests flagged']]){
        const item=el('div');item.append(el('strong',`${value} / ${total}`),el('span',label));numbers.append(item);
      }
      card.append(numbers,el('p','Held-out '+(study.source!=='reviewed'?'synthetic ':'')+'test · '+c.test.rows+' examples','surface-note'));
      card.append(el('p',c.preselected?'Selected using validation data':'Comparison only · not selected for review','surface-note'));
      if(Array.isArray(c.ablation)){for(const a of c.ablation)card.append(el('p',`Without ${a.component}: ${-Math.round(a.validation_recall_drop*100)} points validation recall.`, 'ablation-result'))}
      else if(c.ablation){const a=c.ablation,delta=Math.round(a.validation_recall_delta*100);card.append(el('p',`${a.removed_group} features: ${delta>=0?'+':''}${delta} points validation recall; ${a.validation_false_hold_delta>=0?'+':''}${a.validation_false_hold_delta} legitimate holds.`, 'ablation-result'))}
      const meter=el('meter');meter.min=0;meter.max=1;meter.value=c.test.recall;meter.setAttribute('aria-label',c.name+' synthetic scam recall');card.append(meter);
      const reasons=el('ul');for(const reason of c.reasons)reasons.append(el('li',reason));card.append(reasons);
      const details=el('details',undefined,'world-details');details.append(el('summary','Features, metrics & counterexamples'));
      const pre=el('pre',JSON.stringify({features:c.features,validation:c.validation,test:c.test,counterexamples:c.counterexamples,artifact_hash:c.artifact_hash},null,2),'science-evidence');details.append(pre);card.append(details);
      if(study.source==='request_benchmark'&&c.preselected&&!active()){
        const button=el('button',c.registered_tool_id?'Registered for investigation':'Use as advisory investigation tool','secondary-button');button.disabled=busy||!token||!!c.registered_tool_id;
        button.onclick=()=>write('/register',{study_id:study.id,candidate_id:c.id,note:'Operator reviewed the synthetic evaluation and its limitations. Register as advisory investigation evidence only; no payment-serving approval.'});
        card.append(button,el('p','Operator review required. A failed payment-release gate remains failed.','surface-note'));
      }
      $('risk-candidates').append(card);
    }
    $('risk-verdict').hidden=!study?.verdict;$('risk-verdict').replaceChildren();
    if(study?.verdict){$('risk-verdict').append(el('h3','Validator decision'),el('p',study.verdict.summary||study.verdict.reason));for(const risk of study.verdict.risks||[])$('risk-verdict').append(el('p',risk,'surface-note'));$('risk-verdict').append(el('strong','Current payment protection is unchanged.'))}
    $('risk-run-details').hidden=!study;
    $('risk-run-json').textContent=study?JSON.stringify(publicEvidence({study_id:study.id,dataset_hash:study.dataset_hash,validation:study.manifest,notice:data.notice}),null,2):'';
    $('risk-access').textContent=token?'Operator token held in this page only. Requests are validated by the server.':data.operator_configured?'Operator access is configured.':'Configure MINTTOWN_RISK_OPERATOR_TOKEN on the server to enable research writes.';
    $('risk-seed').disabled=busy||!token;$('risk-start').disabled=busy||!token||!!active();$('risk-curate-submit').disabled=busy||!token||!data.reviewed_cases.length;
    $('risk-provider').querySelector('[value=gemini]').disabled=!data.live_available;
    if(!data.live_available)$('risk-provider').value='fake';
  }
  async function load(){
    clearTimeout(timer);data=await request();
    study=selected?await request('/studies/'+encodeURIComponent(selected)):data.latest;
    if(!initialized){$('risk-source').value=study?.source||(data.datasets.request_benchmark?.rows?'request_benchmark':data.datasets.benchmark.rows?'benchmark':'reviewed');initialized=true}
    if(study)selected=study.id;render();
    if(active()&&visible&&!document.hidden&&polls++<45)timer=setTimeout(()=>load().catch(e=>error(e.message)),3000);
  }
  async function write(path,body){
    if(busy)return;busy=true;error('');render();
    try{const result=await request(path,body);if(path==='/start'){selected=result.id;polls=0}await load()}
    catch(e){error(e.message)}finally{busy=false;render()}
  }
  async function show(on){
    if(visible!==on)window.scrollTo({top:0,behavior:'instant'});visible=on;clearTimeout(timer);document.querySelector('.demo-story').hidden=on;history.replaceState(null,'',on?'#models':'#agent');$('case-workspace').hidden=on;$('risk-view').hidden=!on;
    $('fraud-view').querySelector('.page-heading').hidden=on;
    $('risk-cases-tab').setAttribute('aria-pressed',String(!on));$('risk-models-tab').setAttribute('aria-pressed',String(on));
    if(on){polls=0;await load()}else if(onCases)await onCases();
  }
  $('risk-cases-tab').onclick=()=>show(false).catch(e=>error(e.message));$('risk-models-tab').onclick=()=>show(true).catch(e=>error(e.message));
  $('risk-source').onchange=render;
  $('risk-study-select').onchange=()=>{selected=$('risk-study-select').value;polls=0;load().catch(e=>error(e.message))};
  $('risk-unlock').onsubmit=e=>{e.preventDefault();token=$('risk-token').value;$('risk-token').value='';render()};
  $('risk-seed').onclick=()=>{const source=$('risk-source').value==='request_benchmark'?'request_benchmark':'benchmark';$('risk-source').value=source;write('/seed',{source})};
  $('risk-start').onclick=()=>write('/start',{request_id:crypto.randomUUID(),source:$('risk-source').value,provider:$('risk-provider').value});
  $('risk-curate').onsubmit=e=>{e.preventDefault();write('/curate',{report_id:$('risk-case').value,label:Number($('risk-label').value),note:$('risk-curation-note').value})};
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else if(visible){polls=0;load().catch(e=>error(e.message))}});
  return {show,load,pause:()=>{visible=false;clearTimeout(timer)}};
}
