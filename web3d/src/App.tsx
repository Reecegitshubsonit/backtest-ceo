import { useEffect, useMemo, useReducer, useState } from 'react'
import { createPortal } from 'react-dom'
import { PANEL_CLOSED, panelReduce } from './model/panel'
import type { Asset } from './model/types'
import { api } from './net/api'
import { ComputerPanel } from './panels/ComputerPanel'
import { ScreenView } from './panels/ScreenView'
import { Scene } from './scene/Scene'
import { Labels } from './scene/labels'

type Engine = { state: 'checking' } | { state: 'up'; keys: boolean } | { state: 'down' }

export default function App() {
  const [panel, dispatch] = useReducer(panelReduce, PANEL_CLOSED)
  const [engine, setEngine] = useState<Engine>({ state: 'checking' })
  const [asset, setAsset] = useState<Asset>('etfs')
  const [resetKey, setResetKey] = useState(0)
  // one DOM node holds the open screen's view; it moves from the 3D screen to the full panel and back, keeping its state
  const host = useMemo(() => { const d = document.createElement('div'); d.className = 'slotfill'; return d }, [])
  useEffect(() => {
    const check = () => api.health().then(h => setEngine({ state: 'up', keys: h.alpaca_keys_present })).catch(() => setEngine({ state: 'down' }))
    check()
    const id = setInterval(check, 15000)
    return () => clearInterval(id)
  }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') dispatch({ type: 'back' }) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const shown = (panel.phase === 'focused' || panel.phase === 'expanded') && panel.screen
  return (
    <div className="app">
      <Scene panel={panel} dispatch={dispatch} host={host} resetKey={resetKey} />
      <Labels hidden={panel.phase !== 'closed'} />
      <header className="hud">
        <h1>BACKTEST CEO</h1>
        <span className={`engine ${engine.state}`}>
          {engine.state === 'checking' ? 'Engine: checking…'
            : engine.state === 'down' ? 'Engine: not running'
            : engine.keys ? 'Engine: connected' : 'Engine: connected, Alpaca keys missing'}
        </span>
      </header>
      {panel.phase === 'closed' && (
        <p className="hint">Drag to spin · scroll to zoom · click any screen <button className="reset" onClick={() => setResetKey(k => k + 1)}>⟲ Reset view</button></p>
      )}
      {panel.phase === 'focused' && <p className="hint">⤢ Expand or double-click the title bar for full screen · Esc back to the room</p>}
      {shown && createPortal(
        <ScreenView id={panel.screen!} asset={asset} onAsset={setAsset} onHeaderDoubleClick={() => dispatch({ type: 'expand' })}
          actions={panel.phase === 'focused'
            ? <>
                <button className="close" onClick={() => dispatch({ type: 'expand' })} aria-label="Expand to full screen">⤢ Expand</button>
                <button onClick={() => dispatch({ type: 'back' })} aria-label="Back to the room">✕</button>
              </>
            : <button className="close" onClick={() => dispatch({ type: 'back' })} aria-label="Back to the screen">✕ Close</button>} />,
        host)}
      <ComputerPanel panel={panel} host={host} />
    </div>
  )
}
