import type { ComputerId } from '../model/types'

/** Rectangle in source-image pixels. */
export interface Rect { x: number; y: number; w: number; h: number }
export type Pt = [number, number]

/**
 * The room picture: the 16:9 Grok render (docs/reference/grok-room-wide.jpg) with its baked-in text painted out,
 * at its original pixels. All coordinates below are in the source's 1280 x 720 pixels.
 */
export const ROOM_IMAGE = { src: '/room.jpg', w: 1280, h: 720 }

/** One screen on the wall behind the CEO. `computer` is set when the screen opens one of the computers. */
export interface WallScreen { id: string; n: number; rect: Rect; computer?: ComputerId; seat?: string }

/** All 17 screens on the wall, numbered left to right, top to bottom. Every one is clickable. */
export const WALL_SCREENS: WallScreen[] = [
  { id: 's1', n: 1, rect: { x: 12, y: 28, w: 266, h: 172 }, computer: 'backtests' },
  { id: 's2', n: 2, rect: { x: 12, y: 204, w: 266, h: 96 } },
  { id: 's3', n: 3, rect: { x: 8, y: 326, w: 172, h: 88 } },
  { id: 's4', n: 4, rect: { x: 182, y: 316, w: 110, h: 88 } },
  { id: 's5', n: 5, rect: { x: 310, y: 86, w: 228, h: 110 }, computer: 'scanner' },
  { id: 's6', n: 6, rect: { x: 310, y: 200, w: 140, h: 88 } },
  { id: 's7', n: 7, rect: { x: 452, y: 200, w: 88, h: 88 } },
  { id: 's8', n: 8, rect: { x: 542, y: 112, w: 40, h: 186 } },
  { id: 's9', n: 9, rect: { x: 700, y: 112, w: 38, h: 150 } },
  { id: 's10', n: 10, rect: { x: 740, y: 104, w: 102, h: 100 }, computer: 'strategies' },
  { id: 's11', n: 11, rect: { x: 740, y: 208, w: 102, h: 60 } },
  { id: 's12', n: 12, rect: { x: 846, y: 92, w: 120, h: 84 } },
  { id: 's13', n: 13, rect: { x: 846, y: 180, w: 120, h: 100 } },
  { id: 's14', n: 14, rect: { x: 998, y: 76, w: 268, h: 140 } },
  { id: 's15', n: 15, rect: { x: 998, y: 222, w: 268, h: 82 } },
  { id: 's16', n: 16, rect: { x: 986, y: 316, w: 130, h: 90 } },
  { id: 's17', n: 17, rect: { x: 1100, y: 326, w: 166, h: 94 } },
]

/** Screens built into the desk: one in front of each agent (its console), three on the front edge of the table. */
export const DESK_SCREENS: WallScreen[] = [
  { id: 'd-scanner', n: 1, seat: 'scanner', rect: { x: 335, y: 418, w: 120, h: 40 } },
  { id: 'd-strategist', n: 2, seat: 'strategist', rect: { x: 462, y: 392, w: 104, h: 34 } },
  { id: 'd-backtester', n: 3, seat: 'backtester', rect: { x: 716, y: 392, w: 104, h: 34 } },
  { id: 'd-auditor', n: 4, seat: 'auditor', rect: { x: 826, y: 418, w: 120, h: 40 } },
  { id: 'd-regime', n: 5, seat: 'regime', rect: { x: 322, y: 486, w: 150, h: 66 } },
  { id: 'd-risk', n: 6, seat: 'risk', rect: { x: 812, y: 486, w: 150, h: 66 } },
  { id: 'd7', n: 7, rect: { x: 400, y: 556, w: 150, h: 46 } },
  { id: 'd8', n: 8, rect: { x: 560, y: 568, w: 160, h: 36 } },
  { id: 'd9', n: 9, rect: { x: 730, y: 556, w: 150, h: 46 } },
]

export const screenById = (id: string): WallScreen | undefined => [...WALL_SCREENS, ...DESK_SCREENS].find(s => s.id === id)
export const isDesk = (id: string) => DESK_SCREENS.some(s => s.id === id)

/** Where each seat's label sits (where the picture had its own text) and the agent's chest, for data streams. */
export const SEAT_SPOTS: Record<string, { label: Rect; chest: Pt }> = {
  scanner: { label: { x: 300, y: 286, w: 114, h: 54 }, chest: [362, 400] },
  strategist: { label: { x: 430, y: 258, w: 114, h: 54 }, chest: [488, 372] },
  backtester: { label: { x: 736, y: 258, w: 114, h: 54 }, chest: [792, 372] },
  auditor: { label: { x: 868, y: 286, w: 114, h: 54 }, chest: [918, 400] },
  regime: { label: { x: 214, y: 410, w: 116, h: 56 }, chest: [282, 520] },
  risk: { label: { x: 940, y: 412, w: 116, h: 56 }, chest: [998, 545] },
}

export const CEO_CHEST: Pt = [640, 240]
/** Where the CEO's title sits on the chest. */
export const CEO_LABEL: Rect = { x: 570, y: 194, w: 140, h: 84 }
/** The table's own summary text, replaced with ours. */
export const SUMMARY_LABEL: Rect = { x: 550, y: 518, w: 180, h: 46 }
export const RING_CENTER: Pt = [640, 455]
/** Projector beam the CEO stands in (sparkles rise through it). */
export const BEAM: Rect = { x: 608, y: 95, w: 64, h: 360 }

/**
 * CSS transform (origin top-left, translate in % of the stage, then scale) that brings `r` to the middle of the
 * stage, filling most of it. Used as the "camera flight" into a screen.
 */
export function zoomTo(r: Rect, img = ROOM_IMAGE): { tx: number; ty: number; s: number } {
  const s = Math.min((0.92 * img.w) / r.w, (0.92 * img.h) / r.h, 3.2)
  const cx = r.x + r.w / 2, cy = r.y + r.h / 2
  return { tx: 50 - (s * cx * 100) / img.w, ty: 50 - (s * cy * 100) / img.h, s }
}
