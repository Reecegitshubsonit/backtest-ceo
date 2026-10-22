export type Vec3 = [number, number, number]
export interface CamPose { pos: Vec3; target: Vec3 }

const NARROW = 1.25

/** Point on a circle around the room centre; 0 degrees faces the viewer (+z), 180 is behind the CEO. */
export function onArc(angleDeg: number, r: number, y: number): Vec3 {
  const a = (angleDeg * Math.PI) / 180
  return [Math.sin(a) * r, y, Math.cos(a) * r]
}

/** On narrow screens widen the field of view instead of backing the camera out through the wall. */
export function fovFor(aspect: number): number {
  if (aspect >= NARROW) return 48
  return Math.min(80, (2 * Math.atan(4.4 / 9.8 / aspect) * 180) / Math.PI)
}

/** Close and a little above the table, looking down at it, like the reference image. */
export const roomPose = (aspect: number): CamPose => ({ pos: [0, 4.0, aspect >= NARROW ? 9.2 : 9.8], target: [0, 2.3, 0] })

interface Facing { yaw: number; pitch: number }
interface Placed extends Facing { center: Vec3; w: number; h: number }

/** Unit vector out of a screen's face. */
export function screenNormal({ yaw, pitch }: Facing): Vec3 {
  return [Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch)]
}

const tanHalf = (fovDeg: number) => Math.tan((fovDeg * Math.PI) / 360)

/** Distance at which a w x h screen, seen square on, fills `fill` of the view in its tighter dimension. */
export function flyDistance(w: number, h: number, fovDeg: number, aspect: number, fill = 0.85): number {
  const t = 2 * tanHalf(fovDeg)
  return Math.max(h / (fill * t), w / (fill * t * aspect))
}

/** Camera square in front of a screen, filling most of the view. */
export function flyPose(s: Placed, fovDeg: number, aspect: number, fill = 0.85): CamPose {
  const d = flyDistance(s.w, s.h, fovDeg, aspect, fill), n = screenNormal(s)
  return { pos: [s.center[0] + n[0] * d, s.center[1] + n[1] * d, s.center[2] + n[2] * d], target: s.center }
}

/** On-screen width in CSS px of a `w`-wide screen seen square on from `dist`. */
export const projectedWidthPx = (w: number, dist: number, fovDeg: number, aspect: number, viewportW: number): number =>
  (w / (2 * dist * tanHalf(fovDeg) * aspect)) * viewportW

/** drei <Html transform> draws 1 CSS px as distanceFactor / 400 world units. */
export const htmlDistanceFactor = (wWorld: number, px: number): number => (400 * wWorld) / px

/** Keep a point within `maxR` of the room's axis and between two heights. */
export function clampToRoom([x, y, z]: Vec3, maxR: number, yMin: number, yMax: number): Vec3 {
  const r = Math.hypot(x, z), k = r > maxR ? maxR / r : 1
  return [x * k, Math.min(yMax, Math.max(yMin, y)), z * k]
}

const dist = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
export const poseDistance = (a: CamPose, b: CamPose): number => Math.max(dist(a.pos, b.pos), dist(a.target, b.target))
