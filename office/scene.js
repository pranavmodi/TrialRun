// Original procedural cutaway. All dimensions are in the same world space.
import * as T from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
export {enterTour} from './tour.js';
const v=(x,y,z)=>new T.Vector3(x,y,z);
const anchors={monitor:[-.32,1.87,.35],phone:[-1.87,1.33,1],folder:[.34,1.25,1.3],pad:[1.55,1.25,1.4],tray:[1.65,1.42,.27]};
const labels={monitor:'Intake monitor',phone:'Desk phone',folder:'Case folder',pad:'Callback pad',tray:'Lawyer’s inbox'};
export function enter(stage,onPick,onFailure){
  const ren=new T.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
  const gl=ren.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');
  const software=debug&&/swiftshader|llvmpipe|software/i.test(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL));
  ren.setPixelRatio(software?.7:Math.min(devicePixelRatio,1.5));ren.shadowMap.enabled=true;ren.shadowMap.type=software?T.BasicShadowMap:T.PCFSoftShadowMap;ren.shadowMap.autoUpdate=false;ren.shadowMap.needsUpdate=true;
  ren.setClearColor(0,0);const canvas=ren.domElement;stage.prepend(canvas);canvas.setAttribute('aria-label','3D model of the Harbor and Stone intake office');canvas.tabIndex=0;
  const scene=new T.Scene(),camera=new T.PerspectiveCamera(36,1,.08,110),orbit=new OrbitControls(camera,canvas);
  orbit.enablePan=false;orbit.maxPolarAngle=Math.PI*.475;orbit.minPolarAngle=.2;orbit.rotateSpeed=.7;orbit.minDistance=1.5;orbit.maxDistance=48;
  const mcache=new Map(), geo=new Map(),root=new T.Group();scene.add(root);
  const mat=color=>{if(typeof color!=='string')return color;if(!mcache.has(color))mcache.set(color,new T.MeshStandardMaterial({color,roughness:.78}));return mcache.get(color)};
  function group(x,y,z,parent=root){const g=new T.Group();parent.add(g);g.position.set(x,y,z);return g}
  function mesh(g,key,make,color,x,y,z){if(!geo.has(key))geo.set(key,make());const o=new T.Mesh(geo.get(key),mat(color));g.add(o);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;return o}
  function box(g,c,x,y,z,w,h,d){const o=mesh(g,'cube',()=>new T.BoxGeometry(),c,x,y,z);o.scale.set(w,h,d);return o}
  function tube(g,c,x,y,z,top,bottom,h){return mesh(g,[top,bottom,h].join('/'),()=>new T.CylinderGeometry(top,bottom,h,24),c,x,y,z)}
  function ball(g,c,x,y,z,a,b,d){let o=mesh(g,'ball',()=>new T.SphereGeometry(1,18,12),c,x,y,z);o.scale.set(a,b,d);return o}
  function beam(g,c,a,b,r){const A=v(...a),B=v(...b),D=B.clone().sub(A);let o=tube(g,c,0,0,0,r,r,D.length());o.position.copy(A).lerp(B,.5);o.quaternion.setFromUnitVectors(v(0,1,0),D.normalize());return o}
  const texs=[],extras=[];function art(w,h,draw){const el=document.createElement('canvas');el.width=w;el.height=h;draw(el.getContext('2d'));const tex=new T.CanvasTexture(el);tex.colorSpace=T.SRGBColorSpace;tex.anisotropy=Math.min(4,ren.capabilities.getMaxAnisotropy());texs.push(tex);const m=new T.MeshBasicMaterial({map:tex});extras.push(m);return m}
  function picture(g,m,x,y,z,w,h){const o=mesh(g,'plane',()=>new T.PlaneGeometry(),m,x,y,z);o.scale.set(w,h,1);o.castShadow=false;return o}
  let seed=42;const random=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
  const walnut='#805438',edge='#503629',oak='#b38355',gold='#caa365',green='#35534a',deep='#263e39',paper='#ece1c2',ink='#272d2e';
  scene.add(new T.HemisphereLight(0xfff1d9,0x958878,2.05));
  const sun=new T.DirectionalLight(0xffddad,2.35);sun.position.set(-2,8,5);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);
  Object.assign(sun.shadow.camera,{left:-8,right:8,top:8,bottom:-8,near:.1,far:30});sun.shadow.normalBias=.018;sun.shadow.bias=-.00025;scene.add(sun);
  const rim=new T.DirectionalLight(0xa6cce5,1.0);rim.position.set(2,4,-4);scene.add(rim);
  // Floating plinth, individual staggered boards with printed grain and a woven rug.
  box(root,deep,0,-.28,0,9.7,.46,7.45);box(root,gold,0,-.095,0,9.72,.035,7.47);
  const planks=['#956747','#9d7050','#a77751','#a5734f','#966747'];for(let j=0;j<17;j++){let x=-4.8;for(let n=0;x<4.79;n++){
    let w=Math.min(n===0&&j%2?1.53:3.18,4.8-x);box(root,planks[(j*7+n*3)%5],x+w/2,-.031,-3.6+j*.437,w-.014,.075,.426);x+=w}}
  const rug=art(768,512,c=>{c.fillStyle='#9b5949';c.fillRect(0,0,768,512);
    for(const [i,col] of [[12,'#dbb88a'],[23,'#633f38'],[28,'#c3966f'],[45,'#dfbe91']]){c.strokeStyle=col;c.lineWidth=i===23?8:3;c.strokeRect(i,i,768-2*i,512-2*i)}
    for(let x=70;x<720;x+=49)for(let y=67;y<460;y+=43){c.strokeStyle='#ba8263';c.beginPath();c.moveTo(x,y-8);c.lineTo(x+12,y);c.lineTo(x,y+8);c.lineTo(x-12,y);c.closePath();c.stroke()}});
  let carpet=picture(root,rug,0,.018,.48,6.4,3.95);carpet.rotation.x=-Math.PI/2;
  // Two architectural walls: hide their geometry when viewed from behind.
  const back=group(0,0,-3.61),left=group(-4.78,0,0);left.rotation.y=Math.PI/2;
  for(const [wall,width] of [[back,9.65],[left,7.37]]){
    box(wall,'#6b8477',0,1.73,0,width,3.46,.14);box(wall,green,0,.61,.085,width,1.22,.08);
    for(let x=-width/2+.17;x<width/2;x+=.76)box(wall,'#496354',x,.61,.14,.055,1.1,.045);
    for(const [y,h] of [[.13,.19],[1.21,.09],[3.45,.11]])box(wall,oak,0,y,.13,width+.02,h,.19)}
  const view=art(640,360,c=>{let g=c.createLinearGradient(0,0,0,360);g.addColorStop(0,'#7092a2');g.addColorStop(.54,'#e4b9a1');g.addColorStop(1,'#efcc9e');c.fillStyle=g;c.fillRect(0,0,640,360);
    c.fillStyle='#f8d4a2';c.beginPath();c.arc(455,100,30,0,7);c.fill();for(let layer=0;layer<2;layer++){let x=-5;while(x<640){let w=12+random()*38,y=(layer?205:170)+random()*65;c.fillStyle=layer?'#667d77':'#9a9e93';c.fillRect(x,y,w,360-y);for(let xx=x+4;xx<x+w-3;xx+=8)for(let yy=y+6;yy<349;yy+=14){if(random()>.7){c.fillStyle='#d9b79a';c.fillRect(xx,yy,3,5)}}x+=w+2}}});
  const win=group(-1.91,2.13,.19,back);box(win,edge,0,0,0,4.25,2.02,.11);picture(win,view,0,0,.063,4.08,1.86);
  for(const x of [-2.05,-.69,.69,2.05])box(win,paper,x,0,.095,.055,1.92,.06);box(win,paper,0,.22,.095,4.12,.043,.06);box(win,oak,0,-1,.12,4.46,.11,.34);
  const sign=art(640,280,c=>{c.fillStyle='#eddfc4';c.fillRect(0,0,640,280);c.textAlign='center';c.fillStyle='#29463e';c.font='70px Georgia';c.fillText('Harbor & Stone',320,135);c.font='21px sans-serif';c.fillText('I N J U R Y   L A W',320,195)});
  box(back,edge,2.61,2.33,.15,2.44,1.13,.12);picture(back,sign,2.61,2.33,.22,2.32,1.02);
  // Built-in bookcase and the client's bench.
  const shelf=group(0,0,.43,left);for(const x of [-1.68,1.68])box(shelf,edge,x,1.49,0,.13,2.96,.62);
  const spines=['#344c45','#ad704f','#c3a66d','#5b6873','#724b45'];for(let row=0;row<4;row++){
    const y=.21+row*.71;box(shelf,walnut,0,y,0,3.5,.1,.68);
    for(let i=0;i<11;i++){let x=-1.46+i*.26,h=.35+random()*.22;box(shelf,spines[(i+row*2)%5],x,y+.05+h/2,.04,.17,h,.41);box(shelf,gold,x,y+.05+h*.7,.25,.13,.018,.009)}}
  box(shelf,oak,0,3.02,0,3.56,.12,.74);
  const bench=group(-1.94,0,-2.8);box(bench,green,0,.42,0,3.3,.43,.87);box(bench,'#a7a98a',0,.69,.03,3.34,.17,.88);
  for(const x of [-1.43,1.43])for(const z of [-.31,.31])tube(bench,edge,x,.14,z,.07,.055,.27);
  for(const x of [-1.1,.99]){const p=box(bench,x>0?'#bd825e':'#d0bf97',x,.92,-.26,.6,.44,.14);p.rotation.x=-.19;p.rotation.z=.08*x}
  function plant(x,z,size){const g=group(x,0,z);g.scale.setScalar(size);tube(g,'#b57556',0,.34,0,.35,.24,.65);tube(g,'#774e3d',0,.67,0,.31,.31,.014);
    for(let i=0;i<19;i++){const a=i*2.399,h=.95+random()*.93,r=.28+random()*.34;const dx=Math.cos(a)*r,dz=Math.sin(a)*r;beam(g,'#697752',[0,.66,0],[dx,h,dz],.018);const leaf=ball(g,i%3?'#456950':'#81956b',dx,h,dz,.105,.33,.09);leaf.rotation.z=-dx;leaf.rotation.x=dz}}
  plant(3.83,-2.75,1.24);plant(-3.76,2.5,.8);
  // Desk, brass edged top, trestles, drawers and leather writing blotter.
  const desk=group(0,0,.68);for(const x of [-2.08,2.08])for(const z of [-.76,.76])box(desk,edge,x,.59,z,.13,1.18,.13);
  box(desk,edge,0,1.04,0,4.53,.19,1.85);box(desk,oak,0,1.18,0,4.75,.13,2.03);
  box(desk,walnut,1.76,.78,-.05,.83,.52,1.43);for(const y of [.68,.91]){box(desk,oak,1.76,y,.68,.77,.21,.03);box(desk,gold,1.76,y,.71,.23,.028,.043)}
  box(desk,'#374c45',-.24,1.255,.07,2.19,.015,1.27);
  const targets=[];function item(id,x,y,z){let g=group(x,y,z);g.userData.station=id;targets.push(g);return g}
  const monitor=item('monitor',-.32,1.265,.32);box(monitor,ink,0,.025,0,.65,.05,.44);box(monitor,ink,0,.255,-.06,.13,.42,.12);
  box(monitor,ink,0,.79,-.05,1.76,1.04,.097);
  const screen=art(640,336,()=>{});picture(monitor,screen,0,.79,.003,1.66,.92);
  function display(count){let c=screen.map.image.getContext('2d');c.fillStyle='#153832';c.fillRect(0,0,640,336);c.fillStyle='#a5bdab';c.font='20px sans-serif';c.fillText('HARBOR  &  STONE     /     INTAKE',40,56);c.fillStyle='#f6eacb';c.font='58px Georgia';c.fillText('Leads inbox',38,160);c.fillStyle='#e0ba76';c.font='29px sans-serif';c.fillText(count+' new '+(count===1?'inquiry':'inquiries'),40,240);screen.map.needsUpdate=true;dirty=true}
  box(monitor,'#394039',-.07,.026,.57,1.17,.046,.33);for(let row=0;row<3;row++)for(let j=0;j<14;j++)box(monitor,'#a9a896',-.59+j*.079,.054,.465+row*.091,.065,.012,.06);
  ball(monitor,'#4a514c',.69,.046,.58,.084,.05,.13);
  const phone=item('phone',-1.81,1.25,1);phone.rotation.y=.18;box(phone,ink,0,.09,0,.65,.16,.47);
  for(const x of [-.23,.23])ball(phone,'#383c39',x,.22,-.11,.12,.096,.118);box(phone,'#313a37',0,.25,-.12,.45,.09,.13);
  for(let i=0;i<9;i++)box(phone,'#c7c1a7',(i%3-1)*.08,.178,.01+Math.floor(i/3)*.067,.054,.017,.04);
  const file=item('folder',.44,1.268,1.4);file.rotation.y=-.15;box(file,'#bd8c48',0,0,0,.76,.026,.51);box(file,paper,0,.023,0,.71,.027,.47);box(file,'#d5a75e',0,.052,-.01,.755,.02,.49);box(file,'#d5a75e',-.21,.051,-.27,.26,.018,.08);box(file,paper,-.08,.064,0,.34,.01,.1);
  const pad=item('pad',1.62,1.27,1.41);pad.rotation.y=.19;box(pad,paper,0,.015,0,.4,.037,.51);for(let i=0;i<6;i++)box(pad,'#b8b399',0,.038,-.13+i*.05,.31,.004,.009);box(pad,'#344943',.24,.03,0,.025,.03,.48);
  const tray=item('tray',1.66,1.25,.26);for(let j=0;j<2;j++){let y=.08+j*.21;box(tray,walnut,0,y,0,.86,.055,.66);
    for(const x of [-.41,.41])box(tray,oak,x,y+.057,0,.045,.16,.65);box(tray,oak,0,y+.06,-.31,.82,.15,.05);box(tray,paper,-.03,y+.048,.025,.65,.038,.49)}
  const lamp=group(-1.87,1.25,-.04);tube(lamp,gold,0,.045,0,.19,.23,.09);tube(lamp,gold,0,.36,0,.027,.035,.65);box(lamp,gold,0,.67,0,.53,.034,.04);
  ball(lamp,'#27664c',0,.74,0,.42,.16,.19);box(lamp,'#f3cf89',0,.70,0,.69,.029,.32);
  const chair=group(-.4,0,-.83);tube(chair,ink,0,.37,0,.062,.08,.7);for(let i=0;i<5;i++){let a=i*1.257,dx=Math.sin(a)*.44,dz=Math.cos(a)*.44;beam(chair,ink,[0,.19,0],[dx,.12,dz],.04);ball(chair,ink,dx,.095,dz,.065,.065,.065)}
  box(chair,'#995e42',0,.72,0,.84,.17,.75);box(chair,'#995e42',0,1.16,-.34,.83,.78,.14);for(const x of [-.46,.46]){box(chair,ink,x,.92,0,.045,.38,.045);box(chair,walnut,x,1.105,0,.075,.055,.53)}
  const grain=art(512,128,c=>{c.fillStyle='#f2e9d9';c.fillRect(0,0,512,128);for(let i=0;i<230;i++){let y=random()*128,x=random()*80-80;c.beginPath();c.moveTo(x,y);c.strokeStyle=i%4?'rgba(77,45,29,.095)':'rgba(255,255,253,.35)';c.lineWidth=random()*1.3+.3;for(let k=0;k<12;k++){x+=55;c.lineTo(x,y+Math.sin(i+x*.012)*random()*2.7)}c.stroke()}});
  for(const color of [walnut,edge,oak,...planks])mat(color).map=grain.map;
  const brass=mat(gold);brass.metalness=.34;brass.roughness=.39;
  // Batch static meshes by material per pickable station or cutaway wall.
  // This keeps the detailed scene usable on phones and software renderers.
  const partitions=new Set([root,back,left,...targets]),batched=[];root.updateMatrixWorld(true);
  for(const g of partitions){const batches=new Map(),inv=g.matrixWorld.clone().invert();
    function collect(parent){for(const obj of [...parent.children]){
      if(partitions.has(obj))continue;if(!obj.isMesh){collect(obj);continue}
      const key=obj.material.uuid+obj.castShadow+obj.receiveShadow;
      if(!batches.has(key))batches.set(key,{m:obj.material,c:obj.castShadow,r:obj.receiveShadow,parts:[]});
      batches.get(key).parts.push(obj.geometry.clone().applyMatrix4(inv.clone().multiply(obj.matrixWorld)));parent.remove(obj)}}
    collect(g);for(const {m,c,r,parts} of batches.values()){const merged=mergeGeometries(parts);parts.forEach(p=>p.dispose());batched.push(merged);
      const chunk=new T.Mesh(merged,m);chunk.castShadow=c;chunk.receiveShadow=r;g.add(chunk)}}
  // Event-driven drawing: no idle animation or network requests. Camera state
  // is independent of evidence updates; custom framing remains when a run polls.
  let dirty=true,raf=0,flight=null,disposed=false;const reduce=matchMedia('(prefers-reduced-motion: reduce)');
  function invalidate(){dirty=true;if(!raf&&!disposed)raf=requestAnimationFrame(draw)}
  function draw(now){raf=0;if(disposed)return;if(flight){const t=Math.min(1,(now-flight.t)/470),s=t*t*(3-2*t);camera.position.lerpVectors(flight.a,flight.b,s);orbit.target.lerpVectors(flight.c,flight.d,s);if(t>=1)flight=null}
    orbit.update();const showBack=camera.position.z>-3.65,showLeft=camera.position.x>-4.8;
    if(back.visible!==showBack||left.visible!==showLeft)ren.shadowMap.needsUpdate=true;
    back.visible=showBack;left.visible=showLeft;
    ren.render(scene,camera);canvas.setAttribute('aria-description','Distance '+camera.position.distanceTo(orbit.target).toFixed(1)+' m; bearing '+Math.round(orbit.getAzimuthalAngle()*180/Math.PI)+'°. Use arrow keys to orbit, plus or minus to zoom, Home to reset.');dirty=false;if(flight)invalidate()}
  function move(pos,target,instant=false){flight=null;if(instant||reduce.matches||software){camera.position.copy(pos);orbit.target.copy(target);orbit.update()}else flight={a:camera.position.clone(),b:pos,c:orbit.target.clone(),d:target,t:performance.now()};invalidate()}
  function home(instant=false){const aspect=camera.aspect;let d=Math.min(46,Math.max(14.4,17.4/aspect));const target=v(0,1,0);move(v(.55,.49,.79).normalize().multiplyScalar(d).add(target),target,instant)}
  let lastShape=0;const resize=()=>{const {width:w,height:h}=stage.getBoundingClientRect();if(!w||!h)return;camera.aspect=w/h;camera.updateProjectionMatrix();ren.setSize(w,h,false);if(!lastShape||Math.abs(Math.log(camera.aspect/lastShape))>.45)home(true);lastShape=camera.aspect;invalidate()};
  const observer=new ResizeObserver(resize);observer.observe(stage);resize();display(0);
  // Real surface variation on the orbital model, even at a station close-up.
  for(const [name,surfaces,bump] of [
    ['walnut',[walnut,oak,edge,...planks],.013],['leather',['#374c45'],.008],
    ['plaster',['#6b8477'],.016],['linen',['#a7a98a','#bd825e','#d0bf97'],.012]
  ]){
    const tex=new T.TextureLoader().load('/static/office-'+name+'.webp',()=>{if(disposed)return;
      for(const color of surfaces){const m=mat(color);m.map=tex;m.bumpMap=tex;m.bumpScale=bump;
        if(name==='walnut'||name==='leather')m.color.set(name==='leather'?'#dedbd0':color===edge?'#a3998c':'#f2e0ca');m.needsUpdate=true}invalidate()});
    tex.colorSpace=T.SRGBColorSpace;tex.anisotropy=Math.min(4,ren.capabilities.getMaxAnisotropy());texs.push(tex);
  }
  orbit.addEventListener('change',invalidate);orbit.addEventListener('start',()=>{flight=null});
  function zoom(k){let delta=camera.position.clone().sub(orbit.target);delta.setLength(T.MathUtils.clamp(delta.length()*k,orbit.minDistance,orbit.maxDistance));move(orbit.target.clone().add(delta),orbit.target.clone())}
  const ray=new T.Raycaster();function hit(e){const rect=canvas.getBoundingClientRect();ray.setFromCamera(new T.Vector2((e.clientX-rect.left)/rect.width*2-1,1-(e.clientY-rect.top)/rect.height*2),camera);
    const visible=[];root.traverseVisible(o=>{if(o.isMesh)visible.push(o)});let o=ray.intersectObjects(visible,false)[0]?.object;while(o&&!o.userData.station)o=o.parent;return o?.userData.station}
  let down, multi=false;const pointers=new Set();canvas.onpointerdown=e=>{pointers.add(e.pointerId);if(pointers.size>1)multi=true;down=[e.clientX,e.clientY]};
  canvas.onpointercancel=e=>{pointers.delete(e.pointerId);down=null;if(!pointers.size)multi=false};
  canvas.onpointerup=e=>{pointers.delete(e.pointerId);if(!multi&&down&&Math.hypot(e.clientX-down[0],e.clientY-down[1])<5){let id=hit(e);if(id)onPick(id)}down=null;if(!pointers.size)multi=false};
  const hint=stage.querySelector('.room-hover');canvas.onpointermove=e=>{const id=!e.buttons&&e.pointerType==='mouse'&&hit(e);canvas.style.cursor=id?'pointer':e.buttons?'grabbing':'grab';hint.hidden=!id;if(id){hint.textContent=labels[id];hint.style.left=Math.min(stage.clientWidth-158,e.offsetX+16)+'px';hint.style.top=Math.max(8,e.offsetY-35)+'px'}};
  canvas.onpointerleave=()=>{hint.hidden=true};
  canvas.onkeydown=e=>{if(e.key==='+'||e.key==='=')zoom(.8);else if(e.key==='-')zoom(1.25);else if(e.key==='Home')home();else if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){const s=new T.Spherical().setFromVector3(camera.position.clone().sub(orbit.target));if(e.key==='ArrowLeft')s.theta-=.16;if(e.key==='ArrowRight')s.theta+=.16;if(e.key==='ArrowUp')s.phi-=.12;if(e.key==='ArrowDown')s.phi+=.12;s.phi=T.MathUtils.clamp(s.phi,orbit.minPolarAngle,orbit.maxPolarAngle);move(new T.Vector3().setFromSpherical(s).add(orbit.target),orbit.target.clone())}else return;e.preventDefault()};
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();if(!disposed)onFailure()},{once:true});
  return {home,zoom,focus(id){if(!anchors[id])return;const t=v(...anchors[id]);move(t.clone().add(v(1.15,1.32,2.55).multiplyScalar(camera.aspect<1?1.35:1)),t)},count(n){display(n);invalidate()},
    destroy(){disposed=true;observer.disconnect();orbit.dispose();cancelAnimationFrame(raf);batched.forEach(x=>x.dispose());geo.forEach(x=>x.dispose());mcache.forEach(x=>x.dispose());extras.forEach(x=>x.dispose());texs.forEach(x=>x.dispose());sun.shadow.dispose();ren.dispose();ren.forceContextLoss();canvas.remove();hint.hidden=true}};
}
