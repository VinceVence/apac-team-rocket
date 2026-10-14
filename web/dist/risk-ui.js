export function createRiskUI({$,state,error,onCases}){
  let data=null,study=null,token='',busy=false,timer=null,selected='',visible=false,polls=0,initialized=false;
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
  const active=()=>study&&['queued','scientist','planned','training','validator'].includes(study.status);
  const names={queued:'Queued',scientist:'Scientist choosing an experiment',planned:'Experiment planned',training:'Fitting models on the CPU',validator:'Validator checking results',needs_data:'More curated data needed',awaiting_model_review:'Candidate ready for human model review',rejected:'Study rejected',failed:'Study stopped',interrupted:'Study interrupted'};
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
    $('risk-mode').textContent=study?.model||(data.live_available?'Gemini available':'Fake-model rehearsal');
    $('risk-study-status').textContent=study?(names[study.status]||study.status)+' · '+(study.source==='benchmark'?'synthetic benchmark':'curated cases')+(study.error?' — '+study.error:''):'No saved experiments yet.';
    $('risk-hypothesis').textContent=study?.plan?.hypothesis||'The scientist chooses a hypothesis and model recipes after the dataset passes its checks.';
    $('risk-trail').replaceChildren();
    for(const t of study?.trace||[]){const row=el('li');row.append(el('strong',t.role.replaceAll('_',' ')+' · '+t.tool.replaceAll('_',' ')),el('p',t.purpose));$('risk-trail').append(row)}
    $('risk-candidates').replaceChildren();
    for(const c of study?.candidates||[]){
      const card=el('article',undefined,'risk-candidate '+c.status),head=el('div',undefined,'risk-candidate-heading');
      head.append(el('h3',c.name),el('span',c.status==='eligible'?'Gate passed':c.status==='reference'?'Reference':'Rejected','risk-result'));card.append(head);
      const numbers=el('div',undefined,'risk-score-pair');
      for(const [value,total,label] of [[c.test.caught,c.test.positives,'scams detected'],[c.test.false_holds,c.test.negatives,'legitimate requests held']]){
        const item=el('div');item.append(el('strong',`${value} / ${total}`),el('span',label));numbers.append(item);
      }
      card.append(numbers,el('p','Held-out '+(study.source==='benchmark'?'synthetic ':'')+'test · '+c.test.rows+' examples','surface-note'));
      card.append(el('p',c.preselected?'Selected using validation data':'Comparison only · not selected for review','surface-note'));
      const meter=el('meter');meter.min=0;meter.max=1;meter.value=c.test.recall;meter.setAttribute('aria-label',c.name+' synthetic scam recall');card.append(meter);
      const reasons=el('ul');for(const reason of c.reasons)reasons.append(el('li',reason));card.append(reasons);
      const details=el('details',undefined,'world-details');details.append(el('summary','Features, metrics & counterexamples'));
      const pre=el('pre',JSON.stringify({features:c.features,validation:c.validation,test:c.test,counterexamples:c.counterexamples,artifact_hash:c.artifact_hash},null,2),'science-evidence');details.append(pre);card.append(details);$('risk-candidates').append(card);
    }
    $('risk-verdict').hidden=!study?.verdict;$('risk-verdict').replaceChildren();
    if(study?.verdict){$('risk-verdict').append(el('h3','Validator decision'),el('p',study.verdict.summary||study.verdict.reason));for(const risk of study.verdict.risks||[])$('risk-verdict').append(el('p',risk,'surface-note'));$('risk-verdict').append(el('strong','Current payment protection is unchanged.'))}
    $('risk-run-details').hidden=!study;
    $('risk-run-json').textContent=study?JSON.stringify({study_id:study.id,dataset_hash:study.dataset_hash,manifest:study.manifest,model:study.model,budget:study.budget,notice:data.notice},null,2):'';
    $('risk-access').textContent=token?'Operator token held in this page only. Requests are validated by the server.':data.operator_configured?'Operator access is configured.':'Configure MINTTOWN_RISK_OPERATOR_TOKEN on the server to enable research writes.';
    $('risk-seed').disabled=busy||!token;$('risk-start').disabled=busy||!token||!!active();$('risk-curate-submit').disabled=busy||!token||!data.reviewed_cases.length;
    $('risk-provider').querySelector('[value=gemini]').disabled=!data.live_available;
    if(!data.live_available)$('risk-provider').value='fake';
  }
  async function load(){
    clearTimeout(timer);data=await request();
    study=selected?await request('/studies/'+encodeURIComponent(selected)):data.latest;
    if(!initialized){$('risk-source').value=study?.source||(data.datasets.benchmark.rows?'benchmark':'reviewed');initialized=true}
    if(study)selected=study.id;render();
    if(active()&&visible&&!document.hidden&&polls++<45)timer=setTimeout(()=>load().catch(e=>error(e.message)),3000);
  }
  async function write(path,body){
    if(busy)return;busy=true;error('');render();
    try{const result=await request(path,body);if(path==='/start'){selected=result.id;polls=0}await load()}
    catch(e){error(e.message)}finally{busy=false;render()}
  }
  async function show(on){
    visible=on;clearTimeout(timer);document.querySelector('.demo-story').hidden=on;history.replaceState(null,'',on?'#models':'#agent');$('case-workspace').hidden=on;$('risk-view').hidden=!on;
    $('fraud-view').querySelector('.page-heading').hidden=on;
    $('risk-cases-tab').setAttribute('aria-pressed',String(!on));$('risk-models-tab').setAttribute('aria-pressed',String(on));
    if(on){polls=0;await load()}else if(onCases)await onCases();
  }
  $('risk-cases-tab').onclick=()=>show(false).catch(e=>error(e.message));$('risk-models-tab').onclick=()=>show(true).catch(e=>error(e.message));
  $('risk-source').onchange=render;
  $('risk-study-select').onchange=()=>{selected=$('risk-study-select').value;polls=0;load().catch(e=>error(e.message))};
  $('risk-unlock').onsubmit=e=>{e.preventDefault();token=$('risk-token').value;$('risk-token').value='';render()};
  $('risk-seed').onclick=()=>{$('risk-source').value='benchmark';write('/seed',{})};
  $('risk-start').onclick=()=>write('/start',{request_id:crypto.randomUUID(),source:$('risk-source').value,provider:$('risk-provider').value});
  $('risk-curate').onsubmit=e=>{e.preventDefault();write('/curate',{report_id:$('risk-case').value,label:Number($('risk-label').value),note:$('risk-curation-note').value})};
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else if(visible){polls=0;load().catch(e=>error(e.message))}});
  return {show,load,pause:()=>{visible=false;clearTimeout(timer)}};
}
