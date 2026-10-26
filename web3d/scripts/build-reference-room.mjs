import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import * as T from '../node_modules/three/build/three.module.js'
import {GLTFLoader} from '../node_modules/three/examples/jsm/loaders/GLTFLoader.js'
import {GLTFExporter} from '../node_modules/three/examples/jsm/exporters/GLTFExporter.js'
import {mergeGeometries,mergeVertices} from '../node_modules/three/examples/jsm/utils/BufferGeometryUtils.js'

const root=fileURLToPath(new URL('../../',import.meta.url))
const out=path.resolve(process.argv[3]??fileURLToPath(new URL('../public/models',import.meta.url)))
const source=path.resolve(process.argv[2]??'/tmp/room3d-assets')
fs.mkdirSync(out,{recursive:true})
const camera=new T.PerspectiveCamera(48,1280/720,.05,80)
camera.position.set(0,3.844,7.04);camera.lookAt(0,3.3,0)
camera.setViewOffset(1280,720,0,86.4,1280,720);camera.updateMatrixWorld(true)
const room=new T.Group(), meta={camera:{position:camera.position.toArray(),target:[0,3.3,0],fov:48,offsetY:86.4},screens:[],objects:[]}
const neutral=new T.MeshBasicMaterial({color:'#0a1630'})

function pack(j,bin){const s=Buffer.from(JSON.stringify(j));const a=Buffer.alloc(Math.ceil(s.length/4)*4,32);s.copy(a);const b=Buffer.alloc(Math.ceil(bin.length/4)*4);bin.copy(b);const h=Buffer.alloc(20);h.writeUInt32LE(0x46546c67,0);h.writeUInt32LE(2,4);h.writeUInt32LE(28+a.length+b.length,8);h.writeUInt32LE(a.length,12);h.writeUInt32LE(0x4e4f534a,16);const bh=Buffer.alloc(8);bh.writeUInt32LE(b.length);bh.writeUInt32LE(0x004e4942,4);return Buffer.concat([h,a,bh,b])}
async function load(path){const b=fs.readFileSync(path);let n=b.readUInt32LE(12),j=JSON.parse(b.subarray(20,20+n)),bin=b.subarray(28+n);for(const m of j.meshes??[])for(const p of m.primitives)delete p.material;delete j.images;delete j.materials;delete j.textures;delete j.samplers;const clean=pack(j,bin);const g=await new GLTFLoader().parseAsync(clean.buffer.slice(clean.byteOffset,clean.byteOffset+clean.byteLength),'');g.scene.updateMatrixWorld(true);return g.scene}
function flat(scene,filter=()=>true){const gs=[];scene.traverse(o=>{if(!o.isMesh||!filter(o))return;let g=o.geometry.clone();if(o.isSkinnedMesh){const p=g.attributes.position,v=new T.Vector3();for(let i=0;i<p.count;i++){v.fromBufferAttribute(o.geometry.attributes.position,i);o.applyBoneTransform(i,v);p.setXYZ(i,v.x,v.y,v.z)}}g.applyMatrix4(o.matrixWorld);for(const k of Object.keys(g.attributes))if(k!=='position'&&k!=='normal')g.deleteAttribute(k);g.clearGroups();if(!g.index)g=mergeVertices(g);g.computeVertexNormals();gs.push(g)});return mergeGeometries(gs)}
function add(name,g,kind){g.computeVertexNormals();g.computeBoundingBox();g.computeBoundingSphere();const m=new T.Mesh(g,neutral);m.name=name;m.userData={kind};room.add(m);meta.objects.push({name,kind,bounds:[g.boundingBox.min.toArray(),g.boundingBox.max.toArray()]});return m}
function project(p){const v=p.clone().project(camera);return [(v.x+1)*640,(1-v.y)*360,-p.clone().applyMatrix4(camera.matrixWorldInverse).z]}
function ray(x,y){return new T.Ray(camera.position.clone(),new T.Vector3(x/640-1,1-y/360,.5).unproject(camera).sub(camera.position).normalize())}
// Pose a detailed, rigged CC0 human. The anatomy is the imported mesh.
const human=await load(source+'/human.glb')
function aim(name,end,direction){const bone=human.getObjectByName(name),tip=human.getObjectByName(end);if(!bone||!tip)throw Error(name);const from=tip.getWorldPosition(new T.Vector3()).sub(bone.getWorldPosition(new T.Vector3())).normalize();const q=new T.Quaternion().setFromUnitVectors(from,direction.normalize());const world=bone.getWorldQuaternion(new T.Quaternion()).premultiply(q);bone.quaternion.copy(bone.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(world));human.updateMatrixWorld(true)}
for(const[side,s]of[['L',1],['R',-1]]){
  aim('upperleg01'+side,'lowerleg01'+side,new T.Vector3(s*.015,0,.40))
  aim('lowerleg01'+side,'foot'+side,new T.Vector3(s*.015,-.4,0))
  aim('upperarm01'+side,'lowerarm01'+side,new T.Vector3(s*.04,-.12,.20))
  aim('lowerarm01'+side,'wrist'+side,new T.Vector3(-s*.025,0,.25))
}
// Turn the palms toward the desktop without changing hand/arm proportions.
for(const[side,sign]of[['L',1],['R',-1]]){
 const wrist=human.getObjectByName('wrist'+side)
 const width=human.getObjectByName('finger2-1'+side).getWorldPosition(new T.Vector3()).sub(human.getObjectByName('finger5-1'+side).getWorldPosition(new T.Vector3())).normalize()
 const world=wrist.getWorldQuaternion(new T.Quaternion()).premultiply(new T.Quaternion().setFromUnitVectors(width,new T.Vector3(-sign,0,0)))
 wrist.quaternion.copy(wrist.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(world));human.updateMatrixWorld(true)
}
const sitting=flat(human,o=>o.name==='base'||o.name==='base_male_bodyhigh-poly')
sitting.computeBoundingBox();const sitBottom=sitting.boundingBox.min.y;const pelvis=human.getObjectByName('root').getWorldPosition(new T.Vector3());pelvis.y-=sitBottom;sitting.translate(0,-sitBottom,0)
const chairScene=await load(source+'/chair.glb'),chair=flat(chairScene)
// Shared world-space seating: every body keeps the source mesh's proportions.
// The previous per-vertex image fitting flattened torsos and stretched chairs.
const seatSpecs=[['scanner',-95],['strategist',-140],['backtester',140],['auditor',95],['regime',-45],['risk',45]]
const seatLayout=new Map()
for(const[id,degrees]of [...seatSpecs,['operator',0]]){
 const theta=degrees*Math.PI/180,radius=id==='operator'?4.30:3.65
 const x=Math.sin(theta)*radius,z=Math.cos(theta)*radius,yaw=theta+Math.PI
 const scale=id==='operator'?1.95:1.9
 const person=sitting.clone().translate(0,0,-pelvis.z).scale(scale,scale,scale).rotateY(yaw).translate(x,0,z)
 // Preserve chair shape in plan; align the cushion to the posed pelvis with one vertical scale.
 const furniture=chair.clone(),cp=furniture.attributes.position
 for(let i=0;i<cp.count;i++){const y=cp.getY(i);cp.setY(i,y<=.62?y*.75:.465+(y-.62)*1.35)}
 furniture.scale(scale,scale,scale).translate(0,0,.12*scale).rotateY(yaw).translate(x,0,z)
 add(id==='operator'?'operator':'agent_'+id,person,id==='operator'?'operator':'hologram')
 add('chair_'+id,furniture,'chair')
 seatLayout.set(id,{theta,x,z,scale})
}
const ceo=flat(await load(root+'/web3d/public/models/ceo-standing.glb'))
ceo.scale(3.2,3.2,3.2);ceo.translate(0,1.7,0);add('ceo',ceo,'ceo')

// Adapt the recessed, bevelled CC0 table rather than rebuilding it from cylinders.
const tableScene=await load(source+'/table.glb')
const table=flat(tableScene,o=>/concrete|bowl/i.test(o.name))
// Uniform radial scaling keeps a genuinely circular, bevelled table.
table.scale(5.5,3.6,5.5)
add('command_desk',table,'desk')
const insert=flat(await load(source+'/projector-top.glb'),o=>o.name.startsWith('Solid_oak_circular_dining_top'))
insert.computeBoundingBox();const ib=insert.boundingBox,ic=ib.getCenter(new T.Vector3()),isz=ib.getSize(new T.Vector3());insert.translate(-ic.x,-ic.y,-ic.z);insert.scale(2.7/isz.x,.045/isz.y,2.7/isz.z);insert.translate(0,1.50,0);add('projector_inset',insert,'desk')

// Continuous architectural surfaces follow the reference's radial wall/floor/ceiling.
// Tessellation is authored as a mesh asset; no rejected procedural furniture is used.
function surface(name,fn,nu,nv,kind){const a=[],idx=[];for(let j=0;j<=nv;j++)for(let i=0;i<=nu;i++)a.push(...fn(i/nu,j/nv));for(let j=0;j<nv;j++)for(let i=0;i<nu;i++){const q=j*(nu+1)+i;idx.push(q,q+nu+1,q+1,q+1,q+nu+1,q+nu+2)}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(a,3));g.setIndex(idx);return add(name,g,kind)}
surface('curved_wall',(u,v)=>{let a=u*Math.PI*2,r=8.35+.10*Math.cos(v*Math.PI*8);return[Math.sin(a)*r,v*7.2,Math.cos(a)*r]},256,44,'wall')
surface('floor',(u,v)=>{let a=u*Math.PI*2,r=v*8.45;return[Math.sin(a)*r,-.015,Math.cos(a)*r]},256,48,'floor')
surface('ceiling',(u,v)=>{let a=u*Math.PI*2,r=v*8.45;return[Math.sin(a)*r,7.2-.2*Math.sin(v*Math.PI),Math.cos(a)*r]},256,32,'ceiling')

const config=fs.readFileSync(root+'/web3d/src/config/imageRoom.ts','utf8')
function readArray(name){return Function('return '+config.match(new RegExp('export const '+name+': WallScreen\\[\\] = (\\[[\\s\\S]*?\\n\\])'))[1])()}
const screenSource=[...readArray('WALL_SCREENS').map(s=>({...s,kind:'wall'})),...readArray('DESK_SCREENS').map(s=>({...s,kind:'desk'}))]
const monitorScene=await load(source+'/monitor.glb')
const enclosure=flat(monitorScene,o=>o.name==='Display_enclosure'),glass=flat(monitorScene,o=>o.name==='Display_glass')
if(!enclosure||!glass)throw Error('Monitor model did not expose its enclosure and glass')
enclosure.computeBoundingBox();glass.computeBoundingBox()
const glassBox=glass.boundingBox,glassCenter=glassBox.getCenter(new T.Vector3()),glassSize=glassBox.getSize(new T.Vector3())
for(const s of screenSource){const r=s.rect,cx=r.x+r.w/2,cy=r.y+r.h/2;let centre,normal;
 if(s.kind==='wall'){const rr=ray(cx,cy),o=rr.origin,d=rr.direction;const A=d.x*d.x+d.z*d.z,B=2*(o.x*d.x+o.z*d.z),C=o.x*o.x+o.z*o.z-7.95*7.95;const t=(-B+Math.sqrt(B*B-4*A*C))/(2*A);centre=rr.at(t,new T.Vector3());normal=new T.Vector3(-centre.x,0,-centre.z).normalize();if(cy>300)normal.y=.48;normal.normalize()}
 else {
  const theta=s.seat?seatLayout.get(s.seat).theta:({d7:-20,d8:0,d9:20}[s.id]*Math.PI/180)
  const radius=s.seat?2.48:2.64
  centre=new T.Vector3(Math.sin(theta)*radius,1.535,Math.cos(theta)*radius)
  normal=new T.Vector3(0,1,0)
 }
 const theta=s.kind==='desk'?Math.atan2(centre.x,centre.z):0
 const right=s.kind==='desk'?new T.Vector3(Math.cos(theta),0,-Math.sin(theta)):new T.Vector3(0,1,0).cross(normal).normalize(),up=normal.clone().cross(right).normalize()
 const plane=new T.Plane().setFromNormalAndCoplanarPoint(normal,centre)
 const lr=ray(r.x,cy).intersectPlane(plane,new T.Vector3()),rr=ray(r.x+r.w,cy).intersectPlane(plane,new T.Vector3());const tr=ray(cx,r.y).intersectPlane(plane,new T.Vector3()),br=ray(cx,r.y+r.h).intersectPlane(plane,new T.Vector3())
 const w=s.kind==='desk'?(s.seat?1.10:.76):Math.abs(rr.clone().sub(lr).dot(right)),h=s.kind==='desk'?(s.seat?.78:.58):Math.abs(tr.clone().sub(br).dot(up))
 const rotation=new T.Quaternion().setFromRotationMatrix(new T.Matrix4().makeBasis(right,up,normal))
 const frame=enclosure.clone(),p=frame.attributes.position
 for(let i=0;i<p.count;i++){let v=new T.Vector3().fromBufferAttribute(p,i).sub(glassCenter);v.set(v.x*w/glassSize.x,v.y*h/glassSize.y,(v.z-(glassSize.z/2))*.8).applyQuaternion(rotation).add(centre);p.setXYZ(i,v.x,v.y,v.z)}
 add('frame_'+s.id,frame,'monitor')
 // Glass face is extracted from the real monitor; whole face is the pick target.
 const corners=[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]],v=[]
 for(const[x,y]of corners)v.push(...centre.clone().addScaledVector(right,x*w).addScaledVector(up,y*h).addScaledVector(normal,.004).toArray())
 const face=new T.BufferGeometry();face.setAttribute('position',new T.Float32BufferAttribute(v,3));face.setAttribute('uv',new T.Float32BufferAttribute([0,0,1,0,1,1,0,1],2));face.setIndex([0,1,2,0,2,3]);add('screen_'+s.id,face,'screen')
 meta.screens.push({...s,center:centre.toArray(),normal:normal.toArray(),quaternion:rotation.toArray(),w,h})
}

globalThis.FileReader=class{readAsArrayBuffer(blob){blob.arrayBuffer().then(r=>{this.result=r;this.onloadend?.()})}}
const output=await new GLTFExporter().parseAsync(room,{binary:true})
fs.writeFileSync(out+'/reference-room.glb',Buffer.from(output));fs.writeFileSync(out+'/layout.json',JSON.stringify(meta,null,2))
console.log('EXPORTED',output.byteLength,'bytes',room.children.length,'objects',meta.screens.length,'screens')

// Bake a depth atlas so foreground figures are never painted onto the wall or floor.
const W=1280,H=720,depth=new Float32Array(W*H)
let triangles=0
room.traverse(o=>{if(!o.isMesh)return;const p=o.geometry.attributes.position,ind=o.geometry.index;const points=[];for(let i=0;i<p.count;i++){const v=new T.Vector3().fromBufferAttribute(p,i);const[x,y,z]=project(v);points.push([x,y,z,v.y])}for(let k=0;k<(ind?ind.count:p.count);k+=3){const a=points[ind?ind.getX(k):k],b=points[ind?ind.getX(k+1):k+1],c=points[ind?ind.getX(k+2):k+2];if(Math.min(a[2],b[2],c[2])<.05)continue;if(o.name==='ceo'&&Math.max(a[3],b[3],c[3])<2.6)continue;let x0=Math.max(0,Math.floor(Math.min(a[0],b[0],c[0]))),x1=Math.min(W-1,Math.ceil(Math.max(a[0],b[0],c[0]))),y0=Math.max(0,Math.floor(Math.min(a[1],b[1],c[1]))),y1=Math.min(H-1,Math.ceil(Math.max(a[1],b[1],c[1])));const den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(den)<1e-8)continue;for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){const u=((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(y+.5-c[1]))/den,v=((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(y+.5-c[1]))/den,w=1-u-v;if(u<-.01||v<-.01||w<-.01)continue;const inv=u/a[2]+v/b[2]+w/c[2],index=(H-1-y)*W+x;if(inv>depth[index])depth[index]=inv}triangles++}})
for(let i=0;i<depth.length;i++)depth[i]=depth[i]>0?1/depth[i]:80
fs.writeFileSync(out+'/reference-depth.bin',Buffer.from(depth.buffer))
console.log('DEPTH',W,H,triangles,'triangles')

// Refresh generated layout contracts from the canonical imageRoom mappings.
const screensFile=path.join(root,'web3d/src/config/roomScreens.ts')
if(fs.existsSync(screensFile)){
 const code=fs.readFileSync(screensFile,'utf8'),marker='export const ROOM_SCREENS: RoomScreen[] = ';
 const a=code.indexOf(marker)+marker.length,b=code.indexOf('\nexport const screenById',a);
 fs.writeFileSync(screensFile,code.slice(0,a)+JSON.stringify(meta.screens,null,2)+code.slice(b));
 fs.writeFileSync(path.join(root,'web3d/src/config/roomObjects.ts'),'export const ROOM_OBJECTS = '+JSON.stringify(meta.objects,null,2)+' as const\n');
}
