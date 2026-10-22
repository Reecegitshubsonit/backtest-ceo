export type Rand = () => number
type V = [number, number, number]

export function mulberry32(seed: number): Rand {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const cross = (a: V, b: V): V => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
const norm = (a: V): V => { const l = Math.hypot(...a) || 1; return [a[0] / l, a[1] / l, a[2] / l] }

/** Points on (and a few inside) a capsule from a to b; sx/sz flatten it (torso). */
function seg(out: number[], a: V, b: V, r: number, n: number, rand: Rand, sx = 1, sz = 1) {
  const d: V = [b[0] - a[0], b[1] - a[1], b[2] - a[2]]
  const dir = norm(d)
  const u = norm(cross(dir, Math.abs(dir[1]) > 0.9 ? [1, 0, 0] : [0, 1, 0]))
  const v = cross(dir, u)
  for (let i = 0; i < Math.round(n); i++) {
    const t = rand(), ang = rand() * Math.PI * 2
    const rr = r * (rand() < 0.2 ? rand() : 0.85 + rand() * 0.15)
    const c = Math.cos(ang) * rr, s = Math.sin(ang) * rr
    out.push(a[0] + d[0] * t + (u[0] * c + v[0] * s) * sx, a[1] + d[1] * t + u[1] * c + v[1] * s, a[2] + d[2] * t + (u[2] * c + v[2] * s) * sz)
  }
}

/** Body parts as capsules: from, to, radius, particle weight, x and z flattening. Shared by particles and the glow mesh. */
export type Part = [V, V, number, number, number, number]

export const STANDING: Part[] = [
  [[0, 0.98, 0], [0, 1.42, 0], 0.19, 900, 1.25, 0.65],
  [[0, 1.42, 0], [0, 1.5, 0], 0.06, 80, 1, 1],
  [[-0.25, 1.4, 0], [-0.3, 1.1, 0.02], 0.055, 200, 1, 1],
  [[0.25, 1.4, 0], [0.3, 1.1, 0.02], 0.055, 200, 1, 1],
  [[-0.3, 1.1, 0.02], [-0.33, 0.82, 0.08], 0.045, 160, 1, 1],
  [[0.3, 1.1, 0.02], [0.33, 0.82, 0.08], 0.045, 160, 1, 1],
  [[-0.1, 0.98, 0], [-0.12, 0.5, 0], 0.075, 260, 1, 1],
  [[0.1, 0.98, 0], [0.12, 0.5, 0], 0.075, 260, 1, 1],
  [[-0.12, 0.5, 0], [-0.13, 0.04, 0.02], 0.055, 220, 1, 1],
  [[0.12, 0.5, 0], [0.13, 0.04, 0.02], 0.055, 220, 1, 1],
]

export const SEATED: Part[] = [
  [[0, 0.56, -0.05], [0, 1.0, -0.1], 0.19, 900, 1.25, 0.65],
  [[0, 1.0, -0.1], [0, 1.08, -0.1], 0.06, 80, 1, 1],
  [[-0.25, 0.98, -0.1], [-0.29, 0.72, 0.05], 0.055, 200, 1, 1],
  [[0.25, 0.98, -0.1], [0.29, 0.72, 0.05], 0.055, 200, 1, 1],
  [[-0.29, 0.72, 0.05], [-0.24, 0.7, 0.38], 0.045, 160, 1, 1],
  [[0.29, 0.72, 0.05], [0.24, 0.7, 0.38], 0.045, 160, 1, 1],
  [[-0.11, 0.56, 0], [-0.13, 0.56, 0.46], 0.075, 260, 1, 1],
  [[0.11, 0.56, 0], [0.13, 0.56, 0.46], 0.075, 260, 1, 1],
  [[-0.13, 0.56, 0.46], [-0.14, 0.06, 0.52], 0.055, 220, 1, 1],
  [[0.13, 0.56, 0.46], [0.14, 0.06, 0.52], 0.055, 220, 1, 1],
]

export const HEAD_RADIUS = 0.115
export const headPivotFor = (seated: boolean): V => (seated ? [0, 1.05, -0.1] : [0, 1.47, 0])

export interface FigurePoints { body: Float32Array; head: Float32Array; headPivot: V }

/** Particle human facing +z. Standing: feet at y=0, about 1.85 tall. Seated: on a seat at y~0.5. */
export function figurePoints(seated: boolean, density: number, rand: Rand): FigurePoints {
  const b: number[] = [], h: number[] = []
  for (const [a, e, r, n, sx, sz] of seated ? SEATED : STANDING) seg(b, a, e, r, n * density, rand, sx, sz)
  for (let i = 0; i < Math.round(520 * density); i++) {
    const t = Math.acos(2 * rand() - 1), p = rand() * Math.PI * 2
    const r = HEAD_RADIUS * (rand() < 0.15 ? rand() : 1)
    h.push(r * Math.sin(t) * Math.cos(p), 0.16 + r * 1.2 * Math.cos(t), r * Math.sin(t) * Math.sin(p))
  }
  return { body: new Float32Array(b), head: new Float32Array(h), headPivot: headPivotFor(seated) }
}
