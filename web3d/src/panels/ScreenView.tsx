import type { ReactNode } from 'react'
import { computerById } from '../config/computers'
import { screenById } from '../config/screens3d'
import { SEATS } from '../config/seats'
import { ASSET_TABS, type Asset } from '../model/types'
import { BacktestTab } from './BacktestTab'
import { ComingNext } from './ComingNext'

interface Props { id: string; asset: Asset; onAsset: (a: Asset) => void; actions: ReactNode; onHeaderDoubleClick?: () => void }

/** Title bar and content of one screen; the same view is shown on the screen in 3D and in the full panel. */
export function ScreenView({ id, asset, onAsset, actions, onHeaderDoubleClick }: Props) {
  const screen = screenById(id)
  const seat = screen?.seat ? SEATS.find(x => x.id === screen.seat) : undefined
  const c = screen?.computer ? computerById(screen.computer) : undefined
  const title = c ? c.label : seat ? `${seat.name} · CONSOLE` : `${screen?.kind === 'desk' ? 'DESK SCREEN' : 'SCREEN'} ${screen?.n}`
  return (
    <div className="screenview">
      <header onDoubleClick={onHeaderDoubleClick}>
        <h2>{title}</h2>
        {c && (
          <nav className="tabs" role="tablist">
            {ASSET_TABS.map(t => (
              <button key={t.id} role="tab" aria-selected={asset === t.id} className={asset === t.id ? 'on' : ''} onClick={() => onAsset(t.id)}>{t.label}</button>
            ))}
          </nav>
        )}
        {actions}
      </header>
      <div className={`panelbody${c ? '' : ' comingnext'}`}>
        {c?.id === 'backtests' ? <BacktestTab key={asset} asset={asset} />
          : c ? <ComingNext computer={c.id as 'scanner' | 'strategies'} asset={asset} />
          : seat ? <><h3>{seat.job}</h3><p className="muted">This agent's console. Talking to the agent and setting its rules arrive with the agents piece.</p></>
          : <><h3>Not assigned yet</h3><p className="muted">This screen works and opens; tell Claude what it should show.</p></>}
      </div>
    </div>
  )
}
