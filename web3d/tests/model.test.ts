import { describe, expect, it } from 'vitest'
import { fmtTime, fmtStamp, fmtPrice } from '../src/model/format'
import { initialReplay, pause, play, revealed, seek, step, tick } from '../src/model/replay'
import { PANEL_CLOSED, panelReduce } from '../src/model/panel'
import { fovFor, onArc, poseDistance, roomPose, screenPose } from '../src/model/camera'
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
  it('click flies, arrives opens, close returns', () => {
    let s = panelReduce(PANEL_CLOSED, { type: 'click', id: 'backtests' })
    expect(s).toEqual({ phase: 'flying', computer: 'backtests' })
    s = panelReduce(s, { type: 'arrived' })
    expect(s.phase).toBe('open')
    s = panelReduce(s, { type: 'close' })
    expect(s.phase).toBe('closing')
    expect(panelReduce(s, { type: 'returned' })).toEqual(PANEL_CLOSED)
  })
  it('ignores clicks while closing and arrivals while closed', () => {
    const closing = { phase: 'closing' as const, computer: 'scanner' as const }
    expect(panelReduce(closing, { type: 'click', id: 'backtests' })).toBe(closing)
    expect(panelReduce(PANEL_CLOSED, { type: 'arrived' })).toBe(PANEL_CLOSED)
  })
  it('clicking another computer while open flies to it', () => {
    const open = { phase: 'open' as const, computer: 'scanner' as const }
    expect(panelReduce(open, { type: 'click', id: 'strategies' })).toEqual({ phase: 'flying', computer: 'strategies' })
  })
})

describe('camera', () => {
  it('180 degrees is straight behind the CEO', () => {
    const [x, y, z] = onArc(180, 7, 3)
    expect(x).toBeCloseTo(0); expect(y).toBe(3); expect(z).toBeCloseTo(-7)
  })
  it('screen pose sits in front of the screen, looking at it', () => {
    const p = screenPose(180, 7.4, 3)
    expect(p.target[2]).toBeCloseTo(-7.4)
    expect(p.pos[2]).toBeCloseTo(-4.8)
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
