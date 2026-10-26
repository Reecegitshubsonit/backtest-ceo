import { useEffect, useReducer, useState } from 'react'
import { PANEL_CLOSED, panelReduce } from './model/panel'
import { api } from './net/api'
import { ComputerPanel } from './panels/ComputerPanel'
import { ImageRoom } from './room/ImageRoom'
import { CeoReview } from './room/CeoReview'
import { FullRoomApp } from './room3d/FullRoomApp'

type Engine = { state: 'checking' } | { state: 'up'; keys: boolean } | { state: 'down' }

export default function App() {
  const params = new URLSearchParams(window.location.search)
  if (params.get('review') === 'ceo') return <CeoReview />
  return params.get('room') === 'image' ? <RoomApp /> : <FullRoomApp />
}

function RoomApp() {
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
      <ImageRoom panel={panel} dispatch={dispatch} />
      <header className="hud">
        <h1>BACKTEST CEO</h1>
        <span className={`engine ${engine.state}`}>
          {engine.state === 'checking' ? 'Engine: checking…'
            : engine.state === 'down' ? 'Engine: not running'
            : engine.keys ? 'Engine: connected' : 'Engine: connected, Alpaca keys missing'}
        </span>
      </header>
      {panel.phase === 'closed' && <p className="hint">Click a screen on the wall to open it</p>}
      <ComputerPanel panel={panel} dispatch={dispatch} />
    </div>
  )
}
