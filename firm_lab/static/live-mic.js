class OfficeMic extends AudioWorkletProcessor {
  constructor(){super();this.buf=new Int16Array(640);this.i=0}
  process(inputs){
    for(const x of inputs[0]?.[0]||[]){
      this.buf[this.i++]=Math.max(-1,Math.min(1,x))*(x<0?32768:32767);
      if(this.i===640){this.port.postMessage(this.buf.buffer,[this.buf.buffer]);this.buf=new Int16Array(640);this.i=0}
    }return true
  }
}
registerProcessor('office-mic',OfficeMic);
