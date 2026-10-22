import * as THREE from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import { MeshSurfaceSampler } from 'three/examples/jsm/math/MeshSurfaceSampler.js'
import { mulberry32 } from './particles'

type V = [number, number, number]
const up = new THREE.Vector3(0, 1, 0)

/** Tapered limb from a (radius r1) to b (radius r2), with rounded ends. */
function limb(a: V, b: V, r1: number, r2: number): THREE.BufferGeometry[] {
  const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b)
  const cyl = new THREE.CylinderGeometry(r2, r1, A.distanceTo(B), 18, 1, true)
  cyl.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(up, B.clone().sub(A).normalize()))
  const m = A.clone().add(B).multiplyScalar(0.5)
  cyl.translate(m.x, m.y, m.z)
  return [cyl, ball(a, r1), ball(b, r2)]
}

function ball(c: V, r: number, s: V = [1, 1, 1]): THREE.BufferGeometry {
  const g = new THREE.SphereGeometry(r, 18, 14)
  g.scale(...s); g.translate(...c)
  return g
}

/** Torso as a lathe: hips, waist, chest, sloping shoulders into the neck; flattened front to back. */
function torso(y0: number, lean: number): THREE.BufferGeometry {
  const prof: [number, number][] = [[0.001, 0], [0.15, 0.02], [0.165, 0.08], [0.145, 0.17], [0.16, 0.3], [0.19, 0.42], [0.2, 0.48], [0.15, 0.53], [0.06, 0.56], [0.001, 0.57]]
  const g = new THREE.LatheGeometry(prof.map(([r, y]) => new THREE.Vector2(r, y)), 28)
  g.scale(1.12, 1, 0.62)
  g.rotateX(-lean)
  g.translate(0, y0, -lean * 0.3)
  return g
}

function standing(): THREE.BufferGeometry[] {
  const out: THREE.BufferGeometry[] = [torso(0.92, 0), ball([0, 0.95, 0], 0.16, [1.08, 0.62, 0.68])]
  out.push(...limb([0, 1.46, 0], [0, 1.56, 0.01], 0.052, 0.046))                                  // neck
  for (const s of [-1, 1]) {
    out.push(ball([s * 0.21, 1.41, 0], 0.075))                                                     // shoulder
    out.push(...limb([s * 0.23, 1.4, 0], [s * 0.28, 1.12, -0.01], 0.056, 0.045))                   // upper arm
    out.push(...limb([s * 0.28, 1.12, -0.01], [s * 0.31, 0.87, 0.04], 0.044, 0.032))              // forearm
    out.push(ball([s * 0.315, 0.8, 0.05], 0.036, [0.8, 1.7, 1.1]))                                 // hand
    out.push(...limb([s * 0.095, 0.93, 0], [s * 0.11, 0.52, 0.01], 0.085, 0.056))                  // thigh
    out.push(...limb([s * 0.11, 0.5, 0.01], [s * 0.12, 0.07, -0.01], 0.052, 0.035))                // shin
    out.push(ball([s * 0.12, 0.035, 0.05], 0.045, [1.1, 0.7, 2.2]))                                // foot
  }
  return out
}

function seated(): THREE.BufferGeometry[] {
  const out: THREE.BufferGeometry[] = [torso(0.5, 0.12), ball([0, 0.55, 0], 0.16, [1.08, 0.62, 0.68])]
  out.push(...limb([0, 1.02, -0.13], [0, 1.11, -0.12], 0.052, 0.046))
  for (const s of [-1, 1]) {
    out.push(ball([s * 0.21, 0.98, -0.11], 0.075))
    out.push(...limb([s * 0.23, 0.97, -0.11], [s * 0.27, 0.73, 0.03], 0.056, 0.045))
    out.push(...limb([s * 0.27, 0.73, 0.03], [s * 0.23, 0.72, 0.36], 0.044, 0.032))
    out.push(ball([s * 0.22, 0.72, 0.42], 0.036, [0.9, 0.7, 1.7]))
    out.push(...limb([s * 0.1, 0.56, 0.02], [s * 0.12, 0.56, 0.46], 0.085, 0.058))
    out.push(...limb([s * 0.12, 0.54, 0.46], [s * 0.13, 0.07, 0.5], 0.054, 0.036))
    out.push(ball([s * 0.13, 0.035, 0.55], 0.045, [1.1, 0.7, 2.2]))
  }
  return out
}

/** Head relative to its pivot (top of the neck): skull, jaw, brow, nose, ears; face toward +z. */
function headParts(): THREE.BufferGeometry[] {
  return [
    ball([0, 0.17, 0], 0.105, [0.88, 1.12, 1]),
    ball([0, 0.1, 0.025], 0.07, [0.95, 0.85, 1]),
    ball([0, 0.205, 0.07], 0.03, [2.3, 0.55, 0.8]),
    ball([0, 0.155, 0.1], 0.017, [0.8, 1.5, 1.1]),
    ball([-0.093, 0.16, 0], 0.022, [0.6, 1.3, 1]),
    ball([0.093, 0.16, 0], 0.022, [0.6, 1.3, 1]),
  ]
}

const cache = new Map<string, THREE.BufferGeometry>()
const cached = (k: string, make: () => THREE.BufferGeometry[]) => {
  if (!cache.has(k)) cache.set(k, mergeGeometries(make().map(g => g.toNonIndexed()))!)
  return cache.get(k)!
}

export const bodyGeometry = (isSeated: boolean) => cached(isSeated ? 'seated' : 'standing', isSeated ? seated : standing)
export const headGeometry = () => cached('head', headParts)
/** Where the head attaches (top of the neck). */
export const headPivot = (isSeated: boolean): V => (isSeated ? [0, 1.08, -0.12] : [0, 1.53, 0.01])

/** Points spread evenly over a surface, nudged slightly inside, plus faint links between near neighbours. */
export function surfacePoints(geo: THREE.BufferGeometry, count: number, seed: number, minY = -Infinity) {
  const sampler = new MeshSurfaceSampler(new THREE.Mesh(geo))
  ;(sampler as unknown as { randomFunction: () => number }).randomFunction = mulberry32(seed) // seeded; not in the type defs
  sampler.build()
  const rand = mulberry32(seed + 1)
  const p = new THREE.Vector3(), n = new THREE.Vector3(), pts: number[] = []
  let guard = 0
  while (pts.length < count * 3 && guard++ < count * 4) {
    sampler.sample(p, n)
    if (p.y < minY) continue
    p.addScaledVector(n, -rand() * 0.012)
    pts.push(p.x, p.y, p.z)
  }
  // plexus: link a subset of points to their nearest neighbours
  const links: number[] = [], k = Math.min(pts.length / 3, 420), step = Math.max(1, Math.floor(pts.length / 3 / k))
  for (let i = 0; i < pts.length / 3; i += step) {
    let made = 0
    for (let j = i + step; j < pts.length / 3 && made < 2; j += step) {
      const dx = pts[i * 3] - pts[j * 3], dy = pts[i * 3 + 1] - pts[j * 3 + 1], dz = pts[i * 3 + 2] - pts[j * 3 + 2]
      if (dx * dx + dy * dy + dz * dz < 0.0045) { links.push(pts[i * 3], pts[i * 3 + 1], pts[i * 3 + 2], pts[j * 3], pts[j * 3 + 1], pts[j * 3 + 2]); made++ }
    }
  }
  return { points: new Float32Array(pts), links: new Float32Array(links) }
}

const VERT = `
varying vec3 vN; varying vec3 vV; varying float vY;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vec4 mv = viewMatrix * world;
  vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); vY = world.y;
  gl_Position = projectionMatrix * mv;
}`
const FRAG = `
uniform vec3 uColor; uniform float uIntensity, uFade0, uFade1, uTime;
varying vec3 vN; varying vec3 vV; varying float vY;
void main() {
  float rim = pow(1.0 - abs(dot(normalize(vN), normalize(vV))), 2.2);
  float scan = 0.85 + 0.15 * sin(vY * 80.0 - uTime * 3.0);
  float a = (0.1 + rim * 0.95) * scan * uIntensity * smoothstep(uFade0, uFade1, vY);
  gl_FragColor = vec4(uColor * (0.6 + rim * 1.4), a);
}`

export interface HoloOptions { intensity?: number; fadeFrom?: number; fadeTo?: number }

/** Additive see-through hologram: bright at the silhouette edge, faint scan lines, optional fade below a world height. */
export function holoMaterial(color: number, o: HoloOptions = {}): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(color) }, uIntensity: { value: o.intensity ?? 1 },
      uFade0: { value: o.fadeFrom ?? -100 }, uFade1: { value: o.fadeTo ?? -99 }, uTime: { value: 0 },
    },
    vertexShader: VERT, fragmentShader: FRAG,
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
  })
}
