import { useEffect, useMemo } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { BlendFunction, Effect, EffectAttribute } from 'postprocessing'
import { Matrix4, Uniform, Vector2 } from 'three'

// A ray-marched light field, evaluated in world space and clipped by scene depth.
// It is illumination, not a cone/point-cloud substitute for the CEO's anatomy.
const shader=`
uniform mat4 uInverseProjection,uCameraWorld;
uniform vec2 uNearFar;
uniform float uClock;
// Reference look: a soft cylinder of vertical light filaments rising from the projector rings
// into the CEO's hips, with a bright core thread continuing up to the chest.
void mainImage(const in vec4 inputColor,const in vec2 uv,out vec4 outputColor){
 vec4 vv=uInverseProjection*vec4(uv*2.-1.,1.,1.);vec3 local=normalize(vv.xyz/vv.w);
 vec3 rd=normalize(mat3(uCameraWorld)*local),ro=uCameraWorld[3].xyz;
 const float R=.78;
 float A=dot(rd.xz,rd.xz),B=2.*dot(ro.xz,rd.xz),C=dot(ro.xz,ro.xz)-R*R;
 float disc=B*B-4.*A*C;
 outputColor=inputColor;
 if(disc<0.||A<.00001)return;
 float start=max(0.,(-B-sqrt(disc))/(2.*A)),finish=(-B+sqrt(disc))/(2.*A);
 float d=readDepth(uv),near=uNearFar.x,far=uNearFar.y;
 float z=2.*near*far/(far+near-(d*2.-1.)*(far-near));
 finish=min(finish,z/max(.0001,-local.z));
 if(finish<=start)return;
 float stepSize=(finish-start)/48.,light=0.,white=0.;
 for(int i=0;i<48;i++){
   vec3 p=ro+rd*(start+(float(i)+.5)*stepSize);
   float h=p.y-1.72;
   if(h>0.&&h<3.3){
     float r=length(p.xz),ang=atan(p.z,p.x);
     float radius=.62+.10*smoothstep(0.,1.6,h);
     float column=(1.-smoothstep(radius*.45,radius,r))*.7+exp(-r*r/.05)*.5;
     float fade=smoothstep(0.,.04,h)*(1.-smoothstep(.9,2.1,h));
     float filaments=pow(max(0.,cos(ang*46.+sin(p.y*1.7-uClock*.35)*.25)),26.)+.6*pow(max(0.,cos(ang*19.-1.3)),40.);
     float shell=smoothstep(.15,.9,r/radius);
     float base=exp(-h*h/.06)*exp(-r*r/.25);
     float core=exp(-r*r/.0007)*(1.-smoothstep(2.2,3.2,h));
     light+=(column*(.30+filaments*shell*2.2)*fade*(1.25-.35*h)+base*.9+core*1.1)*stepSize;
     white+=core*stepSize;
   }
 }
 outputColor.rgb+=vec3(.02,.40,1.)*light*2.0+vec3(.25,.45,.5)*white*1.5;
}`
class BeamEffect extends Effect {
 constructor(){super('ReferenceHologramBeam',shader,{attributes:EffectAttribute.DEPTH,blendFunction:BlendFunction.NORMAL,uniforms:new Map<string,Uniform>([
  ['uInverseProjection',new Uniform(new Matrix4())],['uCameraWorld',new Uniform(new Matrix4())],['uNearFar',new Uniform(new Vector2(.05,80))],['uClock',new Uniform(0)],
 ])})}
}
export function Beam(){
 const camera=useThree(s=>s.camera)
 const effect=useMemo(()=>new BeamEffect(),[])
 useFrame(({clock})=>{
   effect.uniforms.get('uInverseProjection')!.value.copy(camera.projectionMatrixInverse)
   effect.uniforms.get('uCameraWorld')!.value.copy(camera.matrixWorld)
   effect.uniforms.get('uClock')!.value=clock.getElapsedTime()
 })
 useEffect(()=>()=>effect.dispose(),[effect])
 return <primitive object={effect} dispose={null}/>
}
