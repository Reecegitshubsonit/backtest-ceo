import { onArc, type Vec3 } from '../model/camera'
import type { ComputerId } from '../model/types'
import { computerById } from './computers'
import { TABLE_H, TABLE_R, WALL_SCREEN_R } from './room'
import { SEATS } from './seats'

/** One screen in the room. Faces along `yaw` (0 = +z), tilted back by `pitch` (0 = upright). */
export interface Screen3D {
  id: string; n: number; kind: 'wall' | 'desk'
  center: Vec3; yaw: number; pitch: number; w: number; h: number
  computer?: ComputerId; seat?: string
}

/** The wall screens as laid out in the Grok picture (docs/reference/grok-room-wide.jpg), in its 1280 x 720 pixels. */
const PICTURE: [number, number, number, number, ComputerId?][] = [
  [12, 28, 266, 172, 'backtests'], [12, 204, 266, 96], [8, 326, 172, 88], [182, 316, 110, 88],
  [310, 86, 228, 110, 'scanner'], [310, 200, 140, 88], [452, 200, 88, 88], [542, 112, 40, 186],
  [700, 112, 38, 150], [740, 104, 102, 100, 'strategies'], [740, 208, 102, 60], [846, 92, 120, 84],
  [846, 180, 120, 100], [998, 76, 268, 140], [998, 222, 268, 82], [986, 316, 110, 90], [1100, 326, 166, 94],
]
/** World units per picture pixel, and the world height of the picture's top edge. */
const PX = 0.0135
const TOP = 7.2
const rad = (deg: number) => (deg * Math.PI) / 180

function wallScreen(n: number, [x, y, w, h, computer]: (typeof PICTURE)[number]): Screen3D {
  // picture left of centre -> left of the CEO as seen from the front (+z), on the arc behind it (180 degrees)
  const deg = 180 - (((x + w / 2 - 640) * PX) / WALL_SCREEN_R) * (180 / Math.PI)
  return { id: `s${n}`, n, kind: 'wall', center: onArc(deg, WALL_SCREEN_R, TOP - (y + h / 2) * PX), yaw: rad(deg) + Math.PI, pitch: 0, w: w * PX, h: h * PX, computer }
}

const TILT = rad(35)
/** A screen standing on the table at `deg`, facing outward (towards the seat at that angle), tilted back. */
function deskScreen(id: string, n: number, deg: number, r: number, w: number, h: number, seat?: string): Screen3D {
  return { id, n, kind: 'desk', center: onArc(deg, r, TABLE_H + (h / 2) * Math.cos(TILT) + 0.02), yaw: rad(deg), pitch: TILT, w, h, seat }
}

export const SCREENS: Screen3D[] = [
  ...PICTURE.map((p, i) => wallScreen(i + 1, p)),
  ...SEATS.map((s, i) => deskScreen(`d-${s.id}`, i + 1, s.angleDeg, TABLE_R - 0.5, 0.95, 0.53, s.id)),
  deskScreen('d7', 7, -20, TABLE_R - 0.5, 0.55, 0.31),
  deskScreen('d8', 8, 0, TABLE_R - 0.5, 1.0, 0.43),
  deskScreen('d9', 9, 20, TABLE_R - 0.5, 0.55, 0.31),
]

export const screenById = (id: string): Screen3D | undefined => SCREENS.find(s => s.id === id)

/** The tag shown on hover. */
export function screenName(s: Screen3D): string {
  if (s.computer) return computerById(s.computer).label
  if (s.seat) return SEATS.find(x => x.id === s.seat)!.name
  return s.kind === 'wall' ? `SCREEN ${s.n}` : `DESK ${s.n}`
}
