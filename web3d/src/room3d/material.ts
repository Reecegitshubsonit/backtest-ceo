import * as THREE from 'three'

// Every surface is shaded from its own 3D position, normal and the room's light sources
// (projector column, CEO, neon strips). No photograph is projected onto any mesh, so the
// room reads the same from the home view and from any orbit angle.
export const VERTEX = `
varying vec3 vWorld, vNormal;
varying vec2 vUv;
void main() {
 vec4 world = modelMatrix * vec4(position,1.0);
 vWorld=world.xyz; vNormal=normalize(mat3(modelMatrix)*normal); vUv=uv;
 gl_Position=projectionMatrix*viewMatrix*world;
}`
const FRAGMENT = `
uniform sampler2D uSharp,uPhoto;
uniform float uKind,uTime,uHot,uDetail,uDesk;
varying vec3 vWorld,vNormal;
varying vec2 vUv;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float line(float d,float width){return 1.-smoothstep(width,width*3.,abs(d));}
vec3 lin(vec3 c){return pow(c,vec3(2.2));}
vec2 deskUV(vec3 world){
 vec2 q=world.xz/vec2(1.,2.75/2.65);float r=length(q);
 float t=r<1.35?r*.19/1.35:.19+(r-1.35)*(.485-.19)/1.30;
 return vec2(.5)+normalize(q+vec2(.000001))*t;
}
// Cyan light emitted by the projector beam and CEO: nearest point on the light column.
vec3 columnLight(vec3 p,vec3 n,out float near){
 vec3 c=vec3(0.,clamp(p.y,1.75,4.5),0.),L=c-p;float d=max(length(L),1e-4);L/=d;
 near=1./(1.+d*d*.30);
 return vec3(.02,.30,1.)*max(0.,dot(n,L))*near;
}
// Particle sparkle field used by every hologram body.
float sparkle(vec3 p,vec3 n,float density,float threshold){
 vec2 g=(abs(n.z)>abs(n.x)?p.xy:p.zy)*density,cell=floor(g);
 float d=length(fract(g)-vec2(hash(cell),hash(cell+7.)));
 return (1.-smoothstep(.03,.14,d))*step(threshold,hash(cell+13.))*(.6+.4*sin(uTime*1.7+hash(cell+3.)*30.));
}
void main(){
 vec3 n=normalize(vNormal)*(gl_FrontFacing?1.:-1.),view=normalize(cameraPosition-vWorld);
 float nv=abs(dot(n,view)),fres=1.-nv,r=length(vWorld.xz),a=atan(vWorld.x,vWorld.z);
 float relief=.3+.7*max(0.,dot(n,normalize(vec3(-.4,.8,.4))));
 float near;vec3 glow=columnLight(vWorld,n,near);
 vec3 haze=vec3(.0007,.0018,.0068);
 vec3 base=haze*relief;
 float alpha=1.;
 bool wall=uKind<.5,floorMesh=uKind>6.5&&uKind<7.5,ceiling=uKind>7.5&&uKind<8.5;
 if(wall){
  float seam=line(fract((a+3.14159265)*16./6.2831853)-.5,.005);
  float panel=line(fract((a+3.14159265)*48./6.2831853)-.5,.004)*step(1.1,vWorld.y)*step(vWorld.y,6.2);
  base=vec3(.0009,.0022,.0085)*relief+vec3(.003,.008,.022)*seam+vec3(.001,.003,.009)*panel+glow*.05;
  float strips=line(vWorld.y-1.05,.012)+line(vWorld.y-.24,.012)+line(vWorld.y-6.3,.015);
  base+=vec3(.20,.045,.42)*strips;
  base+=vec3(.010,.003,.022)*(exp(-pow((vWorld.y-1.05)/.25,2.))+exp(-pow((vWorld.y-6.3)/.3,2.)));
 }
 if(floorMesh){
  base=vec3(.0006,.0014,.0062)*(.7+.3*relief)+glow*.08;
  base+=vec3(.015,.002,.04)*(line(r-7.4,.005)+line(r-5.9,.005));
  base+=vec3(.010,.003,.030)*exp(-pow((r-2.75)/.35,2.));
 }
 if(ceiling){
  base=vec3(.002,.004,.012)*relief;
  base+=vec3(.22,.05,.4)*(line(r-6.5,.018)+line(r-7.7,.012));
  base+=vec3(.04,.3,.65)*(line(r-2.3,.018)+line(r-1.85,.012));
 }
 if(uKind>.5&&uKind<1.5){
  vec3 atlas=lin(texture2D(uSharp,deskUV(vWorld)).rgb);
  if(abs(n.y)>.45){
   base=atlas*(r<1.35?.65:.35)*relief*vec3(.85,.95,1.1);
   base+=vec3(.025,.32,.65)*line(r-1.03,.008)+vec3(.32,.07,.6)*line(r-1.29,.007);
   base+=vec3(.03,.35,.6)*exp(-r*r/.015);
   // bright outer lip of the desk top
   base+=vec3(.012,.08,.22)*line(r-2.60,.006)*step(1.5,vWorld.y);
  }else{
   // dark fascia, vertical service panels and a cyan seam under the top edge
   float panels=line(fract((a+3.14159265)*36./6.2831853)-.5,.012);
   base=vec3(.0006,.0014,.0045)*relief+vec3(.002,.006,.018)*panels*step(.25,vWorld.y)+vec3(.003,.01,.03)*pow(fres,2.);
   base+=vec3(.02,.16,.42)*line(vWorld.y-1.56,.005)*step(2.2,r);
   base+=vec3(.09,.02,.20)*line(vWorld.y-.18,.006)*step(1.2,r);
  }
 }
 bool agent=uKind>2.5&&uKind<3.5,ceo=uKind>4.5&&uKind<5.5;
 if(agent){
  float dots=sparkle(vWorld,n,38.,.78)+sparkle(vWorld+.21,n,75.,.88)*.5;
  vec2 g=(abs(n.z)>.5?vWorld.xy:vWorld.zy)*35.;vec2 e=abs(fract(g)-.5);
  float wire=1.-smoothstep(.006,.023,min(min(e.x,e.y),abs(e.x-e.y)));
  float scan=.92+.08*sin(vWorld.y*240.-uTime*1.5);
  base=(vec3(.0015,.016,.070)*(.45+.55*relief)+vec3(.004,.17,.85)*pow(fres,2.4)+vec3(.05,.45,1.)*dots*.9+vec3(.001,.010,.035)*wire+glow*.35)*scan;
 }
 if(ceo){
  float y=(vWorld.y-1.7)/3.2;
  float dots=sparkle(vWorld,n,46.,.72)+sparkle(vWorld+.37,n,90.,.9)*.6;
  float scan=.9+.1*sin(vWorld.y*180.-uTime*2.);
  float streak=pow(max(0.,sin(vWorld.x*70.+hash(vec2(floor(vWorld.x*70./6.283)))*6.)),18.)*(1.-smoothstep(.15,.5,y));
  base=(vec3(.003,.030,.120)*(.35+.65*relief)+vec3(.04,.38,1.)*pow(fres,2.2)*1.3+vec3(.35,.72,1.)*dots*1.5+vec3(.02,.35,.9)*streak*.6)*scan;
  base+=vec3(.004,.12,.38)*(1.-smoothstep(.0,.35,y));
  alpha=mix(.22,1.,smoothstep(.06,.45,y));
 }
 if(uKind>1.5&&uKind<2.5){
  // black leather: dark navy body, cyan specular from the projector column, purple neon rim
  vec3 L=normalize(vec3(0.,clamp(vWorld.y,1.75,4.5),0.)-vWorld),h=normalize(L+view);
  float spec=pow(max(0.,dot(n,h)),28.)*near;
  base=vec3(.0008,.0019,.0072)*relief+glow*.04+vec3(.03,.15,.50)*spec*.8+vec3(.009,.004,.024)*pow(fres,3.);
 }
 if(uKind>3.5&&uKind<4.5){
  base=vec3(.0008,.0018,.0055)*relief+vec3(.005,.035,.13)*pow(fres,3.)+glow*.03;
 }
 if(uKind>8.5&&uKind<9.5){
  float fabric=.96+.04*sin(vWorld.y*430.)*sin(vWorld.x*430.);
  base=(vec3(.0012,.0022,.006)*relief+vec3(.004,.028,.10)*pow(fres,3.)+glow*.035)*fabric;
 }
 if(uKind>9.5&&uKind<10.5){base=vec3(.0006,.0010,.0022)*relief+vec3(.003,.02,.07)*pow(fres,2.5);}
 if(uKind>10.5&&uKind<11.5){
  // monitor housings: satin dark shell, catching the room's blue haze on its edges
  base=vec3(.0016,.003,.009)*relief+vec3(.006,.02,.06)*pow(fres,2.)+glow*.05;
 }
 if(uKind>11.5){
  // architecture trim: pillars with edge light strips, the wall console ledge with a lit lip
  vec3 radial=normalize(vec3(vWorld.x,0.,vWorld.z));
  float front=step(.6,-dot(n,radial));
  float edge=1.-smoothstep(.0,.06,min(vUv.x,1.-vUv.x));
  base=vec3(.0012,.0026,.0085)*relief+vec3(.003,.009,.028)*pow(fres,2.)+glow*.03;
  base+=vec3(.03,.20,.55)*edge*front*step(.3,vWorld.y)*step(vWorld.y,6.7)*(r>7.6?1.:0.);
  if(r>7.6&&abs(n.y)<.5){
   base+=vec3(.002,.006,.018)*line(fract(vWorld.y*2.5)-.5,.03);
   base+=vec3(.10,.03,.24)*(line(vWorld.y-1.25,.006)+line(vWorld.y-6.15,.006))*step(8.1,r);
  }
  if(r<7.6||vWorld.y<.95){
   base+=vec3(.03,.22,.6)*line(r-7.45,.008)*step(.5,n.y)+vec3(.16,.04,.36)*line(vWorld.y-.62,.008)*step(.5,front)*step(r,7.6);
  }
 }
 vec3 color=base;
 if(uKind>5.5&&uKind<6.5){
  vec3 chart=lin(texture2D(uSharp,vUv).rgb);
  // distant wall displays sit back in the dark like the reference; full contrast when focused
  color=chart*mix(.42,1.,uDetail)*vec3(.8,.9,1.1);
  if(uDesk>.5)color=mix(lin(texture2D(uPhoto,deskUV(vWorld)).rgb)*.35,chart,uDetail);
  float edge=min(min(vUv.x,1.-vUv.x),min(vUv.y,1.-vUv.y));
  if(uDesk<.5)color+=vec3(.02,.09,.24)*(1.-smoothstep(.002,.008,edge));
  color+=uHot*(vec3(.015,.05,.1)+vec3(.08,.32,.65)*(1.-smoothstep(.005,.04,edge)));
 }
 if(alpha<.015)discard;
 gl_FragColor=vec4(color,alpha);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`
export const KIND: Record<string,number> = {wall:0,floor:7,ceiling:8,desk:1,chair:2,hologram:3,operator:4,ceo:5,monitor:11,screen:6,cloth:9,hair:10,trim:12}
const blank=new THREE.DataTexture(new Uint8Array([0,0,0,255]),1,1)
blank.needsUpdate=true
export function roomMaterial(kind: string,sharp?: THREE.Texture) {
 return new THREE.ShaderMaterial({
   vertexShader:VERTEX,fragmentShader:FRAGMENT,
   uniforms:{uSharp:{value:sharp??blank},uKind:{value:KIND[kind]??0},
    uTime:{value:0},uHot:{value:0},uDetail:{value:0},uDesk:{value:0},uPhoto:{value:blank}},
   side:THREE.DoubleSide,transparent:kind==='ceo',depthWrite:true,toneMapped:false,
 })
}
