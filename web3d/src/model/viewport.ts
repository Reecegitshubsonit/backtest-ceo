import type { Bar } from './types'

export const MIN_SPAN = 10
const MAX_PRICE_ZOOM = 20

/** Visible slice of a chart: start index and span in bars (Infinity = all), plus a vertical zoom and shift. */
export interface ChartView { start: number; span: number; priceZoom: number; priceShift: number }

export const fullView = (): ChartView => ({ start: 0, span: Infinity, priceZoom: 1, priceShift: 0 })

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x))

/** Zoom the time axis by `factor` (>1 zooms in) keeping the bar under `anchor` (0..1 across the chart) fixed. */
export function zoomTime(v: ChartView, n: number, factor: number, anchor: number): ChartView {
  const span0 = Math.min(v.span, n)
  const span = Math.min(n, Math.max(MIN_SPAN, span0 / factor))
  const idx = v.start + anchor * span0
  return { ...v, span, start: clamp(idx - anchor * span, 0, Math.max(0, n - span)) }
}

export function panTime(v: ChartView, n: number, deltaBars: number): ChartView {
  const span = Math.min(v.span, n)
  return { ...v, span, start: clamp(v.start + deltaBars, 0, Math.max(0, n - span)) }
}

export function zoomPrice(v: ChartView, factor: number): ChartView {
  const priceZoom = clamp(v.priceZoom * factor, 1, MAX_PRICE_ZOOM)
  return { ...v, priceZoom, priceShift: priceZoom === 1 ? 0 : v.priceShift }
}

/** Shift the price axis by a fraction of the visible price range. */
export function panPrice(v: ChartView, fraction: number): ChartView {
  return { ...v, priceShift: v.priceZoom === 1 ? 0 : v.priceShift + fraction }
}

export function visibleRange(bars: Bar[], v: ChartView): { i0: number; i1: number } {
  const n = bars.length
  const span = Math.min(v.span, n)
  const i0 = clamp(Math.floor(v.start), 0, Math.max(0, n - 1))
  return { i0, i1: Math.min(n, Math.ceil(v.start + span)) }
}

export function priceRange(bars: Bar[], v: ChartView): { lo: number; hi: number } {
  const { i0, i1 } = visibleRange(bars, v)
  let lo = Infinity, hi = -Infinity
  for (let i = i0; i < i1; i++) { if (bars[i].l < lo) lo = bars[i].l; if (bars[i].h > hi) hi = bars[i].h }
  if (!Number.isFinite(lo)) return { lo: 0, hi: 1 }
  const pad = (hi - lo) * 0.06 || Math.max(0.01, hi * 0.001)
  lo -= pad; hi += pad
  const range = (hi - lo) / v.priceZoom
  const center = (hi + lo) / 2 + v.priceShift * range
  return { lo: center - range / 2, hi: center + range / 2 }
}
