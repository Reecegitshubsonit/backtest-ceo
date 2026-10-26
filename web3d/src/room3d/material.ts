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
uniform sampler2D uReference, uDepth, uSharp;
uniform float uKind,uTime,uHot,uDetail;
varying vec4 vReference;
varying vec3 vWorld,vNormal;
varying vec2 vUv;
varying float vDepth;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float box(vec2 p,vec4 b){return step(b.x,p.x)*step(p.x,b.z)*step(b.y,p.y)*step(p.y,b.w);}
float line(float d,float width){return 1.0-smoothstep(width,width*3.0,abs(d));}
void main(){
 vec3 n=normalize(vNormal)*(gl_FrontFacing?1.0:-1.0),view=normalize(cameraPosition-vWorld);
 float rim=pow(1.0-abs(dot(n,view)),2.5);
 float r=length(vWorld.xz),a=atan(vWorld.x,vWorld.z);
 vec3 base=vec3(.0005,.0014,.0045);
 float relief=max(0.0,dot(n,normalize(vec3(-.4,.8,.4))));
 base+=vec3(.001,.002,.005)*relief;
 if(uKind<.5){
   float seam=line(fract(a*8.0/3.14159265)-.5,.008);
   base+=vec3(.003,.005,.012)*seam;
   float strips=line(vWorld.y-1.05,.012)+line(vWorld.y-.24,.012)+line(vWorld.y-6.3,.015);
   float floorRing=(line(r-7.4,.012)+line(r-5.9,.007))*step(vWorld.y,.1);
   base+=vec3(.20,.045,.42)*(strips+floorRing)*.8;
   base+=vec3(.025,.12,.3)*line(r-3.6,.006)*step(vWorld.y,.1);
 }
 if(uKind>.5&&uKind<1.5){
   float rr=length(vWorld.xz-vec2(0.,-.35));
   base+=vec3(.013,.028,.05)*relief;
   base+=vec3(.04,.5,.9)*(line(r-1.5,.012)+line(r-.99,.008))*step(1.4,vWorld.y);
   base+=vec3(.38,.08,.7)*line(r-1.75,.013)*step(1.3,vWorld.y);
   base+=vec3(.008,.025,.05)*line(fract(a*9.0)-.5,.02)*step(1.0,vWorld.y);
 }
 bool holo=uKind>2.5&&uKind<3.5||uKind>4.5&&uKind<5.5;
 if(holo){
   vec2 g=(abs(n.z)>.5?vWorld.xy:vWorld.zy)*48.0,cell=floor(g);
   vec2 centre=vec2(hash(cell),hash(cell+7.));
   float dotLight=(1.-smoothstep(.02,.15,length(fract(g)-centre)))*step(.65,hash(cell+13.));
   vec2 e=abs(fract(g)-.5);float wire=1.-smoothstep(.006,.03,min(min(e.x,e.y),abs(e.x-e.y)));
   base=vec3(.002,.01,.035)+vec3(.025,.23,.65)*rim+vec3(.035,.28,.62)*dotLight+vec3(.002,.012,.035)*wire;
 }
 if(uKind>1.5&&uKind<2.5)base+=vec3(.002,.007,.018)*rim;
 if(uKind>3.5&&uKind<4.5)base=vec3(.001,.002,.006)+vec3(.002,.006,.015)*rim;
 vec2 uv=vReference.xy/vReference.w*.5+.5;
 float inside=step(0.,uv.x)*step(uv.x,1.)*step(0.,uv.y)*step(uv.y,1.)*step(0.,vReference.w);
 float depth=texture2D(uDepth,clamp(uv,0.,1.)).r;
 float tolerance=holo?.24:.13;
 float away=smoothstep(.015,.25,distance(cameraPosition,vec3(0.,3.844,7.04)));
 float visible=inside*mix(1.,smoothstep(-tolerance,.025,depth-vDepth),away);
 if(holo)visible*=mix(1.,smoothstep(-.18,.18,dot(normalize(vNormal),normalize(vec3(0.,3.844,7.04)-vWorld))),away);
 vec2 px=vec2(uv.x*1280.,(1.-uv.y)*720.);
 float foreground=max(box(px,vec4(550.,85.,725.,405.)),box(px,vec4(320.,337.,435.,465.)));
 foreground=max(foreground,box(px,vec4(450.,308.,553.,416.)));
 foreground=max(foreground,box(px,vec4(725.,308.,830.,416.)));
 foreground=max(foreground,box(px,vec4(845.,337.,960.,465.)));
 foreground=max(foreground,box(px,vec4(238.,466.,433.,714.)));
 foreground=max(foreground,box(px,vec4(845.,466.,1045.,714.)));
 foreground=max(foreground,box(px,vec4(530.,550.,750.,720.)));
 if(!holo&&!(uKind>3.5&&uKind<4.5))visible*=1.-foreground*away;
 if(uKind<.5)visible*=1.-box(px,vec4(310.,398.,970.,635.))*away;
 float angle=acos(clamp(dot(normalize(cameraPosition-vec3(0.,3.3,0.)),normalize(vec3(0.,.544,7.04))),-1.,1.));
 if(uKind>1.5&&uKind<2.5)visible*=1.-smoothstep(.25,1.1,angle);
 if(uKind>.5&&uKind<1.5){
   vec3 atlas=pow(texture2D(uSharp,vWorld.xz/8.+.5).rgb,vec3(2.2));
   if(abs(n.y)>.35||vWorld.y>1.5)base=atlas;
   else base=vec3(.0007,.002,.006)+vec3(.005,.015,.035)*line(vWorld.y-1.2,.008);
   visible*=1.-away;
 }
 vec3 photograph=texture2D(uReference,clamp(uv,0.,1.)).rgb;
 vec3 color=mix(base,photograph,visible);
 float alpha=1.;
 if(uKind>4.5&&uKind<5.5){
   float y=(vWorld.y-1.7)/3.2;
   alpha=max(smoothstep(.24,.49,y),smoothstep(.35,.58,abs(vWorld.x))*smoothstep(.18,.3,y));
 }
 if(uKind>5.5){
   color=mix(color,pow(texture2D(uSharp,vUv).rgb,vec3(2.2)),max(uDetail,foreground*away));
   float edge=min(min(vUv.x,1.-vUv.x),min(vUv.y,1.-vUv.y));
   color+=uHot*(vec3(.015,.05,.10)+vec3(.08,.32,.65)*(1.-smoothstep(.005,.04,edge)));
 }
 if(holo)color*=.985+.015*sin(vWorld.y*320.-uTime*2.);
 gl_FragColor=vec4(color,alpha);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`
export const KIND: Record<string,number> = {wall:0,floor:0,ceiling:0,desk:1,chair:2,hologram:3,operator:4,ceo:5,monitor:2,screen:6}
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
