import test from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../static/vendor/three.module.js';
import {turn,cm360,verticalFov,recoil,maps,RAD} from '../static/js/aim-core.mjs';
test('one physical turn maps to 360 degrees independent of DPI choice',()=>{
 for(const dpi of [400,800,1600]) for(const sens of [.1,.35,1]){
  const counts=cm360(dpi,sens)/2.54*dpi;
  assert.ok(Math.abs(turn(counts,sens)-Math.PI*2)<1e-10);
 }
 assert.equal(turn(100,.4,2),2*turn(100,.4));
});
test('16:9 projection has a 103 degree horizontal field',()=>{
 const v=verticalFov(16/9)*RAD;
 assert.ok(Math.abs(2*Math.atan(Math.tan(v/2)*16/9)/RAD-103)<1e-10);
});
test('first shot is centered and longer bursts climb with bounded recoil',()=>{
 assert.deepEqual(recoil(0,'vandal'),{pitch:0,yaw:0});
 assert.ok(recoil(6,'vandal',()=>.5).pitch>recoil(2,'vandal',()=>.5).pitch);
 assert.ok(recoil(60,'vandal').pitch<=4.3*RAD);
});
test('spawns and targets do not overlap blocking geometry',()=>{
 for(const map of Object.values(maps)){
  for(const [x,z] of [map.spawn,...map.targets]){
   assert.ok(x>map.bounds[0]&&x<map.bounds[1]&&z>map.bounds[2]&&z<map.bounds[3]);
   assert.ok(!map.boxes.some(([bx,by,bz,w,h,d])=>x>bx-w/2-.3&&x<bx+w/2+.3&&z>bz-d/2-.3&&z<bz+d/2+.3),map.name+' point in wall '+[x,z]);
  }
 }
});
test('ray hits nearest wall before a target behind it',()=>{
 const wall=new T.Mesh(new T.BoxGeometry(3,3,1),new T.MeshBasicMaterial());wall.position.z=-5;
 const target=new T.Mesh(new T.SphereGeometry(.2),new T.MeshBasicMaterial());target.position.z=-8;
 wall.updateMatrixWorld();target.updateMatrixWorld();
 const hits=new T.Raycaster(new T.Vector3(),new T.Vector3(0,0,-1)).intersectObjects([target,wall]);
 assert.equal(hits[0].object,wall);
});
