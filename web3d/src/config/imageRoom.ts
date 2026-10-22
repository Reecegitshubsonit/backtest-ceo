import type { ComputerId } from '../model/types'

/** Rectangle in source-image pixels. */
export interface Rect { x: number; y: number; w: number; h: number }
export type Pt = [number, number]

/** The room picture (Grok reference, upscaled). All coordinates below are in its original 456 x 704 pixels. */
export const ROOM_IMAGE = { src: '/room.jpg', w: 456, h: 704 }

/** Wall screens that act as the three computers. */
export const SCREEN_RECTS: Record<ComputerId, Rect> = {
  backtests: { x: 4, y: 84, w: 156, h: 68 },
  scanner: { x: 4, y: 158, w: 156, h: 58 },
  strategies: { x: 298, y: 80, w: 156, h: 136 },
}

/** Where each seat's label sits (covering the picture's own text) and the agent's chest, for data streams. */
export const SEAT_SPOTS: Record<string, { label: Rect; chest: Pt }> = {
  scanner: { label: { x: 4, y: 236, w: 88, h: 36 }, chest: [42, 305] },
  strategist: { label: { x: 88, y: 215, w: 70, h: 34 }, chest: [122, 292] },
  backtester: { label: { x: 300, y: 215, w: 74, h: 34 }, chest: [336, 292] },
  auditor: { label: { x: 382, y: 238, w: 72, h: 36 }, chest: [414, 308] },
  regime: { label: { x: 6, y: 368, w: 80, h: 34 }, chest: [52, 445] },
  risk: { label: { x: 380, y: 370, w: 74, h: 34 }, chest: [420, 445] },
}

export const CEO_CHEST: Pt = [228, 205]
export const RING_CENTER: Pt = [228, 360]
/** Projector beam the CEO stands in (sparkles rise through it). */
export const BEAM: Rect = { x: 196, y: 70, w: 64, h: 300 }

/**
 * CSS transform (origin top-left, translate in % of the stage, then scale) that brings `r` to the middle of the
 * stage, filling most of it. Used as the "camera flight" into a screen.
 */
export function zoomTo(r: Rect, img = ROOM_IMAGE): { tx: number; ty: number; s: number } {
  const s = Math.min((0.92 * img.w) / r.w, (0.92 * img.h) / r.h, 3.2)
  const cx = r.x + r.w / 2, cy = r.y + r.h / 2
  return { tx: 50 - (s * cx * 100) / img.w, ty: 50 - (s * cy * 100) / img.h, s }
}
