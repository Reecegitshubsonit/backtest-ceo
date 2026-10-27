import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { SEATS } from '../config/seats'
import { CEO_LABEL, SEAT_SPOTS, SUMMARY_LABEL } from '../config/imageRoom'
import { ROOM_OBJECTS } from '../config/roomObjects'
import { screenById, screenName } from '../config/roomScreens'
import { referencePoint } from './camera'

const nodes=new Map<string,HTMLDivElement>()
let hovered:string|null=null
export function getHovered(){return hovered}
let inspecting:string|null=null
export function getInspecting(){return inspecting}
export function setHovered(id:string|null){hovered=id;const show=id&&id!==inspecting,el=nodes.get('hover');if(el){el.textContent=show?screenName(screenById(id)!):'';el.style.display=show?'':'none'}}
/** While a screen is being read head-on, room labels step aside and a short hint says how to get out. */
export function setInspecting(id:string|null){inspecting=id;setHovered(hovered);const el=nodes.get('inspect');if(el){el.style.display=id?'':'none';const name=el.querySelector('b');if(name)name.textContent=id?screenName(screenById(id)!):''}}
const middle=(r:{x:number;y:number;w:number;h:number})=>[r.x+r.w/2,r.y+r.h/2]
const anchors=[
 {id:'ceo',point:middle(CEO_LABEL),z:.14,lines:['CEO AI','STRATEGIC OVERSIGHT','FINAL DECISION AUTHORITY']},
 {id:'summary',point:middle(SUMMARY_LABEL),z:1.2,lines:['EXECUTIVE SUMMARY','SYNTHESIZING AGENT REPORTS']},
 ...SEATS.map(s=>{
  const o=ROOM_OBJECTS.find(o=>o.name===`agent_${s.id}`)!;const z=(o.bounds[0][2]+o.bounds[1][2])/2
  return{id:s.id,point:middle(SEAT_SPOTS[s.id].label),z,lines:[s.name,s.job,'● Live Feed']}
 }),
].map(a=>{
 // Canonical reference label positions, anchored at each object's real depth.
 const world=referencePoint(a.point[0],a.point[1],a.z)
 return {...a,world,homeDistance:world.distanceTo(new THREE.Vector3(0,3.844,7.04))}
})
export function RoomLabels(){return <div className="room-labels" aria-hidden>
 {anchors.map(a=><div key={a.id} className={`room-label ${a.id==='ceo'?'ceo':a.id==='summary'?'summary':'agent'}`} ref={el=>{if(el)nodes.set(a.id,el);else nodes.delete(a.id)}}>
  <b>{a.lines[0]}</b>{a.lines.slice(1).map((l,i)=><span key={i}>{l}</span>)}
 </div>)}
 <div className="room-hover-name" style={{display:'none'}} ref={el=>{if(el)nodes.set('hover',el);else nodes.delete('hover')}}/>
 <div className="room-inspect-hint" style={{display:'none'}} ref={el=>{if(el)nodes.set('inspect',el);else nodes.delete('inspect')}}><b/><span>Scroll out, Esc or double-click to step back · click to open</span></div>
 </div>}
export function LabelProjector({hidden}:{hidden:boolean}){
 const {camera,size}=useThree()
 useFrame(()=>{
  const occupied:{left:number;right:number;top:number;bottom:number}[]=[]
  const ordered=[...anchors].sort((a,b)=>(a.id==='ceo'?-1000:a.world.distanceTo(camera.position))-(b.id==='ceo'?-1000:b.world.distanceTo(camera.position)))
  for(const a of ordered){
   const el=nodes.get(a.id);if(!el)continue
   const v=a.world.clone().project(camera),behind=v.z>1||v.z< -1
   const scale=THREE.MathUtils.clamp(a.homeDistance/camera.position.distanceTo(a.world),.4,1.3)
   const x=(v.x+1)*size.width/2,y=(1-v.y)*size.height/2
   const off=hidden||behind||inspecting!==null
   el.style.display=off?'none':''
   if(off)continue
   const w=el.offsetWidth*scale,h=el.offsetHeight*scale
   const rect={left:x-w/2-4,right:x+w/2+4,top:y-h/2-3,bottom:y+h/2+3}
   const overlaps=occupied.some(b=>rect.left<b.right&&rect.right>b.left&&rect.top<b.bottom&&rect.bottom>b.top)
   el.style.display=overlaps?'none':''
   if(!overlaps)occupied.push(rect)
   el.style.transform=`translate(-50%,-50%) translate(${x}px,${y}px) scale(${scale})`
  }
  const hint=nodes.get('inspect');if(hint)hint.style.display=inspecting&&!hidden?'':'none'
  const el=nodes.get('hover');if(el&&hovered&&hovered!==inspecting){const s=screenById(hovered)!;const v=new THREE.Vector3(...s.center).project(camera);el.style.transform=`translate(-50%,-100%) translate(${(v.x+1)*size.width/2}px,${(1-v.y)*size.height/2-16}px)`}
 })
 return null
}
