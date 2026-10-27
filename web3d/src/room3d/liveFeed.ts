// The room's one live data source: a separate live-events service (not the engine) that the agents and
// the backtest runner POST to. The room only reads. Three event kinds:
//   agent_activity   {slot, task, state, strategy?, symbol?, progress?, log?, level?}
//   ceo_decision     {id, agent, strategy, reason, outcome: approved|rejected|pending, time}
//   strategy_result  {strategy, name, market, stage, stats, in_sample?, out_of_sample?, equity[], trades[], runs?}
// Read with GET <live>/v1/events?since=<seq> (1 s poll, CORS for localhost:5175); see the v10 report for
// the full service spec. <live> = ?live=<url>, default http://127.0.0.1:8030.
//   ?demo=1  simulated agent activity and CEO decisions, labelled DEMO · SIMULATED everywhere.
//   no service: honest empty states ("NO LIVE FEED"); wall strategies still show the embedded
//   results.json snapshot, which is real backtest output.
import { RESULTS_SNAPSHOT, RESULTS_SNAPSHOT_AT } from './resultsSnapshot'

export const SLOTS = ['scanner', 'strategist', 'backtester', 'auditor', 'regime', 'risk'] as const
export type Slot = typeof SLOTS[number]
export const STAGES = ['scanning', 'strategist', 'backtest', 'validation', 'risk', 'ceo'] as const
export type Stage = typeof STAGES[number]
export const STAGE_LABEL: Record<Stage, string> = { scanning: 'SCAN', strategist: 'STRATEGIST', backtest: 'BACKTEST', validation: 'VALIDATION', risk: 'RISK', ceo: 'CEO' }
export type Outcome = 'approved' | 'rejected' | 'pending'
export type AgentState = 'idle' | 'working' | 'waiting' | 'error'
export interface LogLine { t: string; msg: string; level: 'info' | 'warn' | 'error' }
export interface AgentNow { task: string | null; state: AgentState; strategy: string | null; symbol: string | null; progress: number | null; updated: string | null; log: LogLine[] }
export interface Decision { id: string; agent: Slot; strategy: string; reason: string; outcome: Outcome; time: string }
export interface RunStats { trades: number; win_rate: number; profit_factor: number; net_return_pct: number; max_drawdown_pct: number; sharpe?: number; start?: string; end?: string }
export interface Trade { entry_time: string; exit_time: string; side: 'long' | 'short'; entry: number; exit: number; ret: number }
export interface StrategyResult {
 strategy: string; name: string; origin?: string; market: string; primary_run?: string; source_url?: string; tuned?: boolean
 stage: Stage; source?: string; split_date?: string; stats: RunStats; in_sample?: RunStats | null; out_of_sample?: RunStats | null
 equity: number[]; equity_from?: string; equity_to?: string; trades: Trade[]
 runs?: { id: string; market: string; tuned?: boolean; full: RunStats; out_of_sample?: RunStats | null }[]
}
export type FeedSource = 'connecting' | 'live' | 'none' | 'demo'
type Ev = { kind: string; seq?: number; at?: string } & Record<string, unknown>

const blankAgent = (): AgentNow => ({ task: null, state: 'idle', strategy: null, symbol: null, progress: null, updated: null, log: [] })
export const params = new URLSearchParams(typeof window === 'undefined' ? '' : window.location.search)
export const LIVE_URL = (params.get('live') || 'http://127.0.0.1:8030').replace(/\/$/, '')
export const DEMO = params.get('demo') === '1'

/** Shared store. Every part has a version so canvases redraw (and re-upload) only when their data changed. */
export const feed = {
 source: (DEMO ? 'demo' : 'connecting') as FeedSource, detail: DEMO ? 'DEMO · SIMULATED DATA' : `connecting to ${LIVE_URL}`,
 agents: new Map<Slot, AgentNow>(SLOTS.map(s => [s, blankAgent()])),
 decisions: new Map<string, Decision>(),
 strategies: new Map<string, StrategyResult & { from: 'snapshot' | 'live' | 'demo' }>(RESULTS_SNAPSHOT.map(s => [s.strategy, { ...s, from: 'snapshot' as const }])),
 version: { source: 0, agents: new Map<Slot, number>(SLOTS.map(s => [s, 0])), decisions: 0, strategies: new Map<string, number>() },
 snapshotAt: RESULTS_SNAPSHOT_AT,
}
const listeners = new Set<() => void>()
let tick = 0
/** For React (useSyncExternalStore): a number that changes whenever anything in the store changes. */
export const feedTick = () => tick
export function subscribe(f: () => void) { listeners.add(f); return () => { listeners.delete(f) } }
const changed = () => { tick++; for (const f of listeners) f() }
function setSource(s: FeedSource, detail: string) { if (feed.source !== s || feed.detail !== detail) { feed.source = s; feed.detail = detail; feed.version.source++; changed() } }

const str = (v: unknown) => typeof v === 'string' && v ? v : null
const num = (v: unknown) => typeof v === 'number' && Number.isFinite(v) ? v : null
/** Apply one event. Malformed events are ignored rather than guessed at. */
export function applyEvent(e: Ev, from: 'live' | 'demo' = 'live') {
 const at = str(e.at) ?? new Date().toISOString()
 if (e.kind === 'agent_activity' && SLOTS.includes(e.slot as Slot)) {
  const slot = e.slot as Slot, a = { ...feed.agents.get(slot)! }, p = num(e.progress)
  if (str(e.task)) a.task = str(e.task)
  a.state = (['idle', 'working', 'waiting', 'error'] as const).find(s => s === e.state) ?? 'working'
  if ('strategy' in e) a.strategy = str(e.strategy); if ('symbol' in e) a.symbol = str(e.symbol)
  if (p !== null) a.progress = Math.max(0, Math.min(1, p)); else if ('progress' in e) a.progress = null
  if (str(e.log)) a.log = [{ t: at, msg: str(e.log)!, level: (e.level === 'warn' || e.level === 'error' ? e.level : 'info') as LogLine['level'] }, ...a.log].slice(0, 40)
  a.updated = at; feed.agents.set(slot, a); feed.version.agents.set(slot, feed.version.agents.get(slot)! + 1)
 } else if (e.kind === 'ceo_decision' && str(e.id) && SLOTS.includes(e.agent as Slot) && ['approved', 'rejected', 'pending'].includes(e.outcome as string)) {
  feed.decisions.set(e.id as string, { id: e.id as string, agent: e.agent as Slot, strategy: str(e.strategy) ?? '', reason: str(e.reason) ?? '', outcome: e.outcome as Outcome, time: str(e.time) ?? at })
  feed.version.decisions++
 } else if (e.kind === 'strategy_result' && str(e.strategy) && str(e.name) && e.stats && typeof e.stats === 'object') {
  const s = e as unknown as StrategyResult, prev = feed.strategies.get(s.strategy)
  feed.strategies.set(s.strategy, { ...prev, ...s, stage: STAGES.includes(s.stage) ? s.stage : 'backtest', equity: Array.isArray(s.equity) ? s.equity.filter(v => typeof v === 'number') : [], trades: Array.isArray(s.trades) ? s.trades : [], from })
  feed.version.strategies.set(s.strategy, (feed.version.strategies.get(s.strategy) ?? 0) + 1)
 } else return
 changed()
}
/** Latest CEO decision about a strategy (matched by id or name). */
export function verdictFor(s: StrategyResult): Decision | undefined {
 let best: Decision | undefined
 for (const d of feed.decisions.values()) if ((d.strategy === s.strategy || d.strategy === s.name) && (!best || d.time > best.time)) best = d
 return best
}
export function decisionsBy(slot: Slot) { const c = { approved: 0, rejected: 0, pending: 0 }; for (const d of feed.decisions.values()) if (d.agent === slot) c[d.outcome]++; return c }

// ---- live service: poll /v1/events?since=seq; a new boot id means the service restarted, so start over ----
async function pollLoop(stop: { v: boolean }) {
 let since = 0, boot = ''
 while (!stop.v) {
  let wait = 1000
  try {
   const r = await fetch(`${LIVE_URL}/v1/events?since=${since}`, { headers: { accept: 'application/json' } })
   if (!r.ok) throw Error(`HTTP ${r.status}`)
   const body = await r.json() as { boot: string; seq: number; events: Ev[] }
   if (boot && body.boot !== boot) { since = 0; boot = body.boot; reset(); continue }
   boot = body.boot
   for (const e of body.events) applyEvent(e)
   since = body.seq
   setSource('live', `LIVE · ${LIVE_URL}`)
  } catch {
   setSource('none', `NO LIVE FEED · nothing answering at ${LIVE_URL}`); wait = 5000
  }
  await new Promise(r => setTimeout(r, wait))
 }
}
function reset() {
 for (const s of SLOTS) { feed.agents.set(s, blankAgent()); feed.version.agents.set(s, feed.version.agents.get(s)! + 1) }
 feed.decisions.clear(); feed.version.decisions++
 for (const s of RESULTS_SNAPSHOT) { feed.strategies.set(s.strategy, { ...s, from: 'snapshot' }); feed.version.strategies.set(s.strategy, (feed.version.strategies.get(s.strategy) ?? 0) + 1) }
 for (const k of [...feed.strategies.keys()]) if (!RESULTS_SNAPSHOT.some(s => s.strategy === k)) feed.strategies.delete(k)
 changed()
}

// ---- DEMO: simulated agents working through the real strategies; every surface says DEMO ----
const DEMO_TASKS: Record<Slot, [string, string][]> = {
 scanner: [['Scanning crypto 4h for trend setups', 'BTC/USD'], ['Ranking ETH/USD breakouts by ADX', 'ETH/USD'], ['Screening index opens', 'NQ']],
 strategist: [['Drafting exit rules', ''], ['Writing entry conditions', ''], ['Reviewing auditor notes', '']],
 backtester: [['Backtesting full history 2018-2026', ''], ['Running out-of-sample split', ''], ['Recomputing costs and slippage', '']],
 auditor: [['Validating out-of-sample stability', ''], ['Checking for look-ahead bias', ''], ['Comparing IS vs OOS profit factor', '']],
 regime: [['Labelling trend vs range regimes', 'BTC/USD'], ['Measuring realised volatility', 'ETH/USD'], ['Tagging session regimes', 'QQQ']],
 risk: [['Sizing at fixed fractional risk', ''], ['Stress-testing max drawdown', ''], ['Checking correlation with live book', '']],
}
const DEMO_LOG = ['loaded data window', 'computed indicators', 'step complete', 'wrote interim report', 'flagged an outlier trade', 'cached results', 'sent summary to CEO']
function startDemo() {
 let seed = 20261027, k = 0, n = 0
 const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296 }
 const names = RESULTS_SNAPSHOT.map(s => s.name), iso = () => new Date().toISOString()
 const step = () => {
  const slot = SLOTS[k++ % SLOTS.length], a = feed.agents.get(slot)!, tasks = DEMO_TASKS[slot]
  const newTask = a.progress === null || a.progress >= 1
  const [task, sym] = newTask ? tasks[Math.floor(rand() * tasks.length)] : [a.task ?? '', a.symbol ?? '']
  const strategy = newTask ? names[Math.floor(rand() * names.length)] : a.strategy
  const progress = newTask ? 0.05 : Math.min(1, (a.progress ?? 0) + .08 + rand() * .12)
  applyEvent({ kind: 'agent_activity', at: iso(), slot, task, strategy, symbol: sym || null, progress, state: 'working', log: `${DEMO_LOG[Math.floor(rand() * DEMO_LOG.length)]} · ${Math.round(progress * 100)}%` }, 'demo')
  if (progress >= 1) {
   const outcome = (['approved', 'rejected', 'pending'] as const)[Math.floor(rand() * 3)]
   applyEvent({ kind: 'ceo_decision', id: `demo-${++n}`, agent: slot, strategy: strategy ?? names[0], outcome, time: iso(),
    reason: `DEMO: ${slot} ${outcome === 'approved' ? 'recommends promotion' : outcome === 'rejected' ? 'recommends rejection' : 'requests a decision'} after "${task.toLowerCase()}"` }, 'demo')
  }
 }
 for (let i = 0; i < 90; i++) step() // warm-up so the demo has history
 return window.setInterval(step, 700)
}

let started = false
/** Start the feed once for the page (the room may mount twice in development). */
export function startFeed() {
 if (started) return; started = true
 if (DEMO) { startDemo(); return }
 void pollLoop({ v: false })
}
