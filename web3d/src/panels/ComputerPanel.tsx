import { useEffect, useState } from 'react'
import type { PanelAction, PanelState } from '../model/panel'
import { ASSET_TABS, type Asset } from '../model/types'
import { computerById } from '../config/computers'
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
  const c = computerById(panel.computer)
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
