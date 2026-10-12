export function createMeshUI({$,api,state,setPlaying,setBusy,refresh,error,addHandoff,route}){
  let catalogue=null,book=null,draft=null,run=null,editingRole='scientist',stop=false,working=false;
  const name=role=>catalogue?.roles[role]?.name||role;
  const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el};
  function stashPrompt(){if(draft)draft.prompts[editingRole]=$('mesh-prompt').value}
  function editRole(role){stashPrompt();editingRole=role;$('mesh-role-select').value=role;$('mesh-prompt').value=draft.prompts[role];$('mesh-role-purpose').textContent=catalogue.roles[role].purpose}
  function chooseBook(id){
    book=catalogue.playbooks.find(p=>p.id===id);draft=JSON.parse(JSON.stringify(book));
    $('mesh-role-select').replaceChildren();for(const role of book.role_ids)$('mesh-role-select').add(new Option(catalogue.roles[role].name,role));
    if(!book.role_ids.includes(editingRole))editingRole=book.role_ids.includes('scientist')?'scientist':book.role_ids[0];
    $('mesh-role-select').value=editingRole;
    $('mesh-playbook').value=id;$('mesh-objective').value=book.objective;$('mesh-turn-limit').value=book.max_turns;
    $('mesh-mission').value=book.objective;
    $('mesh-revision').textContent='Playbook v'+book.revision+' · '+book.domain;
    $('mesh-prompt').value=draft.prompts[editingRole];$('mesh-role-purpose').textContent=catalogue.roles[editingRole].purpose;
    $('mesh-description').textContent=book.objective;renderTarget();
  }
  function renderTarget(){
    const cases=state.data.cases.filter(c=>c.kind===book.domain).reverse();$('mesh-case-field').hidden=!['fraud','cashflow'].includes(book.domain);
    $('mesh-case').replaceChildren();for(const c of cases)$('mesh-case').add(new Option(c.id+' · '+c.title,c.id));
    if(run?.playbook.id===book.id&&run.inputs.case_id)$('mesh-case').value=run.inputs.case_id;
  }
  function render(){
    if(!catalogue)return;
    const roles=$('mesh-roles');roles.replaceChildren();
    for(const id of (run?.playbook.role_ids||book.role_ids)){
      const role=catalogue.roles[id];
      const count=run?.turns.filter(t=>t.from_role===id&&t.status==='completed').length||0;
      const active=run?.active_role===id&&['running','stepping'].includes(run.status);
      const button=node('button',undefined,'mesh-role'+(active?' current':count?' visited':''));button.type='button';
      button.append(node('span',role.code,'agent-avatar'),node('strong',role.name),node('small',active?'Active':count?count+' recorded turns':'Ready'));
      button.onclick=()=>{editRole(id);$('mesh-editor').open=true;$('mesh-prompt').focus()};roles.append(button);
    }
    const edges=new Map();for(const turn of run?.turns||[]){if(turn.to_role){const edge=name(turn.from_role)+' → '+name(turn.to_role);edges.set(edge,(edges.get(edge)||0)+1)}}
    $('mesh-connections').textContent=edges.size?[...edges].map(([edge,count])=>edge+(count>1?' ×'+count:'')).join(' · '):'A shared objective, tool results and permitted handoffs. Roles can ask for more evidence.';
    $('mesh-engine').textContent=catalogue.runtime.label;
    $('mesh-mode').textContent=(run?.mode||state.mode)==='gemini'?'Gemini chooses tools and handoffs · metered':'Local rehearsal · deterministic handoffs · $0';
    $('mesh-agent-notice').textContent=(run?.mode||state.mode)==='gemini'?'Agent decisions: Gemini selects each tool and recipient after reading the previous results.':'Live agents are off. This is a scripted tool rehearsal, not a demonstration of AI reasoning.';
    $('mesh-conversation-title').textContent=(run?.mode||state.mode)==='gemini'?'Agent decisions & evidence':'Tool rehearsal & evidence';
    $('mesh-run-state').textContent=run?run.playbook.name+' v'+run.playbook.revision+' · '+run.status.replaceAll('_',' ')+' · '+run.step+'/'+run.playbook.max_turns+' turns':'Choose a financial playbook to begin.';
    $('mesh-run').textContent=working?'Team is working…':run?.status==='running'?'Resume work':state.mode==='gemini'?'Start agent mission':'Rehearse the tools';$('mesh-run').disabled=working;
    $('mesh-pause').hidden=!working;$('mesh-save').disabled=working;$('mesh-playbook').disabled=working;$('mesh-new').disabled=working;$('mesh-case').disabled=working;$('mesh-history').disabled=working;$('mesh-mission').disabled=working;
    const feed=$('mesh-messages');feed.replaceChildren();
    if(!run)feed.append(node('p','Each handoff will show who asked for work, which tool ran, and the evidence returned.','surface-note'));
    for(const turn of run?.turns||[]){
      const item=node('li',undefined,'mesh-message'),avatar=node('span',catalogue.roles[turn.from_role].code,'agent-avatar'),body=node('div');
      body.append(node('strong',name(turn.from_role)+' → '+name(turn.to_role||turn.from_role)),node('small','Turn '+(turn.seq+1)+' · '+(turn.decision?.tool||turn.status)+' · '+(turn.provider==='baseline'?'Scripted rehearsal':turn.provider)));
      body.append(node('p',turn.decision?.message||turn.error||'Waiting for this agent’s response.'));
      if(turn.decision?.args&&Object.keys(turn.decision.args).length)body.append(node('small','Selected inputs: '+Object.entries(turn.decision.args).map(([k,v])=>k+' = '+v).join(' · ')));
      if(turn.artifact?.data.routing_gate)body.append(node('p',turn.artifact.data.routing_gate,'mesh-gate-note'));
      if(turn.error)body.append(node('p',turn.error,'mesh-gate-note'));
      const refs=turn.decision?.evidence_ids||[];if(refs.length)body.append(node('small','Evidence: '+refs.join(', ')));
      const detail=node('details',undefined,'world-details');detail.append(node('summary','Tool result & Google ADK trace'));
      detail.append(node('pre',JSON.stringify({artifact:turn.artifact,adk:turn.router_trace,usage:{input:turn.input_tokens,output:turn.output_tokens,estimated_usd:turn.cost_usd}},null,2),'science-evidence'));
      body.append(detail);item.append(avatar,body);feed.append(item);
    }
    $('mesh-outcome').hidden=!run||['running','stepping'].includes(run.status);
    if(run){
      $('mesh-outcome').textContent=run.error||({completed:run.playbook.domain==='customer_dna'?'Work cycle recorded. A pilot launch is not proof of business impact; inspect matured message/control outcomes.':'Outcome independently verified. Service receipts and evidence are saved.',withheld:'A quality gate withheld execution. No unsupported plan was applied.',needs_review:'The agent requested review instead of executing an uncertain plan.',budget_exhausted:'The playbook reached its limit. No further model calls were made.'}[run.status]||run.status);
    }
  }
  function activity(){
    if(!run)return;
    for(const id of ['investigation','macro-investigation','science-investigation','idle-agent'])$(id).hidden=true;
    $('mesh-investigation').hidden=false;$('mesh-activity-title').textContent=run.playbook.name;
    $('mesh-activity-copy').textContent=run.turns.at(-1)?.decision?.message||run.playbook.objective;
    $('mesh-activity-state').textContent=run.status.replaceAll('_',' ')+' · '+run.step+' turns · '+(run.mode==='gemini'?'Gemini':'local rehearsal');
    route('Agent mesh → '+name(run.active_role),'Five reusable BFSI roles share evidence and pass bounded tasks.');
  }
  async function load(){
    catalogue=await api('/api/mesh');const selected=book?.id||'customer-growth';
    $('mesh-playbook').replaceChildren();for(const p of catalogue.playbooks)$('mesh-playbook').add(new Option(p.name,p.id));
    chooseBook(selected);$('mesh-role-select').value=editingRole;if(run)$('mesh-mission').value=run.playbook.objective;
    $('mesh-history').replaceChildren();$('mesh-history').add(new Option('Select a saved run',''));
    for(const r of catalogue.runs)$('mesh-history').add(new Option(r.id+' · '+r.status+' · '+r.mode,r.id));
    render();
  }
  async function start(playbookId=null,caseId=null){
    if(working)return;setPlaying(false);error('');stop=false;working=true;setBusy(true);$('mesh-pause').textContent='Pause after turn';
    try{
      if(!catalogue)await load();
      if(playbookId||!run||run.status!=='running'){
        const id=playbookId||book.id;const target=caseId||(['fraud','cashflow'].includes(catalogue.playbooks.find(p=>p.id===id).domain)?$('mesh-case').value:null);
        const body={playbook_id:id,mode:state.mode,request_id:crypto.randomUUID()};if(target)body.case_id=target;
        if(!playbookId&&$('mesh-mission').value.trim())body.objective=$('mesh-mission').value.trim();
        run=await api('/api/mesh/start',body);chooseBook(id);$('mesh-mission').value=run.playbook.objective;
      }
      render();activity();
      while(run.status==='running'&&!stop){
        run=await api('/api/mesh/runs/'+run.id+'/step',{expected_step:run.step});
        const turn=run.turns.at(-1);if(turn?.decision)addHandoff(catalogue.roles[turn.from_role].code,name(turn.from_role)+' → '+name(turn.to_role),turn.decision.message);
        render();activity();await refresh();
      }
      await load();activity();
    }catch(e){
      error(e.message);if(run)run=await api('/api/mesh/runs/'+run.id).catch(()=>run);render();activity();await refresh().catch(()=>{});
    }finally{working=false;setBusy(false);render()}
  }
  $('mesh-run').onclick=()=>start();$('mesh-pause').onclick=()=>{stop=true;$('mesh-pause').textContent='Pausing after this turn…'};
  $('mesh-new').onclick=()=>{run=null;$('mesh-pause').textContent='Pause after turn';render()};
  $('mesh-playbook').onchange=e=>{run=null;chooseBook(e.target.value);render()};$('mesh-role-select').onchange=e=>editRole(e.target.value);
  $('mesh-save').onclick=async()=>{stashPrompt();error('');try{const updated=await api('/api/mesh/playbooks/'+book.id,{expected_revision:book.revision,objective:$('mesh-objective').value,prompts:draft.prompts,max_turns:Number($('mesh-turn-limit').value)});catalogue.playbooks=catalogue.playbooks.map(p=>p.id===updated.id?updated:p);chooseBook(updated.id);$('mesh-save-status').textContent='Saved v'+updated.revision+'. Existing runs keep their original prompts.'}catch(e){error(e.message)}};
  $('mesh-history').onchange=async e=>{if(!e.target.value||working)return;run=await api('/api/mesh/runs/'+e.target.value);chooseBook(run.playbook.id);$('mesh-mission').value=run.playbook.objective;render();activity()};
  return {load,start,choose:id=>{run=null;chooseBook(id);render()},runCase:caseId=>start(state.data.cases.find(c=>c.id===caseId)?.kind==='cashflow'?'cashflow-care':'fraud-response',caseId)};
}
