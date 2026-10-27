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
import { HOME, flightDistance, inRoom, ZOOM } from './camera'
import type { Asset, Bar, Timeframe } from '../model/types'
import { SEATS } from '../config/seats'
import { api } from '../net/api'
import { CameraRig } from './CameraRig'
import { roomMaterial } from './material'
import { Beam } from './Beam'
import { LabelProjector, setHovered, getHovered } from './labels'

THREE.Mesh.prototype.raycast=acceleratedRaycast
type Props={panel:PanelState;dispatch:(a:PanelAction)=>void;host:HTMLElement;resetKey:number;onReady:(ready:boolean)=>void}
type Geo=THREE.BufferGeometry&{boundsTree?:MeshBVH}

// ---------------------------------------------------------------------------------------------
// Display graphics. Each canvas has the physical aspect of its monitor (the old shared 16:9 chart
// was stretched up to 4.6x on the tall s8/s9 panels), a title bar, axes and readable labels.
function rng(seed:number){return()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}}
const PURPLE='#9b7bff',BLUE='#3d8bff',CYAN='#5fd0ff',TEXT='#86a9d6',GRID='#0d1d38'
function displayTexture(screen:RoomScreen,index:number){
 const aspect=screen.w/screen.h,long=1536
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
// Live desk consoles, drawn into each console's own screen texture (no DOM overlay). Data is read
// only from the existing engine API the panels use: /api/health (heartbeat, keys) and /api/bars
// (each agent's market feed). There is no agent runtime yet, so every agent reports IDLE honestly;
// the feed panel, its indicator read-outs and the clock update live. Redrawn once a second.
type Engine={state:'checking'|'up'|'down';keys:boolean;at:number;latency:number[]}
type Feed={asset:Asset;symbol:string;tf:Timeframe;days:number;focus:string}
const FEEDS:Record<string,Feed>={
 scanner:{asset:'etfs',symbol:'QQQ',tf:'1Min',days:4,focus:'MOVE SCAN'},
 strategist:{asset:'etfs',symbol:'SPY',tf:'5Min',days:6,focus:'SMA 9 / 21'},
 backtester:{asset:'crypto',symbol:'BTC/USD',tf:'1Min',days:1,focus:'REPLAY FEED'},
 auditor:{asset:'etfs',symbol:'IWM',tf:'15Min',days:8,focus:'DATA CHECKS'},
 regime:{asset:'etfs',symbol:'SPY',tf:'1Day',days:150,focus:'REGIME READ'},
 risk:{asset:'crypto',symbol:'ETH/USD',tf:'1Min',days:1,focus:'RISK READ'},
}
const STEP_MS:Record<Timeframe,number>={'1Min':6e4,'5Min':3e5,'15Min':9e5,'1Hour':36e5,'1Day':864e5}
type FeedState={bars:Bar[];at:number;error?:string}
const live={engine:{state:'checking',keys:false,at:0,latency:[]} as Engine,feeds:new Map<string,FeedState>()}
const day=(ms:number)=>new Date(ms).toISOString().slice(0,10)
async function pollFeed(seat:string){
 const f=FEEDS[seat],now=Date.now()
 try{const r=await api.bars(f.asset,f.symbol,f.tf,day(now-f.days*864e5),day(now))
  live.feeds.set(seat,{bars:r.bars.filter(b=>Date.parse(b.t)<=now).slice(-90),at:Date.now()})} // never show bars from the future
 catch(e){live.feeds.set(seat,{bars:live.feeds.get(seat)?.bars??[],at:Date.now(),error:(e as {code?:string}).code??'ERROR'})}
}
async function pollHealth(){const t0=performance.now()
 try{const h=await api.health();const e=live.engine;live.engine={state:'up',keys:h.alpaca_keys_present,at:Date.now(),latency:[...e.latency,performance.now()-t0].slice(-40)}}
 catch{live.engine={...live.engine,state:'down',at:Date.now()}}}
const sma=(v:number[],n:number)=>v.map((_,i)=>i+1<n?NaN:v.slice(i+1-n,i+1).reduce((a,b)=>a+b)/n)
const stdev=(v:number[])=>{const m=v.reduce((a,b)=>a+b,0)/v.length;return Math.sqrt(v.reduce((a,b)=>a+(b-m)**2,0)/Math.max(1,v.length-1))}
const hhmmss=(ms:number)=>new Date(ms).toLocaleTimeString([],{hour12:false})
const fmt=(v:number)=>v>=1000?v.toLocaleString(undefined,{maximumFractionDigits:0}):v.toFixed(2)
/** Role read-outs computed from the feed's bars (indicator values, not agent decisions). */
function readouts(seat:string,bars:Bar[],tf:Timeframe,now:number):[string,string,string?][]{
 const c=bars.map(b=>b.c),last=c.at(-1)!,first=c[0],ch=(last/first-1)*100,ret=c.slice(1).map((v,i)=>Math.log(v/c[i]))
 const sign=(v:number)=>(v>=0?'+':'')+v.toFixed(2)+'%'
 switch(seat){
  case 'scanner':{const vol=bars.map(b=>b.v),avg=vol.slice(0,-1).reduce((a,b)=>a+b,0)/Math.max(1,vol.length-1),hi=Math.max(...bars.map(b=>b.h)),lo=Math.min(...bars.map(b=>b.l))
   return[['Window move',sign(ch),ch>=0?CYAN:PURPLE],['Range',`${fmt(lo)} – ${fmt(hi)}`],['Last bar volume',`${(vol.at(-1)!/avg).toFixed(2)}× avg`]]}
  case 'strategist':{const a=sma(c,9).at(-1)!,b=sma(c,21).at(-1)!
   return[['SMA 9',fmt(a)],['SMA 21',fmt(b)],['State',a>b?'9 ABOVE 21':'9 BELOW 21',a>b?CYAN:PURPLE]]}
  case 'backtester':return[['Bars buffered',String(bars.length)],['Last close',fmt(last)],['Backtest','none running']]
  case 'auditor':{let gaps=0;for(let i=1;i<bars.length;i++)if(Date.parse(bars[i].t)-Date.parse(bars[i-1].t)>STEP_MS[tf]*1.5)gaps++
   const age=Math.round((now-Date.parse(bars.at(-1)!.t))/6e4)
   return[['Bars checked',String(bars.length)],['Session gaps',String(gaps)],['Last bar age',age<120?`${age} min`:`${Math.round(age/60)} h`]]}
  case 'regime':{const r20=(last/c[Math.max(0,c.length-21)]-1)*100,v=stdev(ret.slice(-20))*Math.sqrt(252)*100
   return[['20-bar return',sign(r20),r20>=0?CYAN:PURPLE],['Realised vol',v.toFixed(1)+'%'],['Read',Math.abs(r20)<2?'RANGE':r20>0?'TREND UP':'TREND DOWN',r20>=0?CYAN:PURPLE]]}
  default:{let peak=-Infinity,dd=0;for(const v of c){peak=Math.max(peak,v);dd=Math.min(dd,v/peak-1)}
   return[['Max drawdown',(dd*100).toFixed(2)+'%',PURPLE],['Bar σ',(stdev(ret)*100).toFixed(3)+'%'],['Limits','none set']]}
 }
}
function drawConsole(t:THREE.CanvasTexture,screen:RoomScreen,now:number){
 const canvas=t.image as HTMLCanvasElement,c=canvas.getContext('2d')!,W=canvas.width,H=canvas.height,u=H/100,e=live.engine
 const seat=screen.seat?SEATS.find(x=>x.id===screen.seat):undefined,feed=seat?FEEDS[seat.id]:undefined,fs=seat?live.feeds.get(seat.id):undefined
 c.fillStyle='#040a1a';c.fillRect(0,0,W,H)
 c.textBaseline='middle';c.textAlign='left'
 // header: agent, state, clock
 c.fillStyle='#0b1a36';c.fillRect(0,0,W,10*u)
 c.fillStyle='#e4f0ff';c.font=`700 ${5*u}px system-ui,sans-serif`;c.fillText(seat?seat.name:`DESK SCREEN ${screen.n}`,2.5*u,5.2*u)
 c.textAlign='right';c.font=`600 ${4.4*u}px ui-monospace,monospace`;c.fillStyle='#cfe6ff';c.fillText(hhmmss(now),W-2.5*u,5.2*u)
 // engine strip
 const dot=e.state==='up'?'#38e6a0':e.state==='down'?'#ff5a7a':'#f3c74b'
 c.textAlign='left';c.fillStyle=dot;c.beginPath();c.arc(3.6*u,14.5*u,1.3*u,0,7);c.fill()
 c.font=`600 ${3.4*u}px ui-monospace,monospace`;c.fillStyle='#9fc3ee'
 const rt=e.latency.at(-1)
 c.fillText(`ENGINE ${e.state==='up'?'UP':e.state==='down'?'OFFLINE':'…'}${e.state==='up'&&!e.keys?' · NO KEYS':''}${rt!==undefined&&e.state==='up'?` · ${rt.toFixed(0)} ms`:''}`,6*u,14.5*u)
 c.textAlign='right';c.fillStyle=seat?'#f3c74b':'#6d86a8';c.fillText(seat?'IDLE · NO STRATEGY RUNNING':'UNASSIGNED',W-2.5*u,14.5*u)
 c.textAlign='left'
 const box=(x:number,y:number,w:number,h:number)=>{c.strokeStyle='#1d3d6c';c.lineWidth=.35*u;c.strokeRect(x,y,w,h)}
 if(!seat||!feed){
  box(2.5*u,20*u,W-5*u,H-23*u)
  c.fillStyle='#cfe3f7';c.font=`600 ${4.6*u}px system-ui,sans-serif`;c.fillText('Not assigned yet',6*u,30*u)
  c.fillStyle='#7f9cc4';c.font=`${3.4*u}px system-ui,sans-serif`;c.fillText('Click to open this screen.',6*u,38*u)
  c.fillText(`Engine checked ${e.at?Math.max(0,Math.round((now-e.at)/1000)):'–'} s ago`,6*u,45*u)
  const L=e.latency;if(L.length>1){const max=Math.max(...L,1);c.strokeStyle=CYAN;c.lineWidth=.4*u;c.beginPath();L.forEach((v,i)=>{const x=6*u+i/(L.length-1)*(W-12*u),y=H-8*u-v/max*25*u;i?c.lineTo(x,y):c.moveTo(x,y)});c.stroke();c.fillStyle='#7f9cc4';c.font=`${2.8*u}px ui-monospace,monospace`;c.fillText('ENGINE ROUND TRIP',6*u,H-38*u)}
  t.needsUpdate=true;return
 }
 // feed panel
 const px=2.5*u,py=20*u,pw=W*.64-px,ph=H-py-3*u
 box(px,py,pw,ph)
 c.fillStyle='#9fc3ee';c.font=`600 ${3.4*u}px ui-monospace,monospace`;c.fillText(`${feed.symbol} · ${feed.tf}`,px+2*u,py+4*u)
 const bars=fs?.bars??[]
 if(bars.length>1){
  const last=bars.at(-1)!,lo=Math.min(...bars.map(b=>b.l)),hi=Math.max(...bars.map(b=>b.h)),cx=px+2*u,cw=pw-12*u,cy=py+9*u,ch=ph-17*u
  const Y=(v:number)=>cy+ch*(1-(v-lo)/Math.max(1e-9,hi-lo))
  c.textAlign='right';c.fillStyle=last.c>=bars[0].c?CYAN:PURPLE;c.font=`700 ${4.2*u}px ui-monospace,monospace`;c.fillText(fmt(last.c),px+pw-2*u,py+4*u);c.textAlign='left'
  c.strokeStyle=GRID;c.lineWidth=.2*u;for(let i=0;i<=4;i++){const y=cy+ch*i/4;c.beginPath();c.moveTo(cx,y);c.lineTo(cx+cw,y);c.stroke()}
  const n=bars.length,bw=cw/n
  bars.forEach((b,i)=>{const x=cx+(i+.5)*bw,up=b.c>=b.o;c.strokeStyle=c.fillStyle=up?CYAN:PURPLE;c.lineWidth=Math.max(1,.18*u);c.beginPath();c.moveTo(x,Y(b.h));c.lineTo(x,Y(b.l));c.stroke();c.fillRect(x-bw*.32,Math.min(Y(b.o),Y(b.c)),bw*.64,Math.max(1,Math.abs(Y(b.o)-Y(b.c))))})
  if(seat.id==='strategist'){for(const [nn,col] of [[9,'#f3c74b'],[21,'#c9b8ff']] as [number,string][]){const m=sma(bars.map(b=>b.c),nn);c.strokeStyle=col;c.lineWidth=.4*u;c.beginPath();let on=false;m.forEach((v,i)=>{if(isNaN(v))return;const x=cx+(i+.5)*bw;on?c.lineTo(x,Y(v)):c.moveTo(x,Y(v));on=true});c.stroke()}}
  c.fillStyle='#7f9cc4';c.font=`${2.7*u}px ui-monospace,monospace`;c.textAlign='right';c.fillText(fmt(hi),px+pw-1.2*u,cy+1.5*u);c.fillText(fmt(lo),px+pw-1.2*u,cy+ch-1.5*u);c.textAlign='left'
  c.fillText(`last bar ${new Date(last.t).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})}`,cx,py+ph-3.5*u)
 }else{c.fillStyle='#7f9cc4';c.font=`${3.4*u}px system-ui,sans-serif`;c.fillText(fs?.error?`Feed unavailable (${fs.error})`:'Waiting for engine feed…',px+2*u,py+16*u)}
 // read-outs
 const rx=W*.64+2*u,rw=W-rx-2.5*u
 box(rx,py,rw,ph)
 c.fillStyle='#9fc3ee';c.font=`600 ${3.4*u}px ui-monospace,monospace`;c.fillText(feed.focus,rx+2*u,py+4*u)
 const rows=bars.length>1?readouts(seat.id,bars,feed.tf,now):[]
 rows.forEach(([k,v,col],i)=>{const y=py+13*u+i*13*u;c.fillStyle='#7f9cc4';c.font=`${2.9*u}px system-ui,sans-serif`;c.fillText(k,rx+2*u,y);c.fillStyle=col??'#e4f0ff';c.font=`700 ${4.1*u}px ui-monospace,monospace`;c.fillText(v,rx+2*u,y+5*u)})
 c.fillStyle='#6d86a8';c.font=`${2.7*u}px ui-monospace,monospace`
 c.fillText(fs?`feed ${Math.max(0,Math.round((now-fs.at)/1000))} s ago`:'feed …',rx+2*u,py+ph-9*u)
 c.fillText(seat.job.toLowerCase()+' · awaiting',rx+2*u,py+ph-3.5*u)
 t.needsUpdate=true
}
/** Polls the engine read-only and redraws every desk console's own texture once a second. */
function useLiveConsoles(maps:Map<string,THREE.CanvasTexture>){
 useEffect(()=>{
  const desks=ROOM_SCREENS.filter(s=>s.kind==='desk')
  const draw=()=>{const now=Date.now();for(const s of desks){const t=maps.get(s.id);if(t)drawConsole(t,s,now)}}
  const feeds=()=>{for(const id of Object.keys(FEEDS))pollFeed(id).then(draw)}
  pollHealth().then(draw);feeds();draw()
  const a=setInterval(draw,1000),b=setInterval(pollHealth,3000),f=setInterval(feeds,15000)
  return()=>{clearInterval(a);clearInterval(b);clearInterval(f)}
 },[maps])
}

// ---------------------------------------------------------------------------------------------
// Plain smooth zoom. Wheel, trackpad pinch (ctrl+wheel) and two-finger touch pinch feed one damped
// log-distance accumulator. Camera and orbit target scale together toward the 3D point under the
// cursor, so the view direction never changes: no auto-rotate, no auto re-centre. It stops a
// fixed distance before the surface under the cursor and never leaves the room on the way out.
function SmoothZoom({controls,enabled}:{controls:RefObject<Controls|null>;enabled:boolean}){
 const {camera,gl,scene}=useThree()
 const pending=useRef(0),focus=useRef(new THREE.Vector3(...HOME.target)),surface=useRef(Infinity)
 const ray=useMemo(()=>new THREE.Raycaster(),[])
 const live=useRef(enabled);live.current=enabled
 useEffect(()=>{
  const el=gl.domElement
  const aim=(cx:number,cy:number)=>{
   const r=el.getBoundingClientRect();ray.setFromCamera(new THREE.Vector2((cx-r.left)/r.width*2-1,-(cy-r.top)/r.height*2+1),camera);ray.far=60
   const hit=ray.intersectObjects(scene.children,true).find(h=>h.object.visible&&!((h.object as THREE.Mesh).material as THREE.MeshBasicMaterial)?.wireframe)
   if(hit){focus.current.copy(hit.point);surface.current=hit.distance}
   else{const t=controls.current?.target??new THREE.Vector3(...HOME.target);focus.current.copy(ray.ray.at(camera.position.distanceTo(t),new THREE.Vector3()));surface.current=Infinity}
  }
  const wheel=(e:WheelEvent)=>{if(!live.current)return;e.preventDefault();aim(e.clientX,e.clientY)
   let dy=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?400:1);if(e.ctrlKey)dy*=3
   pending.current=THREE.MathUtils.clamp(pending.current+dy*ZOOM.wheel,-1.2,1.2)}
  let pinch=0
  const touches=(e:TouchEvent)=>{if(e.touches.length!==2){pinch=0;return}const [a,b]=[e.touches[0],e.touches[1]],d=Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY);if(pinch&&live.current){aim((a.clientX+b.clientX)/2,(a.clientY+b.clientY)/2);pending.current=THREE.MathUtils.clamp(pending.current+Math.log(pinch/d),-1.2,1.2)}pinch=d}
  el.addEventListener('wheel',wheel,{passive:false});el.addEventListener('touchstart',touches,{passive:true});el.addEventListener('touchmove',touches,{passive:true});el.addEventListener('touchend',touches)
  return()=>{el.removeEventListener('wheel',wheel);el.removeEventListener('touchstart',touches);el.removeEventListener('touchmove',touches);el.removeEventListener('touchend',touches)}
 },[gl,camera,scene,controls,ray])
 useFrame((_,dt)=>{
  const c=controls.current
  if(!c||!enabled){pending.current=0;return}
  if(Math.abs(pending.current)<1e-4){pending.current=0;return}
  const step=pending.current*(1-Math.exp(-Math.min(dt,.1)*ZOOM.smoothing));pending.current-=step
  let k=Math.exp(step)
  const F=focus.current,pos=camera.position,dist=pos.distanceTo(F)
  const at=(kk:number)=>F.clone().add(pos.clone().sub(F).multiplyScalar(kk))
  if(k<1&&dist*k<ZOOM.minSurface){k=Math.min(1,ZOOM.minSurface/dist);pending.current=0}
  if(k>1&&(!inRoom(at(k))||dist*k>ZOOM.maxDistance)){let lo=1,hi=k;for(let i=0;i<14;i++){const mid=(lo+hi)/2;if(inRoom(at(mid))&&dist*mid<=ZOOM.maxDistance)lo=mid;else hi=mid}k=lo;pending.current=0}
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
function Screen({mesh,screen,panel,dispatch,onHover,tableMap,sharp}:{sharp:THREE.CanvasTexture;tableMap:THREE.Texture;mesh:THREE.Mesh;screen:RoomScreen;panel:PanelState;dispatch:Props['dispatch'];onHover:(id:string|null)=>void}){
 const [hot,setHot]=useState(false)
 const material=useMemo(()=>{const m=roomMaterial('screen',sharp);m.uniforms.uDesk.value=screen.kind==='desk'?1:0;m.uniforms.uPhoto.value=tableMap;return m},[sharp,tableMap,screen.kind])
 const {camera,size}=useThree()
 useFrame(()=>{
   const projected=screen.w/(2*camera.position.distanceTo(new THREE.Vector3(...screen.center))*Math.tan(48*Math.PI/360)*(size.width/size.height))*size.width
   // desk consoles always show their live texture; wall displays stay dim until approached
   material.uniforms.uDetail.value=screen.kind==='desk'?1:THREE.MathUtils.smoothstep(projected,screen.rect.w*1.5,screen.rect.w*2.5)
   if(screen.kind==='desk'){ // a flat console reads upright from whichever side of the desk you look at it
    const q=new THREE.Quaternion(...screen.quaternion),up=new THREE.Vector3(0,1,0).applyQuaternion(q),side=camera.position.clone().sub(new THREE.Vector3(...screen.center)).dot(up)
    if(Math.abs(side)>.05)material.uniforms.uFlip.value=side>0?1:0
   }
   material.uniforms.uHot.value=hot||getHovered()===screen.id?1:0
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
 const sharpMap=useMemo(()=>new Map(ROOM_SCREENS.map((s,i)=>[s.id,displayTexture(s,i)])),[])
 useLiveConsoles(sharpMap)
 const wallMap=sharpMap.get('s5')!
 const wireMaterial=useMemo(()=>new THREE.MeshBasicMaterial({color:'#49baff',wireframe:true,transparent:true,opacity:.012,depthWrite:false,blending:THREE.AdditiveBlending,polygonOffset:true,polygonOffsetFactor:-1}),[])
 const assets=useMemo(()=>{
   const result:{mesh:THREE.Mesh;kind:string;material:THREE.ShaderMaterial}[]=[]
   scene.traverse(o=>{if(!(o instanceof THREE.Mesh))return;const geometry=o.geometry as Geo;if(!geometry.boundsTree)geometry.boundsTree=new MeshBVH(geometry,{maxLeafTris:12});const kind=o.userData.kind??'wall';result.push({mesh:o,kind,material:roomMaterial(kind,kind==='desk'?tableMap:kind==='wall'?wallMap:undefined)})})
   return result
 },[scene,tableMap,wallMap])
 useEffect(()=>()=>{for(const a of assets)a.material.dispose();tableMap.dispose();for(const texture of sharpMap.values())texture.dispose();wireMaterial.dispose();document.body.style.cursor=''},[assets,tableMap,sharpMap,wireMaterial])
 useFrame(({clock})=>{
   for(const a of assets)a.material.uniforms.uTime.value=clock.getElapsedTime()
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
        onPointerOut={()=>{if(kind==='desk'||frameScreen){setHovered(null);document.body.style.cursor=''}}} onPointerOver={e=>e.stopPropagation()}/>{kind==='hologram'&&<mesh geometry={mesh.geometry} material={wireMaterial} raycast={()=>null}/>}</group>
  })}
  {focused&&<Preview screen={focused} host={host}/>}

 </>
}
// Development-only handle for headless visual checks (camera poses, raycast click tests).
function DevHandle({controls}:{controls:React.RefObject<Controls|null>}){
 const state=useThree()
 useEffect(()=>{if(!import.meta.env.DEV)return;(window as unknown as {__room3d?:unknown}).__room3d={camera:state.camera,scene:state.scene,gl:state.gl,controls:controls.current};return()=>{delete (window as unknown as {__room3d?:unknown}).__room3d}},[state.camera,state.scene,state.gl,controls])
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
  <SmoothZoom controls={controls} enabled={props.panel.phase==='closed'}/>
  <CameraRig panel={props.panel} dispatch={props.dispatch} controls={controls} resetKey={props.resetKey}/>
  {import.meta.env.DEV&&<DevHandle controls={controls}/>}
  <LabelProjector hidden={props.panel.phase!=='closed'}/>
  <EffectComposer depthBuffer multisampling={0}>
   <Beam/>
   {fx?<Bloom intensity={.55} luminanceThreshold={.20} mipmapBlur/>:<></>}
  </EffectComposer>
 </Canvas></>
}
