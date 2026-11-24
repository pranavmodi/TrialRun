// Browser audio is presentation only. Durable turns and provider work belong to the run.
const officePhone=(()=>{
  let session=null,box=null,live=false,busy=false,rec=null,muted=false,heard=new Set(),seqSent=null;
  let minimized=false,armed=false,audio=null,auto=false,nextTimer=0;
  const q=s=>box?.querySelector(s);
  function stopMic(){if(rec){rec.onend=rec.onerror=rec.onresult=null;rec.abort();rec=null}}
  function leave(){stopRing();liveVoice.stop();clearTimeout(nextTimer);stopMic();window.speechSynthesis?.cancel();box?.remove();box=null;
    session=null;heard=new Set();busy=false;seqSent=null;minimized=false;auto=false;armed=false}
  let ring=null;
  function unlockSound(){
    try{audio??=new (window.AudioContext||window.webkitAudioContext)();audio.resume().catch(()=>{})}catch{}
  }
  function pulse(r){
    if(audio?.state!=='running')return;
    const t=audio.currentTime,g=audio.createGain();r.gains.push(g);g.connect(audio.destination);
    g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(.065,t+.03);
    g.gain.setValueAtTime(.065,t+1.05);g.gain.linearRampToValueAtTime(0,t+1.12);
    for(const hz of [440,480]){const o=audio.createOscillator();o.frequency.value=hz;o.connect(g);
      o.start(t);o.stop(t+1.13);o.onended=()=>o.disconnect()}
  }
  function stopRing(){
    if(!ring)return;clearTimeout(ring.timer);for(const g of ring.gains)g.disconnect();
    ring=null;officeDesk.ring(false,false);controls()
  }
  function ringThenAnswer(r){
    const seq=ring={number:1,gains:[],timer:0};
    function beat(){
      if(ring!==seq)return;
      if(session?.id!==r.id||!live||session.status!=='running'){stopRing();return}
      officeDesk.ring(true,true);controls();pulse(seq);
      seq.timer=setTimeout(()=>{
        if(seq.number===1){officeDesk.ring(true,matchMedia('(prefers-reduced-motion: reduce)').matches);
          seq.timer=setTimeout(()=>{seq.number=2;beat()},1600);return}
        stopRing();
        if(r.call_mode==='live')action('live').catch(err=>notice(err.message));
        else{armed=true;muted=false;const greeting=r.state.turns.find(t=>t.conversation_id===r.conversation_id&&t.speaker==='agent');if(greeting)say(greeting.text);controls()}
      },1150)
    }
    beat()
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
      '<button data-phone="live">Connect microphone</button><button data-phone="retry">Retry reply</button><button data-phone="listen">Enable sound</button><button data-phone="end">End call</button></div>'+
      '<small class="phone-audio"></small><p class="phone-error" role="alert"></p>';
    document.querySelector('#office-desk').append(box);
    if(!window.SpeechRecognition&&!window.webkitSpeechRecognition)q('.phone-audio').textContent='Dictation is unavailable in this browser. Type your turn below.';
    box.querySelector('textarea').oninput=()=>controls();
    box.addEventListener('click',e=>{const a=e.target.closest('[data-phone]')?.dataset.phone;if(a)action(a).catch(err=>notice(err.message))})
  }
  function controls(){
    if(!box||!session)return;
    const human=session.call_mode==='human',wait=busy||seqSent===session.call_seq||session.ai_state!=='listening',open=session.status==='running';
    const rt=session.call_mode==='live',onMic=liveVoice.connected();q('[data-phone=live]').hidden=!rt||!open;q('[data-phone=listen]').hidden=rt;
    q('[data-phone=live]').textContent=onMic?'Disconnect microphone':'Connect microphone';
    const phoneStation=document.querySelector('#office-desk [data-station=phone]');if(rt&&phoneStation)phoneStation.textContent=onMic?'Calls · Mic on':'Calls';
    q('.phone-compose').hidden=!human||!open;q('[data-phone=send]').disabled=wait||!q('textarea').value.trim();
    q('[data-phone=speak]').disabled=wait||!(window.SpeechRecognition||window.webkitSpeechRecognition);
    q('[data-phone=speak]').textContent=rec?'Finish dictation':'Use microphone';
    q('[data-phone=demo]').hidden=q('[data-phone=auto]').hidden=rt||human||!open||session.call_seq>=4;
    q('[data-phone=demo]').disabled=wait||auto;q('[data-phone=auto]').textContent=auto?'Pause conversation':'Play conversation';
    q('[data-phone=retry]').hidden=!open||!['failed','interrupted'].includes(session.ai_state);q('[data-phone=retry]').disabled=busy;
    q('[data-phone=end]').hidden=!open;q('[data-phone=listen]').textContent=armed&&!muted?'Mute sound':'Enable sound';
    q('.phone-state').textContent=!open?'Ended · transcript saved':({queued:'Clerk is queued…',working:'Clerk is thinking…',failed:'Reply failed',interrupted:'Reply interrupted'})[session.ai_state]||
      (rt?'Gemini Live · You are the caller':human?'Connected · You are the caller':session.call_seq>=4?'Demo complete · ready to end':'Connected · Jamie is the scripted caller');
    q('.phone-lines').hidden=q('.phone-audio').hidden=!!ring;
    if(ring){
      q('.phone-state').textContent='Incoming call · Ring '+ring.number+' of 2';
      q('.phone-compose').hidden=true;
      for(const k of ['live','demo','auto','listen','retry'])q('[data-phone='+k+']').hidden=true
    }
  }
  function scheduleDemo(){
    clearTimeout(nextTimer);if(!auto||!session||!live||session.ai_state!=='listening'||session.call_seq>=4||seqSent===session.call_seq||busy)return;
    nextTimer=setTimeout(()=>{if(window.speechSynthesis?.speaking||window.speechSynthesis?.pending)scheduleDemo();else action('demo').catch(err=>{auto=false;notice(err.message)})},650)
  }
  function render(r,atLive){
    if(!r.call_mode)return;const first=!session;session=r;live=atLive;
    if(ring&&(!atLive||r.status!=='running'))stopRing();
    if(!box)shell();box.hidden=minimized||!atLive;
    const turns=r.state.turns.filter(t=>t.conversation_id===r.conversation_id),list=q('.phone-lines');
    if(list.childElementCount!==turns.length){
      list.innerHTML=turns.map(t=>'<li><b>'+esc(t.speaker==='agent'?'Intake clerk':r.call_mode==='demo'?'Jamie':'You')+'</b> '+esc(t.text)+'</li>').join('');list.scrollTop=list.scrollHeight;
    }
    if(first&&r.call_mode==="live")q(".phone-audio").textContent="Connect your microphone to speak with the realtime agent.";
    if(r.call_mode==="live"&&(!atLive||r.status!=="running")&&liveVoice.connected())liveVoice.stop();
    for(const t of turns)if(!heard.has(t.id)){heard.add(t.id);if(r.call_mode!=="live"&&!first&&atLive&&(t.speaker==='agent'||r.call_mode==='demo'))say(t.text,t.speaker==='caller')}
    if(!atLive||r.status!=='running'){stopMic();auto=false;clearTimeout(nextTimer);if(!atLive)window.speechSynthesis?.cancel()}
    if(r.stop_reason&&['failed','interrupted'].includes(r.ai_state))notice(r.stop_reason);
    controls();scheduleDemo()
  }
  async function action(a){
    const r=session;if(!r)return;
    if(ring&&!['hide','end'].includes(a))return;
    if(a==='end')stopRing();
    if(a==='live'&&live&&r.status==='running'){
      const status=msg=>{if(session?.id===r.id){q('.phone-audio').textContent=msg;controls()}};
      if(liveVoice.connected()){await liveVoice.stop(true);status('Microphone disconnected. You can reconnect to this attempt.');return}
      return liveVoice.start(r.id,status)
    }
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
      if(a==='end'){auto=false;clearTimeout(nextTimer);window.speechSynthesis?.cancel();await liveVoice.stop(true);await op('call.end',{id:r.id});await op('run.grade',{id:r.id});location.assign(path(r.id));return}
      if(a==='retry')await op('call.retry',{id:r.id});
      else if(a==='send'||a==='demo'){await op('call.turn',{id:r.id,sequence:r.call_seq,...(a==='send'?{text:q('textarea').value}:{})});
        if(session?.id!==r.id)return;seqSent=r.call_seq;if(a==='send')q('textarea').value=''}
      if(session?.id===r.id){const fresh=await op('run.inspect',{id:r.id});if(session?.id===r.id)render(fresh,live)}
    }finally{if(session?.id===r.id){busy=false;controls();scheduleDemo()}}
  }
  document.addEventListener('click',e=>{if(!e.target.closest('[data-call-launch]'))return;
    const ps=agents.profiles.filter(p=>agents.providers.some(x=>x.id===p.provider&&x.configured&&x.models.includes(p.model)));
    dialog('Start an incoming call','<p>Use fictional details. Each call gets a fresh office. Nothing is dialed or sent to a real firm.</p>'+
      (ps.length||agents.live_voice?'<form id="call-setup"><label>Who is calling?<select name="mode">'+(agents.live_voice?'<option value="live">Me — realtime voice (Gemini Live)</option>':'')+(ps.length?'<option value="human">Me — type or dictate one turn</option><option value="demo">Jamie — scripted caller</option>':'')+'</select></label>'+
      '<label>Clerk model<select name="profile_id">'+ps.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+' · '+esc(p.model)+'</option>').join('')+'</select></label>'+
      '<p>Realtime sends microphone audio to Google Gemini and plays its voice back. Other modes use typed or dictated turns. Use fictional details only. TrialRun saves transcripts and simulated actions, not microphone audio.</p>'+
      '<button class="primary">Ring the office</button><p role="alert"></p></form>':'<p>Configure a model provider before starting a call.</p>'));
    const form=document.querySelector('#call-setup');if(!form)return;const mode=form.elements.mode,profile=form.elements.profile_id;
    mode.onchange=()=>{profile.disabled=mode.value==='live';profile.closest('label').hidden=profile.disabled};mode.onchange();form.onsubmit=async ev=>{ev.preventDefault();const b=form.querySelector('button');if(b.disabled)return;b.disabled=true;
      try{unlockSound();const out=await op('call.start',Object.fromEntries(new FormData(form)));$('#modal').close();history.pushState(null,'',path(out.id)+'?view=office');
        await route();if(session?.id===out.id)ringThenAnswer(session)}
      catch(err){form.querySelector('[role=alert]').textContent=err.message;b.disabled=false}}
  });
  window.addEventListener('pagehide',()=>{stopRing();liveVoice.stop();stopMic();clearTimeout(nextTimer);window.speechSynthesis?.cancel()});
  return {render,leave,openPanel};
})();
