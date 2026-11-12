// Controller's read-only lens on one attempt. Never replace the manual firm's world ID.
let watching=null, watchPage='leads', watchData=null, watchTimer, watchRequest=0;
const watchTabs={leads:'Leads inbox',matters:'Intake pipeline',contacts:'Contacts',tasks:'Tasks & callbacks',
  messages:'Communications',appointments:'Calendar',documents:'Documents',escalations:'Attorney handoffs',
  conversations:'Conversations',events:'Activity'};
async function enterWatch(id){
  clearTimeout(watchTimer);watching=id;watchPage='leads';watchData=null;
  sessionStorage.setItem('watched-intake',id);
  $('#world-select').hidden=true;$('#world-label').hidden=false;$('#world-label').textContent='Viewing test';
  $('#reset-demo').hidden=true;$('.sidebar-bottom a').hidden=true;
  $('.nav-label').textContent='TEST WORKSPACE';
  $('#nav').innerHTML=Object.entries(watchTabs).map(([k,v])=>btn(v,'watch-page','data-page="'+k+'"')).join('');
  $('#clock').textContent='';$('#page-actions').innerHTML=btn('Back to evaluation lab','leave-watch');
  $('#content').textContent='Loading attempt…';
  await refreshWatch(true);
}
async function refreshWatch(force=false){
  const id=watching,seq=++watchRequest;
  clearTimeout(watchTimer);
  try{
    const r=await op('run.inspect',{id});
    if(watching!==id||seq!==watchRequest)return;
    const changed=!watchData||watchData.state.events.length!==r.state.events.length||watchData.status!==r.status||watchData.results.length!==r.results.length;
    watchData=r;
    if(force||changed)drawWatch(r);
  }finally{
    if(watching===id&&seq===watchRequest&&!watchData?.results.length)
      watchTimer=setTimeout(()=>refreshWatch().catch(err=>notify(err.message,true)),1500);
  }
}
function drawWatch(r){
  const script=r.watch_mode==='scripted',lead=r.state.leads.find(l=>l.id===r.submission?.id);
  const result=r.results.at(-1);
  $('#world-label').textContent='Viewing test · Attempt '+r.attempt_number;
  $('#section-kicker').textContent=script?'SCRIPTED EXAMPLE · NOT AN AI EVALUATION':'EXTERNAL AGENT TEST';
  $('#page-title').textContent=watchTabs[watchPage];
  $('#page-description').textContent='Only records from this attempt are shown. Your manual firm is unchanged.';
  $('#nav').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.page===watchPage));
  let control='';
  if(!r.submission)control=btn('Submit Jamie’s website form','watch-submit','','primary');
  else if(script&&lead?.status==='new'&&r.status==='running')control=btn('Run scripted conversion','watch-script','','primary');
  if(r.submission&&!result)control+=btn('Finish and evaluate','watch-grade');
  const who=e=>({'website':'Website visitor','reference-script':'Script','evaluated-agent':'Agent'})[e.actor]||e.actor;
  const events=r.state.events.slice(r.timeline_start);
  const changes=new Set(r.changes.map(c=>c.id));
  const history=events.filter(e=>changes.has(e.id)||e.action==='tool.call');
  const items=history.map(e=>{
    const record=e.after||e.before||{};
    const title=e.actor==='website'&&e.entity==='leads'?'Submitted website form':
      e.action==='tool.call'?(e.detail.error?'Failed: ':'Called ')+e.detail.operation:
      e.action==='update'&&e.entity==='leads'?'Inquiry → '+record.status:
      e.action+' · '+e.entity+' · '+(record.name||record.title||'record');
    return '<li><details><summary><strong>'+esc(who(e))+'</strong> · '+esc(title)+'</summary>'+pretty(e.detail?.operation?{operation:e.detail.operation,error:e.detail.error}:record)+'</details></li>';
  }).join('');
  const next=!r.submission?'The inbox starts empty. Jamie has not submitted the form yet.':
    lead?.status==='converted'?'The inquiry is converted. Inspect the linked contact and potential case.':
    (script?'Jamie’s inquiry is new. The script has not converted it yet.':'Jamie’s inquiry is new. Connect your external agent; this view updates as it works.');
  const score=result?'<section class="card"><h2>'+esc(result.passed)+' of '+esc(result.total)+' checks passed</h2>'+result.checks.map(c=>'<details><summary>'+badge(c.verdict,c.verdict==='failed'?'bad':'')+' '+esc(c.label)+'</summary>'+pretty(c.evidence)+'</details>').join('')+'</section>':'';
  const timeline='<section class="card"><h2>Attempt activity</h2><ol><li>Lab · Empty Leads inbox prepared</li>'+items+'</ol></section>';
  const records=watchPage==='events'?'':'<section class="card"><h2>'+esc(watchTabs[watchPage])+'</h2>'+
    (r.state[watchPage].map(x=>'<details><summary>'+esc(x.name||x.title||x.subject||x.reason||watchPage)+' '+badge(x.status||x.stage||'record')+'</summary>'+pretty(x)+'</details>').join('')||'<p>No records in this '+(watchPage==='leads'?'inbox':'section')+' yet.</p>')+'</section>';
  const form=!r.submission?'<section class="card"><p class="eyebrow">SIMULATED WEBSITE VISITOR</p><h2>Jamie’s website form</h2>'+
    Object.entries(r.visitor_form).map(([key,value])=>'<p><strong>'+esc(schemas.leads[key]?.label||key)+'</strong>: '+esc(value)+'</p>').join('')+'</section>':'';
  $('#content').innerHTML=form+'<section class="callout"><strong>'+esc(next)+'</strong><div class="actions">'+control+'</div></section>'+records+timeline+score;
}
async function watchAction(el){
  const action=el.dataset.action,id=watching;
  if(action==='watch-page'){watchPage=el.dataset.page;if(watchData)drawWatch(watchData);return}
  if(action==='leave-watch'){
    clearTimeout(watchTimer);watching=null;watchData=null;sessionStorage.removeItem('watched-intake');
    $('.nav-label').textContent='FIRM WORKSPACE';$('.sidebar-bottom a').hidden=false;
    selectedRun=null;page='lab';await boot();return;
  }
  el.disabled=true;
  try{
    if(action==='watch-submit')await op('run.submit',{id});
    else if(action==='watch-script')await op('run.script',{id});
    else if(action==='watch-grade'){await op('run.finish',{id});await op('run.grade',{id})}
    if(watching===id)await refreshWatch(true);
  }finally{el.disabled=false}
}
