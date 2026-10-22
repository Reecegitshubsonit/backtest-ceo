import type { ComputerId } from '../model/types'

/** Rectangle in source-image pixels. */
export interface Rect { x: number; y: number; w: number; h: number }
export type Pt = [number, number]

/**
 * The room picture: the 16:9 Grok render (docs/reference/grok-room-wide.jpg) with its baked-in text painted out,
 * upscaled 2x. All coordinates below are in the source's 1280 x 720 pixels.
 */
export const ROOM_IMAGE = { src: '/room.jpg', w: 1280, h: 720 }

/** Wall screens that act as the three computers. */
export const SCREEN_RECTS: Record<ComputerId, Rect> = {
  backtests: { x: 6, y: 22, w: 282, h: 306 },
  scanner: { x: 306, y: 84, w: 240, h: 212 },
  strategies: { x: 736, y: 84, w: 234, h: 212 },
}

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
