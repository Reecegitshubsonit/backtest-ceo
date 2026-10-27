import * as THREE from 'three'
import type { RoomScreen, XYZ } from '../config/roomScreens'

export const HOME = { position: [0, 3.844, 7.04] as XYZ, target: [0, 3.3, 0] as XYZ, fov: 48, offsetY: 86.4 }
export const LIMITS = { radius: 8, floor: 0.18, ceiling: 7.0 }
/** Zoom tuning: wheel sensitivity (log-distance per wheel pixel), damping rate, closest approach to the
 * surface under the cursor, farthest camera-to-focus distance. */
export const ZOOM = { wheel: 0.00125, smoothing: 11, minSurface: 0.32, maxDistance: 11 }
/** Inspect (zoom-to-read) tuning. A screen under the pointer is taken head-on once the user has
 * scrolled toward it by `gesture` in total (log-distance, two mouse notches; it resets when the pointer
 * moves to another screen, the user scrolls out or drags) or it already
 * fills `fraction` of the view. The head-on pose fills `fill` of the view with the screen. */
export const INSPECT = { gesture: 0.24, fraction: 0.34, fill: 0.7, minDistance: 0.3, clearance: 0.14 }
/** Free space for the camera: inside the wall/monitor ring, above the floor, below the ceiling,
 * out of the command desk and the wall console ledge. */
export function inRoom(p: THREE.Vector3) {
  const r = Math.hypot(p.x, p.z)
  if (r > LIMITS.radius - 0.25 || p.y < LIMITS.floor + 0.12 || p.y > LIMITS.ceiling - 0.15) return false
  if (r < 2.9 && p.y < 1.8) return false
  if (r > 7.25 && p.y < 1.1) return false
  return true
}
export function referenceCamera() {
  const c = new THREE.PerspectiveCamera(HOME.fov, 1280 / 720, 0.05, 80)
  c.position.set(...HOME.position); c.lookAt(...HOME.target)
  c.setViewOffset(1280, 720, 0, HOME.offsetY, 1280, 720); c.updateMatrixWorld()
  return c
}
export function flightDistance(w: number, h: number, aspect: number, fov = 48) {
  return Math.max(w / aspect, h) / (1.7 * Math.tan(fov * Math.PI / 360))
}
export function flightPose(s: RoomScreen, aspect: number) {
  const d = flightDistance(s.w, s.h, aspect)
  return {position: s.center.map((v,i)=>v+s.normal[i]*d) as XYZ, target: s.center, up: new THREE.Vector3(0,1,0).applyQuaternion(new THREE.Quaternion(...s.quaternion)).toArray() as XYZ}
}
export function constrain([x,y,z]: XYZ): XYZ {
  const r = Math.hypot(x,z), k = r>LIMITS.radius?LIMITS.radius/r:1
  return [x*k, Math.max(LIMITS.floor, Math.min(LIMITS.ceiling,y)), z*k]
}
export function referencePoint(x: number,y: number,z: number) {
  const c = referenceCamera()
  const direction = new THREE.Vector3(x/640-1,1-y/360,.5).unproject(c).sub(c.position).normalize()
  return c.position.clone().addScaledVector(direction,(z-c.position.z)/direction.z)
}

/** Distance from a screen's face at which its limiting dimension fills `fill` of the view. */
export function inspectDistance(w: number, h: number, aspect: number, fill = INSPECT.fill, fov = HOME.fov) {
  return Math.max(w / aspect, h) / (fill * 2 * Math.tan(fov * Math.PI / 360))
}
/** Fraction of the view the screen would fill at distance `d` if seen head-on (ignores foreshortening). */
export function screenFraction(w: number, h: number, d: number, aspect: number, fov = HOME.fov) {
  const view = 2 * Math.max(d, 1e-3) * Math.tan(fov * Math.PI / 360)
  return Math.max(w / (view * aspect), h / view)
}
/** The screen's readable "up" in world space. Flat desk consoles are drawn rotated 180° when seen from
 * their far side (Scene.tsx uFlip), so their readable up depends on which side the viewer is on. */
export function readableUp(s: RoomScreen, from: THREE.Vector3) {
  const up = new THREE.Vector3(0, 1, 0).applyQuaternion(new THREE.Quaternion(...s.quaternion))
  if (s.kind === 'desk' && from.clone().sub(new THREE.Vector3(...s.center)).dot(up) > 0.05) up.negate()
  return up
}
/** Head-on reading pose: the camera sits on the screen normal at distance `d`, upright to the screen's
 * readable up. `viewOffset` is the vertical projection offset in NDC (the calibrated home view shifts
 * the frame by HOME.offsetY), so the target is nudged along "up" to keep the screen centred. */
export function inspectPose(s: RoomScreen, d: number, up: THREE.Vector3, viewOffset: number, fov = HOME.fov) {
  const c = new THREE.Vector3(...s.center), n = new THREE.Vector3(...s.normal)
  const position = c.clone().addScaledVector(n, d)
  const target = c.clone().addScaledVector(up, d * viewOffset * Math.tan(fov * Math.PI / 360))
  return { position, target }
}
