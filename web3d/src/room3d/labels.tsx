import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { SEATS } from '../config/seats'
import { CEO_LABEL, SEAT_SPOTS, SUMMARY_LABEL } from '../config/imageRoom'
import { ROOM_OBJECTS } from '../config/roomObjects'
import { screenById, screenName } from '../config/roomScreens'
import { referencePoint } from './camera'

const nodes=new Map<string,HTMLDivElement>()
let hovered:string|null=null
export function setHovered(id:string|null){hovered=id;const el=nodes.get('hover');if(el){el.textContent=id?screenName(screenById(id)!):'';el.style.display=id?'':'none'}}
const middle=(r:{x:number;y:number;w:number;h:number})=>[r.x+r.w/2,r.y+r.h/2]
const anchors=[
 {id:'ceo',point:middle(CEO_LABEL),z:.14,lines:['CEO AI','STRATEGIC OVERSIGHT','FINAL DECISION AUTHORITY']},
 {id:'summary',point:middle(SUMMARY_LABEL),z:1.2,lines:['EXECUTIVE SUMMARY','SYNTHESIZING AGENT REPORTS']},
 ...SEATS.map(s=>{
  const o=ROOM_OBJECTS.find(o=>o.name===`agent_${s.id}`)!;const z=(o.bounds[0][2]+o.bounds[1][2])/2
  return{id:s.id,point:middle(SEAT_SPOTS[s.id].label),z,lines:[s.name,s.job,'● Live Feed']}
 }),
].map(a=>({...a,world:referencePoint(a.point[0],a.point[1],a.z)}))
export function RoomLabels(){return <div className="room-labels" aria-hidden>
 {anchors.map(a=><div key={a.id} className={`room-label ${a.id==='ceo'?'ceo':a.id==='summary'?'summary':'agent'}`} ref={el=>{if(el)nodes.set(a.id,el);else nodes.delete(a.id)}}>
  <b>{a.lines[0]}</b>{a.lines.slice(1).map((l,i)=><span key={i}>{l}</span>)}
 </div>)}
 <div className="room-hover-name" style={{display:'none'}} ref={el=>{if(el)nodes.set('hover',el);else nodes.delete('hover')}}/>
 </div>}
export function LabelProjector({hidden}:{hidden:boolean}){
 const {camera,size}=useThree()
 useFrame(()=>{
  for(const a of anchors){const el=nodes.get(a.id);if(!el)continue;const v=a.world.clone().project(camera);const behind=v.z>1||v.z< -1;el.style.display=hidden||behind?'none':'';el.style.transform=`translate(-50%,-50%) translate(${(v.x+1)*size.width/2}px,${(1-v.y)*size.height/2}px)`}
  const el=nodes.get('hover');if(el&&hovered){const s=screenById(hovered)!;const v=new THREE.Vector3(...s.center).project(camera);el.style.transform=`translate(-50%,-100%) translate(${(v.x+1)*size.width/2}px,${(1-v.y)*size.height/2-16}px)`}
 })
 return null
}
