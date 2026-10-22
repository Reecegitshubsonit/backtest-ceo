import { useState } from 'react'
import { api, ApiFailure } from '../net/api'
import { lastSession } from '../model/dates'
import { TIMEFRAMES, type Asset, type Bar, type Contract, type Timeframe } from '../model/types'
import { ChartPane } from './ChartPane'
import { OptionsPicker } from './OptionsPicker'

const DEFAULTS: Record<Exclude<Asset, 'options'>, string[]> = {
  stocks: ['AAPL', 'NVDA', 'TSLA'], etfs: ['SPY', 'QQQ', 'IWM'], crypto: ['BTC/USD', 'ETH/USD'],
}

interface Loaded { title: string; tf: Timeframe; bars: Bar[]; companion?: { title: string; bars: Bar[] } }

/** Pick a symbol (or an option contract), a timeframe and dates; load bars from the engine; replay them. */
export function BacktestTab({ asset }: { asset: Asset }) {
  const [symbol, setSymbol] = useState(asset === 'options' ? '' : DEFAULTS[asset][0])
  const [tf, setTf] = useState<Timeframe>(asset === 'crypto' ? '15Min' : '5Min')
  const [start, setStart] = useState(lastSession(new Date()))
  const [end, setEnd] = useState(lastSession(new Date()))
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [underlying, setUnderlying] = useState<string | null>(null)

  const load = async (sym = symbol, u = underlying) => {
    if (!sym) return
    setBusy(true); setError(null)
    try {
      const main = await api.bars(asset, sym, tf, start, end)
      const companion = asset === 'options' && u
        ? await api.bars('etfs', u, tf, start, end).then(r => ({ title: r.symbol, bars: r.bars })).catch(() => undefined)
        : undefined
      setLoaded({ title: main.symbol, tf, bars: main.bars, companion })
    } catch (e) {
      setError((e as ApiFailure).message); setLoaded(null)
    } finally { setBusy(false) }
  }

  const pickContract = (c: Contract, u: string) => {
    setSymbol(c.symbol); setUnderlying(u)
    void load(c.symbol, u)
  }

  return (
    <div className="backtesttab">
      {asset === 'options' && (
        <OptionsPicker day={start} picked={symbol || null} onPick={pickContract}
          onDay={d => { setStart(d); setEnd(d) }} />
      )}
      <form className="formrow" onSubmit={e => { e.preventDefault(); void load() }}>
        <label>{asset === 'options' ? 'Contract' : 'Symbol'}
          <input list={`syms-${asset}`} value={symbol} size={asset === 'options' ? 22 : 9}
            placeholder={asset === 'options' ? 'SPY261120C00600000' : ''}
            onChange={e => setSymbol(e.target.value.toUpperCase())} />
          {asset !== 'options' && <datalist id={`syms-${asset}`}>{DEFAULTS[asset].map(s => <option key={s} value={s} />)}</datalist>}
        </label>
        <label>Timeframe
          <select value={tf} onChange={e => setTf(e.target.value as Timeframe)}>{TIMEFRAMES.map(t => <option key={t}>{t}</option>)}</select>
        </label>
        <label>From <input type="date" value={start} onChange={e => setStart(e.target.value)} /></label>
        <label>To <input type="date" value={end} onChange={e => setEnd(e.target.value)} /></label>
        <button type="submit" disabled={busy || !symbol}>{busy ? 'Loading…' : 'Load'}</button>
      </form>
      {error && <p className="warn" role="alert">{error}</p>}
      {loaded
        ? <ChartPane title={loaded.title} tf={loaded.tf} bars={loaded.bars} companion={loaded.companion} />
        : !error && <p className="muted">{asset === 'options' ? 'Pick a contract from the ladder, or type one.' : 'Pick a symbol and press Load.'}</p>}
    </div>
  )
}
