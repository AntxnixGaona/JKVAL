import * as T from '../vendor/three.module.js';
import {RAD,clamp,turn,cm360,verticalFov,recoil,maps} from './aim-core.mjs';
const $=id=>document.getElementById('aim-'+id), canvas=$('canvas');
const controls=['map','mode','weapon','sens','dpi','factor','recoil','duration'];
let renderer;
try {renderer=new T.WebGLRenderer({canvas,antialias:true});} catch { $('message').textContent='No se pudo iniciar WebGL. Prueba un navegador con aceleración gráfica.'; $('start').disabled=true; }
if(renderer) init();
function init(){
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0x343b4b);
  const scene=new T.Scene();scene.fog=new T.Fog(0x343b4b,35,95);
  scene.add(new T.HemisphereLight(0xeaf2ff,0x828b9e,2.4));const sun=new T.DirectionalLight(0xffffff,2.6);sun.position.set(-8,25,12);scene.add(sun);
  const camera=new T.PerspectiveCamera(70,1,.05,120);camera.rotation.order='YXZ';scene.add(camera);
  const gun=new T.Group();camera.add(gun);gun.position.set(.25,-.24,-.48);
  for(const [w,h,d,x,y,z] of [[.10,.09,.38,0,0,0],[.035,.035,.25,0,.02,-.3],[.07,.15,.08,0,-.10,.06]]){const part=new T.Mesh(new T.BoxGeometry(w,h,d),new T.MeshStandardMaterial({color:0x343048,roughness:.6}));part.position.set(x,y,z);gun.add(part);}
  const world=new T.Group();scene.add(world);const ray=new T.Raycaster();
  const keys=new Set();let walls=[],solid=[],targets=[],marks=[],map,shot=0,ammo=25,shots=0,hits=0,kills=0,heads=0,movingShots=0;
  let yaw=0,pitch=0,velocity=new T.Vector3(),elapsed=0,lastShot=-100,reloadEnd=0,active=false,started=false,trigger=false,raw='';
  let previous=performance.now(),feedbackUntil=0,hitTimes=[],pendingPeek=null;
  const mat=new T.MeshStandardMaterial({color:0xdde1e8,roughness:.92});
  const targetMat=new T.MeshStandardMaterial({color:0x7546dd,roughness:.8});
  const headMat=new T.MeshStandardMaterial({color:0xff9565,roughness:.6});
  const capacity=()=>$('weapon').value==='phantom'?30:25;
  const number=(id,min,max,def)=>{const v=Number($(id).value);return Number.isFinite(v)?clamp(v,min,max):def;};
  const setting=()=>({sens:number('sens',.01,10,.35),dpi:number('dpi',100,32000,800),factor:number('factor',.1,5,1)});
  try {const saved=JSON.parse(localStorage.getItem('jkval-aim-settings')||'{}');for(const id of controls){const el=$(id);if(typeof saved[id]===typeof(el.type==='checkbox'?true:'')){if(el.type==='checkbox')el.checked=saved[id];else el.value=saved[id];}}}catch{}
  for(const id of ['map','mode','weapon','duration']) if(!$(id).value)$(id).selectedIndex=0;
  function save(){const s=setting();for(const id of ['sens','dpi','factor'])$(id).value=s[id];$('distance').textContent=`${Math.round(s.dpi*s.sens)} eDPI · ${cm360(s.dpi,s.sens).toFixed(1)} cm/360 de referencia`;
    try{localStorage.setItem('jkval-aim-settings',JSON.stringify(Object.fromEntries(controls.map(id=>[id,$(id).type==='checkbox'?$(id).checked:$(id).value]))));}catch{}
  }
  function dispose(group){group.traverse(o=>{o.geometry?.dispose();if(o.material&&! [mat,targetMat,headMat].includes(o.material))o.material.dispose?.();});group.clear();}
  function box(x,y,z,w,h,d,color){const mesh=new T.Mesh(new T.BoxGeometry(w,h,d),color?new T.MeshStandardMaterial({color,roughness:.9}):mat);mesh.position.set(x,y,z);world.add(mesh);return mesh;}
  function build(){
    dispose(world);walls=[];solid=[];targets=[];marks=[];map=maps[$('map').value];
    const floor=box(0,-.15,0,70,.3,90,0x8993a4);walls.push(floor);
    const grid=new T.GridHelper(80,40,0x636d80,0xa8b1bf);grid.position.y=.015;world.add(grid);
    for(const b of map.boxes){const wall=box(...b);walls.push(wall);solid.push(new T.Box3().setFromObject(wall));
      const edge=new T.LineSegments(new T.EdgesGeometry(wall.geometry),new T.LineBasicMaterial({color:0x758397}));edge.position.copy(wall.position);world.add(edge);}
    if($('mode').value==='spray'){
      const board=box(map.spawn[0],2,map.spawn[1]-12,7,4,.2,0xeeeeee);walls.push(board);
      const dot=new T.Mesh(new T.RingGeometry(.06,.12,32),new T.MeshBasicMaterial({color:0x6f49c8,side:T.DoubleSide}));dot.position.set(map.spawn[0],1.65,map.spawn[1]-11.88);world.add(dot);
    }else for(const [x,z] of map.targets){
      const group=new T.Group();group.position.set(x,0,z);
      const body=new T.Mesh(new T.CylinderGeometry(.26,.30,1.15,10),targetMat);body.position.y=.84;group.add(body);
      const head=new T.Mesh(new T.SphereGeometry(.17,16,12),headMat);head.position.y=1.58;group.add(head);
      const base=new T.Mesh(new T.CylinderGeometry(.42,.42,.08,20),new T.MeshStandardMaterial({color:0x403254}));base.position.y=.04;group.add(base);
      const t={group,body,head,x,z,hp:100,respawn:0,visibleSince:null};body.userData.target=t;head.userData.target=t;head.userData.head=true;targets.push(t);world.add(group);
    }
    $('map-hint').textContent=map.hint;reset();
  }
  function reset(){active=false;started=false;trigger=false;keys.clear();document.exitPointerLock?.();
    camera.position.set(...[map.spawn[0],1.65,map.spawn[1]]);yaw=0;pitch=0;velocity.set(0,0,0);shot=0;ammo=capacity();shots=hits=kills=heads=movingShots=elapsed=0;lastShot=-100;reloadEnd=0;hitTimes=[];pendingPeek=null;
    for(const [i,t] of targets.entries()){t.group.visible=$('mode').value!=='peek'||i===0;t.hp=100;t.respawn=t.group.visible?0:Infinity;t.visibleSince=null;t.group.position.set(t.x,0,t.z);}
    for(const m of marks){world.remove(m);m.geometry.dispose();m.material.dispose();}marks=[];
    $('message').textContent='Pulsa Comenzar para capturar el mouse. Esc pausa la sesión.';$('start').textContent='COMENZAR';$('feedback').textContent='';$('results').textContent='Tu resumen aparecerá al terminar la sesión.';hud();
  }
  function hud(){const duration=Number($('duration').value);$('clock').textContent=duration?`${Math.ceil(Math.max(0,duration-elapsed))} s`:`${Math.floor(elapsed)} s`;$('score').textContent=`${kills} objetivos`;$('ammo').textContent=reloadEnd?'Recargando…':`${ammo} / ${capacity()}`;}
  function summary(){const mean=hitTimes.length?Math.round(hitTimes.reduce((a,b)=>a+b,0)/hitTimes.length):null;
    $('results').textContent=`${shots} disparos · ${hits} impactos · ${shots?Math.round(hits/shots*100):0}% precisión · ${kills} objetivos · ${heads} impactos a cabeza · ${movingShots} disparos en movimiento${mean!==null?' · '+mean+' ms desde objetivo visible hasta eliminación':''}. Tiempo activo: ${elapsed.toFixed(1)} s.`;
  }
  async function start(){
    if(!canvas.requestPointerLock){$('message').textContent='Este navegador no permite capturar el mouse. Abre el entrenador en una computadora con mouse y teclado.';return;}
    if(Number($('duration').value)&&elapsed>=Number($('duration').value))reset();
    try{raw='Se solicitó entrada sin aceleración.';await canvas.requestPointerLock({unadjustedMovement:true});}
    catch(e){if(e.name==='NotSupportedError'){try{raw='Entrada estándar: calibra la sensibilidad; puede aplicar aceleración del sistema.';await canvas.requestPointerLock();}catch{ $('message').textContent='No se pudo capturar el mouse. Pulsa Comenzar de nuevo y permite la captura.'; }}else $('message').textContent='No se pudo capturar el mouse. Pulsa Comenzar de nuevo.';}
  }
  document.addEventListener('pointerlockchange',()=>{
    active=document.pointerLockElement===canvas;if(active)$('stage').scrollIntoView({block:'center'});trigger=false;keys.clear();velocity.set(0,0,0);
    if(active){started=true;$('message').textContent='';$('start').textContent='CONTINUAR';$('input').textContent=raw+' Esc libera el mouse.';}else{if(started){$('message').textContent=Number($('duration').value)&&elapsed>=Number($('duration').value)?'Sesión terminada. Pulsa Comenzar para repetir.':'Sesión en pausa. Pulsa Continuar para volver.';summary();}$('input').textContent='Mouse sin capturar.';}
    for(const id of controls)$(id).disabled=active;
  });
  document.addEventListener('pointerlockerror',()=>{if(!active)$('message').textContent='La captura del mouse fue rechazada. Abre esta página directamente en Chrome o Firefox, fuera de un navegador integrado, y pulsa Comenzar.';});
  document.addEventListener('mousemove',e=>{if(!active)return;const s=setting();yaw-=turn(e.movementX,s.sens,s.factor);pitch=clamp(pitch-turn(e.movementY,s.sens,s.factor),-1.5,1.5);});
  document.addEventListener('keydown',e=>{if(!active)return;if(['KeyW','KeyA','KeyS','KeyD','ShiftLeft','ShiftRight','KeyR','Space'].includes(e.code)){e.preventDefault();keys.add(e.code);}if(e.code==='KeyR')reload();});
  document.addEventListener('keyup',e=>keys.delete(e.code));
  canvas.addEventListener('mousedown',e=>{if(e.button!==0)return;if(!active){start();return;}trigger=true;fire();});document.addEventListener('mouseup',()=>trigger=false);
  window.addEventListener('blur',()=>{trigger=false;keys.clear();if(active)document.exitPointerLock();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&active)document.exitPointerLock();});
  function reload(){if(!reloadEnd&&ammo<capacity()){reloadEnd=elapsed+2.4;trigger=false;shot=0;hud();}}
  function collision(x,z){const r=.3;return x<map.bounds[0]+r||x>map.bounds[1]-r||z<map.bounds[2]+r||z>map.bounds[3]-r||solid.some(b=>x>b.min.x-r&&x<b.max.x+r&&z>b.min.z-r&&z<b.max.z+r);}
  function move(dt){let x=(keys.has('KeyD')?1:0)-(keys.has('KeyA')?1:0),z=(keys.has('KeyS')?1:0)-(keys.has('KeyW')?1:0);const len=Math.hypot(x,z)||1;const speed=keys.has('ShiftLeft')||keys.has('ShiftRight')?2.2:5.4;
    const desired=new T.Vector3((x*Math.cos(yaw)+z*Math.sin(yaw))/len*speed,0,(-x*Math.sin(yaw)+z*Math.cos(yaw))/len*speed);velocity.lerp(desired,1-Math.exp(-18*dt));
    const nx=camera.position.x+velocity.x*dt;if(!collision(nx,camera.position.z))camera.position.x=nx;else velocity.x=0;
    const nz=camera.position.z+velocity.z*dt;if(!collision(camera.position.x,nz))camera.position.z=nz;else velocity.z=0;
  }
  function fire(){
    const interval=$('weapon').value==='phantom'?1/11:1/9.75;
    if(!active||reloadEnd||elapsed-lastShot<interval)return;if(ammo<=0){reload();return;}
    if(elapsed-lastShot>.3)shot=0;lastShot=elapsed;ammo--;shots++;
    const moving=velocity.length()>.8;if(moving)movingShots++;
    const r=$('recoil').checked?recoil(shot,$('weapon').value):{pitch:0,yaw:0};
    const spread=$('recoil').checked?(moving?2:shot>2?.2:0)*RAD:0;
    const rotation=new T.Euler(pitch+r.pitch+(Math.random()-.5)*spread,yaw+r.yaw+(Math.random()-.5)*spread,0,'YXZ');
    const dir=new T.Vector3(0,0,-1).applyEuler(rotation);ray.set(camera.position,dir);
    const objects=[...walls,...targets.filter(t=>t.group.visible).flatMap(t=>[t.body,t.head])];scene.updateMatrixWorld(true);
    const result=ray.intersectObjects(objects,false)[0];
    if(result){const t=result.object.userData.target;if(t){hits++;const head=!!result.object.userData.head;if(head)heads++;t.hp-=head?150:40;
      $('feedback').textContent=head?'CABEZA':'IMPACTO';feedbackUntil=elapsed+.25;
      if(t.hp<=0){kills++;t.group.visible=false;t.respawn=elapsed+.6;if($('mode').value==='peek'){t.respawn=Infinity;const others=targets.filter(o=>o!==t);pendingPeek={target:others[Math.floor(Math.random()*others.length)],at:elapsed+.8};}if(t.visibleSince!==null)hitTimes.push((elapsed-t.visibleSince)*1000);}
    }else{
      const dot=new T.Mesh(new T.SphereGeometry(.035,6,4),new T.MeshBasicMaterial({color:0x35242f}));dot.position.copy(result.point).addScaledVector(dir,-.025);world.add(dot);marks.push(dot);if(marks.length>150){const old=marks.shift();world.remove(old);old.geometry.dispose();old.material.dispose();}
    }}
    shot++;hud();
  }
  $('start').addEventListener('click',start);$('reset').addEventListener('click',reset);
  $('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('stage').requestFullscreen();}catch{$('message').textContent='Pantalla completa no disponible en este navegador.';}});
  for(const id of controls)$(id).addEventListener('change',()=>{save();build();});
  function minimap(){
    const c=$('minimap').getContext('2d');if(!c)return;
    const [xmin,xmax,zmin,zmax]=map.bounds;const scale=130/Math.max(xmax-xmin,zmax-zmin);
    const px=x=>10+(x-xmin)*scale,pz=z=>10+(z-zmin)*scale;
    c.fillStyle='#111827';c.fillRect(0,0,150,150);c.fillStyle='#abb5c7';
    for(const [x,y,z,w,h,d] of map.boxes)c.fillRect(px(x-w/2),pz(z-d/2),w*scale,d*scale);
    c.fillStyle='#68ffd6';c.beginPath();c.arc(px(camera.position.x),pz(camera.position.z),3,0,Math.PI*2);c.fill();
    c.strokeStyle='#68ffd6';c.beginPath();c.moveTo(px(camera.position.x),pz(camera.position.z));c.lineTo(px(camera.position.x)-Math.sin(yaw)*11,pz(camera.position.z)-Math.cos(yaw)*11);c.stroke();
  }
  function resize(){const w=canvas.clientWidth,h=canvas.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.fov=verticalFov(camera.aspect);camera.updateProjectionMatrix();}
  new ResizeObserver(resize).observe($('stage'));save();build();resize();
  function frame(now){requestAnimationFrame(frame);const dt=Math.min((now-previous)/1000,.04);previous=now;
    if(active){elapsed+=dt;move(dt);if(pendingPeek&&elapsed>=pendingPeek.at){pendingPeek.target.respawn=elapsed;pendingPeek=null;}if(reloadEnd&&elapsed>=reloadEnd){ammo=capacity();reloadEnd=0;}
      for(const t of targets){if(!t.group.visible&&elapsed>=t.respawn){t.group.visible=true;t.hp=100;t.visibleSince=null;}
        if(t.group.visible&&$('mode').value==='strafe'){const nx=t.x+Math.sin(elapsed*1.8+t.z)*1.3;if(!solid.some(b=>nx>b.min.x-.35&&nx<b.max.x+.35&&t.z>b.min.z-.35&&t.z<b.max.z+.35))t.group.position.x=nx;}
      }
      camera.rotation.set(pitch,yaw,0);scene.updateMatrixWorld(true);
      // Reaction timing starts only once a live target is in view and not behind cover.
      const frustum=new T.Frustum().setFromProjectionMatrix(new T.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse));
      for(const t of targets){if(t.group.visible&&t.visibleSince===null){const pos=t.head.getWorldPosition(new T.Vector3());if(frustum.containsPoint(pos)){const direction=pos.clone().sub(camera.position);const distance=direction.length();ray.set(camera.position,direction.normalize());const wall=ray.intersectObjects(walls,false)[0];if(!wall||wall.distance>distance)t.visibleSince=elapsed;}}}
      if(trigger)fire();if(elapsed>feedbackUntil)$('feedback').textContent='';
      const duration=Number($('duration').value);if(duration&&elapsed>=duration){elapsed=duration;active=false;trigger=false;document.exitPointerLock();summary();$('message').textContent='Sesión terminada. Pulsa Comenzar para repetir.';}$('start').textContent=active?'EN PRÁCTICA':'COMENZAR';hud();
    }
    gun.rotation.x=Math.exp(-Math.max(0,elapsed-lastShot)*24)*.12;
    camera.rotation.set(pitch,yaw,0);renderer.render(scene,camera);minimap();
  }
  requestAnimationFrame(frame);
}
