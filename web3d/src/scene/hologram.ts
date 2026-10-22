import * as THREE from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import { HEAD_RADIUS, SEATED, STANDING, type Part } from './particles'

function capsule([a, b, r, , sx, sz]: Part): THREE.BufferGeometry {
  const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b)
  const g = new THREE.CapsuleGeometry(r, A.distanceTo(B), 6, 18)
  g.scale(sx, 1, sz)
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), B.clone().sub(A).normalize()))
  const mid = A.add(B).multiplyScalar(0.5)
  g.translate(mid.x, mid.y, mid.z)
  return g
}

const bodies = new Map<boolean, THREE.BufferGeometry>()
/** Solid body (same capsules as the particles) for the glow shell. */
export function bodyGeometry(seated: boolean): THREE.BufferGeometry {
  if (!bodies.has(seated)) bodies.set(seated, mergeGeometries((seated ? SEATED : STANDING).map(capsule))!)
  return bodies.get(seated)!
}

let head: THREE.BufferGeometry | null = null
/** Head, relative to the head pivot (matches the particle head). */
export function headGeometry(): THREE.BufferGeometry {
  if (!head) { head = new THREE.SphereGeometry(HEAD_RADIUS, 24, 18); head.scale(1, 1.2, 1); head.translate(0, 0.16, 0) }
  return head
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
  float rim = pow(1.0 - abs(dot(normalize(vN), normalize(vV))), 2.0);
  float scan = 0.82 + 0.18 * sin(vY * 70.0 - uTime * 3.0);
  float a = (0.07 + rim * 0.9) * scan * uIntensity * smoothstep(uFade0, uFade1, vY);
  gl_FragColor = vec4(uColor * (0.55 + rim * 1.3), a);
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
