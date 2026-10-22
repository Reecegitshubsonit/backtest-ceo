import { useEffect, useState } from 'react'
import type { PanelAction, PanelState } from '../model/panel'
import { ASSET_TABS, type Asset, type ComputerId } from '../model/types'
import { COMPUTERS, computerById } from '../config/computers'
import { isDesk, screenById } from '../config/imageRoom'
import { SEATS } from '../config/seats'
import { BacktestTab } from './BacktestTab'
import { ComingNext } from './ComingNext'

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void }

/** The open computer: asset tabs over the 3D room. Esc or Close flies the camera back. */
export function ComputerPanel({ panel, dispatch }: Props) {
  const [asset, setAsset] = useState<Asset>('etfs')
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') dispatch({ type: 'close' }) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dispatch])
  if (panel.phase !== 'open' || !panel.computer) return null
  const screen = screenById(panel.computer)
  const id = COMPUTERS.some(x => x.id === panel.computer) ? (panel.computer as ComputerId) : screen?.computer
  const seat = screen?.seat ? SEATS.find(x => x.id === screen.seat) : undefined
  const title = seat ? `${seat.name} · CONSOLE` : `${isDesk(panel.computer) ? 'DESK SCREEN' : 'SCREEN'} ${screen?.n}`
  if (!id && seat) return (
    <section className="computerpanel" role="dialog" aria-label={title}>
      <header>
        <h2>{title}</h2>
        <button className="close" onClick={() => dispatch({ type: 'close' })} aria-label="Close console">✕ Close</button>
      </header>
      <div className="panelbody comingnext">
        <h3>{seat.job}</h3>
        <p className="muted">This agent's console. Talking to the agent and setting its rules arrive with the agents piece.</p>
      </div>
    </section>
  )
  if (!id) return (
    <section className="computerpanel" role="dialog" aria-label={title}>
      <header>
        <h2>{title}</h2>
        <button className="close" onClick={() => dispatch({ type: 'close' })} aria-label="Close screen">✕ Close</button>
      </header>
      <div className="panelbody comingnext">
        <h3>Not assigned yet</h3>
        <p className="muted">This screen works and opens; tell Claude what it should show.</p>
      </div>
    </section>
  )
  const c = computerById(id)
  return (
    <section className="computerpanel" role="dialog" aria-label={`${c.label} computer`}>
      <header>
        <h2>{c.label}</h2>
        <nav className="tabs" role="tablist">
          {ASSET_TABS.map(t => (
            <button key={t.id} role="tab" aria-selected={asset === t.id} className={asset === t.id ? 'on' : ''} onClick={() => setAsset(t.id)}>{t.label}</button>
          ))}
        </nav>
        <button className="close" onClick={() => dispatch({ type: 'close' })} aria-label="Close computer">✕ Close</button>
      </header>
      <div className="panelbody">
        {c.id === 'backtests' ? <BacktestTab key={asset} asset={asset} /> : <ComingNext computer={c.id} asset={asset} />}
      </div>
    </section>
  )
}
