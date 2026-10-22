import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Bar, Timeframe } from '../model/types'
import { fullView, panPrice, panTime, zoomPrice, zoomTime, type ChartView as View } from '../model/viewport'
import { fmtPrice, fmtStamp } from '../model/format'
import { INDICATORS } from '../model/indicators'
import { drawChart, type ChartGeometry } from './drawChart'

interface Props { bars: Bar[]; tf: Timeframe; title: string; height?: number }

/** Candles and volume. Wheel = zoom time, Shift+wheel = zoom price, drag = pan, double-click = reset. */
export function ChartView({ bars, tf, title, height = 420 }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const geo = useRef<ChartGeometry | null>(null)
  const drag = useRef<{ x: number; y: number } | null>(null)
  const [view, setView] = useState<View>(fullView())
  const [hover, setHover] = useState<number | null>(null)
  const n = bars.length
  const prevN = useRef(n)
  const overlays = useMemo(() => INDICATORS.map(ind => ({ ind, values: ind.compute(bars) })), [bars])

  // while replaying, keep the newest bar in view if the view was already at the right edge
  useEffect(() => {
    setView(v => {
      if (v.span === Infinity || n === prevN.current) return v
      const atEdge = v.start + Math.min(v.span, prevN.current) >= prevN.current - 0.5
      return atEdge ? { ...v, start: Math.max(0, n - Math.min(v.span, n)) } : v
    })
    prevN.current = n
  }, [n])

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const paint = () => {
      const w = cv.clientWidth, dpr = Math.min(3, window.devicePixelRatio || 1)
      if (!w) return
      cv.width = Math.round(w * dpr); cv.height = Math.round(height * dpr)
      const ctx = cv.getContext('2d')!
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      geo.current = drawChart(ctx, w, height, bars, { view, tf, cross: hover, overlays })
    }
    paint()
    const ro = new ResizeObserver(paint)
    ro.observe(cv)
    return () => ro.disconnect()
  }, [bars, view, hover, height, tf, overlays])

  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const g = geo.current, factor = Math.exp(-e.deltaY * 0.0018)
      if (e.shiftKey) { setView(v => zoomPrice(v, factor)); return }
      const rect = cv.getBoundingClientRect()
      const anchor = g ? Math.min(1, Math.max(0, (e.clientX - rect.left - g.padL) / g.plotW)) : 0.5
      setView(v => zoomTime(v, n, factor, anchor))
    }
    cv.addEventListener('wheel', onWheel, { passive: false })
    return () => cv.removeEventListener('wheel', onWheel)
  }, [n])

  const idxAt = (clientX: number): number | null => {
    const g = geo.current, cv = ref.current
    if (!g || !cv || !g.n) return null
    const rect = cv.getBoundingClientRect()
    return Math.min(g.n - 1, Math.max(0, Math.round(g.start + ((clientX - rect.left - g.padL) / g.plotW) * g.span - 0.5)))
  }
  const timeZoom = useCallback((f: number) => setView(v => zoomTime(v, n, f, 0.5)), [n])
  const onKey = (e: React.KeyboardEvent) => {
    const step = geo.current ? Math.max(1, geo.current.span / 10) : 5
    const fn = ({ '+': () => timeZoom(1.4), '=': () => timeZoom(1.4), '-': () => timeZoom(1 / 1.4), '0': () => setView(fullView()),
      ArrowLeft: () => setView(v => panTime(v, n, -step)), ArrowRight: () => setView(v => panTime(v, n, step)),
      ArrowUp: () => setView(v => zoomPrice(v, 1.3)), ArrowDown: () => setView(v => zoomPrice(v, 1 / 1.3)) } as Record<string, () => void>)[e.key]
    if (fn) { e.preventDefault(); fn() }
  }

  const b = hover != null ? bars[hover] : bars[n - 1]
  const first = bars[0]
  const change = b && first ? ((b.c - first.o) / first.o) * 100 : null
  return (
    <figure className="chart">
      <figcaption className="charthead">
        <b>{title}</b>
        {b && <span> · {fmtPrice(b.c)}</span>}
        {change != null && <span className={change >= 0 ? 'pos' : 'neg'}> {change >= 0 ? '+' : ''}{change.toFixed(2)}%</span>}
        <span className="muted"> · {tf} · {n} bars</span>
        <span className="tools">
          <button onClick={() => timeZoom(1.5)} aria-label="Zoom in time">+</button>
          <button onClick={() => timeZoom(1 / 1.5)} aria-label="Zoom out time">−</button>
          <button onClick={() => setView(fullView())}>Reset</button>
        </span>
      </figcaption>
      <canvas ref={ref} tabIndex={0} role="img" className="chartcanvas" style={{ height }}
        aria-label={`${title} ${tf} chart, ${n} bars. Plus and minus zoom, arrow keys pan, 0 resets.`}
        onPointerDown={e => { drag.current = { x: e.clientX, y: e.clientY }; (e.target as HTMLElement).setPointerCapture(e.pointerId) }}
        onPointerMove={e => {
          const g = geo.current
          if (drag.current && g) {
            const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y
            drag.current = { x: e.clientX, y: e.clientY }
            setView(v => panPrice(panTime(v, n, -dx / (g.plotW / g.span)), dy / g.plotH))
          } else setHover(idxAt(e.clientX))
        }}
        onPointerUp={() => { drag.current = null }}
        onPointerLeave={() => { drag.current = null; setHover(null) }}
        onDoubleClick={() => setView(fullView())} onKeyDown={onKey} />
      <div className="readout">
        {b ? <>
          <b>{fmtStamp(b.t)}</b> O {fmtPrice(b.o)} H {fmtPrice(b.h)} L {fmtPrice(b.l)} C <b>{fmtPrice(b.c)}</b> V {Math.round(b.v).toLocaleString('en-US')}
        </> : <span className="muted">no bars</span>}
      </div>
    </figure>
  )
}
