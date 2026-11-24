// Read-only controller view. Rewind actual record images; never run or re-enact tools.
const officeDesk=(()=>{
  const names={monitor:'Intake monitor',phone:'Desk phone',folder:'Case folder',pad:'Callback pad',tray:'Lawyer’s inbox'};
  const descriptions={monitor:'Inspect the leads inbox for this firm.',phone:'Read recorded conversation turns in this attempt.',folder:'Compare the submitted inquiry with the saved case.',pad:'Inspect callback tasks and their deadlines.',tray:'See handoffs that were actually recorded for attorney review.'};
  const tables=['leads','contacts','matters','tasks','escalations','staff','turns','conversations'];
  let run=null,selection='monitor',cursor=null;
  function events(){return run.state.events.slice(run.timeline_start).filter(e=>tables.includes(e.entity)||e.action==='tool.call'||e.action==='run.finish')}
  function state(ev,i){
    const rows=Object.fromEntries(tables.map(t=>[t,new Map((run.state[t]||[]).map(r=>[r.id,r]))]));
    for(let j=ev.length-1;j>=i;j--){const e=ev[j],m=rows[e.entity];if(!m||!e.record_id)continue;
      if(e.before)m.set(e.record_id,e.before);else m.delete(e.record_id)}
    return Object.fromEntries(tables.map(t=>[t,[...rows[t].values()]]));
  }
  const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list=(rows,f,empty)=>rows.length?'<ul>'+rows.map(r=>'<li>'+f(r)+'</li>').join('')+'</ul>':'<p>'+empty+'</p>';
  const station=k=>'<button type="button" class="desk-point point-'+k+'" data-station="'+k+'" title="'+descriptions[k]+'" aria-pressed="'+(selection===k)+'">'+names[k]+'</button>';
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
    root.innerHTML='<header class="desk-head"><div><small>HARBOR &amp; STONE &nbsp; / &nbsp; FIELD OFFICE</small><h2>The intake desk</h2></div><span>'+mode+' · '+run.attempt_number+'</span></header>'+
      '<div class="desk-room"><div class="desk-display" aria-hidden="true"><small>HARBOR &amp; STONE</small><b>Leads inbox</b><span>'+n+' new '+(n===1?'inquiry':'inquiries')+'</span></div><div class="desk-points">'+Object.keys(names).map(station).join('')+'</div></div>'+
      '<div class="desk-rail"><div><small>OFFICE REPLAY &nbsp; '+i+' / '+ev.length+'</small><p>'+e(actor?actor+' · ':'')+e(caption)+'</p></div><div class="desk-buttons"><button data-step="back" '+(!i?'disabled':'')+'>Previous</button><button data-step="next" '+(i===ev.length?'disabled':'')+'>Next</button><button data-step="end" '+(cursor===null?'disabled':'')+'>'+(run.status==='running'?'Back to live':'Final state')+'</button></div></div>'+
      '<div class="desk-detail"><h3>'+names[selection]+'</h3>'+panel[selection]()+'</div>';
  }
  document.addEventListener('click',evt=>{const b=evt.target.closest('#office-desk button[data-station],#office-desk button[data-step]');if(!b||!run)return;
    if(b.dataset.station)selection=b.dataset.station;
    else{const n=events().length,i=cursor??n;cursor=b.dataset.step==='end'?null:Math.max(0,Math.min(n,i+(b.dataset.step==='back'?-1:1)))}
    const selector=b.dataset.station?'[data-station="'+selection+'"]':'[data-step="'+b.dataset.step+'"]';
    paint();(document.querySelector('#office-desk '+selector+':not(:disabled)')||document.querySelector('#office-desk [aria-pressed=true]')).focus({preventScroll:true});
  });
  return {render(r){if(run?.id!==r.id){selection='monitor';cursor=null}run=r;paint()}};
})();
