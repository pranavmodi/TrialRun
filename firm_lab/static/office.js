// Read-only controller view. Rewind actual record images; never run or re-enact tools.
const officeDesk=(()=>{
  const names={monitor:'Intake monitor',phone:'Desk phone',folder:'Case folder',pad:'Callback pad',tray:'Lawyer’s inbox'};
  const descriptions={monitor:'Inspect the leads inbox for this firm.',phone:'Read recorded conversation turns in this attempt.',folder:'Compare the submitted inquiry with the saved case.',pad:'Inspect callback tasks and their deadlines.',tray:'See handoffs that were actually recorded for attorney review.'};
  const tables=['leads','contacts','matters','tasks','escalations','staff','turns','conversations','messages','appointments','documents','notes'];
  let run=null,selection=null,cursor=null,view=null,mount=null,leadCount=0,renderer=null,model=false,arrival=0,computer=null;
  const actions={monitor:'CRM',phone:'Calls',folder:'Cases',pad:'Callbacks',tray:'Handoffs'};
  function events(){return run.state.events.slice(run.timeline_start).filter(e=>tables.includes(e.entity)||e.action==='tool.call'||e.action==='run.finish')}
  function state(ev,i){
    const rows=Object.fromEntries(tables.map(t=>[t,new Map((run.state[t]||[]).map(r=>[r.id,r]))]));
    for(let j=ev.length-1;j>=i;j--){const e=ev[j],m=rows[e.entity];if(!m||!e.record_id)continue;
      if(e.before)m.set(e.record_id,e.before);else m.delete(e.record_id)}
    return Object.fromEntries(tables.map(t=>[t,[...rows[t].values()]]));
  }
  const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list=(rows,f,empty)=>rows.length?'<ul>'+rows.map(r=>'<li>'+f(r)+'</li>').join('')+'</ul>':'<p>'+empty+'</p>';
  const station=k=>'<button type="button" data-station="'+k+'" title="'+descriptions[k]+'" aria-label="'+names[k]+'" aria-pressed="false">'+actions[k]+'</button>';
  function shell(){
    const root=document.createElement('section');root.id='office-desk';root.setAttribute('aria-label','Interactive law office');
    root.innerHTML='<div class="room-stage"><span class="room-hover" hidden></span></div>'+
      '<header class="room-top"><div><span class="room-overline">TRIALRUN &nbsp; / &nbsp; FIELD OFFICE</span><h1>Harbor &amp; Stone</h1><span class="room-caption">Personal injury practice</span></div><a class="room-exit" href="/lab/attempts/'+encodeURIComponent(run.id)+'">Back to attempt</a></header>'+
      '<div class="room-camera" aria-label="Camera controls"><button data-view title="Switch between the seated desk and the orbital room model">Room model</button><button data-camera="in" title="Zoom in" aria-label="Zoom in">+</button><button data-camera="out" title="Zoom out" aria-label="Zoom out">−</button><button data-camera="home" title="Return to the opening view" aria-label="Reset camera">⌂</button></div>'+
      '<aside class="room-inspector" hidden><button class="room-dismiss" aria-label="Close station">×</button><div class="desk-detail"></div></aside>'+
      '<footer class="room-dock"><div class="room-dock-head"><span class="room-status"></span><span class="room-guide">Drag to orbit · Scroll or pinch to zoom</span></div><div class="room-nav" aria-label="Office stations">'+Object.keys(names).map(station).join('')+'<button data-replay aria-expanded="false">Replay</button></div><div class="desk-rail" hidden></div></footer>';
    root.querySelector('.room-nav').insertAdjacentHTML('beforeend','<button data-call-launch>Start call scenario</button>');
    document.querySelector('#content').replaceChildren(root);mount=root;document.title='Harbor & Stone · Attempt '+run.attempt_number+' · TrialRun';
    import('/static/office-scene.js').then(mod=>{if(root!==mount)return;renderer=mod;loadView()}).catch(()=>{if(root===mount)fallback()});
  }
  function fallback(){view?.destroy();view=null;mount.classList.add('room-flat');mount.dataset.renderer='flat';mount.querySelector('.room-guide').textContent='Click an object or choose a station below';
    const stage=mount.querySelector('.room-stage');if(!stage.querySelector('.flat-photo'))stage.insertAdjacentHTML('afterbegin','<div class="flat-photo" aria-hidden="true">'+
      Object.entries(names).map(([k,n])=>'<button tabindex="-1" data-photo="'+k+'" title="'+n+'"></button>').join('')+'</div>')}
  function loadView(){view?.destroy();view=null;if(!renderer)return;try{
    view=(model?renderer.enter:renderer.enterTour)(mount.querySelector('.room-stage'),pick,fallback);view.count(leadCount);
    if(mount.dataset.ringing==='true'){view.focus('phone');view.ring(mount.dataset.phoneLit==='true')}
    else if(selection)view.focus(selection);mount.dataset.renderer='webgl';mount.dataset.cameraMode=model?'model':'desk';
    mount.querySelector('[data-view]').textContent=model?'Desk view':'Room model';
    mount.querySelector('.room-guide').textContent=model?'Drag to orbit · Scroll or pinch to zoom':'Drag to look around · Click the monitor to enter';
  }catch{fallback()}}
  function ring(active,lit){
    if(!mount)return;
    if(active&&mount.dataset.ringing!=='true'){mount.dataset.framing='phone';view?.focus('phone')}
    mount.dataset.ringing=String(active);mount.dataset.phoneLit=String(lit);view?.ring(lit)
  }
  function postState(){
    const f=computer?.querySelector('iframe');if(!f?.contentWindow||!run)return;
    const ev=events(),s=state(ev,Math.min(cursor??ev.length,ev.length));
    f.contentWindow.postMessage({kind:'office.crm.state',id:run.id,state:s,number:run.attempt_number,scenario:run.scenario.name,
      mode:cursor!==null?'Replay · Event '+cursor+' / '+ev.length:run.status==='running'?'Live':'Finished · Frozen result'},location.origin)
  }
  function openComputer(){
    if(!mount||selection!=='monitor'||computer)return;
    const d=document.createElement('dialog');d.className='office-computer';d.setAttribute('aria-label','Intake computer');
    d.innerHTML='<header><div><span>HARBOR &amp; STONE</span> &nbsp; / &nbsp; Intake computer</div><button type="button" data-return>Back to office</button></header><iframe title="Attempt CRM" src="/lab/attempts/'+encodeURIComponent(run.id)+'/workspace?display=computer#leads"></iframe>';
    mount.append(d);computer=d;d.querySelector('[data-return]').onclick=()=>d.close();d.addEventListener('close',()=>{if(computer!==d)return;computer=null;d.remove();if(mount)dismiss()},{once:true});
    d.showModal();d.querySelector('button').focus();
  }
  window.addEventListener('message',evt=>{if(evt.origin!==location.origin||!computer||evt.source!==computer.querySelector('iframe')?.contentWindow||evt.data?.id!==run?.id)return;
    if(evt.data.kind==='office.crm.ready')postState();if(evt.data.kind==='office.crm.exit')computer.close()});
  function pick(k){clearTimeout(arrival);selection=k;view?.focus(k);paint();
    if(k==='phone'&&run.call_mode&&run.status==='running'&&cursor===null){mount.querySelector('.room-inspector').hidden=true;officePhone.openPanel();return}
    if(k==='monitor'){if(!view||matchMedia('(prefers-reduced-motion: reduce)').matches)openComputer();else arrival=setTimeout(openComputer,520)}
    else mount.querySelector('.room-dismiss').focus({preventScroll:true})}
  function dismiss(){clearTimeout(arrival);const k=selection;selection=null;view?.home();paint();if(k)mount.querySelector('[data-station="'+k+'"]').focus({preventScroll:true})}
  function paint(){
    const root=document.querySelector('#office-desk');if(!root||!run)return;
    const ev=events(),i=Math.min(cursor??ev.length,ev.length),s=state(ev,i),event=ev[i-1];
    const link=t=>cursor===null?'<a class="desk-link" target="_blank" rel="noopener" href="/lab/attempts/'+encodeURIComponent(run.id)+'/workspace#'+t+'">Open '+({leads:'CRM inbox',matters:'case records',tasks:'tasks',escalations:'attorney handoffs',conversations:'conversation records'})[t]+' in workspace ↗</a>':'';
    const inquiry=s.leads.find(l=>l.id===run.submission?.id)||(!run.watch_mode?s.leads.find(l=>l.matter_id===run.target_matter&&run.target_matter)||(!run.target_matter?s.leads[0]:null):null);
    const matter=s.matters.find(m=>m.id===(inquiry?.matter_id||run.target_matter)),person=s.contacts.find(c=>c.id===matter?.contact_id);
    const callbacks=s.tasks.filter(t=>t.kind==='callback'),staff=id=>s.staff.find(x=>x.id===id)?.name||'Unassigned';
    // Seeded, non-interactive inquiries need the original snapshot too:
    // never silently compare an edited lead with another copy of itself.
    const orig=inquiry&&ev.find(v=>v.entity==='leads'&&v.record_id===inquiry.id);
    const forms=run.submission||orig?.before||orig?.after||inquiry;
    const conv=s.conversations.find(c=>c.id===run.conversation_id);
    const audio=cursor===null&&conv?.recording&&['audio/wav','audio/webm','audio/mpeg','audio/ogg'].includes(conv.recording_mime)?'<p>Attached test recording</p><audio controls preload="none" aria-label="Conversation recording" src="data:'+e(conv.recording_mime)+';base64,'+e(conv.recording)+'"></audio>':'';
    const fields=[['Name','name',person],['Callback','phone',person],['Email','email',person],['Incident date','incident_date',matter],['Location','location',matter],['What happened','summary',matter],['Injuries','injury',matter],['Follow-up consent','consent',matter]];
    const panel={
      monitor:()=>list(s.leads,l=>'<strong>'+e(l.name)+'</strong> · '+e(l.status),'No inquiries in the inbox.')+link('leads'),
      folder:()=> (inquiry&&forms?'<div class="desk-compare"><table><thead><tr><th>Detail</th><th>Original inquiry</th><th>Saved record</th></tr></thead><tbody>'+fields.map(([label,k,r])=>'<tr><th>'+label+'</th><td>'+e(forms[k]??'Not supplied')+'</td><td>'+e(r?.[k]??'Not recorded')+'</td></tr>').join('')+'</tbody></table></div>':matter?'<p>'+e(matter.title)+' · '+e(matter.stage)+'</p>':'<p>No inquiry or linked case to inspect yet.</p>')+link('matters'),
      phone:()=>list(s.turns.filter(t=>t.conversation_id===run.conversation_id),t=>'<strong>'+e(t.speaker)+'</strong> · '+e(t.text),'No caller conversation in this scenario at this point.')+audio+link('conversations'),
      pad:()=>list(callbacks,t=>e(t.title)+' · '+e(t.status)+' · '+e(staff(t.assignee_id))+' · Due '+e(t.due_at),'No callback tasks recorded.')+link('tasks'),
      tray:()=>list(s.escalations,t=>'<strong>'+e(t.reason)+'</strong> · '+e(staff(t.assignee_id))+' · '+e(t.status)+' · '+e(s.matters.find(m=>m.id===t.matter_id)?.title||'Case not found'),'No attorney handoffs recorded.')+link('escalations')
    };
    const n=s.leads.filter(x=>x.status==='new').length;
    const mode=cursor!==null?'Replay':run.status==='running'?'Live attempt':'Frozen attempt';
    const actor=event?.actor==='website'?'Website visitor':event?.actor==='evaluated-agent'&&run.execution_mode==='reference_fixture'?'Script':event?.actor;
    const caption=!event?'Starting records':event.action==='tool.call'?(event.detail?.error?'Unsuccessful tool call: ':'Tool call: ')+event.detail?.operation:event.action==='run.finish'?'Evidence frozen':event.entity+' · '+event.action;
    if(n!==leadCount){leadCount=n;view?.count(n)}
    root.querySelector('.room-status').textContent='Attempt '+run.attempt_number+'  /  '+mode;
    root.querySelectorAll('[data-station]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.station===selection));
    root.querySelector('.room-inspector').hidden=!selection||selection==='monitor'||(selection==='phone'&&run.call_mode&&run.status==='running'&&cursor===null);
    if(selection&&selection!=='monitor')root.querySelector('.desk-detail').innerHTML='<small class="room-overline">DESK STATION &nbsp; / &nbsp; '+actions[selection].toUpperCase()+'</small><h2>'+names[selection]+'</h2><p>'+descriptions[selection]+'</p>'+panel[selection]();
    if(computer)postState();
    officePhone.render(run,cursor===null);
    root.querySelector('.desk-rail').innerHTML='<div><small>RECORDED EVENTS &nbsp; '+i+' / '+ev.length+'</small><p>'+e(actor?actor+' · ':'')+e(caption)+'</p></div><div class="desk-buttons"><button data-step="back" '+(!i?'disabled':'')+'>Previous</button><button data-step="next" '+(i===ev.length?'disabled':'')+'>Next</button><button data-step="end" '+(cursor===null?'disabled':'')+'>'+(run.status==='running'?'Back to live':'Final state')+'</button></div>';
  }
  document.addEventListener('click',evt=>{const b=evt.target.closest('#office-desk button');if(!b||!run)return;
    if(b.matches('.room-dismiss')){dismiss();return}
    if(b.dataset.photo){pick(b.dataset.photo);return}
    if(b.hasAttribute('data-view')){dismiss();model=!model;loadView();return}
    if(b.hasAttribute('data-replay')){const rail=mount.querySelector('.desk-rail');rail.hidden=!rail.hidden;b.setAttribute('aria-expanded',!rail.hidden);return}
    if(b.dataset.camera){if(b.dataset.camera==='home')dismiss();else view?.zoom(b.dataset.camera==='in'?.75:1.33);return}
    if(b.dataset.station){pick(b.dataset.station);return}
    if(!b.dataset.step)return;
    const n=events().length,i=cursor??n;cursor=b.dataset.step==='end'?null:Math.max(0,Math.min(n,i+(b.dataset.step==='back'?-1:1)));
    const selector='[data-step="'+b.dataset.step+'"]';
    paint();(document.querySelector('#office-desk '+selector+':not(:disabled)')||document.querySelector('#office-desk [data-replay]')).focus({preventScroll:true});
  });
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&mount&&selection&&!computer)dismiss()});
  return {ring,render(r){
    if(mount&&run?.id!==r.id){
      officePhone.leave();clearTimeout(arrival);computer?.remove();computer=null;selection=null;cursor=null;leadCount=-1;
      mount.querySelector('.room-exit').href=path(r.id);mount.querySelector('.desk-rail').hidden=true;
      mount.querySelector('[data-replay]').setAttribute('aria-expanded','false');
      document.title='Harbor & Stone · Attempt '+r.attempt_number+' · TrialRun';
    }
    run=r;if(!mount)shell();paint()
  },leave(){officePhone.leave();clearTimeout(arrival);computer?.remove();computer=null;view?.destroy();view=null;mount=null;run=null;selection=null;cursor=null;leadCount=0;model=false;renderer=null}};
})();
