import { describe, expect, it } from 'vitest'
import { figurePoints, mulberry32 } from '../src/scene/particles'

const ys = (a: Float32Array) => a.filter((_, i) => i % 3 === 1)

describe('figurePoints', () => {
  it('is deterministic for a seed', () => {
    expect(figurePoints(false, 1, mulberry32(4)).body).toEqual(figurePoints(false, 1, mulberry32(4)).body)
  })
  it('a standing figure spans floor to shoulders, head above', () => {
    const f = figurePoints(false, 1, mulberry32(1))
    expect(Math.min(...ys(f.body))).toBeGreaterThan(-0.1)
    expect(Math.max(...ys(f.body))).toBeLessThan(1.6)
    expect(f.headPivot[1]).toBeCloseTo(1.47)
  })
  it('a seated figure is lower', () => {
    expect(Math.max(...ys(figurePoints(true, 1, mulberry32(1)).body))).toBeLessThan(1.15)
  })
  it('density scales the point count', () => {
    expect(figurePoints(false, 2, mulberry32(1)).body.length).toBeGreaterThan(figurePoints(false, 1, mulberry32(1)).body.length * 1.9)
  })
})
