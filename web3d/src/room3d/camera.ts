import * as THREE from 'three'
import type { RoomScreen, XYZ } from '../config/roomScreens'

export const HOME = { position: [0, 3.844, 7.04] as XYZ, target: [0, 3.3, 0] as XYZ, fov: 48, offsetY: 86.4 }
export const LIMITS = { radius: 8, floor: 0.18, ceiling: 7.0 }
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
