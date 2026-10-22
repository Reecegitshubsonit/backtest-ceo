import { useEffect, useReducer, useState } from 'react'
import { PANEL_CLOSED, panelReduce } from './model/panel'
import { api } from './net/api'
import { ComputerPanel } from './panels/ComputerPanel'
import { ImageRoom } from './room/ImageRoom'
import { Scene } from './scene/Scene'

// the picture room is the default; ?room=3d shows the procedural 3D room
const ROOM_3D = new URLSearchParams(window.location.search).get('room') === '3d'

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
      {ROOM_3D ? <Scene panel={panel} dispatch={dispatch} /> : <ImageRoom panel={panel} dispatch={dispatch} />}
      <header className="hud">
        <h1>BACKTEST CEO</h1>
        <span className={`engine ${engine.state}`}>
          {engine.state === 'checking' ? 'Engine: checking…'
            : engine.state === 'down' ? 'Engine: not running'
            : engine.keys ? 'Engine: connected' : 'Engine: connected, Alpaca keys missing'}
        </span>
      </header>
      {panel.phase === 'closed' && <p className="hint">{ROOM_3D ? 'Click a computer behind the CEO · drag to orbit' : 'Click a screen behind the CEO to open it'}</p>}
      <ComputerPanel panel={panel} dispatch={dispatch} />
    </div>
  )
}
