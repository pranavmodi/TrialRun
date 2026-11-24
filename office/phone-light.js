import * as T from 'three';

// Camera-facing glow fixed to the handset, not to a screen coordinate.
export function callLamp(parent, position, width) {
  const c=document.createElement('canvas');c.width=c.height=64;
  const ctx=c.getContext('2d'),g=ctx.createRadialGradient(32,32,0,32,32,32);
  for(const [at,color] of [[0,'#fff5cb'],[.18,'#ffe09a'],[.26,'#ffa52b'],[.42,'#ff9a2444'],[1,'#ff9a2400']])g.addColorStop(at,color);
  ctx.fillStyle=g;ctx.fillRect(0,0,64,64);
  const map=new T.CanvasTexture(c);map.colorSpace=T.SRGBColorSpace;
  const material=new T.SpriteMaterial({map,depthWrite:false,toneMapped:false});
  const lamp=new T.Sprite(material);lamp.scale.setScalar(width);lamp.position.copy(position);
  lamp.visible=false;parent.add(lamp);
  return {set(on){lamp.visible=on},dispose(){lamp.removeFromParent();material.dispose();map.dispose()}}
}
