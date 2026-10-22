import { describe, expect, it } from 'vitest'
import { SCREENS, screenById, screenName } from '../src/config/screens3d'
import { ROOM_R, TABLE_H, TABLE_R } from '../src/config/room'
import { SEATS } from '../src/config/seats'

const wall = SCREENS.filter(s => s.kind === 'wall'), desk = SCREENS.filter(s => s.kind === 'desk')
const flat = (v: number[]) => Math.hypot(v[0], v[2])

describe('3D screens', () => {
  it('has 17 numbered wall screens and 9 desk screens with unique ids', () => {
    expect(wall.map(s => s.n)).toEqual(Array.from({ length: 17 }, (_, i) => i + 1))
    expect(desk).toHaveLength(9)
    expect(new Set(SCREENS.map(s => s.id)).size).toBe(26)
  })
  it('keeps the computer and console mapping', () => {
    expect(screenById('s1')?.computer).toBe('backtests')
    expect(screenById('s5')?.computer).toBe('scanner')
    expect(screenById('s10')?.computer).toBe('strategies')
    for (const seat of SEATS) expect(screenById(`d-${seat.id}`)?.seat).toBe(seat.id)
  })
  it('wall screens sit inside the room, behind the CEO, facing the centre, without overlapping', () => {
    for (const s of wall) {
      expect(Math.hypot(flat(s.center), s.w / 2)).toBeLessThan(ROOM_R)
      expect(s.center[2]).toBeLessThan(0)
      expect(s.center[1] - s.h / 2).toBeGreaterThan(TABLE_H)
      expect(s.center[1] + s.h / 2).toBeLessThan(7.6)
      const n = [Math.sin(s.yaw), Math.cos(s.yaw)]
      expect(n[0] * s.center[0] + n[1] * s.center[2]).toBeLessThan(0)
    }
    const u = (s: typeof wall[0]) => Math.atan2(s.center[0], s.center[2]) * flat(s.center)
    for (const a of wall) for (const b of wall) {
      if (a === b) continue
      const apart = Math.abs(u(a) - u(b)) >= (a.w + b.w) / 2 - 1e-6 || Math.abs(a.center[1] - b.center[1]) >= (a.h + b.h) / 2 - 1e-6
      expect(apart, `${a.id} overlaps ${b.id}`).toBe(true)
    }
  })
  it('desk screens stand on the table, tilted back, without touching each other', () => {
    for (const s of desk) {
      expect(flat(s.center) + s.h / 2).toBeLessThan(TABLE_R)
      expect(s.center[1] - (s.h / 2) * Math.cos(s.pitch)).toBeGreaterThanOrEqual(TABLE_H)
      expect(s.pitch).toBeGreaterThan(0.3)
    }
    for (const a of desk) for (const b of desk) {
      if (a === b) continue
      const d = Math.hypot(a.center[0] - b.center[0], a.center[2] - b.center[2])
      expect(d, `${a.id} touches ${b.id}`).toBeGreaterThan((a.w + b.w) / 2 + 0.02)
    }
  })
  it('names screens for the hover tag', () => {
    expect(screenName(screenById('s1')!)).toBe('BACKTESTS')
    expect(screenName(screenById('s2')!)).toBe('SCREEN 2')
    expect(screenName(screenById('d-risk')!)).toBe('RISK MANAGER')
    expect(screenName(screenById('d8')!)).toBe('DESK 8')
  })
})
