// One strategy per agent desk region on the ring computer. The room only reads; nothing here starts,
// stops or changes a strategy.
//
// Data source, in order:
//  1. ?demo=1       clearly labelled DEMO: simulated strategies, every tile says "DEMO · SIMULATED".
//  2. the engine    GET /api/agents/live (contract below). Polled every 2 s while it answers.
//  3. nothing       the engine has no such route yet (404) or is down: honest empty states only.
//
// Engine contract (not implemented in the engine yet):
// GET /api/agents/live -> 200
// { "at": "2026-10-27T21:30:00Z",
//   "slots": [ {
//     "slot": "scanner" | "strategist" | "backtester" | "auditor" | "regime" | "risk",
//     "strategy": { "id": "mnq_orb_v1", "name": "MNQ Opening Range Breakout", "version": "1.0.0",
//                   "market": "MNQ", "timeframe": "5Min" } | null,
//     "status": "idle" | "researching" | "coding" | "backtesting" | "live_paper" | "error",
//     "progress": 0..1 | null,               // e.g. share of the backtest window replayed
//     "equity": [ { "t": ISO, "r": -1.5 } ], // cumulative net R, oldest first, at most 500 points
//     "trades": [ { "t": ISO exit time, "side": "long"|"short", "r": 1.8, "pnl_usd": 360 } ], // newest first, <= 20
//     "log": [ { "t": ISO, "level": "info"|"warn"|"error", "msg": "..." } ],               // newest first, <= 20
//     "stats": { "trades": 152, "wr": 0.42, "pf": 1.31, "net_r": 24.5, "max_dd_r": -8.2 } | null,
//     "updated": ISO                          // when this slot last changed
//   } ] }
// Slots missing from the answer are shown as idle. 404 means "route not available"; the room then
// re-checks every 30 s.

export type AgentStatus = 'idle' | 'researching' | 'coding' | 'backtesting' | 'live_paper' | 'error'
export interface LiveTrade { t: string; side: 'long' | 'short'; r: number; pnlUsd?: number }
export interface LiveLog { t: string; level: 'info' | 'warn' | 'error'; msg: string }
export interface LiveStats { trades: number; wr: number | null; pf: number | null; netR: number; maxDD: number }
export interface LiveStrategy { id: string; name: string; version?: string; market?: string; timeframe?: string }
export interface AgentLive {
 slot: string; strategy: LiveStrategy | null; status: AgentStatus; progress: number | null
 equity: number[]; trades: LiveTrade[]; log: LiveLog[]; stats: LiveStats | null; updated: number | null
}
export type LiveSource = 'checking' | 'engine' | 'unavailable' | 'down' | 'demo'

/** Desk region -> agent slot, with the strategy assigned by default (none until the engine says so). */
export const STRATEGY_SLOTS: { desk: string; slot: string; strategy: LiveStrategy | null }[] = [
 { desk: 'd-scanner', slot: 'scanner', strategy: null },
 { desk: 'd-strategist', slot: 'strategist', strategy: null },
 { desk: 'd-backtester', slot: 'backtester', strategy: null },
 { desk: 'd-auditor', slot: 'auditor', strategy: null },
 { desk: 'd-regime', slot: 'regime', strategy: null },
 { desk: 'd-risk', slot: 'risk', strategy: null },
]
export const STATUS_LABEL: Record<AgentStatus, string> = {
 idle: 'IDLE', researching: 'RESEARCHING', coding: 'CODING', backtesting: 'BACKTESTING', live_paper: 'LIVE PAPER', error: 'ERROR',
}

const empty = (slot: string): AgentLive => ({
 slot, strategy: STRATEGY_SLOTS.find(s => s.slot === slot)?.strategy ?? null, status: 'idle', progress: null,
 equity: [], trades: [], log: [], stats: null, updated: null,
})
/** Shared live state. `version` bumps per slot only when that slot's data really changed. */
export const liveAgents = {
 source: 'checking' as LiveSource, detail: '', checked: 0,
 slots: new Map<string, AgentLive>(STRATEGY_SLOTS.map(s => [s.slot, empty(s.slot)])),
 version: new Map<string, number>(STRATEGY_SLOTS.map(s => [s.slot, 0])),
 sourceVersion: 0,
}
export const isDemo = () => typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('demo') === '1'

const num = (v: unknown): number | null => typeof v === 'number' && Number.isFinite(v) ? v : null
const STATUSES = Object.keys(STATUS_LABEL) as AgentStatus[]
/** Validate one slot of the engine answer; anything malformed is dropped rather than guessed. */
export function parseSlot(raw: unknown): AgentLive | null {
 if (!raw || typeof raw !== 'object') return null
 const o = raw as Record<string, unknown>, slot = String(o.slot ?? '')
 if (!STRATEGY_SLOTS.some(s => s.slot === slot)) return null
 const st = o.strategy as Record<string, unknown> | null | undefined
 const strategy = st && typeof st.name === 'string' ? { id: String(st.id ?? st.name), name: st.name, version: st.version as string | undefined, market: st.market as string | undefined, timeframe: st.timeframe as string | undefined } : null
 const status = STATUSES.includes(o.status as AgentStatus) ? o.status as AgentStatus : 'idle'
 const eq = Array.isArray(o.equity) ? o.equity.map(p => num(typeof p === 'object' && p ? (p as { r?: unknown }).r : p)).filter((v): v is number => v !== null).slice(-500) : []
 const trades = Array.isArray(o.trades) ? o.trades.flatMap(t => { const x = t as Record<string, unknown>, r = num(x?.r); return r === null ? [] : [{ t: String(x.t ?? ''), side: x.side === 'short' ? 'short' as const : 'long' as const, r, pnlUsd: num(x.pnl_usd ?? x.pnlUsd) ?? undefined }] }).slice(0, 20) : []
 const log = Array.isArray(o.log) ? o.log.flatMap(l => { const x = l as Record<string, unknown>; return typeof x?.msg === 'string' ? [{ t: String(x.t ?? ''), level: (x.level === 'warn' || x.level === 'error' ? x.level : 'info') as LiveLog['level'], msg: x.msg }] : [] }).slice(0, 20) : []
 const s = o.stats as Record<string, unknown> | null | undefined
 const stats = s && num(s.trades) !== null ? { trades: num(s.trades)!, wr: num(s.wr), pf: num(s.pf), netR: num(s.net_r ?? s.netR) ?? 0, maxDD: num(s.max_dd_r ?? s.maxDD) ?? 0 } : null
 const updated = typeof o.updated === 'string' ? Date.parse(o.updated) || null : null
 return { slot, strategy: strategy ?? empty(slot).strategy, status, progress: num(o.progress), equity: eq, trades, log, stats, updated }
}

function apply(next: Map<string, AgentLive>) {
 for (const { slot } of STRATEGY_SLOTS) {
  const v = next.get(slot) ?? empty(slot), prev = liveAgents.slots.get(slot)
  if (JSON.stringify(prev) !== JSON.stringify(v)) { liveAgents.slots.set(slot, v); liveAgents.version.set(slot, (liveAgents.version.get(slot) ?? 0) + 1) }
 }
}
function setSource(s: LiveSource, detail: string) {
 if (liveAgents.source !== s || liveAgents.detail !== detail) { liveAgents.source = s; liveAgents.detail = detail; liveAgents.sourceVersion++ }
 liveAgents.checked = Date.now()
}

async function pollEngine(): Promise<number> {
 let r: Response
 try { r = await fetch('/api/agents/live', { headers: { accept: 'application/json' } }) }
 catch { setSource('down', 'engine unreachable'); return 10000 }
 if (r.status === 404) { setSource('unavailable', 'engine has no /api/agents/live route yet'); apply(new Map()); return 30000 }
 const body = await r.json().catch(() => null) as { slots?: unknown[] } | null
 if (!r.ok || !body || !Array.isArray(body.slots)) { setSource(r.status >= 500 ? 'down' : 'unavailable', `/api/agents/live answered ${r.status}`); return 10000 }
 apply(new Map(body.slots.map(parseSlot).filter((v): v is AgentLive => !!v).map(v => [v.slot, v])))
 setSource('engine', 'live from engine'); return 2000
}

// ---- DEMO: simulated strategies for previewing the look. Never shown without ?demo=1. ----
const DEMO: [LiveStrategy, AgentStatus][] = [
 [{ id: 'demo_orb', name: 'Opening Range Breakout', version: '1.0.0', market: 'MNQ', timeframe: '5Min' }, 'backtesting'],
 [{ id: 'demo_vwap', name: 'Overnight VWAP Stretch Fade', version: '1.0.1', market: 'MNQ', timeframe: '1Min' }, 'coding'],
 [{ id: 'demo_vol', name: 'Realized-Vol Compression Breakout', version: '1.0.0', market: 'MES', timeframe: '15Min' }, 'backtesting'],
 [{ id: 'demo_nib', name: 'Mid-Morning Nested Inside Bar', version: '1.0.0', market: 'MNQ', timeframe: '5Min' }, 'live_paper'],
 [{ id: 'demo_ovr', name: 'Overnight Range Carryover', version: '1.0.0', market: 'MYM', timeframe: '15Min' }, 'researching'],
 [{ id: 'demo_mdr', name: 'Multi-Day Range Contraction', version: '1.0.0', market: 'MGC', timeframe: '1Hour' }, 'backtesting'],
]
const DEMO_LOG: Record<AgentStatus, string[]> = {
 researching: ['reading prior sessions', 'scoring idea against research memory', 'drafting entry rules', 'checking overlap with library'],
 coding: ['writing signal function', 'unit test passed: entries', 'compiling strategy', 'lint ok · building'],
 backtesting: ['replaying session', 'filled entry', 'stop moved to break-even', 'target hit', 'session closed'],
 live_paper: ['paper order working', 'paper fill', 'position flat', 'risk check ok'],
 idle: [], error: [],
}
function demoTick(state: { k: number; rand: () => number }) {
 const now = Date.now(), iso = (t: number) => new Date(t).toISOString(), next = new Map<string, AgentLive>()
 STRATEGY_SLOTS.forEach(({ slot }, i) => {
  const [strategy, status] = DEMO[i], prev = liveAgents.slots.get(slot)!, rand = state.rand
  const base: AgentLive = prev.strategy?.id === strategy.id ? structuredClone(prev) : { ...empty(slot), strategy, status, progress: 0, log: [] }
  if ((state.k + i) % 3 !== 0) { next.set(slot, base); return } // each slot changes every third tick, staggered
  const trades = status === 'backtesting' || status === 'live_paper'
  if (trades) {
   const r = Math.round(((rand() < .44 ? 1.6 + rand() * 1.2 : -1) + (rand() - .5) * .2) * 100) / 100
   base.trades = [{ t: iso(now), side: (rand() < .5 ? 'long' : 'short') as LiveTrade['side'], r, pnlUsd: Math.round(r * 200) }, ...base.trades].slice(0, 20)
   base.equity = [...(base.equity.length ? base.equity : [0]), (base.equity.at(-1) ?? 0) + r].slice(-500)
   const rs = base.equity.slice(1).map((v, j) => v - base.equity[j]), wins = rs.filter(v => v > 0), loss = rs.filter(v => v <= 0)
   let peak = 0, dd = 0; for (const v of base.equity) { peak = Math.max(peak, v); dd = Math.min(dd, v - peak) }
   base.stats = { trades: rs.length, wr: rs.length ? wins.length / rs.length : null, pf: loss.length ? wins.reduce((a, b) => a + b, 0) / -loss.reduce((a, b) => a + b, 0) : null, netR: base.equity.at(-1)!, maxDD: dd }
  }
  base.progress = status === 'idle' ? null : Math.min(1, (base.progress ?? 0) + .01 + rand() * .02)
  const lines = DEMO_LOG[status]; const msg = lines[Math.floor(rand() * lines.length)] + (trades && base.trades[0] ? ` · ${base.trades[0].side} ${base.trades[0].r >= 0 ? '+' : ''}${base.trades[0].r.toFixed(2)}R` : '')
  base.log = [{ t: iso(now), level: 'info' as const, msg }, ...base.log].slice(0, 20); base.updated = now
  next.set(slot, base)
 })
 state.k++; apply(next)
}
/** Warm the demo up with history so its curves are not empty on first sight. */
function demoSeed(state: { k: number; rand: () => number }) { for (let i = 0; i < 90; i++) demoTick(state) }

/** Start polling (or the demo). Returns a stop function. Safe to call once per mounted room. */
export function startLiveAgents(): () => void {
 let stop = false, timer = 0
 if (isDemo()) {
  let seed = 20261027; const state = { k: 0, rand: () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296 } }
  setSource('demo', 'DEMO · SIMULATED DATA'); demoSeed(state)
  timer = window.setInterval(() => demoTick(state), 1200)
  return () => clearInterval(timer)
 }
 const loop = async () => { const wait = await pollEngine(); if (!stop) timer = window.setTimeout(loop, wait) }
 void loop()
 return () => { stop = true; clearTimeout(timer) }
}
