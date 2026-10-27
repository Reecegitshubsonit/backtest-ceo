// CEO decision ledger: everything the agents sent up to the CEO, opened by clicking the CEO hologram.
// A DOM overlay over the room (not a panel); reads ./liveFeed only.
import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { SEATS } from '../config/seats'
import { feed, feedTick, LIVE_URL, subscribe, type Outcome, type Slot } from './liveFeed'

let open = false
const openListeners = new Set<() => void>()
export function setLedgerOpen(v: boolean) { open = v; for (const f of openListeners) f() }
export const isLedgerOpen = () => open
const subscribeOpen = (f: () => void) => { openListeners.add(f); return () => { openListeners.delete(f) } }

const agentName = (slot: Slot) => SEATS.find(s => s.id === slot)?.name ?? slot
const fmt = (iso: string) => { const t = Date.parse(iso); return Number.isFinite(t) ? new Date(t).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : iso }

export function CeoLedger() {
 const isOpen = useSyncExternalStore(subscribeOpen, isLedgerOpen)
 return isOpen ? <LedgerPanel /> : null
}
function LedgerPanel() {
 const tick = useSyncExternalStore(subscribe, feedTick)
 const [agent, setAgent] = useState<'' | Slot>('')
 const [outcome, setOutcome] = useState<'' | Outcome>('')
 const [strategy, setStrategy] = useState('')
 const [q, setQ] = useState('')
 useEffect(() => {
  const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); setLedgerOpen(false) } }
  window.addEventListener('keydown', key, true); return () => window.removeEventListener('keydown', key, true)
 }, [])
 const all = useMemo(() => [...feed.decisions.values()].sort((a, b) => b.time.localeCompare(a.time)), [tick])
 const strategies = useMemo(() => [...new Set([...[...feed.strategies.values()].map(s => s.name), ...all.map(d => d.strategy)])].filter(Boolean).sort(), [all])
 const needle = q.trim().toLowerCase()
 const rows = all.filter(d => (!agent || d.agent === agent) && (!outcome || d.outcome === outcome) && (!strategy || d.strategy === strategy || feed.strategies.get(d.strategy)?.name === strategy)
  && (!needle || `${d.id} ${agentName(d.agent)} ${d.strategy} ${d.reason} ${d.outcome}`.toLowerCase().includes(needle)))
 const count = (o: Outcome) => all.filter(d => d.outcome === o).length
 const src = feed.source
 return <div className="room-ledger" role="dialog" aria-label="CEO decision ledger" onPointerDown={e => e.stopPropagation()} onWheel={e => e.stopPropagation()}>
  <header>
   <div><h2>CEO DECISION LEDGER</h2><span>Everything the agents sent up to the CEO</span></div>
   <span className={`ledger-src ${src}`}>{src === 'demo' ? 'DEMO · SIMULATED DECISIONS' : src === 'live' ? `LIVE · ${LIVE_URL}` : src === 'none' ? `NO LIVE FEED · ${LIVE_URL}` : 'CONNECTING…'}</span>
   <button className="ledger-close" onClick={() => setLedgerOpen(false)} aria-label="Close ledger">✕</button>
  </header>
  <div className="ledger-filters">
   <label>Agent <select value={agent} onChange={e => setAgent(e.target.value as Slot | '')}><option value="">All agents</option>{SEATS.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
   <div className="ledger-outcomes" role="group" aria-label="Outcome">
    {(['', 'approved', 'rejected', 'pending'] as const).map(o => <button key={o || 'all'} className={`${o || 'all'}${outcome === o ? ' on' : ''}`} onClick={() => setOutcome(o)}>{o ? `${o[0].toUpperCase()}${o.slice(1)} ${count(o)}` : `All ${all.length}`}</button>)}
   </div>
   <label>Strategy <select value={strategy} onChange={e => setStrategy(e.target.value)}><option value="">All strategies</option>{strategies.map(s => <option key={s} value={s}>{s}</option>)}</select></label>
   <input type="search" placeholder="Search reason, strategy, agent…" value={q} onChange={e => setQ(e.target.value)} />
  </div>
  <div className="ledger-body">
   {all.length === 0 ? <p className="ledger-empty">{src === 'none' ? `No live feed at ${LIVE_URL}, so there are no decisions to show.` : 'No decisions have been sent to the CEO yet.'} Agents post <code>ceo_decision</code> events to <code>{LIVE_URL}/v1/events</code>.</p>
    : rows.length === 0 ? <p className="ledger-empty">No decisions match these filters.</p>
    : <table><thead><tr><th>Time</th><th>Agent</th><th>Strategy</th><th>Reason</th><th>Outcome</th></tr></thead>
     <tbody>{rows.slice(0, 300).map(d => <tr key={d.id}><td className="t">{fmt(d.time)}</td><td>{agentName(d.agent)}</td><td>{feed.strategies.get(d.strategy)?.name ?? d.strategy}</td><td className="r">{d.reason}</td><td><span className={`ledger-outcome ${d.outcome}`}>{d.outcome.toUpperCase()}</span></td></tr>)}</tbody></table>}
  </div>
  <footer>{rows.length} of {all.length} decisions{rows.length > 300 ? ' · showing newest 300' : ''} · Esc to close</footer>
 </div>
}
