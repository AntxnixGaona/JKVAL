// Angles are radians; 0.07 degrees/count is the community VALORANT reference.
export const RAD = Math.PI / 180;
export const clamp = (n,a,b) => Math.max(a,Math.min(b,n));
export function turn(counts,sensitivity,calibration=1) { return counts * .07 * sensitivity * calibration * RAD; }
export function cm360(dpi,sensitivity) { return 360 * 2.54 / (dpi * sensitivity * .07); }
export function verticalFov(aspect) { return 2*Math.atan(Math.tan(103*RAD/2)/(16/9))/RAD; }
export function recoil(shot,weapon,random=Math.random) {
  if(shot === 0) return {pitch:0,yaw:0};
  const strength=weapon==='phantom'?.82:1;
  return {pitch:Math.min(shot*.32,4.3)*RAD*strength,yaw:(shot<5?0:Math.sin(shot*.8)*.7+(random()-.5)*.75)*RAD*strength};
}
export const maps = {
  range: {name:'Campo de práctica',hint:'Objetivos a distintas distancias. Practica taps y ráfagas cortas.',spawn:[0,12],bounds:[-14,14,-24,17],boxes:[[-14,2,-4,1,4,42],[14,2,-4,1,4,42],[0,2,-25,29,4,1]],targets:[[-6,-8],[0,-14],[6,-19],[-3,-20],[5,-6]]},
  ascent: {name:'Ascent · entrada a A',hint:'Entrada estrecha, generador y caja de sitio. Sal por los lados y limpia un ángulo a la vez. Esquema aproximado, no réplica.',spawn:[0,15],bounds:[-16,16,-21,18],boxes:[[-7,2,11,10,4,13],[7,2,11,10,4,13],[-5,1.6,-4,4,3.2,5],[5,1,-11,4,2,4],[0,3,-21,33,6,1],[-16,2,-2,1,4,40],[16,2,-2,1,4,40],[10,2.6,-18,9,1,5]],targets:[[-9,-8],[0,-12],[8,-14],[-3,-17],[11,-5]]},
  bind: {name:'Bind · entrada a B',hint:'Pasillo largo, entrada lateral y contenedor central. Comprueba los dos lados de la cobertura. Esquema aproximado.',spawn:[-10,15],bounds:[-16,16,-22,18],boxes:[[-15,2,4,2,4,29],[-5,2,10,7,4,15],[5,2,-5,7,4,5],[12,2,7,7,4,13],[0,2,-22,34,4,1],[16,2,-4,1,4,36],[-8,1,-14,3,2,3]],targets:[[-9,-7],[0,-12],[10,-14],[8,0],[-3,-17]]},
  haven: {name:'Haven · entrada a C',hint:'Línea larga hacia el sitio, cajas centrales y salida lateral de garaje. Practica preaim a altura de cabeza. Esquema aproximado.',spawn:[0,19],bounds:[-15,15,-23,22],boxes:[[-6,2,13,8,4,19],[6,2,13,8,4,19],[0,1.5,-7,5,3,5],[-8,1,-15,4,2,4],[15,2,-5,1,4,35],[-15,2,-5,1,4,35],[0,2,-23,31,4,1],[10,2,-16,7,4,7]],targets:[[-6,-8],[6,-10],[0,-18],[10,-5],[-10,-18]]}
};
