import { Suspense, useEffect, useMemo, useRef, useState, useSyncExternalStore, type RefObject } from 'react'
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls, useGLTF, useTexture } from '@react-three/drei'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import * as THREE from 'three'
import type { OrbitControls as Controls } from 'three-stdlib'
import { acceleratedRaycast, MeshBVH } from 'three-mesh-bvh'
import { ROOM_SCREENS, screenById, screenName, type RoomScreen } from '../config/roomScreens'
import type { PanelAction, PanelState } from '../model/roomPanel'
import { deskScreenAt } from '../model/deskPicking'
import { Slot } from '../panels/Slot'
import { HOME, flightDistance, inRoom, ZOOM } from './camera'
import { RoomScreenView } from '../panels/RoomScreenView'
import { SEATS } from '../config/seats'
import { api } from '../net/api'
import { CameraRig } from './CameraRig'
import { roomMaterial } from './material'
import { Beam } from './Beam'
import { LabelProjector, setHovered, getHovered } from './labels'

THREE.Mesh.prototype.raycast=acceleratedRaycast
type Props={panel:PanelState;dispatch:(a:PanelAction)=>void;host:HTMLElement;resetKey:number;onReady:(ready:boolean)=>void}
type Geo=THREE.BufferGeometry&{boundsTree?:MeshBVH}

// ---------------------------------------------------------------------------------------------
// Display graphics. Each canvas has the physical aspect of its monitor (the old shared 16:9 chart
// was stretched up to 4.6x on the tall s8/s9 panels), a title bar, axes and readable labels.
function rng(seed:number){return()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}}
const PURPLE='#9b7bff',BLUE='#3d8bff',CYAN='#5fd0ff',TEXT='#86a9d6',GRID='#0d1d38'
function displayTexture(screen:RoomScreen,index:number){
 const aspect=screen.w/screen.h,long=screen.kind==='desk'?1024:1536
 const W=Math.round(aspect>=1?long:long*aspect),H=Math.round(aspect>=1?long/aspect:long)
 const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H
 const c=canvas.getContext('2d')!,rand=rng(index*977+31),u=Math.min(W,H)/100
 c.fillStyle='#040a1a';c.fillRect(0,0,W,H)
 const title=screen.seat?SEATS.find(x=>x.id===screen.seat)!.name+' · CONSOLE':screenName(screen)
 c.fillStyle='#0a1830';c.fillRect(0,0,W,7*u);c.fillStyle='#cfe6ff';c.font=`600 ${3.6*u}px system-ui,sans-serif`;c.textBaseline='middle';c.fillText(title,2.5*u,3.6*u)
 c.fillStyle=TEXT;c.font=`${2.4*u}px ui-monospace,monospace`;c.textAlign='right';c.fillText(['SPY','QQQ','BTC/USD','IWM','ETH/USD','AAPL','NVDA','TLT'][index%8]+'  '+['1Min','5Min','15Min','1Hour'][index%4],W-2.5*u,3.6*u);c.textAlign='left'
 const panel=(x:number,y:number,w:number,h:number,label:string)=>{c.strokeStyle='#18345e';c.lineWidth=Math.max(1,.25*u);c.strokeRect(x,y,w,h);c.fillStyle=TEXT;c.font=`${2.1*u}px ui-monospace,monospace`;c.fillText(label,x+1.2*u,y+2.2*u)
  c.strokeStyle=GRID;c.lineWidth=Math.max(1,.15*u);for(let i=1;i<6;i++){const yy=y+h*i/6;c.beginPath();c.moveTo(x,yy);c.lineTo(x+w,yy);c.stroke()}for(let i=1;i<10;i++){const xx=x+w*i/10;c.beginPath();c.moveTo(xx,y+4*u);c.lineTo(xx,y+h);c.stroke()}}
 const candles=(x:number,y:number,w:number,h:number,n:number)=>{let p=.5;const pts:number[]=[];for(let i=0;i<n;i++){const o=p;p=Math.min(.92,Math.max(.08,p+(rand()-.49)*.09));const hi=Math.max(o,p)+rand()*.03,lo=Math.min(o,p)-rand()*.03,xx=x+(i+.5)*w/n;c.strokeStyle=c.fillStyle=p>=o?CYAN:PURPLE;c.lineWidth=Math.max(1,.18*u);c.beginPath();c.moveTo(xx,y+h*(1-hi));c.lineTo(xx,y+h*(1-lo));c.stroke();c.fillRect(xx-w/n*.3,y+h*(1-Math.max(o,p)),w/n*.6,Math.max(1,h*Math.abs(p-o)));pts.push(p)}
  c.strokeStyle='#c9b8ff';c.lineWidth=Math.max(1.5,.3*u);c.beginPath();pts.forEach((v,i)=>{const m=pts.slice(Math.max(0,i-8),i+1).reduce((a,b)=>a+b)/Math.min(i+1,9),xx=x+(i+.5)*w/n,yy=y+h*(1-m);i?c.lineTo(xx,yy):c.moveTo(xx,yy)});c.stroke()
  c.fillStyle=TEXT;c.font=`${1.9*u}px ui-monospace,monospace`;c.textAlign='right';for(let i=0;i<=4;i++)c.fillText((400+i*12.5).toFixed(1),x+w-.6*u,y+h*(1-i/4.4)-.4*u);c.textAlign='left'}
 const bars=(x:number,y:number,w:number,h:number,n:number)=>{for(let i=0;i<n;i++){const v=.15+rand()*.8;c.fillStyle=i%5?BLUE:'#6fb3ff';c.fillRect(x+i*w/n+w/n*.15,y+h*(1-v),w/n*.7,h*v)}}
 const line=(x:number,y:number,w:number,h:number,n:number,color:string)=>{let p=.5;c.strokeStyle=color;c.lineWidth=Math.max(1.5,.32*u);c.beginPath();for(let i=0;i<n;i++){p=Math.min(.95,Math.max(.05,p+(rand()-.5)*.12));const xx=x+i*w/(n-1),yy=y+h*(1-p);i?c.lineTo(xx,yy):c.moveTo(xx,yy)}c.stroke()}
 const table=(x:number,y:number,w:number,h:number,rows:number)=>{c.font=`${2.1*u}px ui-monospace,monospace`;for(let i=0;i<rows;i++){const yy=y+5*u+i*h/rows;c.fillStyle=TEXT;c.fillText(['SPY','QQQ','IWM','DIA','XLF','XLK','GLD','TLT','BTC','ETH','SOL','NVDA'][(i+index)%12],x+1.2*u,yy);const ch=(rand()-.45)*3;c.fillStyle=ch>=0?CYAN:PURPLE;c.textAlign='right';c.fillText((ch>=0?'+':'')+ch.toFixed(2)+'%',x+w-1.2*u,yy);c.textAlign='left'}}
 const m=2*u,top=9*u
 if(aspect<.6){ // tall pillar display: stacked watch list with sparklines
  const rows=Math.floor((H-top)/(14*u));for(let i=0;i<rows;i++){const y=top+i*14*u;panel(m,y,W-2*m,12*u,['SPY','QQQ','BTC','ETH','IWM','TLT','GLD','NVDA','AAPL','MSFT'][(i+index)%10]);line(m+u,y+4*u,W-2*m-2*u,7*u,40,i%2?PURPLE:CYAN)}
 }else if(screen.kind==='desk'){
  panel(m,top,W*.62-m,H*.55,'LAST RUN');candles(m+u,top+4*u,W*.62-3*u,H*.55-5*u,48)
  panel(W*.62+m,top,W*.38-2*m,H*.55,'QUEUE');table(W*.62+m,top,W*.38-2*m,H*.55,6)
  panel(m,top+H*.55+m,W-2*m,H-top-H*.55-2*m,'ACTIVITY');bars(m+u,top+H*.55+5*u,W-4*u,H-top-H*.55-7*u,60)
 }else if(aspect>2.2){ // wide strip
  panel(m,top,W*.7-m,H-top-m,'PRICE');candles(m+u,top+4*u,W*.7-3*u,H-top-6*u,90)
  panel(W*.7+m,top,W*.3-2*m,H-top-m,'MOVERS');table(W*.7+m,top,W*.3-2*m,H-top-m,Math.max(3,Math.floor((H-top)/(5*u))-1))
 }else{
  const kindOf=index%3
  panel(m,top,W-2*m,(H-top)*.58,kindOf===1?'EQUITY CURVE':'PRICE');kindOf===1?line(m+u,top+4*u,W-4*u,(H-top)*.58-5*u,120,PURPLE):candles(m+u,top+4*u,W-4*u,(H-top)*.58-5*u,70)
  const y2=top+(H-top)*.58+m,h2=H-y2-m
  panel(m,y2,W*.6-m,h2,kindOf===2?'DRAWDOWN':'VOLUME');bars(m+u,y2+4*u,W*.6-3*u,h2-5*u,50)
  panel(W*.6+m,y2,W*.4-2*m,h2,'WATCH');table(W*.6+m,y2,W*.4-2*m,h2,Math.max(2,Math.floor(h2/(5*u))-1))
 }
 const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.NoColorSpace;t.anisotropy=16;t.generateMipmaps=true;t.minFilter=THREE.LinearMipmapLinearFilter
 return t
}

// ---------------------------------------------------------------------------------------------
// Live desk consoles. Each desk console mirrors the same RoomScreenView the focused panel shows,
// as real DOM placed on the 3D screen. It mounts only when the camera is close, facing the
// console and not blocked, so it is sharp up close and costs nothing from across the room.
type Engine={state:'checking'|'up'|'down';keys:boolean;at:number;latency:number[]}
/** Read-only engine heartbeat (the same /api/health the HUD polls), with round-trip latency history. */
function useEngine(){
 const [engine,setEngine]=useState<Engine>({state:'checking',keys:false,at:0,latency:[]})
 useEffect(()=>{let alive=true
  const check=()=>{const t0=performance.now();api.health().then(h=>{if(alive)setEngine(e=>({state:'up',keys:h.alpaca_keys_present,at:Date.now(),latency:[...e.latency,performance.now()-t0].slice(-40)}))}).catch(()=>{if(alive)setEngine(e=>({...e,state:'down',at:Date.now()}))})}
  check();const id=setInterval(check,3000);return()=>{alive=false;clearInterval(id)}},[])
 return engine
}
function Spark({values}:{values:number[]}){
 if(values.length<2)return <svg className="live-spark" viewBox="0 0 100 30"/>
 const max=Math.max(...values,1),pts=values.map((v,i)=>`${(i/(values.length-1)*100).toFixed(1)},${(28-v/max*26).toFixed(1)}`).join(' ')
 return <svg className="live-spark" viewBox="0 0 100 30" preserveAspectRatio="none"><polyline points={pts} fill="none" stroke="#5fd0ff" strokeWidth="1.2" vectorEffect="non-scaling-stroke"/></svg>
}
function useNow(ms:number){const [now,setNow]=useState(()=>Date.now());useEffect(()=>{const id=setInterval(()=>setNow(Date.now()),ms);return()=>clearInterval(id)},[ms]);return now}
const CONSOLE_PX=900,noop=()=>{}
// Shared between the 3D projector (inside the Canvas) and the DOM layer (outside it).
const liveNodes=new Map<string,HTMLDivElement>()
const liveStore={key:'',listeners:new Set<()=>void>(),set(k:string){if(k!==this.key){this.key=k;for(const l of this.listeners)l()}}}
const subscribeLive=(l:()=>void)=>{liveStore.listeners.add(l);return()=>{liveStore.listeners.delete(l)}}
function LiveConsole({screen,turn,engine}:{screen:RoomScreen;turn:number;engine:Engine}){
 const now=useNow(1000)
 const seat=screen.seat?SEATS.find(x=>x.id===screen.seat):undefined
 const side=turn%2===1,width=side?CONSOLE_PX*screen.h/screen.w:CONSOLE_PX,height=side?CONSOLE_PX:CONSOLE_PX*screen.h/screen.w
 const ago=engine.at?Math.max(0,Math.round((now-engine.at)/1000)):0
 return <div className="live-console" data-screen={screen.id} data-turn={turn} style={{width,height}} ref={el=>{if(el)liveNodes.set(screen.id,el);else liveNodes.delete(screen.id)}}>
  <div className="live-strip">
   <span className={`live-dot ${engine.state}`}/>
   <span>ENGINE {engine.state==='up'?(engine.keys?'CONNECTED':'CONNECTED · NO KEYS'):engine.state==='down'?'OFFLINE':'CHECKING'}</span>
   <span className="live-state">{seat?'IDLE · AWAITING STRATEGY':'UNASSIGNED'}</span>
   <time>{new Date(now).toLocaleTimeString([], {hour12:false})}</time>
  </div>
  <div className="live-body">
   <RoomScreenView id={screen.id} asset="etfs" onAsset={noop} actions={<span className="live-tag">LIVE · {engine.at?`checked ${ago}s ago`:'…'}</span>}/>
  </div>
  <div className="live-idle">
   <div><span>STATUS</span><b>{seat?'Idle — no strategy assigned':'Not assigned'}</b></div>
   <div><span>WORK QUEUE</span><b>0 tasks</b></div>
   <div><span>LAST REPORT</span><b>—</b></div>
   <div className="wide"><span>ENGINE ROUND TRIP {engine.latency.length?`${engine.latency.at(-1)!.toFixed(0)} ms`:''}</span><Spark values={engine.latency}/></div>
  </div>
 </div>
}
/** DOM layer over the canvas: mounts the consoles the 3D projector says are in view. */
export function LiveConsoleLayer(){
 const key=useSyncExternalStore(subscribeLive,()=>liveStore.key)
 const engine=useEngine()
 const items=key.split(',').filter(Boolean).map(k=>{const [id,turn]=k.split(':');return {screen:screenById(id)!,turn:+turn}})
 return <div className="live-layer">{items.map(i=><LiveConsole key={i.screen.id} screen={i.screen} turn={i.turn} engine={engine}/>)}</div>
}
// Exact projective mapping (homography) of the console rectangle onto the screen's four
// projected corners, as a CSS matrix3d. Includes the calibrated view offset, so DOM and 3D agree.
function homography(src:number[][],dst:number[][]){
 const A:number[][]=[]
 for(let i=0;i<4;i++){const [x,y]=src[i],[u,v]=dst[i];A.push([x,y,1,0,0,0,-u*x,-u*y,u]);A.push([0,0,0,x,y,1,-v*x,-v*y,v])}
 for(let j=0;j<8;j++){let piv=j;for(let i=j+1;i<8;i++)if(Math.abs(A[i][j])>Math.abs(A[piv][j]))piv=i;[A[j],A[piv]]=[A[piv],A[j]];const d=A[j][j];if(Math.abs(d)<1e-12)return null;for(let k=j;k<9;k++)A[j][k]/=d;for(let i=0;i<8;i++)if(i!==j){const f=A[i][j];for(let k=j;k<9;k++)A[i][k]-=f*A[j][k]}}
 const h=A.map(r=>r[8])
 return `matrix3d(${h[0]},${h[3]},0,${h[6]},${h[1]},${h[4]},0,${h[7]},0,0,1,0,${h[2]},${h[5]},0,1)`
}
export const LIVE_RANGE=3.6
function LiveProjector({panel}:{panel:PanelState}){
 const {camera,scene,size}=useThree()
 const desks=useMemo(()=>ROOM_SCREENS.filter(s=>s.kind==='desk'),[])
 const frame=useRef(0),ray=useMemo(()=>new THREE.Raycaster(),[]),blocked=useRef(new Map<string,boolean>()),turns=useRef(new Map<string,number>())
 useEffect(()=>()=>liveStore.set(''),[])
 useFrame(()=>{
  frame.current++
  const list:string[]=[]
  for(const s of desks){
   const c=new THREE.Vector3(...s.center),to=camera.position.clone().sub(c),d=to.length()
   const facing=to.dot(new THREE.Vector3(...s.normal))/d
   if(panel.phase!=='closed'||d>LIVE_RANGE||facing<.22)continue
   const q=new THREE.Quaternion(...s.quaternion),right=new THREE.Vector3(1,0,0).applyQuaternion(q),up=new THREE.Vector3(0,1,0).applyQuaternion(q)
   if(frame.current%10===0||!blocked.current.has(s.id)){ // occlusion: most of the face hidden behind a person
    let hidden=0
    for(const [x,y] of [[0,0],[-.35,-.35],[.35,-.35],[-.35,.35],[.35,.35]]){const p=c.clone().addScaledVector(right,x*s.w).addScaledVector(up,y*s.h),dir=p.clone().sub(camera.position),len=dir.length();ray.set(camera.position,dir.normalize());ray.far=len-.02
     const hit=ray.intersectObjects(scene.children,true).find(h=>h.object.visible&&!h.object.name.startsWith('screen_')&&h.object.name!=='command_desk'&&h.object.name!=='projector_inset');if(hit)hidden++}
    blocked.current.set(s.id,hidden>=3)
   }
   if(blocked.current.get(s.id))continue
   // quarter turn so the content reads upright for this viewer, with hysteresis
   const want=Math.atan2(to.dot(right),-to.dot(up)),prev=turns.current.get(s.id)
   const diff=prev===undefined?Infinity:Math.abs(Math.atan2(Math.sin(want-prev*Math.PI/2),Math.cos(want-prev*Math.PI/2)))
   if(diff>Math.PI*.33)turns.current.set(s.id,((Math.round(want/(Math.PI/2))%4)+4)%4)
   const turn=turns.current.get(s.id)!
   // corners of the face, starting at the content's top-left for this turn
   const local=[[-.5,.5],[.5,.5],[.5,-.5],[-.5,-.5]],pts:number[][]=[]
   let behind=false
   for(let k=0;k<4;k++){const [x,y]=local[(k+4-turn)%4];const p=c.clone().addScaledVector(right,x*s.w).addScaledVector(up,y*s.h).addScaledVector(new THREE.Vector3(...s.normal),.006);const v=p.clone().applyMatrix4(camera.matrixWorldInverse);if(v.z>-.05)behind=true;p.project(camera);pts.push([(p.x+1)/2*size.width,(1-p.y)/2*size.height])}
   if(behind||pts.some(([x,y])=>Math.abs(x-size.width/2)>size.width*2||Math.abs(y-size.height/2)>size.height*2))continue
   list.push(s.id+':'+turn)
   const node=liveNodes.get(s.id)
   if(node){const w=node.offsetWidth,h=node.offsetHeight,m=homography([[0,0],[w,0],[w,h],[0,h]],pts);if(m){node.style.transform=m;node.style.visibility='visible'}}
  }
  liveStore.set(list.join(','))
 })
 return null
}

// ---------------------------------------------------------------------------------------------
// Smooth zoom. Wheel, trackpad pinch (ctrl+wheel) and two-finger touch pinch feed one damped
// log-distance accumulator. The camera and orbit target both slide toward the 3D point under
// the cursor, stop a fixed distance before the surface (never clipping into it) and never leave
// the room on the way out, so there is no clamping fight and no snap.
function SmoothZoom({controls,enabled}:{controls:RefObject<Controls|null>;enabled:boolean}){
 const {camera,gl,scene}=useThree()
 const pending=useRef(0),focus=useRef(new THREE.Vector3(...HOME.target)),surface=useRef(Infinity),assist=useRef<RoomScreen|null>(null)
 const ray=useMemo(()=>new THREE.Raycaster(),[])
 const live=useRef(enabled);live.current=enabled
 useEffect(()=>{
  const el=gl.domElement
  const aim=(cx:number,cy:number)=>{
   const r=el.getBoundingClientRect();ray.setFromCamera(new THREE.Vector2((cx-r.left)/r.width*2-1,-(cy-r.top)/r.height*2+1),camera);ray.far=60
   const hit=ray.intersectObjects(scene.children,true).find(h=>h.object.visible&&!((h.object as THREE.Mesh).material as THREE.MeshBasicMaterial)?.wireframe)
   if(hit){focus.current.copy(hit.point);surface.current=hit.distance
    // aiming at a desk console (its face or its sector of the desk) engages the reading assist
    const n=hit.object.name,direct=n.startsWith('screen_')?screenById(n.slice(7)):undefined
    assist.current=direct?.kind==='desk'?direct:n==='command_desk'?deskScreenAt(hit.point):null}
   else{assist.current=null;const t=controls.current?.target??new THREE.Vector3(...HOME.target);focus.current.copy(ray.ray.at(camera.position.distanceTo(t),new THREE.Vector3()));surface.current=Infinity}
  }
  const wheel=(e:WheelEvent)=>{if(!live.current)return;e.preventDefault();aim(e.clientX,e.clientY)
   let dy=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?400:1);if(e.ctrlKey)dy*=3
   pending.current=THREE.MathUtils.clamp(pending.current+dy*ZOOM.wheel,-1.2,1.2)}
  let pinch=0
  const touches=(e:TouchEvent)=>{if(e.touches.length!==2){pinch=0;return}const [a,b]=[e.touches[0],e.touches[1]],d=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);if(pinch&&live.current){aim((a.clientX+b.clientX)/2,(a.clientY+b.clientY)/2);pending.current=THREE.MathUtils.clamp(pending.current+Math.log(pinch/d),-1.2,1.2)}pinch=d}
  el.addEventListener('wheel',wheel,{passive:false});el.addEventListener('touchstart',touches,{passive:true});el.addEventListener('touchmove',touches,{passive:true});el.addEventListener('touchend',touches)
  return()=>{el.removeEventListener('wheel',wheel);el.removeEventListener('touchstart',touches);el.removeEventListener('touchmove',touches);el.removeEventListener('touchend',touches)}
 },[gl,camera,scene,controls,ray])
 useFrame((_,dt)=>{
  const c=controls.current
  if(!c||!enabled){pending.current=0;return}
  if(Math.abs(pending.current)<1e-4){pending.current=0;return}
  const step=pending.current*(1-Math.exp(-Math.min(dt,.1)*ZOOM.smoothing));pending.current-=step
  let k=Math.exp(step)
  const F=focus.current,pos=camera.position,dist=pos.distanceTo(F)
  const at=(kk:number)=>F.clone().add(pos.clone().sub(F).multiplyScalar(kk))
  if(k<1&&dist*k<ZOOM.minSurface){k=Math.min(1,ZOOM.minSurface/dist);pending.current=0}
  if(k>1&&(!inRoom(at(k))||dist*k>ZOOM.maxDistance)){let lo=1,hi=k;for(let i=0;i<14;i++){const mid=(lo+hi)/2;if(inRoom(at(mid))&&dist*mid<=ZOOM.maxDistance)lo=mid;else hi=mid}k=lo;pending.current=0}
  if(Math.abs(k-1)<1e-6)return
  pos.sub(F).multiplyScalar(k).add(F);c.target.sub(F).multiplyScalar(k).add(F)
  // Reading assist: zooming in on a flat desk console swings the view over it, so the console is
  // seen nearly face-on (not at a grazing, smeared angle) and ends at a comfortable reading distance.
  const a=assist.current
  if(a&&k<1){
   const centre=new THREE.Vector3(...a.center),d=pos.distanceTo(centre)
   const w=THREE.MathUtils.smoothstep(d,ZOOM.assistFar,ZOOM.assistNear)
   if(w>0){
    const flat=pos.clone().sub(centre).setY(0).normalize(),dir=new THREE.Vector3(...a.normal).addScaledVector(flat,.42).normalize()
    const goal=centre.clone().addScaledVector(dir,Math.max(ZOOM.readDistance,d)),blend=w*(1-Math.exp(-Math.min(dt,.1)*6))
    pos.lerp(goal,blend);c.target.lerp(centre,blend)
    focus.current.lerp(centre,blend)
    if(d>ZOOM.readDistance*1.02&&pending.current>-.05)pending.current=Math.min(pending.current,-.05)
   }
  }
  // zooming out gently re-centres the orbit on the command desk
  if(k>1)c.target.lerp(new THREE.Vector3(...HOME.target),Math.min(1,(k-1)*.6))
  c.update()
 })
 return null
}

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
function Screen({mesh,screen,panel,dispatch,onHover,tableMap,sharp}:{sharp:THREE.CanvasTexture;tableMap:THREE.Texture;mesh:THREE.Mesh;screen:RoomScreen;panel:PanelState;dispatch:Props['dispatch'];onHover:(id:string|null)=>void}){
 const [hot,setHot]=useState(false)
 const material=useMemo(()=>{const m=roomMaterial('screen',sharp);m.uniforms.uDesk.value=screen.kind==='desk'?1:0;m.uniforms.uPhoto.value=tableMap;return m},[sharp,tableMap,screen.kind])
 const {camera,size}=useThree()
 useFrame(()=>{
   const projected=screen.w/(2*camera.position.distanceTo(new THREE.Vector3(...screen.center))*Math.tan(48*Math.PI/360)*(size.width/size.height))*size.width
   material.uniforms.uDetail.value=THREE.MathUtils.smoothstep(projected,screen.rect.w*1.5,screen.rect.w*2.5)
   material.uniforms.uHot.value=hot||getHovered()===screen.id?1:0
 })
 useEffect(()=>()=>{material.dispose()},[material])
 const enabled=panel.phase==='closed'||panel.phase==='focused'
 const hover=(on:boolean)=>{if(!enabled)on=false;setHot(on);onHover(on?screen.id:null);document.body.style.cursor=on?'pointer':''}
 const pick=(e:ThreeEvent<MouseEvent>)=>{e.stopPropagation();if(enabled&&e.delta<=6){hover(false);dispatch({type:'click',id:screen.id})}}
 return <mesh name={mesh.name} geometry={mesh.geometry} material={material} visible={!(panel.phase==='focused'&&panel.screen===screen.id)}
   onPointerOver={e=>{e.stopPropagation();hover(true)}} onPointerOut={()=>hover(false)} onClick={pick}/>
}
function Assets({panel,dispatch,host,onReady}:Props){
 const {scene}=useGLTF('/models/reference-room.glb')
 const tableMap=useTexture('/textures/desk-reference-material.png')
 tableMap.colorSpace=THREE.NoColorSpace;tableMap.anisotropy=16
 const sharpMap=useMemo(()=>new Map(ROOM_SCREENS.map((s,i)=>[s.id,displayTexture(s,i)])),[])
 const wallMap=sharpMap.get('s5')!
 const wireMaterial=useMemo(()=>new THREE.MeshBasicMaterial({color:'#49baff',wireframe:true,transparent:true,opacity:.012,depthWrite:false,blending:THREE.AdditiveBlending,polygonOffset:true,polygonOffsetFactor:-1}),[])
 const assets=useMemo(()=>{
   const result:{mesh:THREE.Mesh;kind:string;material:THREE.ShaderMaterial}[]=[]
   scene.traverse(o=>{if(!(o instanceof THREE.Mesh))return;const geometry=o.geometry as Geo;if(!geometry.boundsTree)geometry.boundsTree=new MeshBVH(geometry,{maxLeafTris:12});const kind=o.userData.kind??'wall';result.push({mesh:o,kind,material:roomMaterial(kind,kind==='desk'?tableMap:kind==='wall'?wallMap:undefined)})})
   return result
 },[scene,tableMap,wallMap])
 useEffect(()=>()=>{for(const a of assets)a.material.dispose();tableMap.dispose();for(const texture of sharpMap.values())texture.dispose();wireMaterial.dispose();document.body.style.cursor=''},[assets,tableMap,sharpMap,wireMaterial])
 useFrame(({clock})=>{
   for(const a of assets)a.material.uniforms.uTime.value=clock.getElapsedTime()
 })
 useEffect(()=>{if(panel.phase!=='closed'&&panel.phase!=='focused'){setHovered(null);document.body.style.cursor=''}},[panel.phase])
 useEffect(()=>{onReady(true)},[onReady])
 const deskStation=(e:ThreeEvent<PointerEvent|MouseEvent>)=>panel.phase==='closed'?deskScreenAt(e.point):null
 const focused=panel.phase==='focused'&&panel.screen?screenById(panel.screen):undefined
 return <>
  {assets.map(({mesh,kind,material})=>{
    const s=mesh.name.startsWith('screen_')?screenById(mesh.name.slice(7)):undefined
    const frameScreen=mesh.name.startsWith('frame_')?screenById(mesh.name.slice(6)):undefined
    return s?<Screen key={mesh.name} mesh={mesh} screen={s} panel={panel} dispatch={dispatch} onHover={setHovered} tableMap={tableMap} sharp={sharpMap.get(s.canonicalId??s.id)!}/>
     :<group key={mesh.name}><mesh name={mesh.name} geometry={mesh.geometry} material={material} onClick={e=>{e.stopPropagation();const s=frameScreen&&panel.phase==='closed'?frameScreen:kind==='desk'?deskStation(e):null;if(s&&e.delta<=6){setHovered(null);dispatch({type:'click',id:s.id})}}}
        onPointerMove={e=>{if(kind!=='desk'&&!frameScreen)return;e.stopPropagation();const s=frameScreen&&panel.phase==='closed'?frameScreen:deskStation(e);setHovered(s?.id??null);document.body.style.cursor=s?'pointer':''}}
        onPointerOut={()=>{if(kind==='desk'||frameScreen){setHovered(null);document.body.style.cursor=''}}} onPointerOver={e=>e.stopPropagation()}/>{kind==='hologram'&&<mesh geometry={mesh.geometry} material={wireMaterial} raycast={()=>null}/>}</group>
  })}
  {focused&&<Preview screen={focused} host={host}/>}
  <LiveProjector panel={panel}/>

 </>
}
// Development-only handle for headless visual checks (camera poses, raycast click tests).
function DevHandle({controls}:{controls:React.RefObject<Controls|null>}){
 const state=useThree()
 useEffect(()=>{if(!import.meta.env.DEV)return;(window as unknown as {__room3d?:unknown}).__room3d={camera:state.camera,scene:state.scene,gl:state.gl,controls:controls.current};return()=>{delete (window as unknown as {__room3d?:unknown}).__room3d}},[state.camera,state.scene,state.gl,controls])
 return null
}
export function RoomScene(props:Props){
 const controls=useRef<Controls>(null)
 const fx=new URLSearchParams(window.location.search).get('fx')!=='low'
 return <><Canvas className="room-canvas" dpr={[1,1.5]} camera={{position:HOME.position,fov:48,near:.05,far:80}} gl={{antialias:true,powerPreference:'high-performance'}}>
  <color attach="background" args={['#02040a']}/>
  <Suspense fallback={null}><Assets {...props}/></Suspense>
  <OrbitControls ref={controls} makeDefault target={HOME.target} enablePan enableZoom={false} screenSpacePanning enableDamping dampingFactor={.10}
   minDistance={.05} maxDistance={ZOOM.maxDistance} minPolarAngle={.05} maxPolarAngle={2.0} enabled={props.panel.phase==='closed'}/>
  <SmoothZoom controls={controls} enabled={props.panel.phase==='closed'}/>
  <CameraRig panel={props.panel} dispatch={props.dispatch} controls={controls} resetKey={props.resetKey}/>
  {import.meta.env.DEV&&<DevHandle controls={controls}/>}
  <LabelProjector hidden={props.panel.phase!=='closed'}/>
  <EffectComposer depthBuffer multisampling={0}>
   <Beam/>
   {fx?<Bloom intensity={.55} luminanceThreshold={.20} mipmapBlur/>:<></>}
  </EffectComposer>
 </Canvas><LiveConsoleLayer/></>
}
