// Groups /workspace/backtests/results.json (10 runs) into its 6 strategies.
// A strategy = one rule set from one source; its runs are the markets/settings it was tested on.
import fs from 'node:fs'
export const FAMILIES = [
 { id: 'ema200_adx25_trend', name: 'Grok EMA200 + ADX25 Trend', origin: 'Alpha Insider', runs: ['ai_ema_adx_eth4h', 'ai_ema_adx_btc4h'] },
 { id: 'ema150_adx_trend_tuned', name: 'Grok EMA150 + ADX Trend, source-tuned', origin: 'Alpha Insider', runs: ['ai_ema_adx_eth4h_tuned', 'ai_ema_adx_btc1h_tuned'] },
 { id: 'adaptive_supertrend', name: 'Grok Adaptive SuperTrend Confluence', origin: 'TC Trading Lab', runs: ['supertrend_eth4h', 'supertrend_btc4h'] },
 { id: 'ema9_21_cross', name: 'EMA 9/21 Cross, 2% Stop', origin: 'PineForge / xAI Grok', runs: ['ema9_21_btc1h'] },
 { id: 'first5m_rth_direction', name: 'First 5-min RTH Candle Direction', origin: 'RHerman', runs: ['first5m_nq', 'first5m_qqq'] },
 { id: 'aex_first_hour_vwap', name: 'AEX First-Hour Range + VWAP', origin: 'aexopties Grok Bot', runs: ['aex_first_hour'] },
]
const pick = s => s && { trades: s.trades, win_rate: s.win_rate, profit_factor: s.profit_factor, net_return_pct: s.net_return_pct, max_drawdown_pct: s.max_drawdown_pct, sharpe: s.sharpe, start: s.start, end: s.end }
// Repo copy: defaults to the results.json snapshot the paper runner ships (engine/backtestceo/paper/reference_results.json).
export const DEFAULT_RESULTS = new URL('../../engine/backtestceo/paper/reference_results.json', import.meta.url).pathname
export function loadResults(file = DEFAULT_RESULTS) {
 const doc = JSON.parse(fs.readFileSync(file, 'utf8')), byId = new Map(doc.strategies.map(r => [r.id, r]))
 const seen = new Set(FAMILIES.flatMap(f => f.runs)), extra = doc.strategies.filter(r => !seen.has(r.id))
 if (extra.length) throw Error('results.json has runs not mapped to a strategy: ' + extra.map(r => r.id).join(', '))
 const strategies = FAMILIES.map(f => {
  const runs = f.runs.map(id => byId.get(id)).filter(Boolean), main = runs[0] // the first run is the strategy's primary market
  return {
   strategy: f.id, name: f.name, origin: f.origin, market: main.market, primary_run: main.id, source_url: main.source, tuned: main.tuned,
   stage: 'backtest', // results exist; nothing in results.json says a later stage (validation, risk, CEO) happened
   split_date: main.split_date, stats: pick(main.full), in_sample: pick(main.in_sample), out_of_sample: pick(main.out_of_sample),
   equity: main.equity_curve.map(p => p.equity), equity_from: main.equity_curve[0]?.date, equity_to: main.equity_curve.at(-1)?.date,
   trades: main.last_trades.map(t => ({ entry_time: t.entry_time, exit_time: t.exit_time, side: t.side, entry: t.entry, exit: t.exit, ret: t.ret })),
   runs: runs.map(r => ({ id: r.id, market: r.market, tuned: r.tuned, full: pick(r.full), out_of_sample: pick(r.out_of_sample) })),
  }
 })
 return { generated: doc.generated, costs: doc.costs, data: doc.data, strategies }
}
