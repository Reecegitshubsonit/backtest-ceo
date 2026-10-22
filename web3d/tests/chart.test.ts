import { describe, expect, it } from 'vitest'
import { chartGeometry } from '../src/panels/drawChart'
import { fullView } from '../src/model/viewport'
import type { Bar } from '../src/model/types'

const bars: Bar[] = [0, 1, 2, 3].map(i => ({ t: `2026-10-20T13:3${i}:00Z`, o: 100, h: 101 + i, l: 99 - i, c: 100, v: 10 }))

describe('chartGeometry', () => {
  const g = chartGeometry(800, 400, bars, fullView())
  it('maps the padded price range onto the price plot', () => {
    expect(g.y(g.hi)).toBeCloseTo(g.padT)
    expect(g.y(g.lo)).toBeCloseTo(g.padT + g.plotH)
  })
  it('centres bars in their slots', () => {
    expect(g.x(0)).toBeCloseTo(g.padL + g.plotW / 8)
  })
  it('puts the volume panel below the price plot', () => {
    expect(g.volTop).toBeGreaterThan(g.padT + g.plotH)
    expect(g.volTop + g.volH).toBeLessThanOrEqual(400 - g.padB)
  })
})
