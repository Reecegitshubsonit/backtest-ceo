// The wall bank behind the CEO: one screen per strategy, titled with the strategy's name. Each shows
// the strategy tile (stats, equity curve, recent trades), where it is in the pipeline and the CEO's latest
// verdict. Data comes from ./liveFeed: the embedded results.json snapshot, replaced per strategy by live
// strategy_result events. Screens without a strategy say UNASSIGNED; the three computer screens keep their
// computer title. Nothing is invented: a value the data does not have is drawn as "—".
import * as THREE from 'three'
import { screenName, type RoomScreen } from '../config/roomScreens'
import { SEATS } from '../config/seats'
import { feed, STAGES, STAGE_LABEL, verdictFor, type Decision, type RunStats, type Stage, type StrategyResult } from './liveFeed'

/** Strategy screens in assignment order: the bank's centre first, the computer screens (s1, s5, s10) never. */
export const STRATEGY_SCREENS = ['s8', 's9', 's11', 's12', 's7', 's13', 's6', 's14', 's2', 's3', 's17', 's4', 's16', 's15']
const GREEN = '#3ddc84', RED = '#ff5a6a', ORANGE = '#ff8a3d', AMBER = '#f3c74b', MUTED = '#6d86a8', GRID = '#0d1d38'
export const OUTCOME_COLOR = { approved: GREEN, rejected: RED, pending: AMBER } as const

/** Which strategy each wall screen shows: the active paper legs (snapshot order), then live-only paper legs as they arrive.
 *  Family-level events from older runs or a seeded feed (no `family` field: AEX, EMA150, first 5-min...) are not shown. */
export function wallAssignment(): Map<string, string> {
 const out = new Map<string, string>(), ids = [...feed.strategies.keys()].filter(id => feed.strategies.get(id)?.family)
 ids.slice(0, STRATEGY_SCREENS.length).forEach((id, i) => out.set(STRATEGY_SCREENS[i], id))
 return out
}
export const pct = (v: number | null | undefined, d = 1, sign = true) => v == null || !Number.isFinite(v) ? '—' : `${sign && v > 0 ? '+' : ''}${v.toFixed(d)}%`
const fix = (v: number | null | undefined, d = 2) => v == null || !Number.isFinite(v) ? '—' : v.toFixed(d)
const day = (iso?: string) => iso ? iso.slice(0, 10) : '—'
/** The stage a screen shows: the strategy's own stage, or CEO once a decision about it exists. */
export function shownStage(s: StrategyResult, v?: Decision): Stage { return v ? 'ceo' : s.stage }
export const snapshotLabel = () => `SNAPSHOT OF results.json · ${new Date(feed.snapshotAt).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`

/** What a wall screen's pixels depend on; it is redrawn (and its texture re-uploaded) only when this changes. */
export function wallKey(screen: RoomScreen, assign: Map<string, string>) {
 const id = assign.get(screen.id); if (!id) return 'unassigned'
 const s = feed.strategies.get(id)!, v = verdictFor(s)
 return `${id}|${feed.version.strategies.get(id) ?? 0}|${v ? v.id + v.outcome : ''}|${feed.source}`
}
export function wallCanvas(screen: RoomScreen) {
 const aspect = (screen.shape?.outer ?? screen.w) / screen.h, long = 1536
 const canvas = document.createElement('canvas')
 canvas.width = Math.round(aspect >= 1 ? long : long * aspect); canvas.height = Math.round(aspect >= 1 ? long / aspect : long)
 return canvas
}
export function wallTexture(canvas: HTMLCanvasElement) {
 const t = new THREE.CanvasTexture(canvas); t.colorSpace = THREE.NoColorSpace; t.anisotropy = 16; t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter
 return t
}

export function drawWall(canvas: HTMLCanvasElement, screen: RoomScreen, assign: Map<string, string>) {
 const c = canvas.getContext('2d')!, W = canvas.width, H = canvas.height, u = Math.min(W, H) / 100, wide = W / H
 const text = (v: string, x: number, y: number, size: number, color: string, align: CanvasTextAlign = 'left', weight = 400, mono = true, max?: number) => {
  c.textAlign = align; c.fillStyle = color; c.font = `${weight} ${size * u}px ${mono ? 'ui-monospace,monospace' : 'system-ui,sans-serif'}`; c.fillText(v, x, y, max)
 }
 const box = (x: number, y: number, w: number, h: number, label?: string, accent = '#18345e') => {
  c.beginPath(); c.roundRect(x, y, w, h, 1 * u); c.fillStyle = '#0a1830aa'; c.fill(); c.strokeStyle = accent; c.lineWidth = Math.max(1, .25 * u); c.stroke()
  if (label) text(label, x + 1.4 * u, y + 2.8 * u, 2.4, '#8fb4e0', 'left', 600)
  return { x: x + 1.4 * u, y: y + (label ? 5.4 * u : 1.4 * u), w: w - 2.8 * u, h: h - (label ? 6.8 * u : 2.8 * u) }
 }
 const chip = (label: string, color: string, xr: number, y: number, size = 2.8) => {
  c.font = `700 ${size * u}px ui-monospace,monospace`; const w = c.measureText(label).width + 2.6 * u
  c.beginPath(); c.roundRect(xr - w, y - 2.4 * u, w, 4.8 * u, 1 * u); c.fillStyle = color + '30'; c.fill(); c.strokeStyle = color; c.lineWidth = .3 * u; c.stroke()
  text(label, xr - 1.3 * u, y, size, color, 'right', 700); return w
 }
 c.textBaseline = 'middle'; c.fillStyle = '#040a1a'; c.fillRect(0, 0, W, H)
 const id = assign.get(screen.id), s = id ? feed.strategies.get(id) : undefined
 if (!s) {
  // honest placeholder: title strip, an empty grid and what the screen is for
  c.fillStyle = '#0a1830'; c.fillRect(0, 0, W, 9 * u)
  const title = screen.computer ? screenName(screen) : `SCREEN ${screen.n}`
  text(title, 2.5 * u, 4.6 * u, 4, '#cfe6ff', 'left', 600, false)
  c.strokeStyle = GRID; c.lineWidth = Math.max(1, .15 * u)
  for (let x = 0; x < W; x += 8 * u) { c.beginPath(); c.moveTo(x, 9 * u); c.lineTo(x, H); c.stroke() }
  for (let y = 9 * u; y < H; y += 8 * u) { c.beginPath(); c.moveTo(0, y); c.lineTo(W, y); c.stroke() }
  text(screen.computer ? `${screenName(screen)} COMPUTER` : 'UNASSIGNED', W / 2, H / 2 - 3 * u, 6, screen.computer ? '#9fc3ee' : MUTED, 'center', 700, false)
  text(screen.computer ? 'click to open' : 'no strategy on this screen', W / 2, H / 2 + 4 * u, 3, MUTED, 'center', 400, false)
  return
 }
 const v = verdictFor(s), demo = feed.source === 'demo', stage = shownStage(s, v), m = 2.2 * u
 // header: name, origin/market, verdict
 c.fillStyle = '#0a1830'; c.fillRect(0, 0, W, 15 * u)
 const verdict = v ? `CEO: ${v.outcome.toUpperCase()}${demo ? ' · DEMO' : ''}` : 'CEO: NO VERDICT YET'
 const cw = chip(verdict, v ? OUTCOME_COLOR[v.outcome] : MUTED, W - m, 5 * u, 2.8)
 text(s.name, m, 5 * u, 5, '#f2f7ff', 'left', 700, false, W - cw - 3 * m)
 const runs = s.runs?.length ?? 1
 text([s.origin, s.market, runs > 1 ? `${runs} runs` : '', s.tuned ? 'tuned' : ''].filter(Boolean).join(' · '), m, 11.2 * u, 2.5, '#7fa6d6', 'left', 400, true, W * .62)
 const srcLine = s.from === 'snapshot' ? snapshotLabel() : s.from === 'demo' ? 'DEMO · SIMULATED' : `LIVE FEED · ${s.source ?? 'strategy_result'}`
 text(srcLine, W - m, 11.2 * u, 2.3, s.from === 'snapshot' ? '#9fb9dc' : s.from === 'demo' ? ORANGE : GREEN, 'right', 600, true, W * .36)
 // pipeline: scanning → strategist → backtest → validation → risk → CEO decision
 const py = 17 * u, ph = 6 * u, cur = STAGES.indexOf(stage), gap = .8 * u, pw = (W - 2 * m - gap * 5) / 6
 STAGES.forEach((st, i) => {
  const x = m + i * (pw + gap), done = i < cur, now = i === cur, col = now ? (st === 'ceo' && v ? OUTCOME_COLOR[v.outcome] : '#5fd0ff') : done ? '#3d8bff' : '#24406a'
  c.beginPath(); c.roundRect(x, py, pw, ph, .8 * u); c.fillStyle = now ? col + '40' : done ? '#3d8bff22' : '#0a183088'; c.fill(); c.strokeStyle = col; c.lineWidth = .3 * u; c.stroke()
  text((done ? '✓ ' : '') + (st === 'ceo' ? 'CEO' : STAGE_LABEL[st]), x + pw / 2, py + ph / 2, 2.4, now ? '#f2f7ff' : done ? '#9fc3ee' : MUTED, 'center', now ? 700 : 500, true, pw - u)
 })
 // stats
 const st = s.stats, oos = s.out_of_sample, sy = 25 * u, sh = 12 * u
 const stats: [string, string, string][] = [
  ['TRADES', String(st.trades ?? '—'), '#e4f0ff'],
  ['WIN RATE', st.win_rate != null ? st.win_rate.toFixed(1) + '%' : '—', '#e4f0ff'],
  ['PROFIT F.', fix(st.profit_factor), st.profit_factor >= 1 ? GREEN : RED],
  ['NET', pct(st.net_return_pct, Math.abs(st.net_return_pct) >= 1000 ? 0 : 1), st.net_return_pct >= 0 ? GREEN : RED],
  ['MAX DD', pct(st.max_drawdown_pct, 1, false), RED],
  ['OOS PF', fix(oos?.profit_factor), oos ? (oos.profit_factor >= 1 ? GREEN : RED) : MUTED]]
 const sw = (W - 2 * m - gap * 5) / 6
 stats.forEach(([k, val, col], i) => { const z = box(m + i * (sw + gap), sy, sw, sh, k); text(val, z.x, z.y + 2.4 * u, 4.2, col, 'left', 700, true, z.w) })
 // equity curve (multiple of starting equity) + recent trades / runs
 const by = sy + sh + 2 * u, bh = H - by - 7 * u, split = wide > 1.6 ? .62 : .58
 const eq = box(m, by, (W - 2 * m) * split - gap, bh, `EQUITY · ${day(s.equity_from)} → ${day(s.equity_to)}`)
 const e = s.equity
 if (e.length > 1) {
  const lo = Math.min(1, ...e), hi = Math.max(1, ...e), lw = 9 * u, logScale = hi / Math.max(lo, 1e-6) > 8
  const f = (r: number) => logScale ? Math.log(Math.max(r, 1e-6)) : r, L = f(lo), Hh = f(hi)
  const Y = (r: number) => eq.y + eq.h * (1 - (f(r) - L) / Math.max(1e-9, Hh - L)), X = (i: number) => eq.x + i / (e.length - 1) * (eq.w - lw), up = e.at(-1)! >= 1
  c.strokeStyle = GRID; c.lineWidth = .2 * u; for (let i = 0; i <= 4; i++) { const y = eq.y + eq.h * i / 4; c.beginPath(); c.moveTo(eq.x, y); c.lineTo(eq.x + eq.w - lw, y); c.stroke() }
  c.setLineDash([.8 * u, .8 * u]); c.strokeStyle = '#7f9cc4'; c.lineWidth = .2 * u; c.beginPath(); c.moveTo(eq.x, Y(1)); c.lineTo(eq.x + eq.w - lw, Y(1)); c.stroke(); c.setLineDash([])
  const g = c.createLinearGradient(0, eq.y, 0, eq.y + eq.h); g.addColorStop(0, (up ? GREEN : RED) + '55'); g.addColorStop(1, (up ? GREEN : RED) + '05')
  c.beginPath(); e.forEach((r, i) => i ? c.lineTo(X(i), Y(r)) : c.moveTo(X(i), Y(r))); c.lineTo(X(e.length - 1), Y(1)); c.lineTo(X(0), Y(1)); c.closePath(); c.fillStyle = g; c.fill()
  c.beginPath(); e.forEach((r, i) => i ? c.lineTo(X(i), Y(r)) : c.moveTo(X(i), Y(r))); c.strokeStyle = up ? GREEN : RED; c.lineWidth = .45 * u; c.stroke()
  const mk = (r: number) => r >= 10 ? `${r.toFixed(0)}×` : `${r.toFixed(2)}×`
  const marks: [number, string][] = [[Y(hi), mk(hi)], [Y(1), '1.00×'], [Y(lo), mk(lo)], [Y(e.at(-1)!), mk(e.at(-1)!)]]
  marks.forEach(([y, l], i) => { if (marks.slice(0, i).every(([yy]) => Math.abs(yy - y) > 3 * u)) text(l, eq.x + eq.w, Math.min(eq.y + eq.h - u, Math.max(eq.y + u, y)), 2.3, '#9fb9dc', 'right') })
  if (logScale) text('log scale', eq.x + eq.w, eq.y - 2.6 * u, 2.1, MUTED, 'right')
 } else text('no equity curve', eq.x + eq.w / 2, eq.y + eq.h / 2, 3, MUTED, 'center')
 const rx = m + (W - 2 * m) * split + gap, rw = W - m - rx
 const hasRuns = (s.runs?.length ?? 0) > 1, th = hasRuns ? bh * .56 : bh
 const tr = box(rx, by, rw, th - (hasRuns ? gap : 0), 'RECENT TRADES'), rows = Math.max(1, Math.floor(tr.h / (3.6 * u)))
 if (!s.trades.length) text('no trades', tr.x, tr.y + 1.8 * u, 2.6, MUTED)
 s.trades.slice(-rows).reverse().forEach((t, i) => {
  const y = tr.y + 1.8 * u + i * 3.6 * u, r = t.ret * 100
  text(day(t.exit_time).slice(2), tr.x, y, 2.3, MUTED, 'left', 400, true, tr.w * .36)
  text(t.side === 'long' ? 'LONG' : 'SHORT', tr.x + tr.w * .4, y, 2.3, t.side === 'long' ? '#8fd0ff' : '#c9b8ff', 'left', 600)
  text(pct(r, 2), tr.x + tr.w, y, 2.5, r >= 0 ? GREEN : RED, 'right', 700)
 })
 if (hasRuns) {
  const rb = box(rx, by + th, rw, bh - th, 'RUNS · NET · PF · OOS PF'), n = Math.max(1, Math.floor(rb.h / (3.4 * u)))
  s.runs!.slice(0, n).forEach((r, i) => {
   const y = rb.y + 1.6 * u + i * 3.4 * u, f: RunStats = r.full
   text(r.market.replace(/ /g, ''), rb.x, y, 2.2, '#cfe3f7', 'left', 600, true, rb.w * .3)
   text(pct(f.net_return_pct, 0), rb.x + rb.w * .6, y, 2.2, f.net_return_pct >= 0 ? GREEN : RED, 'right', 600)
   text(fix(f.profit_factor), rb.x + rb.w * .8, y, 2.2, '#cfe3f7', 'right')
   text(fix(r.out_of_sample?.profit_factor), rb.x + rb.w, y, 2.2, (r.out_of_sample?.profit_factor ?? 0) >= 1 ? GREEN : RED, 'right')
  })
 }
 // footer: IS / OOS line and the verdict reason
 const fy = H - 3.5 * u, is = s.in_sample
 text(`IS ${pct(is?.net_return_pct, 0)} PF ${fix(is?.profit_factor)} · OOS ${pct(oos?.net_return_pct, 0)} PF ${fix(oos?.profit_factor)}${s.split_date ? ` · split ${day(s.split_date)}` : ''}`, m, fy, 2.3, '#9fb9dc', 'left', 500, true, W * .5)
 text(v ? `${SEATS.find(x => x.id === v.agent)?.name ?? v.agent}: ${v.reason}` : 'awaiting a CEO decision', W - m, fy, 2.3, v ? (demo ? ORANGE : '#cfe3f7') : MUTED, 'right', 400, true, W * .46)
}
