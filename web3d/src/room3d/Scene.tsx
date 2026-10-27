import { Suspense, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls, useGLTF, useTexture } from '@react-three/drei'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import * as THREE from 'three'
import type { OrbitControls as Controls } from 'three-stdlib'
import { acceleratedRaycast, MeshBVH } from 'three-mesh-bvh'
import { ROOM_SCREENS, screenById, screenName, type RoomScreen } from '../config/roomScreens'
import type { PanelAction, PanelState } from '../model/roomPanel'
import { deskScreenAt } from '../model/deskPicking'
import { Slot } from '../panels/Slot'
import { HOME, INSPECT, LIMITS, flightDistance, inRoom, inspectDistance, inspectPose, readableUp, screenFraction, ZOOM } from './camera'
import { SEATS } from '../config/seats'
import { api } from '../net/api'
import { CameraRig } from './CameraRig'
import { roomMaterial } from './material'
import { Beam } from './Beam'
import { liveAgents, startLiveAgents, STATUS_LABEL, type AgentStatus } from './strategies'
import { LabelProjector, setHovered, getHovered, getInspecting, setInspecting } from './labels'

THREE.Mesh.prototype.raycast=acceleratedRaycast
type Props={panel:PanelState;dispatch:(a:PanelAction)=>void;host:HTMLElement;resetKey:number;onReady:(ready:boolean)=>void}
type Geo=THREE.BufferGeometry&{boundsTree?:MeshBVH}

// ---------------------------------------------------------------------------------------------
// Display graphics. Each canvas has the physical aspect of its monitor (the old shared 16:9 chart
// was stretched up to 4.6x on the tall s8/s9 panels), a title bar, axes and readable labels.
function rng(seed:number){return()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}}
const PURPLE='#9b7bff',BLUE='#3d8bff',CYAN='#5fd0ff',TEXT='#86a9d6',GRID='#0d1d38'
function displayTexture(screen:RoomScreen,index:number){
 const aspect=(screen.shape?.outer??screen.w)/screen.h,long=1536
 const W=Math.round(aspect>=1?long:long*aspect),H=Math.round(aspect>=1?long/aspect:long)
 const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H
 const c=canvas.getContext('2d')!,rand=rng(index*977+31),u=Math.min(W,H)/100
 c.fillStyle='#040a1a';c.fillRect(0,0,W,H)
 const title=screen.seat?SEATS.find(x=>x.id===screen.seat)!.name+' · CONSOLE':screenName(screen)
 c.fillStyle='#0a1830';c.fillRect(0,0,W,7*u);c.fillStyle='#cfe6ff';c.font=`600 ${3.6*u}px system-ui,sans-serif`;c.textBaseline='middle';c.fillText(title,2.5*u,3.6*u)
 c.fillStyle=TEXT;c.font=`${2.4*u}px ui-monospace,monospace`;c.textAlign='right';c.fillText(['SPY','QQQ','BTC/USD','IWM','ETH/USD','AAPL','NVDA','TLT'][index%8]+'  '+['1Min','5Min','15Min','1Hour'][index%4],W-2.5*u,3.6*u);c.textAlign='left'
 const panel=(x:number,y:number,w:number,h:number,label:string)=>{c.strokeStyle='#18345e';c.lineWidth=Math.max(1,.25*u);c.strokeRect(x,y,w,h);c.fillStyle=TEXT;c.font=`${2.1*u}px ui-monospace,monospace`;c.fillText(label,x+1.2*u,y+2.2*u)
  c.strokeStyle=GRID;c.lineWidth=Math.max(1,.15*u);for(let i=1;i<6;i++){const yy=y+h*i/6;c.beginPath();c.moveTo(x,yy);c.lineTo(x+w,yy);c.stroke()}for(let i=1;i<10;i++){const xx=x+w*i/10;c.beginPath();c.moveTo(xx,y+4*u);c.lineTo(xx,y+h);c.stroke()}}
 const candles=(x:number,y:number,w:number,h:number,n:number)=>{let p=.5;const pts:number[]=[];for(let i=0;i<n;i++){const o=p;p=Math.min(.92,Math.max(.08,p+(rand()-.49)*.09));const hi=Math.max(o,p)+rand()*.03,lo=Math.min(o,p)-rand()*.03,xx=x+(i+.5)*w/n;c.strokeStyle=c.fillStyle=p>=o?CYAN:PURPLE;c.lineWidth=Math.max(1,.18*u);c.beginPath();c.moveTo(xx,y+h*(1-hi));c.lineTo(xx,y+h*(1-lo));c.stroke();c.fillRect(xx-w/n*.3,y+h*(1-Math.max(o,p)),w/n*.6,Math.max(1,h*Math.abs(p-o)));pts.push(p)}
  c.strokeStyle='#c9b8ff';c.lineWidth=Math.max(1.5,.3*u);c.beginPath();pts.forEach((v,i)=>{const m=pts.slice(Math.max(0,i-8),i+1).reduce((a,b)=>a+b)/Math.min(i+1,9),xx=x+(i+.5)*w/n,yy=y+h*(1-m);i?c.lineTo(xx,yy):c.moveTo(xx,yy)});c.stroke()
  c.fillStyle=TEXT;c.font=`${1.9*u}px ui-monospace,monospace`;c.textAlign='right';for(let i=0;i<=4;i++)c.fillText((400+i*12.5).toFixed(1),x+w-.6*u,y+h*(1-i/4.4)-.4*u);c.textAlign='left'}
 const bars=(x:number,y:number,w:number,h:number,n:number)=>{for(let i=0;i<n;i++){const v=.15+rand()*.8;c.fillStyle=i%5?BLUE:'#6fb3ff';c.fillRect(x+i*w/n+w/n*.15,y+h*(1-v),w/n*.7,h*v)}}
 const line=(x:number,y:number,w:number,h:number,n:number,color:string)=>{let p=.5;c.strokeStyle=color;c.lineWidth=Math.max(1.5,.32*u);c.beginPath();for(let i=0;i<n;i++){p=Math.min(.95,Math.max(.05,p+(rand()-.5)*.12));const xx=x+i*w/(n-1),yy=y+h*(1-p);i?c.lineTo(xx,yy):c.moveTo(xx,yy)}c.stroke()}
 const table=(x:number,y:number,w:number,h:number,rows:number)=>{c.font=`${2.1*u}px ui-monospace,monospace`;for(let i=0;i<rows;i++){const yy=y+5*u+i*h/rows;c.fillStyle=TEXT;c.fillText(['SPY','QQQ','IWM','DIA','XLF','XLK','GLD','TLT','BTC','ETH','SOL','NVDA'][(i+index)%12],x+1.2*u,yy);const ch=(rand()-.45)*3;c.fillStyle=ch>=0?CYAN:PURPLE;c.textAlign='right';c.fillText((ch>=0?'+':'')+ch.toFixed(2)+'%',x+w-1.2*u,yy);c.textAlign='left'}}
 const m=2*u,top=9*u
 if(aspect<.6){ // tall pillar display: stacked watch list with sparklines
  const rows=Math.floor((H-top)/(14*u));for(let i=0;i<rows;i++){const y=top+i*14*u;panel(m,y,W-2*m,12*u,['SPY','QQQ','BTC','ETH','IWM','TLT','GLD','NVDA','AAPL','MSFT'][(i+index)%10]);line(m+u,y+4*u,W-2*m-2*u,7*u,40,i%2?PURPLE:CYAN)}
 }else if(screen.kind==='desk'){
  panel(m,top,W*.62-m,H*.55,'LAST RUN');candles(m+u,top+4*u,W*.62-3*u,H*.55-5*u,48)
  panel(W*.62+m,top,W*.38-2*m,H*.55,'QUEUE');table(W*.62+m,top,W*.38-2*m,H*.55,6)
  panel(m,top+H*.55+m,W-2*m,H-top-H*.55-2*m,'ACTIVITY');bars(m+u,top+H*.55+5*u,W-4*u,H-top-H*.55-7*u,60)
 }else if(aspect>2.2){ // wide strip
  panel(m,top,W*.7-m,H-top-m,'PRICE');candles(m+u,top+4*u,W*.7-3*u,H-top-6*u,90)
  panel(W*.7+m,top,W*.3-2*m,H-top-m,'MOVERS');table(W*.7+m,top,W*.3-2*m,H-top-m,Math.max(3,Math.floor((H-top)/(5*u))-1))
 }else{
  const kindOf=index%3
  panel(m,top,W-2*m,(H-top)*.58,kindOf===1?'EQUITY CURVE':'PRICE');kindOf===1?line(m+u,top+4*u,W-4*u,(H-top)*.58-5*u,120,PURPLE):candles(m+u,top+4*u,W-4*u,(H-top)*.58-5*u,70)
  const y2=top+(H-top)*.58+m,h2=H-y2-m
  panel(m,y2,W*.6-m,h2,kindOf===2?'DRAWDOWN':'VOLUME');bars(m+u,y2+4*u,W*.6-3*u,h2-5*u,50)
  panel(W*.6+m,y2,W*.4-2*m,h2,'WATCH');table(W*.6+m,y2,W*.4-2*m,h2,Math.max(2,Math.floor(h2/(5*u))-1))
 }
 const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.NoColorSpace;t.anisotropy=16;t.generateMipmaps=true;t.minFilter=THREE.LinearMipmapLinearFilter
 return t
}

// ---------------------------------------------------------------------------------------------
// Live desk consoles, drawn into the ring computer (no DOM overlay). One agent = one strategy: each
// agent's region is a strategy tile (name, status, equity curve, stats, recent trades, log) fed by
// ./strategies (engine /api/agents/live when it exists, ?demo=1 for a labelled simulation, honest
// empty states otherwise). The engine heartbeat comes from /api/health. Nothing here is invented:
// a value the source did not send is drawn as "—".
type Engine={state:'checking'|'up'|'down';keys:boolean;at:number;latency:number[]}
const live={engine:{state:'checking',keys:false,at:0,latency:[]} as Engine,log:new Map<string,string[]>()}
/** Engine events as they happen, shown in the logs when a strategy has nothing of its own yet. */
function note(key:string,line:string){const l=live.log.get(key)??[];if(l[0]?.slice(9)===line)return;l.unshift(`${hhmmss(Date.now())} ${line}`);live.log.set(key,l.slice(0,8))}
async function pollHealth(){const t0=performance.now()
 try{const h=await api.health();const e=live.engine;live.engine={state:'up',keys:h.alpaca_keys_present,at:Date.now(),latency:[...e.latency,performance.now()-t0].slice(-40)};if(e.state!=='up')note('engine',`engine up${h.alpaca_keys_present?'':' · alpaca keys missing'}`)}
 catch{if(live.engine.state!=='down')note('engine','engine unreachable');live.engine={...live.engine,state:'down',at:Date.now()}}}
const hhmmss=(ms:number)=>new Date(ms).toLocaleTimeString([],{hour12:false})
const hhmm=(iso:string)=>{const t=Date.parse(iso);return Number.isFinite(t)?hhmmss(t):'--:--:--'}
const GREEN='#3ddc84',RED='#ff5a6a',ORANGE='#ff8a3d'
const STATUS_COLOR:Record<AgentStatus,string>={idle:'#6d86a8',researching:'#9b7bff',coding:'#5fd0ff',backtesting:ORANGE,live_paper:GREEN,error:RED}
const signR=(v:number)=>(v>0?'+':'')+v.toFixed(1)+'R'
/** What a region's pixels depend on; it is redrawn and re-uploaded only when this changes. */
function consoleKey(screen:RoomScreen,now:number){
 const slot=screen.seat,e=live.engine
 if(slot)return `${liveAgents.version.get(slot)}|${liveAgents.sourceVersion}|${e.state}|${e.keys}`
 if(screen.id==='d8')return `${Math.floor(now/1000)}` // the operator console carries a clock
 return `${e.at}|${e.state}`
}
// One agent's work area on the ring computer, drawn into its own offscreen block (top = toward the
// CEO) and then blended into the ring with soft edges. Panels are glass tints, not framed monitors.
function drawConsole(canvas:HTMLCanvasElement,screen:RoomScreen,now:number){
 const c=canvas.getContext('2d')!,W=canvas.width,H=canvas.height,u=H/100,e=live.engine
 const seat=screen.seat?SEATS.find(x=>x.id===screen.seat):undefined
 const m=4*u,xl=()=>m,xr=()=>W-m
 /** A panel between rows y0..y1 spanning fractions a..b of the usable width; returns its inner rect. */
 const zone=(y0:number,y1:number,a:number,b:number,label?:string,accent='#2b6fc0')=>{
  const x0=xl()+a*(xr()-xl())+(a>0?.6*u:0),x1=xl()+b*(xr()-xl())-(b<1?.6*u:0)
  c.beginPath();c.roundRect(x0,y0,x1-x0,y1-y0,1.2*u);c.fillStyle='#0a1d4270';c.fill();c.globalAlpha=.5;c.strokeStyle=accent;c.lineWidth=.25*u;c.stroke();c.globalAlpha=1
  if(label){c.fillStyle='#8fb4e0';c.font=`600 ${2.5*u}px ui-monospace,monospace`;c.textAlign='left';c.fillText(label,x0+1.4*u,y0+3*u)}
  return {x:x0+1.4*u,y:y0+(label?5.6*u:1.5*u),w:x1-x0-2.8*u,h:y1-y0-(label?7*u:3*u)}
 }
 const text=(v:string,x:number,y:number,size:number,color:string,align:CanvasTextAlign='left',weight=400,mono=true,max?:number)=>{c.textAlign=align;c.fillStyle=color;c.font=`${weight} ${size*u}px ${mono?'ui-monospace,monospace':'system-ui,sans-serif'}`;c.fillText(v,x,y,max)}
 const chip=(label:string,color:string,x:number,y:number,size=2.6)=>{c.font=`700 ${size*u}px ui-monospace,monospace`;const w=c.measureText(label).width+2.4*u
  c.beginPath();c.roundRect(x-w,y-2.2*u,w,4.4*u,.9*u);c.fillStyle=color+'33';c.fill();c.strokeStyle=color;c.lineWidth=.25*u;c.stroke();text(label,x-1.2*u,y,size,color,'right',700);return w}
 const engineLine=()=>`ENGINE ${e.state==='up'?'UP':e.state==='down'?'OFFLINE':'…'}${e.state==='up'&&!e.keys?' · NO KEYS':''}`
 c.clearRect(0,0,W,H);c.textBaseline='middle'
 const g=c.createRadialGradient(W/2,H*.55,H*.1,W/2,H*.55,Math.max(W,H)*.75);g.addColorStop(0,'#0b2a5ccc');g.addColorStop(1,'#04102a55');c.fillStyle=g;c.fillRect(0,0,W,H)
 if(seat){
  const a=liveAgents.slots.get(seat.id)!,src=liveAgents.source,demo=src==='demo',st=a.strategy,s=a.stats
  // header: strategy name, agent and strategy id, status, data source
  const hd=zone(2.5*u,18*u,0,1,undefined,demo?ORANGE:'#3d8bff')
  const cw=chip(STATUS_LABEL[a.status],STATUS_COLOR[a.status],hd.x+hd.w,hd.y+2.6*u,2.8)
  text(st?.name??'NO STRATEGY ASSIGNED',hd.x+.3*u,hd.y+2.8*u,4.4,st?'#f2f7ff':'#8fa9cc','left',700,false,hd.w-cw-2*u)
  text([seat.name,...(st?[st.id,st.version,st.market,st.timeframe].filter(Boolean):[seat.job.toLowerCase()])].join(' · '),hd.x+.3*u,hd.y+7.6*u,2.4,'#7fa6d6','left',400,true,hd.w)
  const srcText=demo?'DEMO · SIMULATED DATA · NOT A REAL RESULT':src==='engine'?`LIVE FROM ENGINE${a.updated?` · updated ${hhmmss(a.updated)}`:''}`:src==='unavailable'?'NO LIVE FEED · engine has no /api/agents/live yet':src==='down'?'ENGINE OFFLINE · no live data':'CHECKING ENGINE…'
  text(srcText,hd.x+.3*u,hd.y+11.6*u,2.4,demo?ORANGE:src==='engine'?GREEN:'#f3c74b','left',700,true,hd.w*.72)
  if(a.progress!==null){const pw=hd.w*.25,px=hd.x+hd.w-pw,py=hd.y+11.1*u;c.fillStyle='#ffffff14';c.fillRect(px,py,pw,1*u);c.fillStyle=STATUS_COLOR[a.status];c.fillRect(px,py,pw*Math.min(1,Math.max(0,a.progress)),1*u)}
  // key stats, RHerman tile style
  const stats:[string,string,string][]=[
   ['TRADES',s?String(s.trades):'—','#e4f0ff'],
   ['WR',s?.wr!=null?(s.wr*100).toFixed(1)+'%':'—','#e4f0ff'],
   ['PF',s?.pf!=null?s.pf.toFixed(2):'—',s?.pf!=null?(s.pf>=1?GREEN:RED):'#e4f0ff'],
   ['NET R',s?signR(s.netR):'—',s?(s.netR>0?GREEN:s.netR<0?RED:'#e4f0ff'):'#e4f0ff'],
   ['MAX DD R',s?s.maxDD.toFixed(1)+'R':'—',s&&s.maxDD<0?RED:'#e4f0ff']]
  stats.forEach(([k,v,col],i)=>{const z=zone(20*u,33*u,i/5,(i+1)/5,k,'#2b6fc0');text(v,z.x,z.y+3*u,4.2,col,'left',700,true,z.w)})
  // equity curve (cumulative net R)
  const eq=zone(35*u,69*u,0,.6,'EQUITY · NET R',demo?ORANGE:'#2b6fc0')
  c.strokeStyle=GRID;c.lineWidth=.2*u;for(let i=0;i<=4;i++){const y=eq.y+eq.h*i/4;c.beginPath();c.moveTo(eq.x,y);c.lineTo(eq.x+eq.w,y);c.stroke()}
  if(a.equity.length>1){
   const v=a.equity,lo=Math.min(0,...v),hi=Math.max(0,...v),Y=(r:number)=>eq.y+eq.h*(1-(r-lo)/Math.max(1e-9,hi-lo)),X=(i:number)=>eq.x+i/(v.length-1)*(eq.w-8*u),up=v.at(-1)!>=0
   c.setLineDash([.8*u,.8*u]);c.strokeStyle='#7f9cc4';c.lineWidth=.2*u;c.beginPath();c.moveTo(eq.x,Y(0));c.lineTo(eq.x+eq.w-8*u,Y(0));c.stroke();c.setLineDash([])
   const fill=c.createLinearGradient(0,eq.y,0,eq.y+eq.h);fill.addColorStop(0,(up?GREEN:RED)+'55');fill.addColorStop(1,(up?GREEN:RED)+'05')
   c.beginPath();v.forEach((r,i)=>i?c.lineTo(X(i),Y(r)):c.moveTo(X(i),Y(r)));c.lineTo(X(v.length-1),Y(0));c.lineTo(X(0),Y(0));c.closePath();c.fillStyle=fill;c.fill()
   c.beginPath();v.forEach((r,i)=>i?c.lineTo(X(i),Y(r)):c.moveTo(X(i),Y(r)));c.strokeStyle=up?GREEN:RED;c.lineWidth=.45*u;c.stroke()
   const marks:[number,string][]=[[Y(hi),signR(hi)],[Y(0),'0R'],[Y(lo),signR(lo)]]
   marks.forEach(([y,l],i)=>{if(marks.slice(0,i).every(([yy])=>Math.abs(yy-y)>3*u))text(l,eq.x+eq.w,Math.min(eq.y+eq.h-1*u,Math.max(eq.y+1*u,y)),2.3,'#7f9cc4','right')})
  }else{
   c.setLineDash([.8*u,.8*u]);c.strokeStyle='#3a5a88';c.lineWidth=.25*u;c.beginPath();c.moveTo(eq.x,eq.y+eq.h/2);c.lineTo(eq.x+eq.w,eq.y+eq.h/2);c.stroke();c.setLineDash([])
   text(st?'awaiting run':'no strategy · no equity',eq.x+eq.w/2,eq.y+eq.h/2-3*u,3,'#7f9cc4','center',600,false)
  }
  if(demo)text('DEMO · SIMULATED',eq.x+eq.w,eq.y-2.6*u,2.3,ORANGE,'right',700)
  // recent trades
  const tr=zone(35*u,69*u,.6,1,'RECENT TRADES'),rows=Math.max(1,Math.floor(tr.h/(3.7*u)))
  if(!a.trades.length)text(st?'no trades yet':'—',tr.x,tr.y+1.8*u,2.6,'#6d86a8')
  a.trades.slice(0,rows).forEach((t,i)=>{const y=tr.y+1.8*u+i*3.7*u;text(hhmm(t.t),tr.x,y,2.4,'#6d86a8');text(t.side==='long'?'LONG':'SHORT',tr.x+tr.w*.48,y,2.4,t.side==='long'?'#8fd0ff':'#c9b8ff','left',600)
   text((t.r>=0?'+':'')+t.r.toFixed(2)+'R',tr.x+tr.w,y,2.6,t.r>=0?GREEN:RED,'right',700)})
  // log: the strategy's own lines; until it has any, the data source and engine events
  const lg=zone(71*u,97*u,0,1,'LOG'),n=Math.max(1,Math.floor(lg.h/(3.5*u)))
  const lines:[string,string,string][]=a.log.length?a.log.map(l=>[hhmm(l.t),l.msg,l.level==='error'?RED:l.level==='warn'?'#f3c74b':'#d6e8ff']):[
   [hhmmss(liveAgents.checked||now),liveAgents.detail||'checking engine for live agent data',demo?ORANGE:'#f3c74b'],
   ...(live.log.get('engine')??[]).map(l=>[l.slice(0,8),l.slice(9),'#9fb9dc'] as [string,string,string])]
  lines.slice(0,n).forEach(([t,msg,col],i)=>{const y=lg.y+1.6*u+i*3.5*u;text(t,lg.x,y,2.5,'#6d86a8');text(msg,lg.x+14*u,y,2.5,i?col+'cc':col,'left',400,true,lg.w-14*u)})
  text(engineLine(),lg.x+lg.w,lg.y-3.6*u,2.3,e.state==='up'?GREEN:e.state==='down'?RED:'#f3c74b','right',600)
 }else if(screen.id==='d8'){
  // the operator's console: every agent's strategy at a glance
  const hd=zone(2.5*u,18*u,0,1,undefined,'#3d8bff')
  text('COMMAND CONSOLE',hd.x+.3*u,hd.y+2.8*u,4.6,'#e8f3ff','left',700,false);text(hhmmss(now),hd.x+hd.w,hd.y+2.8*u,4.4,'#cfe6ff','right',600)
  text('OPERATOR · ONE AGENT PER STRATEGY',hd.x+.3*u,hd.y+7.6*u,2.5,'#7fa6d6')
  const src=liveAgents.source
  text(src==='demo'?'DEMO · SIMULATED DATA':src==='engine'?'LIVE FROM ENGINE':src==='unavailable'?'NO LIVE AGENT FEED ON THIS ENGINE':src==='down'?'ENGINE OFFLINE':'CHECKING…',hd.x+.3*u,hd.y+11.6*u,2.4,src==='demo'?ORANGE:src==='engine'?GREEN:'#f3c74b','left',700)
  text(engineLine(),hd.x+hd.w,hd.y+11.6*u,2.4,e.state==='up'?GREEN:e.state==='down'?RED:'#f3c74b','right',600)
  const tb=zone(20*u,69*u,0,1,'STRATEGIES')
  const cols=[0,.24,.62,.82,1],head=['AGENT','STRATEGY','STATUS','NET R']
  head.forEach((h,i)=>text(h,tb.x+tb.w*cols[i]+(i===3?tb.w*.18:0),tb.y+1.2*u,2.3,'#6d86a8',i===3?'right':'left',600))
  SEATS.forEach((sx,i)=>{const a=liveAgents.slots.get(sx.id)!,y=tb.y+6*u+i*(tb.h-6*u)/6
   text(sx.name.replace(' AGENT',''),tb.x,y,2.5,'#d6e8ff','left',600,false,tb.w*.23)
   text(a.strategy?.name??'—',tb.x+tb.w*cols[1],y,2.5,a.strategy?'#e4f0ff':'#6d86a8','left',400,false,tb.w*.37)
   text(STATUS_LABEL[a.status],tb.x+tb.w*cols[2],y,2.4,STATUS_COLOR[a.status],'left',700)
   text(a.stats?signR(a.stats.netR):'—',tb.x+tb.w,y,2.6,a.stats?(a.stats.netR>=0?GREEN:RED):'#6d86a8','right',700)})
  const lg=zone(71*u,97*u,0,1,'ACTIVITY LOG'),n=Math.max(1,Math.floor(lg.h/(3.5*u)))
  const lines=[...SEATS.flatMap(sx=>(liveAgents.slots.get(sx.id)!.log.slice(0,2)).map(l=>[hhmm(l.t),`${sx.id} · ${l.msg}`])),...(live.log.get('engine')??[]).map(l=>[l.slice(0,8),l.slice(9)])].sort((p,q)=>p[0]<q[0]?1:-1)
  if(!lines.length)text('waiting for first event…',lg.x,lg.y+1.6*u,2.6,'#6d86a8')
  lines.slice(0,n).forEach(([t,msg],i)=>{const y=lg.y+1.6*u+i*3.5*u;text(t,lg.x,y,2.5,'#6d86a8');text(msg,lg.x+14*u,y,2.5,i?'#9fb9dc':'#d6e8ff','left',400,true,lg.w-14*u)})
 }else{
  const rt=e.latency.at(-1)
  const hd=zone(2.5*u,18*u,0,1,undefined,'#3d8bff');text(`AUX CONSOLE ${screen.n}`,hd.x+.3*u,hd.y+3*u,4.2,'#e8f3ff','left',700,false);text('UNASSIGNED',hd.x+.3*u,hd.y+8.6*u,2.6,'#7fa6d6')
  text(engineLine()+(e.state==='up'&&rt!==undefined?` · ${rt.toFixed(0)} ms`:''),hd.x+.3*u,hd.y+12.4*u,2.4,'#9fc3ee','left',600)
  const lt=zone(20*u,69*u,0,1,'ENGINE ROUND TRIP'),L=e.latency
  if(L.length>1){const max=Math.max(...L,1);c.strokeStyle=CYAN;c.lineWidth=.4*u;c.beginPath();L.forEach((v,i)=>{const x=lt.x+i/(L.length-1)*lt.w,y=lt.y+lt.h-v/max*lt.h*.9;i?c.lineTo(x,y):c.moveTo(x,y)});c.stroke();text(`max ${max.toFixed(0)} ms`,lt.x+lt.w,lt.y+1.5*u,2.4,'#7f9cc4','right')}
  const nt=zone(71*u,97*u,0,1,'STATUS');text('Not assigned yet · click to open',nt.x,nt.y+2*u,3,'#cfe3f7','left',600,false)
 }
}
// ---------------------------------------------------------------------------------------------
// The desk top is one ring computer: a single planar texture over the whole disc, shared by every
// desk region mesh. A static layer carries continuous data rings, tick marks and a spectrum that run
// unbroken round the ring; each agent's live work area is composited at its bearing, oriented to
// read from outside the ring (by the agent seated there), with feathered edges so regions blend.
const RING={rim:2.745,inner:1.37,outer:2.66,rin:1.64,rout:2.62},RING_PX=3584
const ringPx=(x:number,z:number):[number,number]=>[(.5+x/(2*RING.rim))*RING_PX,(.5+z/(2*RING.rim))*RING_PX] // matches the build's ringUV
function ringBase(){
 const cv=document.createElement('canvas');cv.width=cv.height=RING_PX;const c=cv.getContext('2d')!,k=RING_PX/(2*RING.rim),C=RING_PX/2,rand=rng(4242)
 const g=c.createRadialGradient(C,C,RING.inner*k,C,C,RING.outer*k);g.addColorStop(0,'#071634');g.addColorStop(.5,'#041029');g.addColorStop(1,'#061637');c.fillStyle=g;c.fillRect(0,0,RING_PX,RING_PX)
 const ring=(r:number,color:string,w:number,alpha=1)=>{c.globalAlpha=alpha;c.strokeStyle=color;c.lineWidth=w*k;c.beginPath();c.arc(C,C,r*k,0,Math.PI*2);c.stroke();c.globalAlpha=1}
 for(let r=RING.inner+.05;r<RING.outer;r+=.06)ring(r,'#1b3d74',.003,.5)
 ring(1.40,'#3fb4ff',.010);ring(1.40,'#3fb4ff',.03,.15);ring(1.60,'#9b6bff',.006);ring(2.64,'#46b8ff',.008);ring(2.64,'#46b8ff',.03,.15)
 // tick marks every degree, longer every ten
 c.strokeStyle='#4f8fd8';for(let d=0;d<360;d++){const a=d*Math.PI/180,r0=1.43,r1=d%10?1.455:1.49;c.lineWidth=(d%10?.002:.004)*k;c.beginPath();c.moveTo(C+Math.sin(a)*r0*k,C+Math.cos(a)*r0*k);c.lineTo(C+Math.sin(a)*r1*k,C+Math.cos(a)*r1*k);c.stroke()}
 // continuous data traces circling the whole ring
 for(const [r,amp,col,w] of [[1.70,.035,'#3d8bff',.004],[1.95,.05,'#7d5bff',.003],[2.30,.04,'#2fb6ff',.003],[2.52,.03,'#5f7dff',.003]] as [number,number,string,number][]){
  let p=0;c.strokeStyle=col;c.globalAlpha=.55;c.lineWidth=w*k;c.beginPath()
  for(let i=0;i<=1440;i++){const a=i/1440*Math.PI*2;p=i===1440?0:Math.max(-1,Math.min(1,p+(rand()-.5)*.35))*(i>1380?(1440-i)/60:1);const rr=r+p*amp;i?c.lineTo(C+Math.sin(a)*rr*k,C+Math.cos(a)*rr*k):c.moveTo(C+Math.sin(a)*rr*k,C+Math.cos(a)*rr*k)}
  c.stroke();c.globalAlpha=1}
 // spectrum round the outer edge
 for(let i=0;i<720;i++){const a=i/720*Math.PI*2,h=.015+rand()*.06;c.strokeStyle=i%6?'#2d6fd0':'#8a6cff';c.globalAlpha=.65;c.lineWidth=.004*k;c.beginPath();c.moveTo(C+Math.sin(a)*2.58*k,C+Math.cos(a)*2.58*k);c.lineTo(C+Math.sin(a)*(2.58-h)*k,C+Math.cos(a)*(2.58-h)*k);c.stroke()}
 c.globalAlpha=1
 return cv
}
type Block={key:string;screen:RoomScreen;canvas:HTMLCanvasElement;mask:HTMLCanvasElement;theta:number;x:number;y:number;box:{x:number;y:number;w:number;h:number};patch:THREE.CanvasTexture;at:THREE.Vector2}
function ringTexture(){const cv=document.createElement('canvas');cv.width=cv.height=RING_PX;const t=new THREE.CanvasTexture(cv);t.colorSpace=THREE.NoColorSpace;t.anisotropy=16;return t}
function ringBlocks():Block[]{
 const k=RING_PX/(2*RING.rim)
 return ROOM_SCREENS.filter(s=>s.kind==='desk').map(screen=>{
  const W=Math.round((screen.shape?.outer??screen.w)*k),H=Math.round((screen.shape?.depth??RING.rout-RING.rin)*k)
  const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H
  const mask=document.createElement('canvas');mask.width=W;mask.height=H
  const theta=Math.atan2(screen.center[0],screen.center[2]),r=screen.shape?.r??(RING.rin+RING.rout)/2,[x,y]=ringPx(Math.sin(theta)*r,Math.cos(theta)*r)
  // axis-aligned pixel box of the rotated block: the only part of the ring this block ever changes
  const cs=Math.abs(Math.cos(theta)),sn=Math.abs(Math.sin(theta)),hw=(W*cs+H*sn)/2+2,hh=(W*sn+H*cs)/2+2
  const x0=Math.max(0,Math.floor(x-hw)),y0=Math.max(0,Math.floor(y-hh)),x1=Math.min(RING_PX,Math.ceil(x+hw)),y1=Math.min(RING_PX,Math.ceil(y+hh))
  const box={x:x0,y:y0,w:x1-x0,h:y1-y0},pc=document.createElement('canvas');pc.width=box.w;pc.height=box.h
  const patch=new THREE.CanvasTexture(pc) // never bound to a material: only a source for copyTextureToTexture
  return {key:'',screen,canvas,mask,theta,x,y,box,patch,at:new THREE.Vector2(box.x,RING_PX-box.y-box.h)} // flipY: GL rows count from the bottom
 })
}
/** Composite one live region onto the CPU ring canvas over a fresh copy of the static base. */
function composeBlock(c:CanvasRenderingContext2D,base:HTMLCanvasElement,b:Block,now:number){
 b.key=consoleKey(b.screen,now);drawConsole(b.canvas,b.screen,now)
 const m=b.mask.getContext('2d')!,W=b.mask.width,H=b.mask.height
 m.globalCompositeOperation='copy';m.drawImage(b.canvas,0,0);m.globalCompositeOperation='destination-in'
 const fx=m.createLinearGradient(0,0,W,0);fx.addColorStop(0,'#0000');fx.addColorStop(.09,'#000f');fx.addColorStop(.91,'#000f');fx.addColorStop(1,'#0000');m.fillStyle=fx;m.fillRect(0,0,W,H)
 const fy=m.createLinearGradient(0,0,0,H);fy.addColorStop(0,'#0000');fy.addColorStop(.05,'#000f');fy.addColorStop(.97,'#000f');fy.addColorStop(1,'#0000');m.fillStyle=fy;m.fillRect(0,0,W,H)
 c.save();c.translate(b.x,b.y);c.rotate(-b.theta);c.beginPath();c.rect(-W/2,-H/2,W,H);c.clip() // top of the block toward the CEO
 c.setTransform(1,0,0,1,0,0);c.drawImage(base,b.box.x,b.box.y,b.box.w,b.box.h,b.box.x,b.box.y,b.box.w,b.box.h)
 c.translate(b.x,b.y);c.rotate(-b.theta);c.drawImage(b.mask,-W/2,-H/2);c.restore()
}
/**
 * The ring computer's texture is 3584 px square. v6 redrew and re-uploaded all of it (51 MB) every
 * second, a visible hitch. Now the full texture is uploaded once; afterwards each live region is
 * redrawn on its own, staggered across the second, and only its pixel box is copied to the GPU.
 */
function useLiveConsoles(ring:THREE.CanvasTexture,gl:THREE.WebGLRenderer){
 useEffect(()=>{
  const base=ringBase(),blocks=ringBlocks(),cv=ring.image as HTMLCanvasElement,c=cv.getContext('2d')!
  let next=0,uploaded=false
  ring.onUpdate=()=>{uploaded=true}
  c.drawImage(base,0,0);for(const b of blocks)composeBlock(c,base,b,Date.now());ring.needsUpdate=true
  const uploads=new Map<string,number>()
  const tick=()=>{ // the next region whose content changed; an unchanged region is never redrawn or re-uploaded
   const now=Date.now();let b:Block|undefined
   for(let i=0;i<blocks.length&&!b;i++){const k=blocks[next++%blocks.length];if(consoleKey(k.screen,now)!==k.key)b=k}
   if(!b)return
   const t0=performance.now();composeBlock(c,base,b,now);uploads.set(b.screen.id,(uploads.get(b.screen.id)??0)+1)
   const pc=b.patch.image as HTMLCanvasElement,p=pc.getContext('2d')!
   p.globalCompositeOperation='copy';p.drawImage(cv,b.box.x,b.box.y,b.box.w,b.box.h,0,0,b.box.w,b.box.h)
   const t1=performance.now()
   if(uploaded)gl.copyTextureToTexture(b.patch,ring,null,b.at) // before the first upload the full canvas goes up anyway
   if(import.meta.env.DEV)Object.assign(window,{__ringTickMs:{draw:t1-t0,uploadCall:performance.now()-t1}})
  }
  if(import.meta.env.DEV)Object.assign(window,{__ringTick:tick,__ringBoxes:blocks.map(b=>[b.box.w,b.box.h]),__ringUploads:uploads}) // perf probes
  const stopAgents=startLiveAgents()
  pollHealth()
  // up to ~9 dirty regions a second, in the idle time after a frame so a redraw never lands mid-frame
  const idle=(window as unknown as {requestIdleCallback?:(f:()=>void,o:{timeout:number})=>number}).requestIdleCallback
  const a=setInterval(()=>idle?idle(tick,{timeout:200}):tick(),Math.round(1000/blocks.length)),h=setInterval(pollHealth,3000)
  return()=>{stopAgents();clearInterval(a);clearInterval(h);for(const b of blocks)b.patch.dispose()}
 },[ring,gl])
}

// ---------------------------------------------------------------------------------------------
// Zoom. Wheel, trackpad pinch (ctrl+wheel) and two-finger touch pinch feed one damped log-distance
// accumulator that moves camera and orbit target toward the 3D point under the pointer.
// Reading a screen: when the pointer is on a screen (its frame, an agent's desk station, the agent or
// its chair all count as that agent's console) and the user deliberately scrolls toward it, the camera
// glides to a head-on pose where the screen fills ~70% of the view, upright to its readable side.
// Scrolling out from there (or Esc / double-click on empty space) glides back. Any other scroll-out, from
// any position or orbit angle, eases back toward the wide overview (home distance and height, same heading). Every glide follows a
// path that is ray-checked against the room, so the camera never passes through people or furniture.
type Pose={position:THREE.Vector3;target:THREE.Vector3}
type Flight={from:Pose;to:Pose;path:(k:number)=>THREE.Vector3;t:number;dur:number;done:()=>void;inward:boolean}
type Inspecting={screen:RoomScreen;pose:Pose;back:Pose;out:number}
/** The wide overview every scroll-out converges on: home target, home distance and home height, at any azimuth. */
const OVERVIEW=(()=>{const p=new THREE.Vector3(...HOME.position),target=new THREE.Vector3(...HOME.target),radius=p.distanceTo(target);return{target,radius,phi:Math.acos((p.y-target.y)/radius)}})()
const sph=new THREE.Spherical(),off=new THREE.Vector3()
const HOME_POSE=():Pose=>({position:new THREE.Vector3(...HOME.position),target:new THREE.Vector3(...HOME.target)})
/** The screen a hit belongs to, for aiming: the face, its frame, a desk station, or the seated agent/chair. */
function screenFromHit(hit:THREE.Intersection):RoomScreen|undefined{
 const n=hit.object.name
 if(n.startsWith('screen_'))return screenById(n.slice(7))
 if(n.startsWith('frame_'))return screenById(n.slice(6))
 const seat=/^(?:agent|chair)_(.+)$/.exec(n)?.[1]
 if(seat)return ROOM_SCREENS.find(s=>s.seat===seat)
 return deskScreenAt(hit.point)??undefined
}
const solid=(h:THREE.Intersection)=>h.object.visible&&(h.object as THREE.Mesh).isMesh
function SmoothZoom({controls,enabled,resetKey}:{controls:RefObject<Controls|null>;enabled:boolean;resetKey:number}){
 const {camera,gl,scene}=useThree()
 const cam=camera as THREE.PerspectiveCamera
 const pending=useRef(0),focus=useRef(new THREE.Vector3(...HOME.target)),under=useRef<RoomScreen|undefined>(undefined)
 const flight=useRef<Flight|null>(null),inspect=useRef<Inspecting|null>(null),anchor=useRef<Pose>(HOME_POSE())
 const gesture=useRef({screen:undefined as RoomScreen|undefined,sum:0})
 const ray=useMemo(()=>{const r=new THREE.Raycaster();(r as THREE.Raycaster&{firstHitOnly?:boolean}).firstHitOnly=false;return r},[])
 const live=useRef(enabled);live.current=enabled
 const pose=():Pose=>({position:camera.position.clone(),target:(controls.current?.target??new THREE.Vector3(...HOME.target)).clone()})
 const aspect=()=>{const r=gl.domElement.getBoundingClientRect();return r.width/Math.max(1,r.height)}
 /** First solid hit along a ray. */
 const cast=(from:THREE.Vector3,dir:THREE.Vector3,far:number)=>{ray.set(from,dir.clone().normalize());ray.near=0;ray.far=far;return ray.intersectObjects(scene.children,true).find(solid)}
 const blocked=(a:THREE.Vector3,b:THREE.Vector3)=>{const d=b.clone().sub(a),l=d.length();return l>1e-4&&!!cast(a,d,l)}
 /** Pick a collision-free path: straight, around the room's axis (clears the CEO hologram), or either raised. */
 const route=(from:THREE.Vector3,to:THREE.Vector3)=>{
  const straight=(k:number)=>from.clone().lerp(to,k)
  const ra=Math.hypot(from.x,from.z),rb=Math.hypot(to.x,to.z),aa=Math.atan2(from.x,from.z)
  let da=Math.atan2(to.x,to.z)-aa;da=Math.atan2(Math.sin(da),Math.cos(da))
  const around=(k:number)=>{const r=THREE.MathUtils.lerp(ra,rb,k),a=aa+da*k;return new THREE.Vector3(Math.sin(a)*r,THREE.MathUtils.lerp(from.y,to.y,k),Math.cos(a)*r)}
  const raise=(f:(k:number)=>THREE.Vector3,h:number)=>(k:number)=>{const p=f(k);p.y=Math.min(LIMITS.ceiling-.3,p.y+Math.sin(Math.PI*k)*h);return p}
  const clear=(f:(k:number)=>THREE.Vector3)=>{let prev=f(0);for(let i=1;i<=32;i++){const p=f(i/32);if(blocked(prev,p))return false;prev=p}return true}
  for(const f of [straight,around,raise(straight,.8),raise(around,.8),raise(straight,1.6),raise(around,1.6)])if(clear(f))return f
  return straight
 }
 const fly=(to:Pose,inward:boolean,done:()=>void=()=>{})=>{
  const from=pose(),len=from.position.distanceTo(to.position)+.5*from.target.distanceTo(to.target)
  if(inward||pending.current<0)pending.current=0
  flight.current={from,to,path:route(from.position,to.position),t:0,dur:THREE.MathUtils.clamp(.45+len*.07,.5,1.1),done,inward}
 }
 const setInspect=(v:Inspecting|null)=>{inspect.current=v;setInspecting(v?.screen.id??null)}
 const startInspect=(s:RoomScreen)=>{
  const c=new THREE.Vector3(...s.center),n=new THREE.Vector3(...s.normal)
  const sw=s.shape?.outer??s.w,sh=s.shape?.depth??s.h // a ring region is framed by its whole work area
  let d=inspectDistance(sw,sh,aspect(),s.kind==='desk'?.85:INSPECT.fill)
  const hit=cast(c.clone().addScaledVector(n,.02),n,d+INSPECT.clearance) // keep the eye clear of heads and furniture
  if(hit)d=Math.max(INSPECT.minDistance,hit.distance+.02-INSPECT.clearance)
  const off=cam.view?.enabled?2*cam.view.offsetY/cam.view.fullHeight:0
  const to=inspectPose(s,d,readableUp(s,camera.position),off,cam.fov)
  const back=inspect.current?.back??anchor.current
  setInspect(null);gesture.current={screen:undefined,sum:0}
  fly(to,true,()=>setInspect({screen:s,pose:to,back,out:0}))
 }
 const leave=(to:Pose)=>{setInspect(null);gesture.current={screen:undefined,sum:0};fly(to,false,()=>{anchor.current=to})}
 const atHome=()=>camera.position.distanceTo(new THREE.Vector3(...HOME.position))<.02&&(controls.current?.target.distanceTo(new THREE.Vector3(...HOME.target))??0)<.02
 useEffect(()=>{flight.current=null;pending.current=0;anchor.current=HOME_POSE();setInspect(null)},[resetKey]) // eslint-disable-line react-hooks/exhaustive-deps
 useEffect(()=>{if(!enabled){flight.current=null;pending.current=0}},[enabled])
 useEffect(()=>{
  const el=gl.domElement
  const aim=(cx:number,cy:number)=>{
   const r=el.getBoundingClientRect();ray.setFromCamera(new THREE.Vector2((cx-r.left)/r.width*2-1,-(cy-r.top)/r.height*2+1),camera);ray.near=0;ray.far=60
   const hit=ray.intersectObjects(scene.children,true).find(solid)
   if(import.meta.env.DEV)(window as unknown as {__zoom?:unknown}).__zoom={hit:hit?.object.name,point:hit?.point.toArray(),under:hit?screenFromHit(hit)?.id:undefined,gesture:gesture.current.sum,inspect:inspect.current?.screen.id}
   if(hit){focus.current.copy(hit.point);under.current=screenFromHit(hit);return hit}
   const t=controls.current?.target??new THREE.Vector3(...HOME.target);focus.current.copy(ray.ray.at(camera.position.distanceTo(t),new THREE.Vector3()));under.current=undefined
  }
  const zoom=(amount:number)=>{ // amount in log-distance; negative = in
   if(flight.current){ // a wheel-out during a glide in turns it around; during a glide out it is kept for afterwards
    if(amount>0&&flight.current.inward){flight.current=null;leave(anchor.current)}
    else if(amount>0)pending.current=THREE.MathUtils.clamp(pending.current+amount,0,1.2)
    return
   }
   const s=under.current,insp=inspect.current
   if(amount<0&&s&&(!insp||insp.screen.id!==s.id)){
    const g=gesture.current
    if(g.screen?.id===s.id)g.sum-=amount;else{g.screen=s;g.sum=-amount}
    const D=camera.position.distanceTo(new THREE.Vector3(...s.center))
    if(g.sum>=INSPECT.gesture||screenFraction(s.shape?.outer??s.w,s.shape?.depth??s.h,D,aspect())>=INSPECT.fraction){startInspect(s);return}
   }else if(amount>0)gesture.current.sum=0
   pending.current=THREE.MathUtils.clamp(pending.current+amount,-1.2,1.2)
  }
  const wheel=(e:WheelEvent)=>{if(!live.current)return;e.preventDefault();aim(e.clientX,e.clientY)
   let dy=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?400:1);if(e.ctrlKey)dy*=3 // trackpad pinch arrives as ctrl+wheel with small deltas
   zoom(THREE.MathUtils.clamp(dy,-240,240)*ZOOM.wheel)} // one coarse notch never jumps more than ~two
  let pinch=0
  const touches=(e:TouchEvent)=>{if(e.touches.length!==2){pinch=0;return}const [a,b]=[e.touches[0],e.touches[1]],d=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);if(pinch&&live.current){aim((a.clientX+b.clientX)/2,(a.clientY+b.clientY)/2);zoom(Math.log(pinch/d))}pinch=d}
  const home=()=>{if(!live.current)return;if(inspect.current||flight.current||!atHome())leave(HOME_POSE())}
  const key=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!document.querySelector('.room-screen-menu'))home()}
  const dbl=(e:MouseEvent)=>{if(!live.current)return;const hit=aim(e.clientX,e.clientY);const n=hit?.object.name??'';if(!n.startsWith('screen_')&&!n.startsWith('frame_'))home()}
  el.addEventListener('wheel',wheel,{passive:false});el.addEventListener('touchstart',touches,{passive:true});el.addEventListener('touchmove',touches,{passive:true});el.addEventListener('touchend',touches)
  el.addEventListener('dblclick',dbl);window.addEventListener('keydown',key)
  return()=>{el.removeEventListener('wheel',wheel);el.removeEventListener('touchstart',touches);el.removeEventListener('touchmove',touches);el.removeEventListener('touchend',touches);el.removeEventListener('dblclick',dbl);window.removeEventListener('keydown',key)}
 },[gl,camera,scene,controls,ray]) // eslint-disable-line react-hooks/exhaustive-deps
 // A drag (orbit or pan) hands the camera back to the user: cancel any glide, and remember where they settle.
 const bound=useRef<Controls|null>(null),unbind=useRef<(()=>void)|null>(null)
 useEffect(()=>()=>{unbind.current?.()},[])
 useFrame((_,dt)=>{
  const c=controls.current
  if(c&&bound.current!==c){
   let grab:Pose|null=null
   const start=()=>{flight.current=null;pending.current=0;grab=pose()}
   const end=()=>{const now=pose() // a plain click (e.g. to open the screen) is not a drag and keeps the reading pose
    if(grab&&now.position.distanceTo(grab.position)+now.target.distanceTo(grab.target)>.005){setInspect(null);gesture.current={screen:undefined,sum:0};anchor.current=now}
    grab=null}
   unbind.current?.();c.addEventListener('start',start);c.addEventListener('end',end);unbind.current=()=>{c.removeEventListener('start',start);c.removeEventListener('end',end)};bound.current=c
  }
  if(!c||!enabled){pending.current=0;return}
  if(import.meta.env.DEV){const w=window as unknown as {__zoom?:Record<string,unknown>};w.__zoom={...w.__zoom,flying:!!flight.current,inspect:inspect.current?.screen.id}}
  const f=flight.current
  if(f){
   f.t=Math.min(1,f.t+Math.min(dt,.05)/f.dur)
   const k=f.t<.5?4*f.t**3:1-(-2*f.t+2)**3/2 // ease in-out
   camera.position.copy(f.path(k));c.target.copy(f.from.target).lerp(f.to.target,k);camera.lookAt(c.target);c.update()
   if(f.t===1){flight.current=null;f.done()}
   return
  }
  if(Math.abs(pending.current)<1e-4){pending.current=0;return}
  const step=pending.current*(1-Math.exp(-Math.min(dt,.1)*ZOOM.smoothing));pending.current-=step
  const insp=inspect.current
  if(insp&&step>0){ // out of a reading pose: first settle back onto it, then glide back to where you came from
   const gap=camera.position.distanceTo(insp.pose.position)+c.target.distanceTo(insp.pose.target)
   if(gap>.01){const a=1-Math.exp(-step*7);camera.position.lerp(insp.pose.position,a);c.target.lerp(insp.pose.target,a);c.update();return}
   insp.out+=step
   if(insp.out>=.06){pending.current=0;leave(insp.back)}
   return
  }
  const pos=camera.position
  if(step>0){ // out: ease toward the overview from wherever you are. Same azimuth, home distance and height
   const a=1-Math.exp(-step*ZOOM.out)
   sph.setFromVector3(off.copy(pos).sub(c.target))
   c.target.lerp(OVERVIEW.target,a)
   sph.radius+=(OVERVIEW.radius-sph.radius)*a;sph.phi+=(OVERVIEW.phi-sph.phi)*a;sph.makeSafe()
   pos.copy(c.target).add(off.setFromSpherical(sph))
   if(!inRoom(pos)){let lo=0,hi=1;for(let i=0;i<14;i++){const mid=(lo+hi)/2;pos.copy(c.target).addScaledVector(off,mid);if(inRoom(pos))lo=mid;else hi=mid}pos.copy(c.target).addScaledVector(off,lo)}
   if(c.target.distanceTo(OVERVIEW.target)<.005&&Math.abs(sph.radius-OVERVIEW.radius)<.005&&Math.abs(sph.phi-OVERVIEW.phi)<.002)pending.current=0
   camera.lookAt(c.target);c.update();return
  }
  let k=Math.exp(step)
  const F=focus.current,dist=pos.distanceTo(F)
  if(dist*k<ZOOM.minSurface){k=Math.min(1,ZOOM.minSurface/dist);pending.current=0}
  if(Math.abs(k-1)<1e-6)return
  pos.sub(F).multiplyScalar(k).add(F);c.target.sub(F).multiplyScalar(k).add(F)
  c.update()
 })
 return null
}

function Preview({screen,host}:{screen:RoomScreen;host:HTMLElement}){
 const {size}=useThree()
 const d=flightDistance(screen.w,screen.h,size.width/size.height)
 const px=screen.w/(2*d*Math.tan(48*Math.PI/360)*(size.width/size.height))*size.width
 const rotation=useMemo(()=>new THREE.Quaternion(...screen.quaternion),[screen])
 const position=new THREE.Vector3(...screen.center).addScaledVector(new THREE.Vector3(...screen.normal),.012)
 return <Html transform position={position} quaternion={rotation} distanceFactor={400*screen.w/px} zIndexRange={[30,20]}>
  <div className="room-screen-preview" style={{width:px,height:px*screen.h/screen.w}}><Slot host={host} className="slotfill"/></div>
 </Html>
}
const TAN_HALF_FOV=Math.tan(48*Math.PI/360)
function Screen({mesh,screen,panel,dispatch,onHover,tableMap,sharp}:{sharp:THREE.CanvasTexture;tableMap:THREE.Texture;mesh:THREE.Mesh;screen:RoomScreen;panel:PanelState;dispatch:Props['dispatch'];onHover:(id:string|null)=>void}){
 const [hot,setHot]=useState(false)
 const material=useMemo(()=>{const m=roomMaterial('screen',sharp);m.uniforms.uDesk.value=screen.kind==='desk'?1:0;m.uniforms.uPhoto.value=tableMap;return m},[sharp,tableMap,screen.kind])
 const {camera,size}=useThree()
 const center=useMemo(()=>new THREE.Vector3(...screen.center),[screen])
 useFrame(()=>{
   // desk consoles always show their live texture; wall displays stay dim until approached
   material.uniforms.uDetail.value=screen.kind==='desk'?1:THREE.MathUtils.smoothstep(screen.w/(2*camera.position.distanceTo(center)*TAN_HALF_FOV*(size.width/size.height))*size.width,screen.rect.w*1.5,screen.rect.w*2.5)
   material.uniforms.uHot.value=(hot||getHovered()===screen.id)&&getInspecting()!==screen.id?1:0 // no glow over a screen being read
 })
 useEffect(()=>()=>{material.dispose()},[material])
 const enabled=panel.phase==='closed'||panel.phase==='focused'
 const hover=(on:boolean)=>{if(!enabled)on=false;setHot(on);onHover(on?screen.id:null);document.body.style.cursor=on?'pointer':''}
 const pick=(e:ThreeEvent<MouseEvent>)=>{e.stopPropagation();if(enabled&&e.delta<=6){hover(false);dispatch({type:'click',id:screen.id})}}
 return <mesh name={mesh.name} geometry={mesh.geometry} material={material} visible={!(panel.phase==='focused'&&panel.screen===screen.id)}
   onPointerOver={e=>{e.stopPropagation();hover(true)}} onPointerOut={()=>hover(false)} onClick={pick}/>
}
function Assets({panel,dispatch,host,onReady}:Props){
 const {scene}=useGLTF('/models/reference-room.glb')
 const tableMap=useTexture('/textures/desk-reference-material.png')
 tableMap.colorSpace=THREE.NoColorSpace;tableMap.anisotropy=16
 const ring=useMemo(()=>ringTexture(),[])
 const sharpMap=useMemo(()=>new Map(ROOM_SCREENS.map((s,i)=>[s.id,s.kind==='desk'?ring:displayTexture(s,i)])),[ring])
 const gl=useThree(s=>s.gl)
 useLiveConsoles(ring,gl)
 const wallMap=sharpMap.get('s5')!
 const assets=useMemo(()=>{
   const result:{mesh:THREE.Mesh;kind:string;material:THREE.ShaderMaterial}[]=[]
   scene.traverse(o=>{if(!(o instanceof THREE.Mesh))return;const geometry=o.geometry as Geo;if(!geometry.boundsTree)geometry.boundsTree=new MeshBVH(geometry,{maxLeafTris:12});const kind=o.userData.kind??'wall';result.push({mesh:o,kind,material:roomMaterial(kind,kind==='desk'?tableMap:kind==='wall'?wallMap:undefined)})})
   return result
 },[scene,tableMap,wallMap])
 useEffect(()=>()=>{for(const a of assets)a.material.dispose();tableMap.dispose();for(const texture of sharpMap.values())texture.dispose();document.body.style.cursor=''},[assets,tableMap,sharpMap])
 useFrame(({clock})=>{
   const t=clock.getElapsedTime();for(const a of assets)a.material.uniforms.uTime.value=t
 })
 useEffect(()=>{if(panel.phase!=='closed'&&panel.phase!=='focused'){setHovered(null);document.body.style.cursor=''}},[panel.phase])
 useEffect(()=>{onReady(true)},[onReady])
 const deskStation=(e:ThreeEvent<PointerEvent|MouseEvent>)=>panel.phase==='closed'?deskScreenAt(e.point):null
 const focused=panel.phase==='focused'&&panel.screen?screenById(panel.screen):undefined
 return <>
  {assets.map(({mesh,kind,material})=>{
    const s=mesh.name.startsWith('screen_')?screenById(mesh.name.slice(7)):undefined
    const frameScreen=mesh.name.startsWith('frame_')?screenById(mesh.name.slice(6)):undefined
    return s?<Screen key={mesh.name} mesh={mesh} screen={s} panel={panel} dispatch={dispatch} onHover={setHovered} tableMap={tableMap} sharp={sharpMap.get(s.canonicalId??s.id)!}/>
     :<group key={mesh.name}><mesh name={mesh.name} geometry={mesh.geometry} material={material} onClick={e=>{e.stopPropagation();const s=frameScreen&&panel.phase==='closed'?frameScreen:kind==='desk'?deskStation(e):null;if(s&&e.delta<=6){setHovered(null);dispatch({type:'click',id:s.id})}}}
        onPointerMove={e=>{if(kind!=='desk'&&!frameScreen)return;e.stopPropagation();const s=frameScreen&&panel.phase==='closed'?frameScreen:deskStation(e);setHovered(s?.id??null);document.body.style.cursor=s?'pointer':''}}
        onPointerOut={()=>{if(kind==='desk'||frameScreen){setHovered(null);document.body.style.cursor=''}}} onPointerOver={e=>e.stopPropagation()}/></group>
  })}
  {focused&&<Preview screen={focused} host={host}/>}

 </>
}
// Development-only handle for headless visual checks (camera poses, raycast click tests).
function DevHandle({controls}:{controls:React.RefObject<Controls|null>}){
 const state=useThree()
 useEffect(()=>{if(!import.meta.env.DEV)return;(window as unknown as {__room3d?:unknown}).__room3d={camera:state.camera,scene:state.scene,gl:state.gl,controls:controls.current,THREE};return()=>{delete (window as unknown as {__room3d?:unknown}).__room3d}},[state.camera,state.scene,state.gl,controls])
 return null
}
export function RoomScene(props:Props){
 const controls=useRef<Controls>(null)
 const fx=new URLSearchParams(window.location.search).get('fx')!=='low'
 return <><Canvas className="room-canvas" dpr={[1,1.5]} camera={{position:HOME.position,fov:48,near:.05,far:80}} gl={{antialias:true,powerPreference:'high-performance'}}>
  <color attach="background" args={['#02040a']}/>
  <Suspense fallback={null}><Assets {...props}/></Suspense>
  <OrbitControls ref={controls} makeDefault target={HOME.target} enablePan enableZoom={false} screenSpacePanning enableDamping dampingFactor={.10}
   minDistance={.05} maxDistance={ZOOM.maxDistance} minPolarAngle={.05} maxPolarAngle={2.0} enabled={props.panel.phase==='closed'}/>
  <SmoothZoom controls={controls} enabled={props.panel.phase==='closed'} resetKey={props.resetKey}/>
  <CameraRig panel={props.panel} dispatch={props.dispatch} controls={controls} resetKey={props.resetKey}/>
  {import.meta.env.DEV&&<DevHandle controls={controls}/>}
  <LabelProjector hidden={props.panel.phase!=='closed'}/>
  <EffectComposer depthBuffer multisampling={0}>
   <Beam/>
   {fx?<Bloom intensity={.55} luminanceThreshold={.20} mipmapBlur resolutionScale={.5}/>:<></>}
  </EffectComposer>
 </Canvas></>
}
