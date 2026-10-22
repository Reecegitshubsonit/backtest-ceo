import { describe, expect, it } from 'vitest'
import { DESK_SCREENS, ROOM_IMAGE, SEAT_SPOTS, WALL_SCREENS, screenById, zoomTo } from '../src/config/imageRoom'
import { SEATS } from '../src/config/seats'

const inside = (x: number, y: number) => x >= 0 && y >= 0 && x <= ROOM_IMAGE.w && y <= ROOM_IMAGE.h

describe('image room', () => {
  it('has 17 numbered wall screens, all inside the picture, each computer on exactly one', () => {
    expect(WALL_SCREENS).toHaveLength(17)
    expect(WALL_SCREENS.map(s => s.n)).toEqual(Array.from({ length: 17 }, (_, i) => i + 1))
    for (const s of WALL_SCREENS) expect(inside(s.rect.x + s.rect.w, s.rect.y + s.rect.h)).toBe(true)
    for (const c of ['backtests', 'scanner', 'strategies']) expect(WALL_SCREENS.filter(s => s.computer === c)).toHaveLength(1)
  })
  it('zoom puts a screen centre in the middle of the stage', () => {
    const r = screenById('s1')!.rect
    const { tx, ty, s } = zoomTo(r)
    expect(((r.x + r.w / 2) / ROOM_IMAGE.w) * 100 * s + tx).toBeCloseTo(50)
    expect(((r.y + r.h / 2) / ROOM_IMAGE.h) * 100 * s + ty).toBeCloseTo(50)
  })
  it('every agent has one desk screen, and all desk screens are inside the picture', () => {
    for (const seat of SEATS) expect(DESK_SCREENS.filter(d => d.seat === seat.id)).toHaveLength(1)
    for (const d of DESK_SCREENS) expect(inside(d.rect.x + d.rect.w, d.rect.y + d.rect.h)).toBe(true)
    expect(screenById('d-risk')?.seat).toBe('risk')
  })
  it('every seat has a spot inside the picture', () => {
    for (const seat of SEATS) {
      const sp = SEAT_SPOTS[seat.id]
      expect(inside(sp.label.x + sp.label.w, sp.label.y + sp.label.h)).toBe(true)
      expect(inside(...sp.chest)).toBe(true)
    }
  })
})
