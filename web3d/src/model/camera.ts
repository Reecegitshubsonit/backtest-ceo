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

/** Camera `dist` in front of a wall screen, looking straight at it. */
export const screenPose = (angleDeg: number, r: number, y: number, dist = 2.6): CamPose =>
  ({ pos: onArc(angleDeg, r - dist, y), target: onArc(angleDeg, r, y) })

const dist = (a: Vec3, b: Vec3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
export const poseDistance = (a: CamPose, b: CamPose): number => Math.max(dist(a.pos, b.pos), dist(a.target, b.target))
