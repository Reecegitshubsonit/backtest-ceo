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
const room=new T.Group(), meta={camera:{position:camera.position.toArray(),target:[0,3.3,0],fov:48,offsetY:86.4},screens:[],instances:[],objects:[]}
const neutral=new T.MeshBasicMaterial({color:'#0a1630'})

function pack(j,bin){const s=Buffer.from(JSON.stringify(j));const a=Buffer.alloc(Math.ceil(s.length/4)*4,32);s.copy(a);const b=Buffer.alloc(Math.ceil(bin.length/4)*4);bin.copy(b);const h=Buffer.alloc(20);h.writeUInt32LE(0x46546c67,0);h.writeUInt32LE(2,4);h.writeUInt32LE(28+a.length+b.length,8);h.writeUInt32LE(a.length,12);h.writeUInt32LE(0x4e4f534a,16);const bh=Buffer.alloc(8);bh.writeUInt32LE(b.length);bh.writeUInt32LE(0x004e4942,4);return Buffer.concat([h,a,bh,b])}
async function load(path){const b=fs.readFileSync(path);let n=b.readUInt32LE(12),j=JSON.parse(b.subarray(20,20+n)),bin=b.subarray(28+n);for(const m of j.meshes??[])for(const p of m.primitives)delete p.material;delete j.images;delete j.materials;delete j.textures;delete j.samplers;const clean=pack(j,bin);const g=await new GLTFLoader().parseAsync(clean.buffer.slice(clean.byteOffset,clean.byteOffset+clean.byteLength),'');g.scene.updateMatrixWorld(true);return g.scene}
function flat(scene,filter=()=>true,tagArms=false){const gs=[];scene.traverse(o=>{if(!o.isMesh||!filter(o))return;let g=o.geometry.clone();
 if(tagArms){const tag=new Float32Array(g.attributes.position.count),si=g.attributes.skinIndex,sw=g.attributes.skinWeight;if(o.isSkinnedMesh&&si)for(let i=0;i<tag.length;i++){let best=0,w=-1;for(let k=0;k<4;k++){const wk=sw.getComponent(i,k);if(wk>w){w=wk;best=si.getComponent(i,k)}}tag[i]=/arm|wrist|hand|finger|thumb|metacarpal/i.test(o.skeleton.bones[best]?.name??'')?1:0}g.setAttribute('arm',new T.BufferAttribute(tag,1))}if(o.isSkinnedMesh){const p=g.attributes.position,v=new T.Vector3();for(let i=0;i<p.count;i++){v.fromBufferAttribute(o.geometry.attributes.position,i);o.applyBoneTransform(i,v);p.setXYZ(i,v.x,v.y,v.z)}}g.applyMatrix4(o.matrixWorld);for(const k of Object.keys(g.attributes))if(k!=='position'&&k!=='normal'&&k!=='arm')g.deleteAttribute(k);g.clearGroups();if(!g.index)g=mergeVertices(g);g.computeVertexNormals();gs.push(g)});return mergeGeometries(gs)}
function add(name,g,kind){if(g.attributes.arm)g.deleteAttribute('arm');g.computeVertexNormals();g.computeBoundingBox();g.computeBoundingSphere();const m=new T.Mesh(g,neutral);m.name=name;m.userData={kind};room.add(m);meta.objects.push({name,kind,bounds:[g.boundingBox.min.toArray(),g.boundingBox.max.toArray()]});return m}
function project(p){const v=p.clone().project(camera);return [(v.x+1)*640,(1-v.y)*360,-p.clone().applyMatrix4(camera.matrixWorldInverse).z]}
function ray(x,y){return new T.Ray(camera.position.clone(),new T.Vector3(x/640-1,1-y/360,.5).unproject(camera).sub(camera.position).normalize())}
// Pose a detailed, rigged CC0 human. The anatomy is the imported mesh.
const human=await load(source+'/human.glb')
function aim(name,end,direction){const bone=human.getObjectByName(name),tip=human.getObjectByName(end);if(!bone||!tip)throw Error(name);const from=tip.getWorldPosition(new T.Vector3()).sub(bone.getWorldPosition(new T.Vector3())).normalize();const q=new T.Quaternion().setFromUnitVectors(from,direction.normalize());const world=bone.getWorldQuaternion(new T.Quaternion()).premultiply(q);bone.quaternion.copy(bone.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(world));human.updateMatrixWorld(true)}
const rest=[];human.traverse(o=>{if(o.isBone)rest.push([o,o.quaternion.clone(),o.position.clone()])})
function poseBody(profile='far',lift=0,legDrop=0){
 for(const[b,q,p]of rest){b.quaternion.copy(q);b.position.copy(p)}human.updateMatrixWorld(true)
 if(profile==='near'){
  const spine=human.getObjectByName('spine05'),q=spine.getWorldQuaternion(new T.Quaternion()).premultiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),-17*Math.PI/180))
  spine.quaternion.copy(spine.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(q));human.updateMatrixWorld(true)
 }
 const arms=profile==='near'?[-.26,.03,-.08,.25]:profile==='operator'?[-.26,.03,-.1,.1]:profile==='mid'?[-.23,.08,.10,.25]:[-.18,.15,.11,.24]
 for(const[side,sign]of[['L',1],['R',-1]]){
  aim('upperleg01'+side,'lowerleg01'+side,new T.Vector3(sign*.015,-legDrop,.40))
  aim('lowerleg01'+side,'foot'+side,new T.Vector3(sign*.015,-.4,0))
  aim('upperarm01'+side,'lowerarm01'+side,profile==='far'?new T.Vector3(sign===1?-.06:-.12,-.20+lift,.14):new T.Vector3(sign*.04,arms[0]+lift,arms[1]))
  aim('lowerarm01'+side,'wrist'+side,profile==='far'?new T.Vector3(sign===1?-.10:.13,.05+lift*.5,sign===1?.25:.22):new T.Vector3(-sign*.025,arms[2]+lift*.5,arms[3]))
 }
 for(const[side,sign]of[['L',1],['R',-1]]){
  const wrist=human.getObjectByName('wrist'+side)
  const width=human.getObjectByName('finger2-1'+side).getWorldPosition(new T.Vector3()).sub(human.getObjectByName('finger5-1'+side).getWorldPosition(new T.Vector3())).normalize()
  const forward=human.getObjectByName('finger3-1'+side).getWorldPosition(new T.Vector3()).sub(wrist.getWorldPosition(new T.Vector3())).normalize()
  width.addScaledVector(forward,-width.dot(forward)).normalize()
  const sourceFrame=new T.Matrix4().makeBasis(width,new T.Vector3().crossVectors(forward,width).normalize(),forward)
  const targetForward=new T.Vector3(0,0,1),targetWidth=new T.Vector3(-sign,0,0)
  const targetFrame=new T.Matrix4().makeBasis(targetWidth,new T.Vector3().crossVectors(targetForward,targetWidth),targetForward)
  const delta=new T.Quaternion().setFromRotationMatrix(targetFrame.multiply(sourceFrame.invert()))
  const world=wrist.getWorldQuaternion(new T.Quaternion()).premultiply(delta)
  wrist.quaternion.copy(wrist.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(world));human.updateMatrixWorld(true)
  for(let finger=2;finger<=5;finger++)for(let joint=2;joint<=3;joint++){
   const bone=human.getObjectByName('finger'+finger+'-'+joint+side),world=bone.getWorldQuaternion(new T.Quaternion()).premultiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),joint===2?.10:.07))
   bone.quaternion.copy(bone.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(world));human.updateMatrixWorld(true)
  }
 }
 const g=flat(human,o=>o.name==='base'||o.name==='base_male_bodyhigh-poly',true);g.computeBoundingBox();g.translate(0,-g.boundingBox.min.y,profile==='near'?.20:0);return g
}
poseBody()
const sitting=flat(human,o=>o.name==='base'||o.name==='base_male_bodyhigh-poly')
sitting.computeBoundingBox();const sitBottom=sitting.boundingBox.min.y;const pelvis=human.getObjectByName('root').getWorldPosition(new T.Vector3());pelvis.y-=sitBottom;sitting.translate(0,-sitBottom,0)
const chairScene=await load(source+'/chair.glb'),chair=flat(chairScene)
// Shared world-space seating: every body keeps the source mesh's proportions.
// The previous per-vertex image fitting flattened torsos and stretched chairs.
// Fit rigid object transforms to measured reference landmarks, without warping any vertices.
function landmarkFit(g,initial,yaw,target,feet=false,radius=false){
 g.computeBoundingBox();const p=g.attributes.position,points=[],head=[],high=g.boundingBox.max.y
 for(let i=0;i<p.count;i+=4){const v=new T.Vector3().fromBufferAttribute(p,i);v.z-=pelvis.z;v.applyAxisAngle(new T.Vector3(0,1,0),yaw);points.push(v);if(p.getY(i)>high-(radius?.10:.24))head.push(v)}
 const metrics=([x,z,scale])=>{
  let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity
  for(const v of head){const[a,b]=project(v.clone().multiplyScalar(scale).add(new T.Vector3(x,0,z)));x0=Math.min(x0,a);x1=Math.max(x1,a);y0=Math.min(y0,b)}
  if(feet)for(const v of points)y1=Math.max(y1,project(v.clone().multiplyScalar(scale).add(new T.Vector3(x,0,z)))[1])
  return[(x0+x1)/2,y0,radius?Math.hypot(x,z):feet?y1:x1-x0]
 }
 let params=[...initial]
 for(let iteration=0;iteration<30;iteration++){
  const base=metrics(params),A=[[],[],[]]
  for(let j=0;j<3;j++){const next=[...params];next[j]+=.001;const m=metrics(next);for(let i=0;i<3;i++)A[i][j]=(m[i]-base[i])/.001}
  for(let i=0;i<3;i++)A[i][3]=target[i]-base[i]
  for(let j=0;j<3;j++){let pivot=j;for(let i=j+1;i<3;i++)if(Math.abs(A[i][j])>Math.abs(A[pivot][j]))pivot=i;[A[j],A[pivot]]=[A[pivot],A[j]];const d=A[j][j];if(Math.abs(d)<1e-8)throw Error('Landmark fit singular');for(let k=j;k<4;k++)A[j][k]/=d;for(let i=0;i<3;i++)if(i!==j){const d=A[i][j];for(let k=j;k<4;k++)A[i][k]-=d*A[j][k]}}
  params=params.map((v,i)=>v+T.MathUtils.clamp(A[i][3],i===2?-.3:-.7,i===2?.3:.7))
  params[2]=T.MathUtils.clamp(params[2],.6,3)
 }
 if(!quietFit)console.log('LANDMARK FIT',params,metrics(params));return params
}
let quietFit=false
function makeChair(id,x,z,scale,yaw){
 const furniture=chair.clone(),cp=furniture.attributes.position
 for(let i=0;i<cp.count;i++){const y=cp.getY(i),near=['regime','risk'].includes(id);if(near&&y>.43){cp.setZ(i,(cp.getZ(i)+.3)*1.4-.3);if(y>.7&&cp.getZ(i)<-.15)cp.setX(i,cp.getX(i)*1.4)}cp.setY(i,y<=.62?y*.75:.465+(y-.62)*(near?NEAR_BACK:1.15))}
 return furniture.scale(scale,scale,scale).translate(0,0,.12*scale).rotateY(yaw).translate(x,0,z)
}
// Solid envelope of the command desk (radially symmetric): pedestal, bevelled underside, slab.
// Measured from the reshaped table mesh: pedestal r<=.85 below y 1.15, underside rim 2.24 at
// y 1.17 widening to 2.75 at 1.33, flat slab to the top at 1.60.
function deskRadius(y){return y<0||y>1.62?0:y<1.14?.85:y<1.17?2.24:y<1.33?2.24+(y-1.17)/.16*.51:2.75}
function deskClip(g,margin=.03){const p=g.attributes.position,arm=g.attributes.arm;let torso=0,arms=0,depth=0
 for(let i=0;i<p.count;i++){const y=p.getY(i),r=Math.hypot(p.getX(i),p.getZ(i)),R=deskRadius(y-margin)+margin;if(R>0&&r<R&&y<1.6+margin){if(arm&&arm.getX(i)>.5)arms++;else torso++;depth=Math.max(depth,R-r)}}
 return{torso,arms,depth}}
function place(g,x,z,scale,yaw){return g.clone().translate(0,0,-pelvis.z).scale(scale,scale,scale).rotateY(yaw).translate(x,0,z)}
// Seated agents were sitting inside the desk: the far pair 1.25 m deep (torso through the slab),
// the mid pair with forearms 0.5 m into it, the near pair's knees through the bevel. Each figure
// is now pushed back along its seat direction until the torso and its chair clear the desk edge,
// its forearms are raised until they rest on the desk top, and its scale/position are re-solved
// so the head still lands on the measured reference landmark.
function seatClear(id,profile,initial,yaw,target,feet){
 quietFit=true
 const dir=Math.hypot(initial[0],initial[1]),ux=initial[0]/dir,uz=initial[1]/dir
 let best=null
 for(let push=0;push<=1.6;push+=.05){
  let posed=poseBody(profile,0,0),fit
  if(feet){fit=landmarkFit(posed,[initial[0]+ux*push,initial[1]+uz*push,initial[2]],yaw,target,true)}
  else fit=landmarkFit(posed,[initial[0]+ux*push,initial[1]+uz*push,initial[2]],yaw,[target[0],target[1],dir+push],false,true)
  let c=deskClip(place(posed,...fit,yaw))
  if(feet&&c.torso){for(let drop=.02;drop<=.2&&c.torso;drop+=.02){posed=poseBody(profile,0,drop);fit=landmarkFit(posed,fit,yaw,target,true);c=deskClip(place(posed,...fit,yaw))}}
  const cc=deskClip(makeChair(id,...fit,yaw));c.torso+=cc.torso+cc.arms
  if(c.torso)continue
  let lift=0
  for(;lift<=.6&&c.arms;lift+=.02){posed=poseBody(profile,lift,0);fit=feet?landmarkFit(posed,fit,yaw,target,true):landmarkFit(posed,fit,yaw,[target[0],target[1],dir+push],false,true);c=deskClip(place(posed,...fit,yaw))}
  best={posed,fit,push,lift,c};break
 }
 quietFit=false
 if(!best)throw Error('No desk-clear seat for '+id)
 best.fit=landmarkFit(best.posed,best.fit,yaw,[target[0],target[1],dir+best.push],false,true);best.c=deskClip(place(best.posed,...best.fit,yaw));console.log('SEAT',id,'push',best.push.toFixed(2),'lift',best.lift.toFixed(2),'fit',best.fit.map(v=>+v.toFixed(3)),'clip',best.c)
 return best
}
const seatSpecs=[
 ['scanner',-3.15,-1.3,1.90,1.20],['strategist',-1.85,-2,2.06,.70],
 ['backtester',1.85,-2,2.06,-.70],['auditor',3.15,-1.3,1.90,-1.20],
 ['regime',-3.05,.7,1.35,1.76],['risk',3.05,.7,1.35,-1.76],
]
// Near (foreground) chairs: the reference shows high executive backs reaching the sitter's
// shoulders. The former 0.67 back scale cut them to waist height behind the regime/risk agents.
const NEAR_BACK=+(process.env.NEAR_BACK??1.12)
const seatLayout=new Map()
for(const[id,initialX,initialZ,initialScale,yaw]of [...seatSpecs,['operator',0,4.3,1.95,Math.PI]]){
 const profile=['regime','risk'].includes(id)?'near':['scanner','auditor'].includes(id)?'mid':id==='operator'?'operator':'far'
 const HEAD={scanner:[357,338],auditor:[923,338],strategist:[486,310],backtester:[794,310],regime:[id==='regime'?281:999,467,710],risk:[999,467,710]}
 let posed,x,z,scale
 if(id==='operator'){posed=poseBody(profile);[x,z,scale]=landmarkFit(posed,[initialX,initialZ,initialScale],yaw,[640,559,53])}
 else{const s=seatClear(id,profile,[initialX,initialZ,initialScale],yaw,HEAD[id],false);posed=s.posed;[x,z,scale]=s.fit}
 const person=place(posed,x,z,scale,yaw)
 const furniture=makeChair(id,x,z,scale,yaw)
 if(id==='operator'){
  const p=furniture.attributes.position,seat=.465*scale
  furniture.computeBoundingBox();const high=furniture.boundingBox.max.y
  const weights=Array.from({length:p.count},(_,i)=>T.MathUtils.clamp((p.getY(i)-seat)/(high-seat),0,1))
  const top=()=>{let result=Infinity;for(let i=0;i<p.count;i++)result=Math.min(result,project(new T.Vector3().fromBufferAttribute(p,i))[1]);return result}
  for(let iteration=0;iteration<5;iteration++){
   const y=top();for(let i=0;i<p.count;i++)p.setY(i,p.getY(i)+weights[i]*.01)
   const derivative=(top()-y)/.01,delta=T.MathUtils.clamp((685-y)/derivative,-.5,.5)-.01
   for(let i=0;i<p.count;i++)p.setY(i,p.getY(i)+weights[i]*delta)
  }
  console.log('OPERATOR CHAIR TOP',top())
 }
 add(id==='operator'?'operator':'agent_'+id,person,id==='operator'?'operator':'hologram')
 add('chair_'+id,furniture,'chair')
 seatLayout.set(id,{theta:Math.atan2(x,z),x,z,scale})
 // Garment and short hair are extracted/sculpted from the real human mesh, not primitive shapes.
 if(id==='operator'){
  const makeLayer=(name,select,amount,kind)=>{
   const g=posed.clone().toNonIndexed(),p=g.attributes.position,n=g.attributes.normal,positions=[]
   for(let i=0;i<p.count;i+=3){const vs=[0,1,2].map(k=>new T.Vector3().fromBufferAttribute(p,i+k));if(!vs.every(select))continue
    for(let k=0;k<3;k++){const v=vs[k].addScaledVector(new T.Vector3().fromBufferAttribute(n,i+k),amount);v.z-=pelvis.z;v.multiplyScalar(scale).applyAxisAngle(new T.Vector3(0,1,0),yaw).add(new T.Vector3(x,0,z));positions.push(...v.toArray())}
   }
   const layer=new T.BufferGeometry();layer.setAttribute('position',new T.Float32BufferAttribute(positions,3));add(name,layer,kind)
  }
  makeLayer('operator_jacket',v=>v.y>.43&&v.y<1.10&&v.z<.27,.032,'cloth')
  makeLayer('operator_hair',v=>v.y>1.25||v.y>1.17&&v.z<.055,.012,'hair')
 }
}
const ceo=flat(await load(root+'/web3d/public/models/ceo-standing.glb'))
ceo.scale(3.2,3.2,3.2);ceo.translate(0,1.7,0);add('ceo',ceo,'ceo')

// Adapt the recessed, bevelled CC0 table rather than rebuilding it from cylinders.
const tableScene=await load(source+'/table.glb')
const table=flat(tableScene,o=>/concrete|bowl/i.test(o.name))
// Uniform radial scaling keeps a genuinely circular, bevelled table.
table.scale(2.65/.574,1.60/.42,2.75/.574)
const deskP=table.attributes.position;for(let i=0;i<deskP.count;i++){const k=.55+.45*T.MathUtils.smoothstep(deskP.getY(i),0,1.30);deskP.setX(i,deskP.getX(i)*k);deskP.setZ(i,deskP.getZ(i)*k)}
add('command_desk',table,'desk')
const insert=flat(await load(source+'/projector-top.glb'),o=>o.name.startsWith('Solid_oak_circular_dining_top'))
insert.computeBoundingBox();const ib=insert.boundingBox,ic=ib.getCenter(new T.Vector3()),isz=ib.getSize(new T.Vector3());insert.translate(-ic.x,-ic.y,-ic.z);insert.scale(2.7/isz.x,.045/isz.y,2.7/isz.z);insert.translate(0,1.705,0);add('projector_inset',insert,'desk')

// Continuous architectural surfaces follow the reference's radial wall/floor/ceiling.
// Tessellation is authored as a mesh asset; no rejected procedural furniture is used.
function surface(name,fn,nu,nv,kind){const a=[],idx=[];for(let j=0;j<=nv;j++)for(let i=0;i<=nu;i++)a.push(...fn(i/nu,j/nv));for(let j=0;j<nv;j++)for(let i=0;i<nu;i++){const q=j*(nu+1)+i;idx.push(q,q+nu+1,q+1,q+1,q+nu+1,q+nu+2)}const uv=[];for(let j=0;j<=nv;j++)for(let i=0;i<=nu;i++)uv.push(i/nu,j/nv);const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(a,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(idx);return add(name,g,kind)}
surface('curved_wall',(u,v)=>{let a=u*Math.PI*2,r=8.35+.10*Math.cos(v*Math.PI*8);return[Math.sin(a)*r,v*7.2,Math.cos(a)*r]},256,44,'wall')
surface('floor',(u,v)=>{let a=u*Math.PI*2,r=v*8.45;return[Math.sin(a)*r,-.015,Math.cos(a)*r]},256,48,'floor')
surface('ceiling',(u,v)=>{let a=u*Math.PI*2,r=v*8.45;return[Math.sin(a)*r,7.2-.2*Math.sin(v*Math.PI),Math.cos(a)*r]},256,32,'ceiling')
// Background architecture. The monitor banks floated on a bare wall: no counter under the tilted
// lower consoles (s3/s4/s16/s17 bottoms at y~1.0, r~7.7) and two 36-degree bare side bays
// (72-108 and 252-288 degrees). A continuous console ledge now carries the tilted displays, and
// structural pillars with edge light strips divide the bank gaps and the side bays.
{
 const ledgeTop=.92,inner=7.42,outer=8.30
 surface('wall_ledge_top',(u,v)=>{const a=u*Math.PI*2,r=inner+(outer-inner)*v;return[Math.sin(a)*r,ledgeTop,Math.cos(a)*r]},256,2,'trim')
 surface('wall_ledge_front',(u,v)=>{const a=u*Math.PI*2,r=inner-.04*Math.sin(v*Math.PI);return[Math.sin(a)*r,v*ledgeTop,Math.cos(a)*r]},256,6,'trim')
 const pillarAngles=[137.5,222.5,-42.5,42.5,76,104,256,284]
 // louvred service panels fill the side bays between their pillars
 for(const [from,to] of [[77.5,102.5],[257.5,282.5]])surface('bay_panel_'+from,(u,v)=>{const a=(from+(to-from)*u)*Math.PI/180,r=8.16;return[Math.sin(a)*r,1.25+v*4.9,Math.cos(a)*r]},48,8,'trim')
 for(const deg of pillarAngles){
  const a=deg*Math.PI/180,g=new T.BoxGeometry(.36,6.95,.30)
  g.translate(0,6.95/2+.0,-8.12).rotateY(a+Math.PI)
  add('pillar_'+String(deg).replace('-','m').replace('.','_'),g,'trim')
 }
}

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
  const radius=s.seat?2.10:2.18
  centre=new T.Vector3(Math.sin(theta)*radius,1.608,Math.cos(theta)*radius)
  normal=new T.Vector3(0,1,0)
 }
 const theta=s.kind==='desk'?Math.atan2(centre.x,centre.z):0
 const right=s.kind==='desk'?new T.Vector3(Math.cos(theta),0,-Math.sin(theta)):new T.Vector3(0,1,0).cross(normal).normalize(),up=normal.clone().cross(right).normalize()
 const plane=new T.Plane().setFromNormalAndCoplanarPoint(normal,centre)
 const lr=ray(r.x,cy).intersectPlane(plane,new T.Vector3()),rr=ray(r.x+r.w,cy).intersectPlane(plane,new T.Vector3());const tr=ray(cx,r.y).intersectPlane(plane,new T.Vector3()),br=ray(cx,r.y+r.h).intersectPlane(plane,new T.Vector3())
 const w=s.kind==='desk'?(s.seat?.70:.65):Math.abs(rr.clone().sub(lr).dot(right)),h=s.kind==='desk'?(s.seat?.55:.50):Math.abs(tr.clone().sub(br).dot(up))
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

// A real rear bank preserves the same command-room framework through a full orbit.
// Instances reuse the canonical applications and assignments; they are not new computers.
const rearRotation=new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),Math.PI)
for(const s of meta.screens.filter(s=>s.kind==='wall')){
 const id='rear-'+s.id,center=[-s.center[0],s.center[1],-s.center[2]],normal=[-s.normal[0],s.normal[1],-s.normal[2]]
 const quaternion=rearRotation.clone().multiply(new T.Quaternion(...s.quaternion)).toArray()
 add('frame_'+id,room.getObjectByName('frame_'+s.id).geometry.clone().rotateY(Math.PI),'monitor')
 add('screen_'+id,room.getObjectByName('screen_'+s.id).geometry.clone().rotateY(Math.PI),'screen')
 meta.instances.push({...s,id,canonicalId:s.id,center,normal,quaternion})
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
 let generated=code.slice(0,a)+JSON.stringify(meta.screens,null,2)+code.slice(b)
 generated=generated.replace(/export const WALL_SCREEN_INSTANCES: RoomScreen\[\] = [\s\S]*$/,'export const WALL_SCREEN_INSTANCES: RoomScreen[] = '+JSON.stringify(meta.instances,null,2)+'\n')
 fs.writeFileSync(screensFile,generated);
 fs.writeFileSync(path.join(root,'web3d/src/config/roomObjects.ts'),'export const ROOM_OBJECTS = '+JSON.stringify(meta.objects,null,2)+' as const\n');
}
