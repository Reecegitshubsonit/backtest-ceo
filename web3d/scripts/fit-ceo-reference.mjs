import fs from 'node:fs'
import * as T from '../node_modules/three/build/three.module.js'
import { GLTFLoader } from '../node_modules/three/examples/jsm/loaders/GLTFLoader.js'
import { GLTFExporter } from '../node_modules/three/examples/jsm/exporters/GLTFExporter.js'

const source = fs.readFileSync(process.argv[2])
const {scene} = await new GLTFLoader().parseAsync(source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength), '')
scene.updateMatrixWorld(true)
const camera = new T.PerspectiveCamera(48, 1280 / 720, 0.01, 20)
camera.position.set(0, 0.67, 2.2)
camera.lookAt(0, 0.5, 0)
camera.setViewOffset(1280, 720, 0, 86.4, 1280, 720)
camera.updateMatrixWorld(true)

// Outer silhouette measured from the original CEO in grok-room-wide.jpg.
// This is a deformation of the continuous sculpt, not silhouette extrusion.
const target = [[85,0],[89,10],[95,18],[105,22],[115,24],[125,24],[135,22],[145,18],[150,15],[155,13],[160,17],[165,25],[170,36],[175,49],[180,55],[190,60],[200,61],[220,64],[240,67],[260,71],[280,76],[300,79],[320,82],[340,83],[350,82],[355,80],[365,75],[370,72],[375,40],[380,36],[395,26],[410,18],[430,8],[455,1],[470,0]]
function interp(points, y) {
  if (y <= points[0][0]) return points[0][1]
  for (let i = 1; i < points.length; i++) if (y < points[i][0]) {
    const [a, x] = points[i-1], [b, z] = points[i]
    return x + (z-x) * (y-a)/(b-a)
  }
  return points.at(-1)[1]
}
const widths = new Map()
scene.traverse(o => {
  if (!o.isMesh || o.name.toLowerCase().includes('eye')) return
  const p = o.geometry.attributes.position
  for (let i=0; i<p.count; i++) {
    const v = new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(o.matrixWorld).project(camera)
    const x = v.x * 640, y = (1-v.y)*360
    for (let row=Math.floor(y-3);row<=Math.ceil(y+3);row++) widths.set(row, Math.max(widths.get(row)??0, Math.abs(x)))
  }
})
const original = [...widths].sort((a,b)=>a[0]-b[0])
const result = new T.Group()
scene.traverse(o => {
  if (!o.isMesh) return
  const geometry = o.geometry.clone(), p = geometry.attributes.position
  const uv = new Float32Array(p.count*2)
  for (let i=0;i<p.count;i++) {
    const v = new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(o.matrixWorld).project(camera)
    const originalY = (1-v.y)*360
    const handWeight = T.MathUtils.smoothstep(Math.abs(v.x * 640),48,65)
    const y = originalY > 335 ? originalY - (originalY-335)*0.12*handWeight : originalY
    const width = interp(original, originalY)
    const scale = width > 1 ? Math.min(1.4, interp(target,y)/width) : 1
    v.x *= scale
    v.y = 1-y/360
    uv[i*2] = (v.x+1)/2
    uv[i*2+1] = (v.y+1)/2
    v.unproject(camera)
    p.setXYZ(i,v.x,v.y,v.z)
  }
  geometry.setAttribute('uv',new T.BufferAttribute(uv,2))
  geometry.computeVertexNormals()
  geometry.computeBoundingBox(); geometry.computeBoundingSphere()
  const mesh = new T.Mesh(geometry,new T.MeshBasicMaterial())
  mesh.name=o.name
  result.add(mesh)
})
globalThis.FileReader=class {readAsArrayBuffer(blob){blob.arrayBuffer().then(result=>{this.result=result;this.onloadend?.()})}}
const output = await new GLTFExporter().parseAsync(result,{binary:true})
fs.writeFileSync(process.argv[3],Buffer.from(output))
console.log(JSON.stringify({bytes:output.byteLength,meshes:result.children.length,source:process.argv[2]}))
