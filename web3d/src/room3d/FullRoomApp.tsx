import { Component, useEffect, useMemo, useReducer, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ROOM_SCREENS, screenName } from '../config/roomScreens'
import { panelReduce, PANEL_CLOSED } from '../model/roomPanel'
import type { Asset } from '../model/types'
import { api } from '../net/api'
import { RoomScreenView } from '../panels/RoomScreenView'
import { Slot } from '../panels/Slot'
import { RoomScene } from './Scene'
import { RoomLabels } from './labels'
import './room.css'

class RoomBoundary extends Component<{children:ReactNode},{failed:boolean}>{
 state={failed:false}
 static getDerivedStateFromError(){return{failed:true}}
 render(){return this.state.failed?<div className="room-error" role="alert"><h2>The 3D room could not load</h2><p>Reload to try again. A browser with WebGL 2 is required.</p><button onClick={()=>location.reload()}>Reload room</button></div>:this.props.children}
}
export function FullRoomApp(){
 const [panel,dispatch]=useReducer(panelReduce,PANEL_CLOSED)
 const [asset,setAsset]=useState<Asset>('etfs'),[resetKey,setResetKey]=useState(0),[menu,setMenu]=useState(false)
 const [ready,setReady]=useState(false)
 const [engine,setEngine]=useState('checking…')
 const host=useMemo(()=>{const d=document.createElement('div');d.className='slotfill';return d},[])
 useEffect(()=>{let alive=true;const check=()=>api.health().then(h=>{if(alive)setEngine(h.alpaca_keys_present?'connected':'connected, Alpaca keys missing')}).catch(()=>{if(alive)setEngine('not running')});check();const id=setInterval(check,15000);return()=>{alive=false;clearInterval(id)}},[])
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){if(menu)setMenu(false);else dispatch({type:'back'})}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[menu])
 const shown=(panel.phase==='focused'||panel.phase==='expanded')&&panel.screen
 return <div className="app full-room">
  <div className="room3d-stage">
   <RoomBoundary><RoomScene panel={panel} dispatch={dispatch} host={host} resetKey={resetKey} onReady={setReady}/></RoomBoundary>
   {!ready&&<div className="room-loading-poster"><img src="/room.jpg" alt=""/><span role="status">Preparing 3D room…</span></div>}
   {ready&&<RoomLabels/>}
  </div>
  <header className="hud"><h1>BACKTEST CEO</h1><span className="engine">Engine: {engine}</span></header>
  {panel.phase==='closed'&&<div className="room-controls"><span>Drag to orbit · scroll toward pointer · right-drag to pan · click a screen</span><button onClick={()=>setResetKey(k=>k+1)}>Reset view</button><button aria-expanded={menu} onClick={()=>setMenu(v=>!v)}>Screens</button></div>}
  {panel.phase==='focused'&&<p className="room-focus-hint">Expand for full screen · Esc returns to the room</p>}
  {menu&&<nav className="room-screen-menu" aria-label="Room screens">
   {ROOM_SCREENS.map(s=><button key={s.id} onClick={()=>{setMenu(false);dispatch({type:'click',id:s.id})}} aria-label={`Open ${screenName(s)} (${s.kind} ${s.n})`}><span>{s.kind==='wall'?'Wall':'Desk'} {s.n}</span>{screenName(s)}</button>)}
  </nav>}
  {shown&&createPortal(<RoomScreenView id={panel.screen!} asset={asset} onAsset={setAsset} onHeaderDoubleClick={()=>dispatch({type:'expand'})}
   actions={panel.phase==='focused'?<><button className="close" onClick={()=>dispatch({type:'expand'})} aria-label="Expand to full screen">Expand</button><button onClick={()=>dispatch({type:'back'})} aria-label="Back to the room">✕</button></>:<button className="close" onClick={()=>dispatch({type:'back'})} aria-label="Back to the screen">✕ Close</button>}/>,host)}
  {panel.phase==='expanded'&&<section className="computerpanel room-expanded" role="dialog" aria-label="Expanded screen"><Slot host={host} className="slotfill"/></section>}
 </div>
}
