import * as THREE from 'three'
import { referenceCamera } from './camera'

export const VERTEX = `
uniform mat4 uReferenceMatrix, uReferenceView;
varying vec4 vReference;
varying vec3 vWorld, vNormal;
varying vec2 vUv;
varying float vDepth;
void main() {
 vec4 world = modelMatrix * vec4(position,1.0);
 vWorld=world.xyz; vNormal=normalize(mat3(modelMatrix)*normal); vUv=uv;
 vReference=uReferenceMatrix*world; vDepth=-(uReferenceView*world).z;
 gl_Position=projectionMatrix*viewMatrix*world;
}`
const FRAGMENT = `
uniform sampler2D uReference,uDepth,uSharp;
uniform float uKind,uTime,uHot,uDetail;
varying vec4 vReference;
varying vec3 vWorld,vNormal;
varying vec2 vUv;
varying float vDepth;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float box(vec2 p,vec4 b){return step(b.x,p.x)*step(p.x,b.z)*step(b.y,p.y)*step(p.y,b.w);}
float line(float d,float width){return 1.-smoothstep(width,width*3.,abs(d));}
void main(){
 vec3 n=normalize(vNormal)*(gl_FrontFacing?1.:-1.),view=normalize(cameraPosition-vWorld);
 float rim=pow(1.-abs(dot(n,view)),2.5),r=length(vWorld.xz),a=atan(vWorld.x,vWorld.z);
 float relief=.3+.7*max(0.,dot(n,normalize(vec3(-.4,.8,.4))));
 vec3 base=vec3(.002,.006,.014)*relief;
 bool wall=uKind<.5,floorMesh=uKind>6.5&&uKind<7.5,ceiling=uKind>7.5;
 if(wall){
  float panelX=fract((a+3.14159265)*16./6.2831853),panelY=fract((vWorld.y-2.35)/1.65);
  float panels=step(2.35,vWorld.y)*step(vWorld.y,5.65)*step(.035,panelX)*step(panelX,.965)*step(.035,panelY)*step(panelY,.965);
  vec3 chart=pow(texture2D(uSharp,vec2(panelX,panelY)).rgb,vec3(2.2));
  base=mix(vec3(.003,.007,.016)*relief,chart*.7,panels);
  base+=vec3(.012,.023,.05)*line(panelX-.01,.004);
  float strips=line(vWorld.y-1.05,.012)+line(vWorld.y-.24,.012)+line(vWorld.y-6.3,.015);
  base+=vec3(.20,.045,.42)*strips;
 }
 if(floorMesh){
  base=vec3(.002,.005,.012)*relief;
  base+=vec3(.14,.025,.32)*(line(r-7.4,.012)+line(r-5.9,.008));
  base+=vec3(.015,.09,.21)*line(r-3.9,.009);
  base+=vec3(.004,.009,.016)*line(fract(a*12./3.14159265)-.5,.003);
 }
 if(ceiling){
  base=vec3(.002,.004,.012)*relief;
  base+=vec3(.22,.05,.4)*(line(r-6.5,.018)+line(r-7.7,.012));
  base+=vec3(.04,.3,.65)*(line(r-2.3,.018)+line(r-1.85,.012));
 }
 if(uKind>.5&&uKind<1.5){
  vec3 atlas=pow(texture2D(uSharp,vWorld.xz/8.+.5).rgb,vec3(2.2));
  base=abs(n.y)>.45?atlas*relief:vec3(.003,.008,.018)*relief;
  base+=vec3(.02,.14,.3)*line(vWorld.y-1.48,.004)*step(2.9,r);
  if(n.y>.45){base+=vec3(.025,.32,.65)*line(r-1.03,.008)+vec3(.32,.07,.6)*line(r-1.29,.007);base+=vec3(.03,.35,.6)*exp(-r*r/.015);}
 }
 bool holo=uKind>2.5&&uKind<3.5||uKind>4.5&&uKind<5.5;
 if(holo){
  vec2 g=(abs(n.z)>.5?vWorld.xy:vWorld.zy)*48.,cell=floor(g);
  float dots=(1.-smoothstep(.02,.12,length(fract(g)-vec2(hash(cell),hash(cell+7.)))))*step(.65,hash(cell+13.));
  vec2 e=abs(fract(g)-.5);float wire=1.-smoothstep(.006,.023,min(min(e.x,e.y),abs(e.x-e.y)));
  float scan=.93+.07*sin(vWorld.y*240.-uTime*1.5);
  base=(vec3(.002,.018,.038)*relief+vec3(.07,.45,.85)*rim+vec3(.025,.25,.55)*dots+vec3(.003,.025,.06)*wire)*scan;
 }
 if(uKind>1.5&&uKind<2.5){
  base=vec3(.004,.011,.025)*relief+vec3(.007,.025,.05)*rim;
 }
 if(uKind>3.5&&uKind<4.5){
  float fabric=.96+.04*sin(vWorld.y*430.)*sin(vWorld.x*430.);
  base=(vec3(.004,.006,.011)*relief+vec3(.008,.016,.03)*rim)*fabric;
 }
 vec2 uv=vReference.xy/vReference.w*.5+.5,px=vec2(uv.x*1280.,(1.-uv.y)*720.);
 float inside=step(0.,uv.x)*step(uv.x,1.)*step(0.,uv.y)*step(uv.y,1.)*step(0.,vReference.w);
 float foreground=max(box(px,vec4(550.,85.,725.,405.)),box(px,vec4(310.,330.,440.,470.)));
 foreground=max(foreground,box(px,vec4(440.,300.,563.,426.)));
 foreground=max(foreground,box(px,vec4(716.,300.,840.,426.)));
 foreground=max(foreground,box(px,vec4(835.,330.,970.,475.)));
 foreground=max(foreground,box(px,vec4(198.,460.,440.,720.)));
 foreground=max(foreground,box(px,vec4(840.,460.,1080.,720.)));
 foreground=max(foreground,box(px,vec4(510.,545.,770.,720.)));
 // Reference detail stays attached to architecture. It never fades with camera position.
 float visible=0.;
 if(wall)visible=inside*(1.-foreground)*(1.-box(px,vec4(300.,395.,980.,640.)));
 if(uKind>4.5&&uKind<5.5){
  float depth=texture2D(uDepth,clamp(uv,0.,1.)).r;
  visible=inside*smoothstep(-.18,.18,dot(normalize(vNormal),normalize(vec3(0.,3.844,7.04)-vWorld)));
 }
 vec3 photograph=texture2D(uReference,clamp(uv,0.,1.)).rgb;
 vec3 color=mix(base,photograph,visible);
 float alpha=1.;
 if(uKind>4.5&&uKind<5.5){
  float y=(vWorld.y-1.7)/3.2;
  alpha=max(smoothstep(.24,.49,y),smoothstep(.35,.58,abs(vWorld.x))*smoothstep(.18,.3,y));
 }
 if(uKind>5.5&&uKind<6.5){
  float fromPhoto=inside*(1.-foreground)*(1.-uDetail);
  color=mix(pow(texture2D(uSharp,vUv).rgb,vec3(2.2)),photograph,fromPhoto);
  float edge=min(min(vUv.x,1.-vUv.x),min(vUv.y,1.-vUv.y));
  color+=uHot*(vec3(.015,.05,.1)+vec3(.08,.32,.65)*(1.-smoothstep(.005,.04,edge)));
 }
 gl_FragColor=vec4(color,alpha);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`
export const KIND: Record<string,number> = {wall:0,floor:7,ceiling:8,desk:1,chair:2,hologram:3,operator:4,ceo:5,monitor:2,screen:6}
export function roomMaterial(reference: THREE.Texture,depth: THREE.DataTexture,kind: string,sharp?: THREE.Texture) {
 const camera=referenceCamera()
 return new THREE.ShaderMaterial({
   vertexShader:VERTEX,fragmentShader:FRAGMENT,
   uniforms:{uReference:{value:reference},uDepth:{value:depth},uSharp:{value:sharp??reference},uKind:{value:KIND[kind]??0},
    uReferenceMatrix:{value:camera.projectionMatrix.clone().multiply(camera.matrixWorldInverse)},uReferenceView:{value:camera.matrixWorldInverse.clone()},
    uTime:{value:0},uHot:{value:0},uDetail:{value:0}},
   side:THREE.DoubleSide,transparent:kind==='ceo',depthWrite:kind!=='ceo',toneMapped:false,
 })
}
