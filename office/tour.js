// Seated, photographic viewpoint. Station coordinates are normalized positions
// in the equirectangular master, not screen pixels; picks follow every camera.
import * as T from 'three';
const PI=Math.PI,rad=PI/180,clamp=T.MathUtils.clamp;
// [left, top, right, bottom] measured on the source panorama.
const stations={monitor:[.425,.439,.588,.61],phone:[.304,.548,.362,.66],folder:[.365,.698,.521,.828],pad:[.539,.704,.643,.823],tray:[.596,.538,.701,.668]};
const labels={monitor:'Enter the intake CRM',phone:'Desk phone',folder:'Case folder',pad:'Callback pad',tray:'Lawyer’s inbox'};
function point(u,v){const a=(u-.5)*PI*2,b=(.5-v)*PI;return new T.Vector3(Math.sin(a)*Math.cos(b),Math.sin(b),-Math.cos(a)*Math.cos(b))}
function patch(x0,y0,x1,y1,cols,rows,r){
  const pos=[],uv=[],idx=[];for(let j=0;j<=rows;j++)for(let i=0;i<=cols;i++){
    const x=i/cols,y=j/rows;pos.push(...point(x0+(x1-x0)*x,y0+(y1-y0)*y).multiplyScalar(r).toArray());uv.push(x,1-y);
    if(j<rows&&i<cols){const n=j*(cols+1)+i;idx.push(n,n+cols+1,n+1,n+1,n+cols+1,n+cols+2)}}
  const g=new T.BufferGeometry();g.setIndex(idx);g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));return g;
}
export function enterTour(stage,onPick,onFailure){
  const ren=new T.WebGLRenderer({antialias:false,alpha:true,powerPreference:'low-power'});
  ren.setPixelRatio(Math.min(devicePixelRatio,1.8));const canvas=ren.domElement;stage.prepend(canvas);
  canvas.tabIndex=0;canvas.setAttribute('aria-label','Panoramic view from the intake desk');
  const scene=new T.Scene(),cam=new T.PerspectiveCamera(78,1,.01,12),hint=stage.querySelector('.room-hover');
  let dead=false,raf=0,flight=null,yaw=0,pitch=-8,fov=78;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const pano=new T.TextureLoader().load('/static/office-panorama.webp',()=>{if(!dead){canvas.dataset.ready='true';invalidate()}},undefined,()=>{if(!dead)onFailure()});
  pano.colorSpace=T.SRGBColorSpace;pano.wrapS=T.RepeatWrapping;
  // The art is a wide interior, not a seamless rear hemisphere. Project only
  // the photographed arc, and constrain the lens so no fabricated seam appears.
  const U=u=>.25+u*.5,V=v=>.19+v*.62;
  const surface=new T.Mesh(patch(U(0),V(0),U(1),V(1),128,64,10),new T.MeshBasicMaterial({map:pano,side:T.DoubleSide}));
  scene.add(surface);
  const display=document.createElement('canvas');display.width=960;display.height=500;
  const screenTex=new T.CanvasTexture(display);screenTex.colorSpace=T.SRGBColorSpace;
  const screen=new T.Mesh(patch(U(.429),V(.445),U(.584),V(.603),12,6,9.94),new T.MeshBasicMaterial({map:screenTex,side:T.DoubleSide,transparent:true,opacity:.92}));
  scene.add(screen);
  function count(n){const c=display.getContext('2d');c.fillStyle='#112326';c.fillRect(0,0,960,500);
    const bloom=c.createLinearGradient(0,0,960,500);bloom.addColorStop(0,'#28433e');bloom.addColorStop(.8,'#0d1a1e');c.fillStyle=bloom;c.fillRect(0,0,960,500);
    c.fillStyle='#b7cbbd';c.font='23px system-ui';c.fillText('HARBOR & STONE     /     INTAKE',52,73);
    c.fillStyle='#fff5d9';c.font='74px Georgia';c.fillText('Leads inbox',50,215);
    c.font='38px system-ui';c.fillStyle='#d3c390';c.fillText(n+' new '+(n===1?'inquiry':'inquiries'),53,304);
    c.font='23px system-ui';c.fillStyle='#b7cbbd';c.fillText('Open workspace',54,429);screenTex.needsUpdate=true;invalidate()}
  function invalidate(){if(!dead&&!raf)raf=requestAnimationFrame(draw)}
  function draw(now){raf=0;if(dead)return;if(flight){const k=clamp((now-flight.t)/520,0,1),e=k*k*(3-2*k);
    [yaw,pitch,fov]=flight.a.map((x,i)=>x+(flight.b[i]-x)*e);if(k===1)flight=null}
    cam.fov=fov;cam.updateProjectionMatrix();cam.lookAt(point(.5+yaw/360,.5-pitch/180));ren.render(scene,cam);
    canvas.setAttribute('aria-description','Field of view '+Math.round(fov)+'°; bearing '+Math.round(yaw)+'°. Arrow keys look around, plus or minus zooms, Home returns to the desk.');
    if(flight)invalidate()}
  function move(y,p,f,animate=false){f=clamp(f,19,Math.min(85,2*Math.atan(Math.tan(76*rad)/cam.aspect)/rad));const limit=54-f/2;p=clamp(p,-limit,limit);
    const h=Math.tan(f*rad/2),edge=Math.atan2(h*cam.aspect,Math.cos(p*rad)-h*Math.abs(Math.sin(p*rad)))/rad;
    y=clamp(y,-89+edge,89-edge);const wrap=y-yaw;
    if(animate&&!reduced.matches)flight={a:[yaw,pitch,fov],b:[yaw+wrap,p,f],t:performance.now()};else{flight=null;yaw=y;pitch=p;fov=f}invalidate()}
  function home(){move(0,-10,cam.aspect<.9?76:62,true)}
  function focus(id){const [l,t,r,b]=stations[id];move((U((l+r)/2)-.5)*360,(.5-V((t+b)/2))*180,id==='monitor'?20:35,true)}
  function zoom(k){move(yaw,pitch,fov*k)}
  const observer=new ResizeObserver(()=>{const w=stage.clientWidth,h=stage.clientHeight;if(!w||!h)return;cam.aspect=w/h;ren.setSize(w,h,false);move(yaw,pitch,fov)});
  cam.aspect=stage.clientWidth/Math.max(1,stage.clientHeight);pitch=-10;fov=cam.aspect<.9?76:62;observer.observe(stage);
  function hit(e){const rect=canvas.getBoundingClientRect(),d=new T.Vector3(2*(e.clientX-rect.left)/rect.width-1,1-2*(e.clientY-rect.top)/rect.height,.5).unproject(cam).normalize();
    const u=(.5+Math.atan2(d.x,-d.z)/(2*PI)-.25)/.5,v=(.5-Math.asin(d.y)/PI-.19)/.62;
    return Object.keys(stations).find(k=>{const [l,t,r,b]=stations[k];return u>=l&&u<=r&&v>=t&&v<=b})}
  const ps=new Map();let click=null;const gap=()=>{const [a,b]=ps.values();return Math.hypot(a.x-b.x,a.y-b.y)};
  canvas.onpointerdown=e=>{if(e.button!==0)return;canvas.setPointerCapture(e.pointerId);ps.set(e.pointerId,{x:e.clientX,y:e.clientY});click=ps.size===1?[e.clientX,e.clientY]:null;flight=null;hint.hidden=true};
  canvas.onpointermove=e=>{const p=ps.get(e.pointerId);if(!p){const k=e.pointerType==='mouse'&&hit(e);hint.hidden=!k;canvas.style.cursor=k?'pointer':'grab';if(k){hint.textContent=labels[k];hint.style.left=clamp(e.offsetX+12,4,stage.clientWidth-170)+'px';hint.style.top=Math.max(4,e.offsetY-32)+'px'}return}
    const before=ps.size===2?gap():0,dx=e.clientX-p.x,dy=e.clientY-p.y;p.x=e.clientX;p.y=e.clientY;
    if(click&&Math.hypot(p.x-click[0],p.y-click[1])>5)click=null;
    if(ps.size===2){if(before&&gap())zoom(before/gap())}else if(ps.size===1)move(yaw-dx*fov/stage.clientHeight,pitch+dy*fov/stage.clientHeight,fov);canvas.style.cursor='grabbing'};
  canvas.onpointerup=e=>{const select=ps.has(e.pointerId)&&click;ps.delete(e.pointerId);click=null;if(select){const k=hit(e);if(k)onPick(k)}};
  canvas.onpointercancel=e=>{ps.delete(e.pointerId);click=null};canvas.onpointerleave=()=>hint.hidden=true;
  canvas.onwheel=e=>{e.preventDefault();zoom(Math.exp(clamp(e.deltaY*(e.deltaMode===1?14:1),-220,220)*.0017))};
  canvas.onkeydown=e=>{switch(e.key){case 'ArrowLeft':move(yaw-10,pitch,fov);break;case 'ArrowRight':move(yaw+10,pitch,fov);break;case 'ArrowUp':move(yaw,pitch+8,fov);break;case 'ArrowDown':move(yaw,pitch-8,fov);break;case '+':case '=':zoom(.8);break;case '-':zoom(1.25);break;case 'Home':home();break;default:return}e.preventDefault()};
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();if(!dead)onFailure()},{once:true});count(0);
  return {home,focus,zoom,count,destroy(){dead=true;observer.disconnect();cancelAnimationFrame(raf);for(const o of [surface,screen]){o.geometry.dispose();o.material.dispose()}pano.dispose();screenTex.dispose();ren.dispose();ren.forceContextLoss();canvas.remove();hint.hidden=true}};
}
