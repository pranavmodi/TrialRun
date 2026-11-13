// The route selects evidence, never an active firm or a worker. All writes carry a run ID.
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty=x=>'<pre>'+esc(JSON.stringify(x,null,2))+'</pre>';
const button=(name,action,id='',primary=false)=>'<button data-action="'+action+'" data-id="'+esc(id)+'" class="'+(primary?'primary':'')+'">'+esc(name)+'</button>';
const path=id=>'/lab/attempts/'+encodeURIComponent(id);
const workspaceLink=(id,label)=>'<a href="'+path(id)+'/workspace" target="_blank" rel="noopener">'+label+'</a>';
const attemptLinks=id=>'<div class="attempt-links"><a href="'+path(id)+'">View attempt</a>'+workspaceLink(id,'View workspace')+'</div>';
let generation=0,timer,scenarios,agents,last='',current=null;
async function api(url,data){
  const res=await fetch(url,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const obj=await res.json();if(!res.ok)throw Error(obj.error||'Request failed');return obj;
}
const op=(name,args={})=>api('/api/ops/'+name,args);
function error(e){$('#toast').textContent=e.message;$('#toast').hidden=false}
function dialog(title,html){$('#modal-title').textContent=title;$('#modal-fields').innerHTML=html;$('#modal').showModal()}
function status(r){return r.outcome||r.results?.at(-1)?.status||({waiting:'Waiting for website inquiry',queued:'AI queued',working:'AI working',stopped:'AI stopped · ready to grade',failed:'AI failed · inspect evidence',interrupted:'AI interrupted'})[r.ai_state]||({queued:'Queued',working:'Running script',failed:'Worker failed',interrupted:'Interrupted'})[r.job_state]||(r.status==='running'?'Open':'Awaiting evaluation')}
function statusPill(text){const tone=/fail|interrupt/i.test(text)?'bad':/pass|stop|complete/i.test(text)?'good':'pending';return '<span class="status-pill '+tone+'">'+esc(text)+'</span>'}
function agentControls(){
  const opts=agents.profiles.filter(p=>agents.providers.some(v=>v.id===p.provider&&v.configured&&v.models.includes(p.model))).map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+' · '+esc(agents.providers.find(v=>v.id===p.provider).label)+' · v'+p.version+'</option>').join('');
  return '<div class="card engine"><p class="eyebrow">AGENT BENCH</p><h3>Model-backed agent</h3><p>Choose who works the inquiry. Both providers use the same firm tools and grading rules.</p>'+(agents.configured?
    '<label>Agent profile<select id="ai-profile">'+opts+'</select></label><div class="actions">'+button('Run with AI','ai','intake-only',true)+button('Edit profile','edit-agent')+button('New profile','new-agent')+'</div>':
    '<p>No inference provider configured. See the runner setup in the README.</p>')+'</div>';
}
function editProfile(p){
  const sources=agents.providers.filter(x=>x.configured);
  dialog(p?'Edit agent profile':'New agent profile','<form id="profile-form"><label>Name<input name="name" required maxlength="80" value="'+esc(p?.name)+'"></label><div class="form-grid"><label>Provider<select name="provider">'+sources.map(x=>'<option value="'+esc(x.id)+'" '+(p?.provider===x.id?'selected':'')+'>'+esc(x.label)+'</option>').join('')+'</select></label><label>Model or gateway agent<select name="model"></select></label></div><label>Standing instructions<textarea name="instructions" required maxlength="4000">'+esc(p?.instructions||'Work from the firm records. Verify the results of your actions.')+'</textarea></label><details><summary>Limits</summary><label>Maximum model turns<input name="max_turns" type="number" min="1" max="20" value="'+(p?.max_turns||8)+'"></label><label>Time limit (seconds)<input name="timeout_seconds" type="number" min="10" max="300" value="'+(p?.timeout_seconds||180)+'"></label></details><button class="primary">Save profile</button><p role="alert"></p></form>');
  const provider=$('[name=provider]'),update=()=>{$('[name=model]').innerHTML=sources.find(x=>x.id===provider.value).models.map(m=>'<option '+(p?.model===m?'selected':'')+'>'+esc(m)+'</option>').join('')};
  provider.onchange=update;update();
  $('#profile-form').onsubmit=async e=>{e.preventDefault();const f=e.target,b=f.querySelector('button.primary');b.disabled=true;try{
    const data=Object.fromEntries(new FormData(f));for(const k of ['max_turns','timeout_seconds'])data[k]=Number(data[k]);
    const saved=await op('agent.save',{...data,...(p?{id:p.id,version:p.version}:{})});
    agents=await op('agent.list');$('#modal').close();await route();$('#ai-profile').value=saved.id;
  }catch(err){f.querySelector('[role=alert]').textContent=err.message}finally{b.disabled=false}};
}
function library(){
  $('#section-kicker').textContent='EVALUATION LAB';$('#page-title').textContent='Scenario library';
  $('#description').textContent='Start an isolated attempt, watch its records change, and compare results. Leaving the page does not stop a run.';
  const card=s=>'<article class="card '+(s.id==='intake-only'?'feature':'')+'"><p class="eyebrow">'+(s.id==='intake-only'?'FEATURED SCENARIO &nbsp; / &nbsp; 01':'PRACTICE SCENARIO')+'</p><h2>'+esc(s.name)+'</h2><p>'+esc(s.description)+'</p><div class="actions">'+button(s.id==='intake-only'?'Try scripted example':'Validate fixture','reference',s.id,true)+button('Set up agent run','external',s.id)+'</div></article>';
  $('#content').innerHTML='<div class="launch-grid">'+card(scenarios.find(s=>s.id==='intake-only'))+agentControls()+'</div><details><summary>More scenarios and other runs</summary><div class="scenario-grid">'+scenarios.filter(s=>s.id!=='intake-only').map(card).join('')+'</div></details>'+
    '<details class="card"><summary>Run scenarios in parallel</summary><p>Select scenarios to run as independent background scripts. This checks the fixtures, not AI performance.</p><div class="parallel-options">'+scenarios.map(s=>'<label><input type="checkbox" name="batch" value="'+esc(s.id)+'">'+esc(s.name)+'</label>').join('')+'</div>'+button('Launch selected scenarios','batch')+'</details><h2>Attempts</h2><div id="attempts"></div>';
}
function listing(runs){
  $('#attempts').innerHTML=runs.length?'<div class="table-wrap"><table><thead><tr><th>Scenario</th><th>Attempt</th><th>Who works</th><th>Status</th><th>Actions</th></tr></thead><tbody>'+runs.slice().reverse().map(r=>'<tr><td>'+esc(r.name)+'</td><td>Attempt '+r.attempt_number+'</td><td>'+(r.execution_mode==='model_agent'?'AI · '+esc(r.agent_metadata.name):r.execution_mode==='reference_fixture'?'Script':'External agent')+'</td><td>'+statusPill(status(r))+'</td><td>'+attemptLinks(r.id)+'</td></tr>').join('')+'</tbody></table></div>':'<div class="empty"><strong>No attempts yet.</strong><p>Start a scripted example or choose a clerk to run a test.</p></div>';
}
function workspace(r){
  const s=r.state,lead=r.submission?s.leads.find(l=>l.id===r.submission.id):s.leads[0];
  const matter=s.matters.find(m=>m.id===lead?.matter_id),person=s.contacts.find(c=>c.id===matter?.contact_id);
  const intake=r.scenario.options.intake_only;
  const summary=intake?'<dl><dt>Inquiry</dt><dd>'+esc(lead?lead.name+' · '+lead.status:'No inquiry yet')+'</dd><dt>Linked contact</dt><dd>'+esc(person?.name||'None')+'</dd><dt>Linked potential case</dt><dd>'+esc(matter?.title||'None')+'</dd></dl>':'';
  const sets=Object.entries(s).filter(([k,v])=>Array.isArray(v)&&k!=='events');
  return '<section class="card" id="workspace-state"><p class="eyebrow">01 / RECORDS</p><h2>Workspace state</h2><p>Saved records in this attempt only.</p>'+summary+sets.map(([k,v])=>'<details data-key="set-'+esc(k)+'"><summary>'+esc(k.replaceAll('_',' '))+' ('+v.length+')</summary>'+v.map(x=>'<details data-key="rec-'+esc(x.id)+'"><summary>'+esc(x.name||x.title||x.subject||x.text||x.reason||k)+'</summary>'+pretty(Object.fromEntries(Object.entries(x).filter(([field])=>field!=='recording'&&field!=='base64')))+'</details>').join('')+'</details>').join('')+'</section>';
}
function activity(r){
  const events=r.state.events.slice(r.timeline_start).filter(e=>e.action==='tool.call'||Array.isArray(r.state[e.entity])||e.action==='run.finish');
  const who=e=>e.actor==='website'?'Website visitor':e.actor==='reference-script'||(e.actor==='evaluated-agent'&&r.execution_mode==='reference_fixture')?'Script':e.actor==='evaluated-agent'?'Agent':e.actor;
  return '<section class="card" id="activity"><p class="eyebrow">02 / EVENT LOG</p><h2>Agent actions &amp; activity</h2><ol><li>Lab · Starting records prepared</li>'+events.map(e=>{
    const rec=e.after||e.before||{},tool=e.action==='tool.call';
    const msg=tool?(e.detail.error?'Failed: ':'Called ')+e.detail.operation:e.actor==='website'&&e.entity==='leads'?'Submitted website form':e.entity==='leads'&&e.action==='update'?'Inquiry → '+rec.status:e.action==='run.finish'?'Evidence frozen':e.action+' · '+e.entity+' · '+(rec.name||rec.title||rec.speaker||'record');
    return '<li><details data-key="evt-'+esc(e.id)+'"><summary><strong>'+esc(who(e))+'</strong> · '+esc(msg)+'</summary>'+pretty(tool?e.detail:{before:e.before,after:e.after})+'</details></li>';
  }).join('')+'</ol></section>';
}
function detail(r){
  const opened=new Set([...document.querySelectorAll('details[open][data-key]')].map(e=>e.dataset.key));
  const script=r.execution_mode==='reference_fixture',open=r.status==='running'&&!r.job_state,res=r.results.at(-1);
  $('#section-kicker').textContent=r.ai_state?'MODEL-BACKED AI ATTEMPT':script?'SCRIPTED EXAMPLE · NOT AN AI EVALUATION':'EXTERNAL AGENT TEST';
  $('#page-title').textContent=r.scenario.name+' · Attempt '+r.attempt_number;$('#description').textContent=r.assignment;
  const ctl=['<a class="badge" href="'+path(r.id)+'/workspace" target="_blank" rel="noopener">View attempt workspace ↗</a>'];
  if(open&&r.watch_mode&&!r.submission)ctl.push(button('Submit Jamie’s website form','submit',r.id,true));
  if(open&&r.watch_mode==='scripted'&&r.submission&&r.state.leads.find(x=>x.id===r.submission.id)?.status==='new')ctl.push(button('Run scripted conversion','script',r.id,true));
  if(open&&r.conversation_id)ctl.push(button('Caller speaks','actor',r.id),button('Human role-play','roleplay',r.id));
  if(!['queued','working'].includes(r.ai_state)&&((open&&(!r.watch_mode||r.submission))||(r.status==='finished'&&!res&&!r.job_state)))ctl.push(button('Finish and evaluate','evaluate',r.id));
  if(r.status==='finished')ctl.push(button('Export evidence','export',r.id),button('Add expert review','review',r.id));
  const form=r.visitor_form&&!r.submission?'<details><summary>Preview Jamie’s website form</summary>'+pretty(r.visitor_form)+'</details>':'';
  const score=res?'<section class="card grade"><p class="eyebrow">EVALUATION RESULT</p><h2>'+res.passed+' of '+res.total+' checks passed</h2><p>Requires independent PI expert review for qualitative performance.</p>'+res.checks.map(c=>'<details data-key="check-'+esc(c.id)+'"><summary>'+statusPill(c.verdict)+' '+esc(c.label)+'</summary>'+pretty(c.evidence)+'</details>').join('')+'</section>':'';
  $('#content').innerHTML='<a href="/lab">← Back to evaluation lab</a><section class="card run-controls"><p class="eyebrow">ATTEMPT CONTROLS</p>'+statusPill(status(r))+'<div class="actions">'+ctl.join('')+'</div>'+form+(r.error?'<p class="error">'+esc(r.error)+'</p>':'')+'</section><div class="scenario-grid">'+workspace(r)+activity(r)+'</div>'+score+r.reviews.map(v=>'<p>Expert review: '+esc(v.verdict+' · '+v.reviewer+' · '+v.reason)+'</p>').join('');
  if(r.ai_state){
    const trace='<section class="card" id="runner"><p class="eyebrow">03 / DECISION LOG</p><h2>Model turns</h2><details data-key="profile"><summary>'+esc(r.agent_metadata.name)+' · v'+r.agent_metadata.version+' · '+esc(r.agent_metadata.model)+'</summary>'+pretty(r.agent_metadata)+'</details>'+
      (r.stop_reason?'<p>Stopped: '+esc(r.stop_reason)+'</p>':'')+(r.runner_trace||[]).map((e,i)=>{
        const changes=e.call?r.changes.filter(c=>c.tool_call_id===e.call):[];
        return '<details data-key="trace-'+i+'"><summary>Turn '+e.turn+' · '+esc(e.event)+' '+esc(e.tool||'')+'</summary>'+pretty(e)+
          (changes.length?'<strong>Workspace changes from this call</strong>'+pretty(changes.map(c=>({entity:c.entity,before:c.before,after:c.after}))):'')+'</details>'
      }).join('')+'</section>';
    $('#content .scenario-grid').insertAdjacentHTML('afterend',trace);
  }
  for(const d of document.querySelectorAll('details[data-key]'))if(opened.has(d.dataset.key))d.open=true;
}
async function route(){
  const g=++generation;clearTimeout(timer);current=null;last='';$('#toast').hidden=true;
  const id=location.pathname.match(/^\/lab\/attempts\/([^/]+)$/)?.[1];
  if(!id)library();else $('#content').innerHTML='<a href="/lab">Back to evaluation lab</a><p>Loading attempt…</p>';
  async function poll(){
    try{
      const r=id?await op('run.inspect',{id}):await op('run.list');
      if(g!==generation)return;
      const key=id?JSON.stringify([r.status,r.job_state,r.ai_state,r.runner_trace?.length,r.state.events.length,r.results.length,r.reviews.length,r.submission?.id]):JSON.stringify(r);
      if(key!==last){last=key;if(id){current=r;detail(r)}else listing(r)}
      if(id&&r.status!=='running'&&(!r.job_state||!['queued','working'].includes(r.job_state))&&r.results.length)return;
    }catch(e){if(g===generation)error(e)}
    if(g===generation)timer=setTimeout(poll,1500);
  }
  await poll();
}
async function start(el){
  const a=el.dataset.action,id=el.dataset.id;
  if(a==='edit-agent'||a==='new-agent'){editProfile(a==='edit-agent'?agents.profiles.find(p=>p.id===$('#ai-profile').value):null);return}
  if(a==='ai'){
    const r=await op('run.create',{scenario_id:id,watch_mode:'ai',profile_id:$('#ai-profile').value});
    history.pushState(null,'',path(r.id));await route();
  }else if(a==='external'||a==='reference'){
    const response=a==='reference'&&id!=='intake-only'?await op('run.launch',{scenario_ids:[id]}):await op('run.create',{scenario_id:id,...(id==='intake-only'?{watch_mode:a==='external'?'external':'scripted'}:{})});
    history.pushState(null,'',path(response.id||response.attempts[0].id));await route();
    if(response.agent_token)dialog('Agent connection details','<p>No agent has started. Give the external agent only this attempt’s token.</p>'+pretty({assignment:response.assignment,world:response.world,agent_token:response.agent_token}));
  }else if(a==='batch'){
    const ids=[...document.querySelectorAll('[name=batch]:checked')].map(x=>x.value);
    if(!ids.length||ids.length>8)throw Error('Select one to eight scenarios.');
    await op('run.launch',{scenario_ids:ids});await route();
  }else{
    if(!current||id!==current.id)return;
    if(a==='submit')await op('run.submit',{id});
    if(a==='script')await op('run.script',{id});
    if(a==='actor')await op('actor.respond',{id});
    if(a==='roleplay'){const text=prompt('Caller message');if(!text)return;await op('actor.respond',{id,text})}
    if(a==='evaluate'){await op('run.finish',{id});await op('run.grade',{id})}
    if(a==='review'){const reviewer=prompt('Reviewer name'),verdict=prompt('Verdict: pass, fail or uncertain'),reason=prompt('Reason');if(!reviewer||!verdict||!reason)return;await op('review.add',{id,reviewer,verdict,reason})}
    if(a==='export'){const data=await op('run.export',{id}),u=URL.createObjectURL(new Blob([JSON.stringify(data)],{type:'application/json'})),l=document.createElement('a');l.href=u;l.download='attempt-'+id+'.json';l.click();setTimeout(()=>URL.revokeObjectURL(u),1000);return}
    await route();
  }
}
document.addEventListener('click',e=>{const el=e.target.closest('[data-action]');if(el){el.disabled=true;start(el).catch(error).finally(()=>el.disabled=false)}});
$('#close-modal').onclick=()=>$('#modal').close();
window.addEventListener('popstate',()=>route().catch(error));
async function boot(){
  let session;try{session=await api('/api/session')}catch{$('#login').hidden=false;return}
  if(session.role!=='controller'){location.replace('/workspace');return}
  [scenarios,agents]=await Promise.all([op('scenario.list'),op('agent.list')]);$('#login').hidden=true;$('#app').hidden=false;await route();
}
$('#login-form').onsubmit=async e=>{e.preventDefault();try{await api('/api/login',{token:$('#token').value});$('#token').value='';await boot()}catch(err){$('#login-error').textContent=err.message}};
$('#logout').onclick=async()=>{await api('/api/logout',{});location.assign('/lab')};
boot().catch(error);
