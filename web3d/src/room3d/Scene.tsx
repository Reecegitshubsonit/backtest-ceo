import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useLoader, useThree, type ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls, useGLTF, useTexture } from '@react-three/drei'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import * as THREE from 'three'
import type { OrbitControls as Controls } from 'three-stdlib'
import { acceleratedRaycast, MeshBVH } from 'three-mesh-bvh'
import { ROOM_SCREENS, screenById, screenName, type RoomScreen } from '../config/roomScreens'
import type { PanelAction, PanelState } from '../model/roomPanel'
import { Slot } from '../panels/Slot'
import { HOME, flightDistance } from './camera'
import { CameraRig } from './CameraRig'
import { roomMaterial } from './material'
import { chartTexture, deskTexture } from './charts'
import { Beam } from './Beam'
import { LabelProjector, setHovered } from './labels'

THREE.Mesh.prototype.raycast=acceleratedRaycast
type Props={panel:PanelState;dispatch:(a:PanelAction)=>void;host:HTMLElement;resetKey:number;onReady:(ready:boolean)=>void}
type Geo=THREE.BufferGeometry&{boundsTree?:MeshBVH}

function Preview({screen,host}:{screen:RoomScreen;host:HTMLElement}){
 const {size}=useThree()
 const d=flightDistance(screen.w,screen.h,size.width/size.height)
 const px=screen.w/(2*d*Math.tan(48*Math.PI/360)*(size.width/size.height))*size.width
 const rotation=useMemo(()=>new THREE.Quaternion(...screen.quaternion),[screen])
 const position=new THREE.Vector3(...screen.center).addScaledVector(new THREE.Vector3(...screen.normal),.012)
 return <Html transform position={position} quaternion={rotation} distanceFactor={400*screen.w/px} zIndexRange={[30,20]}>
  <div className="room-screen-preview" style={{width:px,height:px*screen.h/screen.w}}><Slot host={host} className="slotfill"/></div>
 </Html>
}
function Screen({mesh,screen,reference,depth,panel,dispatch,onHover}:{mesh:THREE.Mesh;screen:RoomScreen;reference:THREE.Texture;depth:THREE.DataTexture;panel:PanelState;dispatch:Props['dispatch'];onHover:(id:string|null)=>void}){
 const [hot,setHot]=useState(false)
 const sharp=useMemo(()=>chartTexture(ROOM_SCREENS.indexOf(screen)),[screen])
 const material=useMemo(()=>roomMaterial(reference,depth,'screen',sharp),[reference,depth,sharp])
 const {camera,size}=useThree()
 useFrame(()=>{
   const projected=screen.w/(2*camera.position.distanceTo(new THREE.Vector3(...screen.center))*Math.tan(48*Math.PI/360)*(size.width/size.height))*size.width
   material.uniforms.uDetail.value=screen.kind==='desk'?1:THREE.MathUtils.smoothstep(projected,screen.rect.w*1.5,screen.rect.w*2.5)
   material.uniforms.uHot.value=hot?1:0
 })
 useEffect(()=>()=>{material.dispose();sharp.dispose()},[material,sharp])
 const enabled=panel.phase==='closed'||panel.phase==='focused'
 const hover=(on:boolean)=>{if(!enabled)on=false;setHot(on);onHover(on?screen.id:null);document.body.style.cursor=on?'pointer':''}
 const pick=(e:ThreeEvent<MouseEvent>)=>{e.stopPropagation();if(enabled&&e.delta<=6){hover(false);dispatch({type:'click',id:screen.id})}}
 return <mesh geometry={mesh.geometry} material={material} visible={!(panel.phase==='focused'&&panel.screen===screen.id)}
   onPointerOver={e=>{e.stopPropagation();hover(true)}} onPointerOut={()=>hover(false)} onClick={pick}/>
}
function Assets({panel,dispatch,host,onReady}:Props){
 const {scene}=useGLTF('/models/reference-room.glb')
 const reference=useTexture('/room.jpg')
 const buffer=useLoader(THREE.FileLoader,'/models/reference-depth.bin',loader=>loader.setResponseType('arraybuffer')) as unknown as ArrayBuffer
 const depth=useMemo(()=>{const t=new THREE.DataTexture(new Float32Array(buffer),1280,720,THREE.RedFormat,THREE.FloatType);t.minFilter=THREE.NearestFilter;t.magFilter=THREE.NearestFilter;t.needsUpdate=true;return t},[buffer])
 const tableMap=useMemo(deskTexture,[])
 const wallMap=useMemo(()=>chartTexture(4),[])
 const assets=useMemo(()=>{
   reference.colorSpace=THREE.SRGBColorSpace;reference.anisotropy=8
   const result:{mesh:THREE.Mesh;kind:string;material:THREE.ShaderMaterial}[]=[]
   scene.traverse(o=>{if(!(o instanceof THREE.Mesh))return;const geometry=o.geometry as Geo;if(!geometry.boundsTree)geometry.boundsTree=new MeshBVH(geometry,{maxLeafTris:12});const kind=o.userData.kind??'wall';result.push({mesh:o,kind,material:roomMaterial(reference,depth,kind,kind==='desk'?tableMap:kind==='wall'?wallMap:undefined)})})
   return result
 },[scene,reference,depth,tableMap,wallMap])
 useEffect(()=>()=>{for(const a of assets)a.material.dispose();tableMap.dispose();wallMap.dispose();depth.dispose();document.body.style.cursor=''},[assets,depth,tableMap,wallMap])
 useFrame(({clock})=>{
   for(const a of assets)a.material.uniforms.uTime.value=clock.getElapsedTime()
 })
 useEffect(()=>{if(panel.phase!=='closed'&&panel.phase!=='focused'){setHovered(null);document.body.style.cursor=''}},[panel.phase])
 useEffect(()=>{onReady(true)},[onReady])
 const focused=panel.phase==='focused'&&panel.screen?screenById(panel.screen):undefined
 return <>
  {assets.map(({mesh,kind,material})=>{
    const s=mesh.name.startsWith('screen_')?screenById(mesh.name.slice(7)):undefined
    return s?<Screen key={mesh.name} mesh={mesh} screen={s} reference={reference} depth={depth} panel={panel} dispatch={dispatch} onHover={setHovered}/>
     :<mesh key={mesh.name} name={mesh.name} geometry={mesh.geometry} material={material} onClick={e=>e.stopPropagation()} onPointerOver={e=>e.stopPropagation()}/>
  })}
  {focused&&<Preview screen={focused} host={host}/>}

 </>
}
export function RoomScene(props:Props){
 const controls=useRef<Controls>(null)
 const fx=new URLSearchParams(window.location.search).get('fx')!=='low'
 return <Canvas className="room-canvas" dpr={[1,1.5]} camera={{position:HOME.position,fov:48,near:.05,far:80}} gl={{antialias:true,powerPreference:'high-performance'}}>
  <color attach="background" args={['#02040a']}/>
  <Suspense fallback={null}><Assets {...props}/></Suspense>
  <OrbitControls ref={controls} makeDefault target={HOME.target} enablePan zoomToCursor screenSpacePanning enableDamping dampingFactor={.10}
   minDistance={.9} maxDistance={16} minPolarAngle={.05} maxPolarAngle={2.0} enabled={props.panel.phase==='closed'}/>
  <CameraRig panel={props.panel} dispatch={props.dispatch} controls={controls} resetKey={props.resetKey}/>
  <LabelProjector hidden={props.panel.phase!=='closed'}/>
  <EffectComposer depthBuffer multisampling={0}>
   <Beam/>
   {fx?<Bloom intensity={.25} luminanceThreshold={.8} mipmapBlur/>:<></>}
  </EffectComposer>
 </Canvas>
}
