// Browser audio is presentation only. Durable turns and provider work belong to the run.
const officePhone=(()=>{
  let session=null,box=null,live=false,busy=false,rec=null,muted=false,heard=new Set(),seqSent=null;
  let minimized=false,armed=false,audio=null,auto=false,nextTimer=0;
  const q=s=>box?.querySelector(s);
  function stopMic(){if(rec){rec.onend=rec.onerror=rec.onresult=null;rec.abort();rec=null}}
  function leave(){clearTimeout(nextTimer);stopMic();window.speechSynthesis?.cancel();box?.remove();box=null;
    session=null;heard=new Set();busy=false;seqSent=null;minimized=false;auto=false;armed=false}
  function tone(){
    try{audio??=new (window.AudioContext||window.webkitAudioContext)();audio.resume().catch(()=>{});
      for(const dt of [0,.23]){const o=audio.createOscillator(),g=audio.createGain(),start=audio.currentTime+dt;
        o.frequency.value=490;g.gain.setValueAtTime(.001,start);g.gain.exponentialRampToValueAtTime(.075,start+.02);
        g.gain.exponentialRampToValueAtTime(.001,start+.18);o.connect(g);g.connect(audio.destination);o.start(start);o.stop(start+.19)}}catch{}
  }
  function say(text,caller=false){
    if(!armed||muted||!window.speechSynthesis)return;
    const s=new SpeechSynthesisUtterance(text),voices=speechSynthesis.getVoices().filter(v=>v.lang.startsWith('en'));
    if(voices.length)s.voice=voices[caller&&voices.length>1?1:0];
    s.rate=caller?1:.95;s.pitch=caller?.9:1.05;
    s.onerror=e=>{if(box&&!['canceled','interrupted'].includes(e.error)){armed=false;q('.phone-audio').textContent='Voice playback unavailable. Enable sound to retry, or follow the transcript.';controls()}};
    speechSynthesis.speak(s)
  }
  function notice(msg){if(box)q('.phone-error').textContent=msg}
  function openPanel(){minimized=false;if(box){box.hidden=false;q('textarea')?.focus()}}
  function shell(){
    box=document.createElement('aside');box.className='phone-console';box.setAttribute('aria-label','Office call');
    box.innerHTML='<header><strong>Office phone</strong><button data-phone="hide" title="Keep the call open while exploring the room">Minimize</button></header>'+
      '<p class="phone-state" role="status"></p><ol class="phone-lines" aria-label="Call transcript"></ol>'+
      '<div class="phone-compose"><label>Your words<textarea maxlength="1500" rows="2" placeholder="Tell the clerk why you’re calling…"></textarea></label>'+
      '<div class="phone-buttons"><button data-phone="speak">Use microphone</button><button data-phone="send">Send turn</button></div></div>'+
      '<div class="phone-buttons"><button data-phone="demo">Next caller turn</button><button data-phone="auto">Play conversation</button>'+
      '<button data-phone="retry">Retry reply</button><button data-phone="listen">Enable sound</button><button data-phone="end">End call</button></div>'+
      '<small class="phone-audio"></small><p class="phone-error" role="alert"></p>';
    document.querySelector('#office-desk').append(box);
    if(!window.SpeechRecognition&&!window.webkitSpeechRecognition)q('.phone-audio').textContent='Dictation is unavailable in this browser. Type your turn below.';
    box.querySelector('textarea').oninput=()=>controls();
    box.addEventListener('click',e=>{const a=e.target.closest('[data-phone]')?.dataset.phone;if(a)action(a).catch(err=>notice(err.message))})
  }
  function controls(){
    if(!box||!session)return;
    const human=session.call_mode==='human',wait=busy||seqSent===session.call_seq||session.ai_state!=='listening',open=session.status==='running';
    q('.phone-compose').hidden=!human||!open;q('[data-phone=send]').disabled=wait||!q('textarea').value.trim();
    q('[data-phone=speak]').disabled=wait||!(window.SpeechRecognition||window.webkitSpeechRecognition);
    q('[data-phone=speak]').textContent=rec?'Finish dictation':'Use microphone';
    q('[data-phone=demo]').hidden=q('[data-phone=auto]').hidden=human||!open||session.call_seq>=4;
    q('[data-phone=demo]').disabled=wait||auto;q('[data-phone=auto]').textContent=auto?'Pause conversation':'Play conversation';
    q('[data-phone=retry]').hidden=!open||!['failed','interrupted'].includes(session.ai_state);q('[data-phone=retry]').disabled=busy;
    q('[data-phone=end]').hidden=!open;q('[data-phone=listen]').textContent=armed&&!muted?'Mute sound':'Enable sound';
    q('.phone-state').textContent=!open?'Ended · transcript saved':({queued:'Clerk is queued…',working:'Clerk is thinking…',failed:'Reply failed',interrupted:'Reply interrupted'})[session.ai_state]||
      (human?'Connected · You are the caller':session.call_seq>=4?'Demo complete · ready to end':'Connected · Jamie is the scripted caller');
  }
  function scheduleDemo(){
    clearTimeout(nextTimer);if(!auto||!session||!live||session.ai_state!=='listening'||session.call_seq>=4||seqSent===session.call_seq||busy)return;
    nextTimer=setTimeout(()=>{if(window.speechSynthesis?.speaking||window.speechSynthesis?.pending)scheduleDemo();else action('demo').catch(err=>{auto=false;notice(err.message)})},650)
  }
  function render(r,atLive){
    if(!r.call_mode)return;const first=!session;session=r;live=atLive;
    if(!box)shell();box.hidden=minimized||!atLive;
    const turns=r.state.turns.filter(t=>t.conversation_id===r.conversation_id),list=q('.phone-lines');
    if(list.childElementCount!==turns.length){
      list.innerHTML=turns.map(t=>'<li><b>'+esc(t.speaker==='agent'?'Intake clerk':r.call_mode==='human'?'You':'Jamie')+'</b> '+esc(t.text)+'</li>').join('');list.scrollTop=list.scrollHeight;
    }
    for(const t of turns)if(!heard.has(t.id)){heard.add(t.id);if(!first&&atLive&&(t.speaker==='agent'||r.call_mode==='demo'))say(t.text,t.speaker==='caller')}
    if(!atLive||r.status!=='running'){stopMic();auto=false;clearTimeout(nextTimer);if(!atLive)window.speechSynthesis?.cancel()}
    if(r.stop_reason&&['failed','interrupted'].includes(r.ai_state))notice(r.stop_reason);
    controls();scheduleDemo()
  }
  async function action(a){
    const r=session;if(!r)return;
    if(a==='hide'){minimized=true;box.hidden=true;stopMic();return}
    if(a==='listen'){if(armed&&!muted){muted=true;window.speechSynthesis?.cancel()}else{armed=true;muted=false;
      const t=r.state.turns.filter(t=>t.conversation_id===r.conversation_id&&t.speaker==='agent').at(-1);if(t)say(t.text)}
      controls();return}
    if(!live||r.status!=='running')return;
    if(a==='auto'){auto=!auto;armed=true;controls();scheduleDemo();return}
    if(a==='speak'){
      if(rec){rec.stop();return}const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Recognition)return;
      armed=true;window.speechSynthesis?.cancel();notice('');const receiver=new Recognition(),input=q('textarea');rec=receiver;
      receiver.lang='en-US';receiver.interimResults=false;receiver.continuous=false;
      receiver.onresult=e=>{input.value=(input.value+' '+e.results[0][0].transcript).trim().slice(0,1500);controls()};
      receiver.onerror=e=>notice('Microphone: '+e.error+'. You can type your turn.');
      receiver.onend=()=>{rec=null;controls()};try{receiver.start()}catch(err){stopMic();throw err}controls();return
    }
    if(busy||((a==='send'||a==='demo')&&seqSent===r.call_seq))return;
    busy=true;controls();notice('');stopMic();
    try{
      if(a==='end'){auto=false;clearTimeout(nextTimer);window.speechSynthesis?.cancel();await op('call.end',{id:r.id});await op('run.grade',{id:r.id});location.assign(path(r.id));return}
      if(a==='retry')await op('call.retry',{id:r.id});
      else if(a==='send'||a==='demo'){await op('call.turn',{id:r.id,sequence:r.call_seq,...(a==='send'?{text:q('textarea').value}:{})});
        if(session?.id!==r.id)return;seqSent=r.call_seq;if(a==='send')q('textarea').value=''}
      if(session?.id===r.id){const fresh=await op('run.inspect',{id:r.id});if(session?.id===r.id)render(fresh,live)}
    }finally{if(session?.id===r.id){busy=false;controls();scheduleDemo()}}
  }
  document.addEventListener('click',e=>{if(!e.target.closest('[data-call-launch]'))return;
    const ps=agents.profiles.filter(p=>agents.providers.some(x=>x.id===p.provider&&x.configured&&x.models.includes(p.model)));
    dialog('Start an incoming call','<p>Use fictional details. Each call gets a fresh office. Nothing is dialed or sent to a real firm.</p>'+
      (ps.length?'<form id="call-setup"><label>Who is calling?<select name="mode"><option value="human">Me — be the caller</option><option value="demo">Jamie — scripted caller</option></select></label>'+
      '<label>Clerk model<select name="profile_id">'+ps.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+' · '+esc(p.model)+'</option>').join('')+'</select></label>'+
      '<p>Type or dictate, review, then send. Dictation may use your browser’s speech service. Transcripts are saved; microphone audio is not recorded by TrialRun.</p>'+
      '<button class="primary">Ring the office</button><p role="alert"></p></form>':'<p>Configure a model provider before starting a call.</p>'));
    const form=document.querySelector('#call-setup');if(!form)return;form.onsubmit=async ev=>{ev.preventDefault();const b=form.querySelector('button');if(b.disabled)return;b.disabled=true;
      try{tone();const out=await op('call.start',Object.fromEntries(new FormData(form)));$('#modal').close();history.pushState(null,'',path(out.id)+'?view=office');
        await route();if(session?.id===out.id){armed=true;muted=false;say(session.state.turns.at(-1).text);controls()}}
      catch(err){form.querySelector('[role=alert]').textContent=err.message;b.disabled=false}}
  });
  window.addEventListener('pagehide',()=>{stopMic();clearTimeout(nextTimer);window.speechSynthesis?.cancel()});
  return {render,leave,openPanel};
})();
