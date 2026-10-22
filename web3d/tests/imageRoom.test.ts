import { describe, expect, it } from 'vitest'
import { ROOM_IMAGE, SCREEN_RECTS, SEAT_SPOTS, zoomTo } from '../src/config/imageRoom'
import { SEATS } from '../src/config/seats'

const inside = (x: number, y: number) => x >= 0 && y >= 0 && x <= ROOM_IMAGE.w && y <= ROOM_IMAGE.h

describe('image room', () => {
  it('zoom puts the screen centre in the middle of the stage', () => {
    const r = SCREEN_RECTS.backtests
    const { tx, ty, s } = zoomTo(r)
    const cx = ((r.x + r.w / 2) / ROOM_IMAGE.w) * 100 * s + tx
    const cy = ((r.y + r.h / 2) / ROOM_IMAGE.h) * 100 * s + ty
    expect(cx).toBeCloseTo(50); expect(cy).toBeCloseTo(50)
    expect(s).toBeGreaterThan(1)
  })
  it('every seat has a spot and every spot is inside the picture', () => {
    for (const seat of SEATS) {
      const sp = SEAT_SPOTS[seat.id]
      expect(sp).toBeDefined()
      expect(inside(sp.label.x + sp.label.w, sp.label.y + sp.label.h)).toBe(true)
      expect(inside(...sp.chest)).toBe(true)
    }
  })
})
