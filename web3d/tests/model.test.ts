import { describe, expect, it } from 'vitest'
import { fmtTime, fmtStamp, fmtPrice } from '../src/model/format'
import { initialReplay, pause, play, revealed, seek, step, tick } from '../src/model/replay'
import { PANEL_CLOSED, panelReduce } from '../src/model/panel'
import { clampToRoom, flyPose, fovFor, htmlDistanceFactor, onArc, poseDistance, projectedWidthPx, roomPose, screenNormal } from '../src/model/camera'
import { SCREENS } from '../src/config/screens3d'
import { ROOM_R } from '../src/config/room'
import { fullView, priceRange, zoomTime } from '../src/model/viewport'
import { lastSession } from '../src/model/dates'
import { INDICATORS } from '../src/model/indicators'
import { COMPUTERS, computerById } from '../src/config/computers'
import { SEATS } from '../src/config/seats'
import type { Bar } from '../src/model/types'

const bar = (i: number, c = 100 + i): Bar => ({ t: new Date(Date.UTC(2026, 9, 20, 13, 30 + i)).toISOString(), o: c, h: c + 1, l: c - 1, c, v: 10 })

describe('format', () => {
  it('shows ET clock time intraday and a date for daily bars', () => {
    expect(fmtTime('2026-10-20T13:30:00Z', '5Min')).toBe('09:30')
    expect(fmtTime('2026-10-20T04:00:00Z', '1Day')).toBe('Oct 20')
    expect(fmtStamp('2026-10-20T13:30:00Z')).toBe('Oct 20 09:30 ET')
  })
  it('uses more decimals for cheap prices', () => {
    expect(fmtPrice(612.5)).toBe('612.50')
    expect(fmtPrice(0.85)).toBe('0.850')
  })
})

describe('replay', () => {
  it('starts showing every bar, paused', () => {
    expect(initialReplay(10)).toMatchObject({ index: 9, playing: false })
  })
  it('play from the end rewinds to the first bar', () => {
    expect(play(initialReplay(10), 10)).toMatchObject({ index: 0, playing: true })
  })
  it('advances speed bars per second and never passes the last bar', () => {
    let s = { ...play(initialReplay(10), 10), speed: 5 }
    s = tick(s, 10, 0.5)
    expect(s.index).toBe(2)
    s = tick(s, 10, 10)
    expect(s).toMatchObject({ index: 9, playing: false })
  })
  it('keeps fractional progress between ticks', () => {
    let s = { ...play(initialReplay(10), 10), speed: 1 }
    s = tick(tick(s, 10, 0.6), 10, 0.6)
    expect(s.index).toBe(1)
  })
  it('does nothing while paused', () => {
    const s = pause(play(initialReplay(10), 10))
    expect(tick(s, 10, 5)).toBe(s)
  })
  it('seek clamps and step pauses', () => {
    const s = initialReplay(10)
    expect(seek(s, 10, 99).index).toBe(9)
    expect(seek(s, 10, -3).index).toBe(0)
    expect(step(play(s, 10), 10, 3)).toMatchObject({ index: 3, playing: false })
  })
  it('revealed never includes bars past the clock', () => {
    const bars = [0, 1, 2, 3].map(i => bar(i))
    expect(revealed(bars, seek(initialReplay(4), 4, 1))).toEqual(bars.slice(0, 2))
  })
})

describe('panel state', () => {
  it('click flies, arrival focuses, expand opens the panel, back steps out one level at a time', () => {
    let s = panelReduce(PANEL_CLOSED, { type: 'click', id: 's1' })
    expect(s).toEqual({ phase: 'flying', screen: 's1' })
    s = panelReduce(s, { type: 'arrived' }); expect(s.phase).toBe('focused')
    s = panelReduce(s, { type: 'expand' }); expect(s.phase).toBe('expanded')
    s = panelReduce(s, { type: 'back' }); expect(s.phase).toBe('focused')
    s = panelReduce(s, { type: 'back' }); expect(s.phase).toBe('closing')
    expect(panelReduce(s, { type: 'returned' })).toEqual(PANEL_CLOSED)
  })
  it('ignores clicks while closing or expanded, and arrivals while closed', () => {
    const closing = { phase: 'closing' as const, screen: 's5' }
    expect(panelReduce(closing, { type: 'click', id: 's1' })).toBe(closing)
    const expanded = { phase: 'expanded' as const, screen: 's5' }
    expect(panelReduce(expanded, { type: 'click', id: 's1' })).toBe(expanded)
    expect(panelReduce(PANEL_CLOSED, { type: 'arrived' })).toBe(PANEL_CLOSED)
    expect(panelReduce(PANEL_CLOSED, { type: 'expand' })).toBe(PANEL_CLOSED)
  })
  it('clicking another screen while focused flies to it; back during a flight returns', () => {
    const focused = { phase: 'focused' as const, screen: 's5' }
    expect(panelReduce(focused, { type: 'click', id: 's10' })).toEqual({ phase: 'flying', screen: 's10' })
    expect(panelReduce({ phase: 'flying', screen: 's1' }, { type: 'back' }).phase).toBe('closing')
  })
})

describe('camera', () => {
  it('180 degrees is straight behind the CEO', () => {
    const [x, y, z] = onArc(180, 7, 3)
    expect(x).toBeCloseTo(0); expect(y).toBe(3); expect(z).toBeCloseTo(-7)
  })
  it('fly pose looks straight at the screen and fills 85% of the view, for every screen', () => {
    for (const aspect of [16 / 9, 4 / 3, 0.5]) {
      const fov = fovFor(aspect)
      for (const s of SCREENS) {
        const p = flyPose(s, fov, aspect)
        expect(p.target).toEqual(s.center)
        const d = Math.hypot(p.pos[0] - s.center[0], p.pos[1] - s.center[1], p.pos[2] - s.center[2])
        const n = screenNormal(s)
        expect(((p.pos[0] - s.center[0]) * n[0] + (p.pos[1] - s.center[1]) * n[1] + (p.pos[2] - s.center[2]) * n[2]) / d).toBeCloseTo(1)
        const visH = 2 * d * Math.tan((fov * Math.PI) / 360)
        expect(Math.max(s.h / visH, s.w / (visH * aspect))).toBeCloseTo(0.85)
        expect(Math.hypot(p.pos[0], p.pos[2]), `${s.id} at aspect ${aspect}`).toBeLessThan(ROOM_R)
      }
    }
  })
  it('screen normal of an upright screen facing +z is +z; tilting back points it up', () => {
    expect(screenNormal({ yaw: 0, pitch: 0 })).toEqual([0, 0, 1])
    expect(screenNormal({ yaw: 0, pitch: Math.PI / 2 })[1]).toBeCloseTo(1)
  })
  it('html scale: a DOM node as wide as the projected screen lands exactly on it', () => {
    const px = projectedWidthPx(2, 3, 48, 16 / 9, 1920)
    expect(px).toBeCloseTo((2 / (2 * 3 * Math.tan((48 * Math.PI) / 360) * (16 / 9))) * 1920)
    expect((htmlDistanceFactor(2, px) * px) / 400).toBeCloseTo(2)
  })
  it('clamps the camera inside the room and above the floor', () => {
    expect(clampToRoom([20, -3, 0], 9, 0.4, 7.6)).toEqual([9, 0.4, 0])
    expect(clampToRoom([1, 2, 1], 9, 0.4, 7.6)).toEqual([1, 2, 1])
  })
  it('narrow screens widen the field of view instead of backing out of the room', () => {
    expect(fovFor(1.6)).toBe(48)
    expect(fovFor(0.46)).toBeGreaterThan(70)
    expect(roomPose(0.46).pos[2]).toBeLessThan(13)
  })
  it('pose distance is zero for equal poses', () => {
    expect(poseDistance(roomPose(1.5), roomPose(1.5))).toBe(0)
  })
})

describe('viewport', () => {
  it('price range pads the visible highs and lows', () => {
    const r = priceRange([bar(0, 100), bar(1, 110)], fullView())
    expect(r.lo).toBeLessThan(99); expect(r.hi).toBeGreaterThan(111)
  })
  it('zoom keeps at least 10 bars', () => {
    expect(zoomTime(fullView(), 100, 1000, 0.5).span).toBe(10)
  })
})

describe('dates', () => {
  it('last session is the previous weekday', () => {
    expect(lastSession(new Date('2026-10-21T15:00:00Z'))).toBe('2026-10-20')
    expect(lastSession(new Date('2026-10-19T15:00:00Z'))).toBe('2026-10-16')
  })
})

describe('config', () => {
  it('ships no indicators', () => { expect(INDICATORS).toEqual([]) })
  it('has six seats and three computers, backtests live', () => {
    expect(SEATS).toHaveLength(6)
    expect(COMPUTERS.map(c => c.id)).toEqual(['scanner', 'backtests', 'strategies'])
    expect(computerById('backtests').live).toBe(true)
  })
})
