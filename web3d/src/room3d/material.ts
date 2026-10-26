import * as THREE from 'three'
import { referenceCamera } from './camera'

export const VERTEX = `
uniform mat4 uReferenceMatrix, uReferenceView;
uniform float uKind;
varying vec4 vReference;
varying vec3 vWorld, vNormal;
varying vec2 vUv;
varying float vDepth;
void main() {
 vec4 world = modelMatrix * vec4(position,1.0);
 vWorld=world.xyz; vNormal=normalize(mat3(modelMatrix)*normal); vUv=uv;
 vec4 referenceWorld=world;
 if((uKind<.5||uKind>10.5||uKind>5.5&&uKind<6.5)&&world.z>0.)referenceWorld.xz=-referenceWorld.xz;
 vReference=uReferenceMatrix*referenceWorld; vDepth=-(uReferenceView*world).z;
 gl_Position=projectionMatrix*viewMatrix*world;
}`
const FRAGMENT = `
uniform sampler2D uReference,uDepth,uSharp,uPhoto;
uniform float uKind,uTime,uHot,uDetail,uDesk;
varying vec4 vReference;
varying vec3 vWorld,vNormal;
varying vec2 vUv;
varying float vDepth;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float box(vec2 p,vec4 b){return step(b.x,p.x)*step(p.x,b.z)*step(b.y,p.y)*step(p.y,b.w);}
float line(float d,float width){return 1.-smoothstep(width,width*3.,abs(d));}
vec2 deskUV(vec3 world){
 vec2 q=world.xz/vec2(1.,2.75/2.65);float r=length(q);
 float t=r<1.35?r*.19/1.35:.19+(r-1.35)*(.485-.19)/1.30;
 return vec2(.5)+normalize(q+vec2(.000001))*t;
}
void main(){
 vec3 n=normalize(vNormal)*(gl_FrontFacing?1.:-1.),view=normalize(cameraPosition-vWorld);
 float rim=pow(1.-abs(dot(n,view)),2.5),r=length(vWorld.xz),a=atan(vWorld.x,vWorld.z);
 float relief=.3+.7*max(0.,dot(n,normalize(vec3(-.4,.8,.4))));
 vec3 base=vec3(.002,.006,.014)*relief;
 bool wall=uKind<.5,floorMesh=uKind>6.5&&uKind<7.5,ceiling=uKind>7.5&&uKind<8.5;
 if(wall){
  float seam=line(fract((a+3.14159265)*16./6.2831853)-.5,.005);
  base=vec3(.001,.003,.009)*relief+vec3(.004,.009,.02)*seam;
  float strips=line(vWorld.y-1.05,.012)+line(vWorld.y-.24,.012)+line(vWorld.y-6.3,.015);
  base+=vec3(.20,.045,.42)*strips;
 }
 if(floorMesh){
  base=vec3(.0003,.0006,.0015)*relief;
  base+=vec3(.015,.002,.04)*(line(r-7.4,.005)+line(r-5.9,.005));
 }
 if(ceiling){
  base=vec3(.002,.004,.012)*relief;
  base+=vec3(.22,.05,.4)*(line(r-6.5,.018)+line(r-7.7,.012));
  base+=vec3(.04,.3,.65)*(line(r-2.3,.018)+line(r-1.85,.012));
 }
 if(uKind>.5&&uKind<1.5){
  vec3 atlas=pow(texture2D(uSharp,deskUV(vWorld)).rgb,vec3(2.2));
  base=abs(n.y)>.45?atlas*(r<1.35?.65:.35)*relief:vec3(.0003,.0008,.002)*relief;
  base+=vec3(.02,.14,.3)*line(vWorld.y-1.60,.004)*step(2.4,r)*(1.-step(.45,abs(n.y)));
  if(n.y>.45){base+=vec3(.025,.32,.65)*line(r-1.03,.008)+vec3(.32,.07,.6)*line(r-1.29,.007);base+=vec3(.03,.35,.6)*exp(-r*r/.015);}
 }
 bool holo=uKind>2.5&&uKind<3.5||uKind>4.5&&uKind<5.5;
 if(holo){
  vec2 g=(abs(n.z)>.5?vWorld.xy:vWorld.zy)*35.,cell=floor(g);
  float dots=(1.-smoothstep(.02,.12,length(fract(g)-vec2(hash(cell),hash(cell+7.)))))*step(.85,hash(cell+13.));
  vec2 e=abs(fract(g)-.5);float wire=1.-smoothstep(.006,.023,min(min(e.x,e.y),abs(e.x-e.y)));
  float scan=.93+.07*sin(vWorld.y*240.-uTime*1.5);
  base=(vec3(.0003,.003,.012)*relief+vec3(.025,.30,1.0)*pow(1.-abs(dot(n,view)),5.)+vec3(.05,.42,1.0)*dots+vec3(.001,.012,.04)*wire)*scan;
 }
 if(uKind>1.5&&uKind<2.5){
  base=vec3(.0004,.001,.002)*relief+vec3(.002,.006,.015)*pow(rim,1.5);
 }
 if(uKind>3.5&&uKind<4.5){
  float fabric=.96+.04*sin(vWorld.y*430.)*sin(vWorld.x*430.);
  base=(vec3(.001,.0013,.0018)*relief+vec3(.001,.002,.003)*rim)*fabric;
 }
 if(uKind>8.5&&uKind<9.5){base=vec3(.0015,.0025,.005)*relief+vec3(.004,.009,.018)*rim;}
 if(uKind>9.5&&uKind<10.5){base=vec3(.0005,.0006,.0008)*relief+vec3(.0002,.0003,.0004)*rim;}
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
 if(uKind>10.5)visible=inside*smoothstep(-.15,.25,dot(normalize(vNormal),normalize(vec3(0.,3.844,vWorld.z>0.?-7.04:7.04)-vWorld)));
 if(wall)visible=inside*(1.-foreground)*(1.-box(px,vec4(300.,395.,980.,640.)));
 if(uKind>4.5&&uKind<5.5){
  float depth=texture2D(uDepth,clamp(uv,0.,1.)).r;
  visible=inside*smoothstep(-.03,.03,vWorld.z);
 }
 vec3 photograph=texture2D(uReference,clamp(uv,0.,1.)).rgb;
 if(uKind>2.5&&uKind<3.5){
  float referenceFacing=smoothstep(-.15,.35,dot(normalize(vNormal),normalize(vec3(0.,3.844,7.04)-vWorld)));
  float blue=smoothstep(.012,.045,photograph.b)*step(photograph.r*1.8,photograph.b);
  visible=inside*referenceFacing*blue*.92;
 }
 vec3 color=mix(base,photograph,visible);
 float alpha=1.;
 if(uKind>4.5&&uKind<5.5){
  float y=(vWorld.y-1.7)/3.2;
  alpha=max(smoothstep(.01,.43,y),smoothstep(.35,.58,abs(vWorld.x))*smoothstep(.18,.3,y));
 }
 if(uKind>5.5&&uKind<6.5){
  float fromPhoto=inside*(1.-foreground)*(1.-uDetail);
  color=mix(pow(texture2D(uSharp,vUv).rgb,vec3(2.2)),photograph,fromPhoto);
  if(uDesk>.5)color=mix(pow(texture2D(uPhoto,deskUV(vWorld)).rgb,vec3(2.2))*.35,pow(texture2D(uSharp,vUv).rgb,vec3(2.2)),uDetail);
  float edge=min(min(vUv.x,1.-vUv.x),min(vUv.y,1.-vUv.y));
  color+=uHot*(vec3(.015,.05,.1)+vec3(.08,.32,.65)*(1.-smoothstep(.005,.04,edge)));
 }
 if(alpha<.015)discard;
 gl_FragColor=vec4(color,alpha);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`
export const KIND: Record<string,number> = {wall:0,floor:7,ceiling:8,desk:1,chair:2,hologram:3,operator:4,ceo:5,monitor:11,screen:6,cloth:9,hair:10}
export function roomMaterial(reference: THREE.Texture,depth: THREE.DataTexture,kind: string,sharp?: THREE.Texture) {
 const camera=referenceCamera()
 return new THREE.ShaderMaterial({
   vertexShader:VERTEX,fragmentShader:FRAGMENT,
   uniforms:{uReference:{value:reference},uDepth:{value:depth},uSharp:{value:sharp??reference},uKind:{value:KIND[kind]??0},
    uReferenceMatrix:{value:camera.projectionMatrix.clone().multiply(camera.matrixWorldInverse)},uReferenceView:{value:camera.matrixWorldInverse.clone()},
    uTime:{value:0},uHot:{value:0},uDetail:{value:0},uDesk:{value:0},uPhoto:{value:reference}},
   side:THREE.DoubleSide,transparent:kind==='ceo',depthWrite:true,toneMapped:false,
 })
}
