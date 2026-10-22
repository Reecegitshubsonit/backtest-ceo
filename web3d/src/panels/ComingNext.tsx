import type { Asset } from '../model/types'

const WHAT = { scanner: 'Scans for this asset class', strategies: 'Every strategy tried, with P&L, win rate and drawdown' }

export function ComingNext({ computer, asset }: { computer: 'scanner' | 'strategies'; asset: Asset }) {
  return (
    <div className="comingnext">
      <h3>{WHAT[computer]}</h3>
      <p className="muted">Comes next. This tab will hold the {asset === 'etfs' ? 'ETF' : asset} view once strategies exist.</p>
    </div>
  )
}
