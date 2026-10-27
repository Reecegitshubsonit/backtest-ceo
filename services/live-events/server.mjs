// Backtest CEO live-events service (prototype, box only). Agents and the backtest runner POST events;
// the 3D room reads them. In-memory store + append-only JSONL log; no dependencies.
//
//   node server.mjs [--port 8030] [--log ./events.jsonl] [--seed /workspace/backtests/results.json]
//
// POST /v1/events           one event or an array of events -> {accepted, seq}
// GET  /v1/events?since=N   events with seq > N (compacted)   -> {boot, seq, events}
// GET  /v1/stream           Server-Sent Events, one `data:` line per new event
// GET  /v1/state            materialised state {agents, decisions, strategies} (debugging)
// GET  /v1/health           {ok, boot, seq, counts}
// CORS: http://localhost:5175 and http://127.0.0.1:5175 (add more with --origin). Nothing is sent anywhere.
import http from 'node:http'
import fs from 'node:fs'
import crypto from 'node:crypto'
import { loadResults } from './results.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d }
const PORT = +arg('--port', 8030), LOG = arg('--log', new URL('./events.jsonl', import.meta.url).pathname), SEED = arg('--seed', '')
const ORIGINS = new Set(['http://localhost:5175', 'http://127.0.0.1:5175', ...(arg('--origin', '') ? arg('--origin').split(',') : [])])
const SLOTS = ['scanner', 'strategist', 'backtester', 'auditor', 'regime', 'risk']
const STAGES = ['scanning', 'strategist', 'backtest', 'validation', 'risk', 'ceo']
const OUTCOMES = ['approved', 'rejected', 'pending']
const boot = crypto.randomBytes(4).toString('hex')
let seq = 0
/** Retained events: every ceo_decision (latest per id), the latest strategy_result per strategy, the last 50 agent_activity per slot. */
let events = []
const clients = new Set()

const str = (v, max = 400) => typeof v === 'string' ? v.slice(0, max) : undefined
const num = v => typeof v === 'number' && Number.isFinite(v) ? v : undefined
function validate(e) {
 if (!e || typeof e !== 'object') throw Error('event must be an object')
 const at = str(e.at) && !isNaN(Date.parse(e.at)) ? e.at : new Date().toISOString(), source = str(e.source, 80)
 switch (e.kind) {
  case 'agent_activity': {
   if (!SLOTS.includes(e.slot)) throw Error(`slot must be one of ${SLOTS}`)
   const p = num(e.progress)
   return { kind: e.kind, at, source, slot: e.slot, task: str(e.task, 200), state: ['idle', 'working', 'waiting', 'error'].includes(e.state) ? e.state : 'working',
    strategy: str(e.strategy, 120), symbol: str(e.symbol, 40), progress: p === undefined ? undefined : Math.max(0, Math.min(1, p)),
    log: str(e.log, 300), level: ['info', 'warn', 'error'].includes(e.level) ? e.level : 'info' }
  }
  case 'ceo_decision': {
   if (!str(e.id, 80)) throw Error('id required')
   if (!SLOTS.includes(e.agent)) throw Error(`agent must be one of ${SLOTS}`)
   if (!OUTCOMES.includes(e.outcome)) throw Error(`outcome must be one of ${OUTCOMES}`)
   return { kind: e.kind, at, source, id: e.id, agent: e.agent, strategy: str(e.strategy, 120) ?? '', reason: str(e.reason, 1000) ?? '', outcome: e.outcome, time: str(e.time) ?? at }
  }
  case 'strategy_result': {
   if (!str(e.strategy, 120) || !str(e.name, 160)) throw Error('strategy (id) and name required')
   if (e.stage !== undefined && !STAGES.includes(e.stage)) throw Error(`stage must be one of ${STAGES}`)
   const eq = Array.isArray(e.equity) ? e.equity.map(v => num(typeof v === 'object' && v ? v.equity : v)).filter(v => v !== undefined).slice(-400) : []
   return { ...e, at, source, stage: e.stage ?? 'backtest', equity: eq, trades: Array.isArray(e.trades) ? e.trades.slice(-20) : [] }
  }
  default: throw Error('kind must be agent_activity, ceo_decision or strategy_result')
 }
}
function compact() {
 const keep = [], perSlot = new Map(), seen = new Set()
 for (let i = events.length - 1; i >= 0; i--) {
  const e = events[i]
  if (e.kind === 'agent_activity') { const n = perSlot.get(e.slot) ?? 0; if (n >= 50) continue; perSlot.set(e.slot, n + 1) }
  else { const k = e.kind + ':' + (e.kind === 'ceo_decision' ? e.id : e.strategy); if (seen.has(k)) continue; seen.add(k) }
  keep.push(e)
 }
 events = keep.reverse()
}
function accept(raw, persist = true) {
 const e = { ...validate(raw), seq: ++seq }
 events.push(e); if (events.length % 200 === 0) compact()
 if (persist) fs.appendFileSync(LOG, JSON.stringify(raw) + '\n')
 for (const res of clients) res.write(`id: ${e.seq}\ndata: ${JSON.stringify(e)}\n\n`)
 return e
}
function state() {
 compact()
 const agents = {}, decisions = [], strategies = {}
 for (const e of events) {
  if (e.kind === 'agent_activity') { const a = agents[e.slot] ??= { log: [] }; Object.assign(a, { task: e.task ?? a.task, state: e.state, strategy: e.strategy ?? a.strategy, symbol: e.symbol ?? a.symbol, progress: e.progress ?? a.progress, at: e.at }); if (e.log) a.log.unshift({ t: e.at, msg: e.log, level: e.level }) }
  else if (e.kind === 'ceo_decision') decisions.push(e)
  else strategies[e.strategy] = e
 }
 return { agents, decisions, strategies }
}

// Replay the log so a restart keeps history, then optionally seed the real backtest results.
if (fs.existsSync(LOG)) for (const line of fs.readFileSync(LOG, 'utf8').split('\n')) { if (!line.trim()) continue; try { accept(JSON.parse(line), false) } catch (e) { console.warn('skipped log line:', e.message) } }
if (SEED) { const r = loadResults(SEED); for (const s of r.strategies) accept({ kind: 'strategy_result', ...s, source: `seeded from results.json ${r.generated.slice(0, 16).replace('T', ' ')}` }, false); console.log(`seeded ${r.strategies.length} strategies from ${SEED}`) }
compact()

const send = (req, res, status, body) => {
 const o = req.headers.origin
 res.writeHead(status, { 'content-type': 'application/json', ...(o && ORIGINS.has(o) ? { 'access-control-allow-origin': o, vary: 'Origin' } : {}) })
 res.end(body === undefined ? '' : JSON.stringify(body))
}
http.createServer((req, res) => {
 const u = new URL(req.url, 'http://x'), o = req.headers.origin
 if (req.method === 'OPTIONS') { // preflight for JSON POSTs from the browser
  res.writeHead(204, o && ORIGINS.has(o) ? { 'access-control-allow-origin': o, 'access-control-allow-methods': 'GET,POST,OPTIONS', 'access-control-allow-headers': 'content-type', 'access-control-max-age': '600', vary: 'Origin' } : {}); return res.end()
 }
 if (req.method === 'GET' && u.pathname === '/v1/health') return send(req, res, 200, { ok: true, boot, seq, retained: events.length, stream_clients: clients.size })
 if (req.method === 'GET' && u.pathname === '/v1/events') {
  const since = +(u.searchParams.get('since') ?? 0) || 0, limit = Math.min(2000, +(u.searchParams.get('limit') ?? 1000) || 1000)
  if (since === 0) compact()
  const out = events.filter(e => e.seq > since).slice(0, limit)
  return send(req, res, 200, { boot, seq: out.length ? out.at(-1).seq : seq, head: seq, events: out })
 }
 if (req.method === 'GET' && u.pathname === '/v1/state') return send(req, res, 200, { boot, seq, ...state() })
 if (req.method === 'GET' && u.pathname === '/v1/stream') {
  res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive', ...(o && ORIGINS.has(o) ? { 'access-control-allow-origin': o } : {}) })
  res.write(`retry: 3000\n\n`); clients.add(res); req.on('close', () => clients.delete(res)); return
 }
 if (req.method === 'POST' && u.pathname === '/v1/events') {
  let body = ''; req.on('data', c => { body += c; if (body.length > 2e6) req.destroy() })
  req.on('end', () => {
   try { const raw = JSON.parse(body), list = Array.isArray(raw) ? raw : [raw], done = list.map(e => accept(e)); send(req, res, 202, { accepted: done.length, seq }) }
   catch (e) { send(req, res, 400, { error: e.message }) }
  })
  return
 }
 send(req, res, 404, { error: 'unknown route' })
}).listen(PORT, '127.0.0.1', () => console.log(`live-events on http://127.0.0.1:${PORT} (boot ${boot}, ${events.length} events retained, log ${LOG})`))
