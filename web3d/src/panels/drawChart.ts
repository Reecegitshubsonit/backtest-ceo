import type { Bar, Timeframe } from '../model/types'
import type { Indicator } from '../model/indicators'
import { fullView, priceRange, type ChartView } from '../model/viewport'
import { fmtPrice, fmtTime } from '../model/format'

export const CHART_COLORS = {
  bg: '#050a18', grid: '#13234a', text: '#9fc4ee', up: '#2fd27a', down: '#ff4d6a', cross: '#6cc8ff', tag: '#0b2a55',
}

export interface IndicatorSeries { ind: Indicator; values: (number | null)[] }
export interface DrawOptions { view?: ChartView; tf: Timeframe; cross?: number | null; overlays?: IndicatorSeries[] }

export interface ChartGeometry {
  start: number; span: number; n: number
  padL: number; padR: number; padT: number; padB: number
  plotW: number; plotH: number; volTop: number; volH: number; lo: number; hi: number
  x: (i: number) => number
  y: (v: number) => number
}

/** Price plot on top (about 80 %), volume panel under it, time axis at the bottom, price axis on the right. */
export function chartGeometry(w: number, h: number, bars: Bar[], view: ChartView = fullView()): ChartGeometry {
  const n = bars.length
  const padL = 8, padR = 66, padT = 10, padB = 24
  const full = Math.max(1, h - padT - padB)
  const volH = Math.round(full * 0.18), gap = 6
  const plotH = Math.max(1, full - volH - gap), volTop = padT + plotH + gap
  const plotW = Math.max(1, w - padL - padR)
  const span = Math.max(1, Math.min(view.span, n))
  const start = Math.min(Math.max(0, view.start), Math.max(0, n - span))
  const { lo, hi } = priceRange(bars, { ...view, start, span })
  return {
    start, span, n, padL, padR, padT, padB, plotW, plotH, volTop, volH, lo, hi,
    x: i => padL + ((i - start + 0.5) / span) * plotW,
    y: v => padT + (1 - (v - lo) / (hi - lo)) * plotH,
  }
}

export function drawChart(ctx: CanvasRenderingContext2D, w: number, h: number, bars: Bar[], o: DrawOptions): ChartGeometry {
  ctx.fillStyle = CHART_COLORS.bg
  ctx.fillRect(0, 0, w, h)
  const g = chartGeometry(w, h, bars, o.view)
  ctx.font = '11px system-ui, sans-serif'
  if (g.n === 0) {
    ctx.fillStyle = CHART_COLORS.text; ctx.textAlign = 'center'
    ctx.fillText('no bars loaded', w / 2, h / 2)
    return g
  }
  const slot = g.plotW / g.span
  const bw = Math.max(1, slot * 0.7)
  const i0 = Math.max(0, Math.floor(g.start) - 1), i1 = Math.min(g.n, Math.ceil(g.start + g.span) + 1)

  // grid, price axis, time axis
  ctx.strokeStyle = CHART_COLORS.grid; ctx.fillStyle = CHART_COLORS.text; ctx.lineWidth = 1; ctx.textAlign = 'left'
  for (let k = 0; k <= 5; k++) {
    const v = g.lo + ((g.hi - g.lo) * k) / 5, yy = Math.round(g.y(v)) + 0.5
    ctx.beginPath(); ctx.moveTo(g.padL, yy); ctx.lineTo(w - g.padR, yy); ctx.stroke()
    ctx.fillText(fmtPrice(v), w - g.padR + 6, yy + 4)
  }
  ctx.textAlign = 'center'
  const every = Math.max(1, Math.ceil(84 / slot))
  for (let i = i0; i < i1; i++) {
    if (i % every !== 0) continue
    const xx = Math.round(g.x(i)) + 0.5
    if (xx < g.padL || xx > w - g.padR) continue
    ctx.beginPath(); ctx.moveTo(xx, g.padT); ctx.lineTo(xx, g.volTop + g.volH); ctx.stroke()
    ctx.fillText(fmtTime(bars[i].t, o.tf), xx, h - g.padB + 16)
  }

  // volume
  let vmax = 0
  for (let i = i0; i < i1; i++) vmax = Math.max(vmax, bars[i].v)
  for (let i = i0; i < i1; i++) {
    const b = bars[i], vh = vmax ? (b.v / vmax) * g.volH : 0
    ctx.fillStyle = (b.c >= b.o ? CHART_COLORS.up : CHART_COLORS.down) + '66'
    ctx.fillRect(g.x(i) - bw / 2, g.volTop + g.volH - vh, bw, vh)
  }

  // candles and overlay indicators, clipped to the price plot
  ctx.save()
  ctx.beginPath(); ctx.rect(g.padL, g.padT, g.plotW, g.plotH); ctx.clip()
  for (let i = i0; i < i1; i++) {
    const b = bars[i], col = b.c >= b.o ? CHART_COLORS.up : CHART_COLORS.down, xx = g.x(i)
    ctx.strokeStyle = col; ctx.fillStyle = col
    ctx.beginPath(); ctx.moveTo(Math.round(xx) + 0.5, g.y(b.h)); ctx.lineTo(Math.round(xx) + 0.5, g.y(b.l)); ctx.stroke()
    const top = g.y(Math.max(b.o, b.c)), bot = g.y(Math.min(b.o, b.c))
    ctx.fillRect(xx - bw / 2, top, bw, Math.max(1, bot - top))
  }
  for (const s of o.overlays ?? []) {
    if (s.ind.pane !== 'overlay') continue
    ctx.strokeStyle = s.ind.color; ctx.lineWidth = 1.4; ctx.beginPath()
    let on = false
    for (let i = i0; i < i1; i++) {
      const v = s.values[i]
      if (v == null) { on = false; continue }
      if (on) ctx.lineTo(g.x(i), g.y(v)); else { ctx.moveTo(g.x(i), g.y(v)); on = true }
    }
    ctx.stroke()
  }
  ctx.restore()

  // crosshair with a price tag on the axis
  if (o.cross != null && o.cross >= i0 && o.cross < i1) {
    const xx = Math.round(g.x(o.cross)) + 0.5, b = bars[o.cross], yy = Math.round(g.y(b.c)) + 0.5
    ctx.strokeStyle = CHART_COLORS.cross; ctx.setLineDash([4, 4]); ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(xx, g.padT); ctx.lineTo(xx, g.volTop + g.volH); ctx.moveTo(g.padL, yy); ctx.lineTo(w - g.padR, yy); ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = CHART_COLORS.tag; ctx.fillRect(w - g.padR + 1, yy - 9, g.padR - 2, 18)
    ctx.fillStyle = '#ffffff'; ctx.textAlign = 'left'; ctx.fillText(fmtPrice(b.c), w - g.padR + 6, yy + 4)
  }
  return g
}
