import { describe, expect, it } from 'vitest'
import * as THREE from 'three'
import { readFileSync } from 'node:fs'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { ROOM_SCREENS } from '../src/config/roomScreens'
import { ROOM_OBJECTS } from '../src/config/roomObjects'
import { WALL_SCREENS, DESK_SCREENS } from '../src/config/imageRoom'
import { PANEL_CLOSED, panelReduce } from '../src/model/roomPanel'
import { constrain, flightPose, HOME, LIMITS, referenceCamera } from '../src/room3d/camera'

describe('complete reference room',()=>{
 it('retains every canonical id and computer/agent assignment',()=>{
  const original=[...WALL_SCREENS,...DESK_SCREENS]
  expect(ROOM_SCREENS).toHaveLength(26)
  expect(new Set(ROOM_SCREENS.map(s=>s.id)).size).toBe(26)
  for(const s of original){const found=ROOM_SCREENS.find(x=>x.id===s.id)!;expect(found).toBeDefined();expect(found.n).toBe(s.n);expect(found.computer).toBe(s.computer);expect(found.seat).toBe(s.seat)}
 })
 it('contains real volume for every person, chair and the command desk',()=>{
  expect(ROOM_OBJECTS.filter(o=>o.kind==='hologram')).toHaveLength(6)
  expect(ROOM_OBJECTS.filter(o=>o.kind==='chair')).toHaveLength(7)
  expect(ROOM_OBJECTS.some(o=>o.name==='operator')).toBe(true)
  expect(ROOM_OBJECTS.some(o=>o.name==='ceo')).toBe(true)
  expect(ROOM_OBJECTS.some(o=>o.name==='projector_inset')).toBe(true)
  for(const o of ROOM_OBJECTS.filter(o=>['hologram','ceo','chair','operator','desk'].includes(o.kind))){for(let axis=0;axis<3;axis++)expect(o.bounds[1][axis]-o.bounds[0][axis]).toBeGreaterThan(.01)}
 })
 it('grounds the seated figures and chairs instead of floating their feet',()=>{
  for(const o of ROOM_OBJECTS.filter(o=>['hologram','chair','operator'].includes(o.kind)))expect(o.bounds[0][1]).toBeCloseTo(0,4)
 })
 it('keeps every desk screen above the furniture so its face can receive clicks',async()=>{
  const bytes=readFileSync(new URL('../public/models/reference-room.glb',import.meta.url))
  const {scene}=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')
  scene.updateMatrixWorld(true)
  const camera=referenceCamera(),ray=new THREE.Raycaster()
  for(const screen of ROOM_SCREENS.filter(s=>s.kind==='desk')){
   ray.set(camera.position,new THREE.Vector3(...screen.center).sub(camera.position).normalize())
   // People can naturally occlude a screen; furniture must never cover its center.
   const hits=ray.intersectObjects(scene.children,true).filter(h=>['desk','screen','monitor'].includes(h.object.userData.kind))
   expect(hits[0]?.object.name,screen.id).toBe(`screen_${screen.id}`)
  }
 })
 it('keeps all seated bodies rigidly proportionate instead of stretching each silhouette',async()=>{
  const bytes=readFileSync(new URL('../public/models/reference-room.glb',import.meta.url))
  const {scene}=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')
  const figures:THREE.Mesh[]=[];scene.traverse(o=>{if(o instanceof THREE.Mesh&&o.name.startsWith('agent_'))figures.push(o)})
  expect(figures).toHaveLength(6)
  const distances=(mesh:THREE.Mesh)=>{
   const p=mesh.geometry.attributes.position
   return [[0,100],[100,1000],[1000,10000]].map(([a,b])=>new THREE.Vector3().fromBufferAttribute(p,a).distanceTo(new THREE.Vector3().fromBufferAttribute(p,b)))
  }
  const expected=distances(figures[0])
  for(const mesh of figures)distances(mesh).forEach((d,i)=>expect(d).toBeCloseTo(expected[i],5))
 })
 it('fits nine separate landscape consoles into the circular desk without overlap',()=>{
  const screens=ROOM_SCREENS.filter(s=>s.kind==='desk')
  const corners=screens.map(s=>{
   expect(s.w).toBeGreaterThan(s.h)
   expect(s.center[1]).toBeCloseTo(1.535)
   const q=new THREE.Quaternion(...s.quaternion)
   return [[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]].map(([x,y])=>new THREE.Vector3(x*s.w,y*s.h,0).applyQuaternion(q).add(new THREE.Vector3(...s.center)))
  })
  for(const points of corners)for(const v of points){expect(Math.hypot(v.x,v.z)).toBeGreaterThan(1.7);expect(Math.hypot(v.x,v.z)).toBeLessThan(3.15)}
  // Separating-axis check on the actual rotated footprints, rather than image rectangles.
  for(let i=0;i<corners.length;i++)for(let j=i+1;j<corners.length;j++){
   const A=corners[i],B=corners[j],axes=[...A.map((p,k)=>p.clone().sub(A[(k+1)%4])),...B.map((p,k)=>p.clone().sub(B[(k+1)%4]))].map(v=>new THREE.Vector3(-v.z,0,v.x).normalize())
   expect(axes.some(axis=>{const a=A.map(v=>v.dot(axis)),b=B.map(v=>v.dot(axis));return Math.max(...a)<Math.min(...b)||Math.max(...b)<Math.min(...a)})).toBe(true)
  }
 })
 it('has one physical frame and one whole pickable face for each screen',()=>{
  for(const s of ROOM_SCREENS){expect(ROOM_OBJECTS.find(o=>o.name===`frame_${s.id}`)).toBeDefined();expect(ROOM_OBJECTS.find(o=>o.name===`screen_${s.id}`)).toBeDefined()}
 })
})
describe('free orbit and screen focus',()=>{
 it('keeps arbitrary orbit positions within the enclosing wall, floor and ceiling',()=>{
  for(let angle=0;angle<Math.PI*2;angle+=.1)for(const y of[-20,0,3,20]){const p=constrain([Math.sin(angle)*30,y,Math.cos(angle)*30]);expect(Math.hypot(p[0],p[2])).toBeLessThanOrEqual(LIMITS.radius+.000001);expect(p[1]).toBeGreaterThanOrEqual(LIMITS.floor);expect(p[1]).toBeLessThanOrEqual(LIMITS.ceiling)}
 })
 it('frames every screen squarely within 85% and keeps each focus pose inside the room',()=>{
  for(const s of ROOM_SCREENS){const p=flightPose(s,16/9),c=new THREE.PerspectiveCamera(48,16/9,.05,80);c.position.set(...p.position);c.up.set(...p.up);c.lookAt(...p.target);c.updateMatrixWorld();const rotation=new THREE.Quaternion(...s.quaternion),points=[];for(const x of[-.5,.5])for(const y of[-.5,.5])points.push(new THREE.Vector3(x*s.w,y*s.h,0).applyQuaternion(rotation).add(new THREE.Vector3(...s.center)).project(c));for(const v of points){expect(Math.abs(v.x)).toBeLessThan(.851);expect(Math.abs(v.y)).toBeLessThan(.851)}expect(constrain(p.position)).toEqual(p.position)}
 })
 it('uses the calibrated camera projection for the reference origin',()=>{
  const c=referenceCamera();expect(c.position.toArray()).toEqual(HOME.position);const v=new THREE.Vector3(0,1.7,0).project(c);expect((v.x+1)*640).toBeCloseTo(640);expect((1-v.y)*360).toBeGreaterThan(450);expect((1-v.y)*360).toBeLessThan(470)
 })
})
describe('focused and expanded panel states',()=>{
 it('flies, focuses, expands, then Escape steps back one level at a time',()=>{
  let s=panelReduce(PANEL_CLOSED,{type:'click',id:'s1'});expect(s.phase).toBe('flying');s=panelReduce(s,{type:'arrived'});expect(s).toEqual({phase:'focused',screen:'s1'});s=panelReduce(s,{type:'expand'});expect(s.phase).toBe('expanded');s=panelReduce(s,{type:'back'});expect(s).toEqual({phase:'focused',screen:'s1'});s=panelReduce(s,{type:'back'});expect(s.phase).toBe('closing');expect(panelReduce(s,{type:'returned'})).toEqual(PANEL_CLOSED)
 })
 it('accepts all desk consoles and ignores new flights during a transition',()=>{
  for(const d of DESK_SCREENS)expect(panelReduce(PANEL_CLOSED,{type:'click',id:d.id})).toEqual({phase:'flying',screen:d.id})
  const busy={phase:'flying' as const,screen:'s1'};expect(panelReduce(busy,{type:'click',id:'s10'})).toBe(busy)
 })
})
