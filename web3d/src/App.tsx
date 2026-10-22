import { useEffect, useReducer, useState } from 'react'
import { PANEL_CLOSED, panelReduce } from './model/panel'
import { api } from './net/api'
import { ComputerPanel } from './panels/ComputerPanel'
import { Scene } from './scene/Scene'

type Engine = { state: 'checking' } | { state: 'up'; keys: boolean } | { state: 'down' }

export default function App() {
  const [panel, dispatch] = useReducer(panelReduce, PANEL_CLOSED)
  const [engine, setEngine] = useState<Engine>({ state: 'checking' })
  useEffect(() => {
    const check = () => api.health().then(h => setEngine({ state: 'up', keys: h.alpaca_keys_present })).catch(() => setEngine({ state: 'down' }))
    check()
    const id = setInterval(check, 15000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="app">
      <Scene panel={panel} dispatch={dispatch} />
      <header className="hud">
        <h1>BACKTEST CEO</h1>
        <span className={`engine ${engine.state}`}>
          {engine.state === 'checking' ? 'Engine: checking…'
            : engine.state === 'down' ? 'Engine: not running'
            : engine.keys ? 'Engine: connected' : 'Engine: connected, Alpaca keys missing'}
        </span>
      </header>
      {panel.phase === 'closed' && <p className="hint">Click a computer behind the CEO · drag to orbit</p>}
      <ComputerPanel panel={panel} dispatch={dispatch} />
    </div>
  )
}
