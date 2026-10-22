import { useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiFailure } from '../net/api'
import type { Chain, Contract } from '../model/types'

const UNDERLYINGS = ['SPY', 'QQQ', 'IWM']
export const OPTIONS_START = '2024-02-01'

interface Props { day: string; onDay: (d: string) => void; onPick: (c: Contract, underlying: string) => void; picked: string | null }

/** Underlying + date -> expirations -> strike ladder (calls left, puts right, ATM highlighted). */
export function OptionsPicker({ day, onDay, onPick, picked }: Props) {
  const [underlying, setUnderlying] = useState('SPY')
  const [exps, setExps] = useState<string[]>([])
  const [exp, setExp] = useState<string | null>(null)
  const [chain, setChain] = useState<Chain | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const early = day < OPTIONS_START
  const ladder = useRef<HTMLTableElement>(null)

  useEffect(() => {
    setExps([]); setExp(null); setChain(null); setError(null)
    if (early || !underlying) return
    setBusy(true)
    api.expirations(underlying, day)
      .then(r => { setExps(r.expirations); setExp(r.expirations[0] ?? null) })
      .catch((e: ApiFailure) => setError(e.message))
      .finally(() => setBusy(false))
  }, [underlying, day, early])

  useEffect(() => {
    setChain(null)
    if (!exp) return
    setBusy(true)
    api.chain(underlying, exp, day).then(setChain).catch((e: ApiFailure) => setError(e.message)).finally(() => setBusy(false))
  }, [underlying, exp, day])

  const rows = useMemo(() => {
    if (!chain) return []
    const by = new Map<number, { call?: Contract; put?: Contract }>()
    for (const c of chain.contracts) by.set(c.strike, { ...by.get(c.strike), [c.type]: c })
    let strikes = [...by.keys()].sort((a, b) => a - b)
    const close = chain.underlying_close
    if (close != null) {  // keep the ladder readable: 15 strikes either side of the money
      const atm = strikes.reduce((best, s) => (Math.abs(s - close) < Math.abs(best - close) ? s : best), strikes[0])
      const i = strikes.indexOf(atm)
      strikes = strikes.slice(Math.max(0, i - 15), i + 16)
    }
    return strikes.map(s => ({ strike: s, ...by.get(s)! }))
  }, [chain])
  const atm = chain?.underlying_close != null && rows.length
    ? rows.reduce((b, r) => (Math.abs(r.strike - chain.underlying_close!) < Math.abs(b.strike - chain.underlying_close!) ? r : b)).strike
    : null

  // open the ladder centred on the at-the-money strike
  useEffect(() => {
    const t = ladder.current, row = t?.querySelector<HTMLTableRowElement>('tr.atm')
    if (t && row) t.scrollTop = row.offsetTop - t.clientHeight / 2
  }, [rows, atm])

  const cell = (c: Contract | undefined, u: string) => c
    ? <button className={c.symbol === picked ? 'picked' : ''} onClick={() => onPick(c, u)}>{c.type === 'call' ? 'C' : 'P'}</button>
    : <span className="muted">-</span>

  return (
    <div className="optpicker">
      <div className="formrow">
        <label>Underlying
          <input list="opt-underlyings" value={underlying} onChange={e => setUnderlying(e.target.value.toUpperCase())} size={6} />
          <datalist id="opt-underlyings">{UNDERLYINGS.map(u => <option key={u} value={u} />)}</datalist>
        </label>
        <label>Day <input type="date" value={day} min={OPTIONS_START} onChange={e => onDay(e.target.value)} /></label>
        <label>Expiration
          <select value={exp ?? ''} onChange={e => setExp(e.target.value)} disabled={!exps.length}>
            {exps.map(x => <option key={x} value={x}>{x}</option>)}
          </select>
        </label>
        {busy && <span className="muted">loading…</span>}
      </div>
      {early && <p className="warn">Alpaca options history starts {OPTIONS_START}. Pick a later day.</p>}
      {error && <p className="warn">{error}</p>}
      <p className="muted small">Options bars have no historical bid/ask, so fills priced from them look better than live trading.</p>
      {rows.length > 0 && (
        <table className="ladder" ref={ladder}>
          <thead><tr><th>Call</th><th>Strike</th><th>Put</th></tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.strike} className={r.strike === atm ? 'atm' : ''}>
                <td>{cell(r.call, underlying)}</td><td>{r.strike}{r.strike === atm ? ' ATM' : ''}</td><td>{cell(r.put, underlying)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
