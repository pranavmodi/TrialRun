// Binary audio to our own server. No provider credential or tool interface in the browser.
const liveVoice=(()=>{
  let active=null;
  function silence(a){for(const n of a.playing){try{n.stop()}catch{}}a.playing.clear();a.next=0}
  function release(a){silence(a);a.stream?.getTracks().forEach(t=>t.stop());a.mic?.disconnect();a.source?.disconnect();if(a.ctx&&a.ctx.state!=='closed')a.ctx.close().catch(()=>{})}
  async function stop(graceful=false){
    const a=active;active=null;if(!a)return;release(a);
    if(a.ws?.readyState===1&&graceful){a.ws.send('stop');await Promise.race([a.closed,new Promise(r=>setTimeout(r,3500))])}
    if(a.ws&&a.ws.readyState<2)a.ws.close()
  }
  async function start(id,status){
    if(active)return;const a={playing:new Set(),next:0};active=a;
    try{
      status('Allow microphone access to answer the desk phone…');
      a.ctx=new AudioContext({sampleRate:16000});
      await Promise.race([a.ctx.resume(),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Audio activation required')),3500))]);
      if(active!==a)return;
      a.stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,channelCount:1}});
      if(active!==a){release(a);return}
      await a.ctx.audioWorklet.addModule('/static/live-mic.js');if(active!==a)return;
      a.mic=new AudioWorkletNode(a.ctx,'office-mic');a.source=a.ctx.createMediaStreamSource(a.stream);
      const silent=a.ctx.createGain();silent.gain.value=0;a.source.connect(a.mic).connect(silent).connect(a.ctx.destination);
      const ws=new WebSocket((location.protocol==='https:'?'wss:':'ws:')+'//'+location.host+'/api/voice/'+encodeURIComponent(id));
      a.ws=ws;ws.binaryType='arraybuffer';a.closed=new Promise(r=>ws.addEventListener('close',r,{once:true}));
      status('Connecting to Gemini Live…');
      a.mic.port.onmessage=e=>{if(a.ready&&ws.readyState===1&&ws.bufferedAmount<64000)ws.send(e.data)};
      ws.onmessage=e=>{
        if(active!==a)return;
        if(typeof e.data==='string'){
          const m=JSON.parse(e.data);
          if(m.type==='ready'){a.ready=true;status('Live · Speak naturally. You can interrupt the clerk.')}
          if(m.type==='interrupted')silence(a);
          if(m.type==='error'){a.error=m.message;status(a.error)}
        }else{
          const pcm=new Int16Array(e.data);if(!pcm.length)return;
          const b=a.ctx.createBuffer(1,pcm.length,24000),out=b.getChannelData(0);
          for(let i=0;i<pcm.length;i++)out[i]=pcm[i]/32768;
          const n=a.ctx.createBufferSource();n.buffer=b;n.connect(a.ctx.destination);
          a.next=Math.max(a.ctx.currentTime+.015,a.next);n.start(a.next);a.next+=b.duration;
          a.playing.add(n);n.onended=()=>a.playing.delete(n)
        }
      };
      ws.onclose=e=>{if(active!==a)return;active=null;release(a);status(a.error||e.reason||'Disconnected. Reconnect the microphone or end the call.')};
    }catch(e){if(active===a){await stop();status(e.name==='NotAllowedError'?'Microphone permission denied. Allow access and reconnect.':'Could not connect the microphone. Check your input device and reconnect.')}}
  }
  return {start,stop,connected:()=>!!active}
})();
