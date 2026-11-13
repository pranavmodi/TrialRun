// Observer only: never load the practice app, choose a world, or issue a write.
const id=location.pathname.split('/')[3];
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tabs={leads:'Leads inbox',matters:'Intake pipeline',contacts:'Contacts',tasks:'Tasks & callbacks',
  messages:'Communications',appointments:'Calendar',documents:'Documents',escalations:'Attorney handoffs',
  notes:'Case notes',conversations:'Conversations',staff:'Staff'};
const refs={contact_id:'contacts',matter_id:'matters',owner_id:'staff',assignee_id:'staff',staff_id:'staff'};
const fields={summary:'What happened',injury:'Injuries or treatment',matter_id:'Linked case',contact_id:'Contact',
  owner_id:'Assigned staff',consent:'Contact permission'};
const title=r=>r.name||r.title||r.subject||r.reason||r.body||r.channel||'Record';
const label=k=>fields[k]||k.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
const link=(tab,rec)=>'<a href="#'+tab+'/'+encodeURIComponent(rec.id)+'">'+esc(title(rec))+'</a>';
let attempt=null;
$('#back').href='/lab/attempts/'+encodeURIComponent(id);
$('#nav').innerHTML=Object.entries(tabs).map(([k,v])=>'<button type="button" data-page="'+k+'">'+v+'</button>').join('');
$('#nav').onclick=e=>{if(e.target.dataset.page)location.hash=e.target.dataset.page};
function render(){
  if(!attempt)return;
  const [key,selected]=location.hash.slice(1).split('/');
  const tab=Object.hasOwn(tabs,key)?key:'leads',s=attempt.state,rows=s[tab]||[];
  $('#title').textContent=tabs[tab];
  for(const b of $('#nav').children)b.classList.toggle('active',b.dataset.page===tab);
  let html='';
  if(selected){
    const rec=rows.find(r=>r.id===selected);
    html='<a href="#'+tab+'">← '+tabs[tab]+'</a>';
    if(!rec)html+='<p>Record not found in this attempt.</p>';
    else{
      html+='<section class="card"><h2>'+esc(title(rec))+'</h2><dl>';
      for(const [k,v] of Object.entries(rec)){
        if(['id','version','recording','base64'].includes(k)||v==null||v===''||typeof v==='object')continue;
        const dest=refs[k],related=dest&&s[dest]?.find(x=>x.id===v);
        html+='<dt>'+esc(label(k))+'</dt><dd>'+(related?link(dest,related):esc(v===true?'Yes':v===false?'No':v))+'</dd>';
      }
      html+='</dl></section>';
      if(tab==='contacts')html+='<h2>Linked cases</h2>'+s.matters.filter(m=>m.contact_id===rec.id).map(m=>link('matters',m)).join('<br>');
      if(tab==='conversations')html+=(s.turns||[]).filter(t=>t.conversation_id===rec.id).map(t=>'<p><strong>'+esc(t.speaker)+'</strong> · '+esc(t.text)+'</p>').join('');
    }
  }else if(tab==='matters'){
    const stages=[...new Set([...(s.meta?.policy?.stages||[]),...rows.map(m=>m.stage)])];
    html='<div class="board">'+stages.map(stage=>'<section class="column"><div class="column-heading">'+esc(stage)+'</div>'+rows.filter(m=>m.stage===stage).map(m=>'<div class="card">'+link(tab,m)+'</div>').join('')+'</section>').join('')+'</div>';
  }else{
    html=rows.length?'<div class="table-wrap"><table><thead><tr><th>Record</th><th>Status or role</th><th>Linked case</th></tr></thead><tbody>'+rows.map(r=>{
      const m=s.matters.find(m=>m.id===r.matter_id);
      return '<tr><td>'+link(tab,r)+'</td><td>'+esc(r.status||r.role||r.channel||'—')+'</td><td>'+(m?link('matters',m):'—')+'</td></tr>';
    }).join('')+'</tbody></table></div>':'<p class="empty">No '+esc(tab)+' in this attempt.</p>';
  }
  $('#content').innerHTML=html;
}
window.addEventListener('hashchange',render);
let previous='';
async function refresh(){
  let retry=true;
  try{
    const res=await fetch('/api/ops/run.inspect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
    if(!res.ok){retry=res.status>=500;throw Error(res.status===401?'Sign in to the Evaluation Lab to view this attempt.':'Attempt unavailable.')}
    const data=await res.json();
    attempt=data;
    $('#attempt').textContent='Attempt '+data.attempt_number+' · Read-only';
    $('#scenario').textContent=data.scenario.name;
    document.title='Attempt '+data.attempt_number+' · '+data.scenario.name+' · TrialRun';
    retry=data.status==='running';
    $('#mode').textContent=retry?'Live':'Finished'+(data.status==='finished'?' · Frozen result':' · '+data.status);
    const version=JSON.stringify(data.state);
    if(version!==previous){render();previous=version}
  }catch(e){
    $('#mode').textContent=e.message;
    if(!retry){attempt=null;$('#content').replaceChildren()}
  }finally{if(retry)setTimeout(refresh,1500)}
}
refresh();
