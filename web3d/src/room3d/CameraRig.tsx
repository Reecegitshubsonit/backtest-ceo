import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import type { OrbitControls } from 'three-stdlib'
import type { PanelAction, PanelState } from '../model/roomPanel'
import { screenById, type XYZ } from '../config/roomScreens'
import { constrain, flightPose, HOME } from './camera'

type Pose={position:XYZ;target:XYZ;offset:number}
export function CameraRig({panel,dispatch,controls,resetKey}:{panel:PanelState;dispatch:(a:PanelAction)=>void;controls:RefObject<OrbitControls|null>;resetKey:number}){
 const {camera,size}=useThree()
 const cam=camera as THREE.PerspectiveCamera
 const home=useRef<Pose|null>(null),animation=useRef<{from:Pose;to:Pose;t:number}|null>(null)
 const offset=useRef(HOME.offsetY)
 const reduced=useRef(window.matchMedia('(prefers-reduced-motion: reduce)').matches)
 const setOffset=(y:number)=>{cam.setViewOffset(1280,720,0,y,1280,720);cam.updateProjectionMatrix();offset.current=y}
 useLayoutEffect(()=>{
  if(panel.phase!=='closed')return
  animation.current=null;home.current=null
  cam.position.set(...HOME.position);controls.current?.target.set(...HOME.target);cam.lookAt(...HOME.target);setOffset(HOME.offsetY)
 },[resetKey])
 useEffect(()=>{
  if(panel.phase!=='flying'&&panel.phase!=='closing')return
  const from:Pose={position:cam.position.toArray() as XYZ,target:(controls.current?.target.toArray()??HOME.target) as XYZ,offset:offset.current}
  if(panel.phase==='flying'&&!home.current)home.current=from
  const screen=panel.screen?screenById(panel.screen):undefined
  const to:Pose=panel.phase==='flying'&&screen?{...flightPose(screen,size.width/size.height),offset:0}:home.current??{...HOME,offset:HOME.offsetY}
  animation.current={from,to,t:0}
 },[panel.phase,panel.screen,size.width,size.height])
 useFrame((_,dt)=>{
  const a=animation.current
  if(a&&(panel.phase==='flying'||panel.phase==='closing')){
   a.t=Math.min(1,a.t+(reduced.current?1:Math.min(dt,.1)/.95))
   const k=a.t*a.t*(3-2*a.t)
   const position=a.from.position.map((v,i)=>THREE.MathUtils.lerp(v,a.to.position[i],k)) as XYZ
   const target=a.from.target.map((v,i)=>THREE.MathUtils.lerp(v,a.to.target[i],k)) as XYZ
   cam.position.set(...constrain(position));controls.current?.target.set(...target);cam.lookAt(...target)
   setOffset(THREE.MathUtils.lerp(a.from.offset,a.to.offset,k))
   if(a.t===1){animation.current=null;if(panel.phase==='closing')home.current=null;dispatch({type:panel.phase==='flying'?'arrived':'returned'})}
  }else if(panel.phase==='closed'){
   cam.position.set(...constrain(cam.position.toArray() as XYZ))
  }
 })
 return null
}
