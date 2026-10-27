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
import type { Asset, Bar, Timeframe } from '../model/types'
import { SEATS } from '../config/seats'
import { api } from '../net/api'
import { CameraRig } from './CameraRig'
import { roomMaterial } from './material'
import { Beam } from './Beam'
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
const live={engine:{state:'checking',keys:false,at:0,latency:[]} as Engine,feeds:new Map<string,FeedState>(),log:new Map<string,string[]>()}
/** Per-console activity log (engine and feed events as they happen); 'engine' is shared by every console. */
function note(key:string,line:string){const l=live.log.get(key)??[];if(l[0]?.slice(9)===line)return;l.unshift(`${hhmmss(Date.now())} ${line}`);live.log.set(key,l.slice(0,8))}
const day=(ms:number)=>new Date(ms).toISOString().slice(0,10)
async function pollFeed(seat:string){
 const f=FEEDS[seat],now=Date.now()
 try{const r=await api.bars(f.asset,f.symbol,f.tf,day(now-f.days*864e5),day(now))
  const bars=r.bars.filter(b=>Date.parse(b.t)<=now).slice(-90) // never show bars from the future
  live.feeds.set(seat,{bars,at:Date.now()});note(seat,bars.length?`${f.symbol} ${f.tf} · ${bars.length} bars · last ${fmt(bars.at(-1)!.c)}`:`${f.symbol} ${f.tf} · no bars in window`)}
 catch(e){const code=(e as {code?:string}).code??'ERROR';live.feeds.set(seat,{bars:live.feeds.get(seat)?.bars??[],at:Date.now(),error:code});note(seat,`${f.symbol} feed failed (${code})`)}
}
async function pollHealth(){const t0=performance.now()
 try{const h=await api.health();const e=live.engine;live.engine={state:'up',keys:h.alpaca_keys_present,at:Date.now(),latency:[...e.latency,performance.now()-t0].slice(-40)};if(e.state!=='up')note('engine',`engine up${h.alpaca_keys_present?'':' · alpaca keys missing'}`)}
 catch{if(live.engine.state!=='down')note('engine','engine unreachable');live.engine={...live.engine,state:'down',at:Date.now()}}}
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
// One agent's work area on the ring computer, drawn into its own offscreen block (top = toward the
// CEO) and then blended into the ring with soft edges. Panels are glass tints, not framed monitors.
function drawConsole(canvas:HTMLCanvasElement,screen:RoomScreen,now:number){
 const c=canvas.getContext('2d')!,W=canvas.width,H=canvas.height,u=H/100,e=live.engine
 const seat=screen.seat?SEATS.find(x=>x.id===screen.seat):undefined,feed=seat?FEEDS[seat.id]:undefined,fs=seat?live.feeds.get(seat.id):undefined
 const inset=0,m=4*u
 const xl=(y:number)=>inset*(1-y/H)+m,xr=(y:number)=>W-xl(y)
 /** A panel between rows y0..y1 spanning fractions a..b of the usable width; returns its inscribed rect. */
 const zone=(y0:number,y1:number,a:number,b:number,label?:string,accent='#2b6fc0')=>{
  const L=(y:number)=>xl(y)+a*(xr(y)-xl(y))+(a>0?.6*u:0),R=(y:number)=>xl(y)+b*(xr(y)-xl(y))-(b<1?.6*u:0)
  c.beginPath();c.moveTo(L(y0),y0);c.lineTo(R(y0),y0);c.lineTo(R(y1),y1);c.lineTo(L(y1),y1);c.closePath()
  c.fillStyle='#0a1d4266';c.fill();c.globalAlpha=.45;c.strokeStyle=accent;c.lineWidth=.25*u;c.stroke();c.globalAlpha=1
  const x0=Math.max(L(y0),L(y1)),x1=Math.min(R(y0),R(y1))
  if(label){c.fillStyle='#8fb4e0';c.font=`600 ${2.8*u}px ui-monospace,monospace`;c.textAlign='left';c.fillText(label,x0+1.4*u,y0+3.2*u)}
  return {x:x0+1.4*u,y:y0+(label?6*u:1.5*u),w:x1-x0-2.8*u,h:y1-y0-(label?7.5*u:3*u)}
 }
 const text=(v:string,x:number,y:number,size:number,color:string,align:CanvasTextAlign='left',weight=400,mono=true,max?:number)=>{c.textAlign=align;c.fillStyle=color;c.font=`${weight} ${size*u}px ${mono?'ui-monospace,monospace':'system-ui,sans-serif'}`;c.fillText(v,x,y,max)}
 // a soft pool of light under the work area; its edges are feathered into the ring by drawRing()
 c.clearRect(0,0,W,H);c.textBaseline='middle'
 const g=c.createRadialGradient(W/2,H*.55,H*.1,W/2,H*.55,Math.max(W,H)*.75);g.addColorStop(0,'#0b2a5ccc');g.addColorStop(1,'#04102a55');c.fillStyle=g;c.fillRect(0,0,W,H)
 // header strip: agent, state, engine, clock
 const dot=e.state==='up'?'#38e6a0':e.state==='down'?'#ff5a7a':'#f3c74b',rt=e.latency.at(-1)
 const hd=zone(2.5*u,19.5*u,0,1,undefined,'#3d8bff')
 const title=seat?seat.name:screen.id==='d8'?'COMMAND CONSOLE':`AUX CONSOLE ${screen.n}`
 text(title,hd.x+.5*u,hd.y+3.6*u,seat||screen.id==='d8'?4.8:4.4,'#e8f3ff','left',700,false)
 text(seat?seat.job.toUpperCase():screen.id==='d8'?'OPERATOR · ALL AGENTS':'UNASSIGNED',hd.x+.5*u,hd.y+8.8*u,2.7,'#7fa6d6')
 if(seat||screen.id==='d8')text(hhmmss(now),hd.x+hd.w,hd.y+3.6*u,4.6,'#cfe6ff','right',600)
 c.fillStyle=dot;c.beginPath();c.arc(hd.x+1.4*u,hd.y+13.4*u,1.1*u,0,7);c.fill()
 text(`ENGINE ${e.state==='up'?'UP':e.state==='down'?'OFFLINE':'…'}${e.state==='up'&&rt!==undefined?` · ${rt.toFixed(0)} ms`:''}${e.state==='up'&&!e.keys?' · NO KEYS':''}`,hd.x+3.6*u,hd.y+13.4*u,2.7,'#9fc3ee','left',600)
 text(seat?'IDLE · NO STRATEGY RUNNING':screen.id==='d8'?'MONITORING':'STANDBY',hd.x+hd.w,hd.y+8.8*u,2.9,seat?'#f3c74b':'#6d86a8','right',600)
 const Y0=22*u,Y1=70*u,Y2=73*u,Y3=97*u
 const latency=(r:{x:number;y:number;w:number;h:number})=>{const L=e.latency;if(L.length<2)return;const max=Math.max(...L,1);c.strokeStyle=CYAN;c.lineWidth=.4*u;c.beginPath();L.forEach((v,i)=>{const x=r.x+i/(L.length-1)*r.w,y=r.y+r.h-v/max*r.h*.9;i?c.lineTo(x,y):c.moveTo(x,y)});c.stroke();text(`max ${max.toFixed(0)} ms`,r.x+r.w,r.y+1.5*u,2.4,'#7f9cc4','right')}
 const logLines=(r:{x:number;y:number;w:number;h:number},keys:string[])=>{
  const lines=keys.flatMap(k=>live.log.get(k)??[]).sort().reverse(),n=Math.max(1,Math.floor(r.h/(3.6*u)))
  if(!lines.length)text('waiting for first event…',r.x,r.y+1.8*u,2.8,'#6d86a8')
  lines.slice(0,n).forEach((l,i)=>{text(l.slice(0,8),r.x,r.y+1.8*u+i*3.6*u,2.7,'#6d86a8');text(l.slice(9),r.x+15*u,r.y+1.8*u+i*3.6*u,2.7,i?'#9fb9dc':'#d6e8ff','left',400,true,r.w-15*u)})
 }
 if(seat&&feed){
  // chart panel: the agent's live feed
  const ch=zone(Y0,Y1,0,.64,`${feed.symbol} · ${feed.tf}`)
  const bars=fs?.bars??[]
  if(bars.length>1){
   const last=bars.at(-1)!,lo=Math.min(...bars.map(b=>b.l)),hi=Math.max(...bars.map(b=>b.h)),cw=ch.w-9*u,cy=ch.y+1*u,chh=ch.h-6*u
   const Y=(v:number)=>cy+chh*(1-(v-lo)/Math.max(1e-9,hi-lo))
   text(fmt(last.c),ch.x+ch.w,ch.y-2.8*u,4,last.c>=bars[0].c?CYAN:PURPLE,'right',700)
   c.strokeStyle=GRID;c.lineWidth=.2*u;for(let i=0;i<=4;i++){const y=cy+chh*i/4;c.beginPath();c.moveTo(ch.x,y);c.lineTo(ch.x+cw,y);c.stroke()}
   const n=bars.length,bw=cw/n
   bars.forEach((b,i)=>{const x=ch.x+(i+.5)*bw,up=b.c>=b.o;c.strokeStyle=c.fillStyle=up?CYAN:PURPLE;c.lineWidth=Math.max(1,.18*u);c.beginPath();c.moveTo(x,Y(b.h));c.lineTo(x,Y(b.l));c.stroke();c.fillRect(x-bw*.32,Math.min(Y(b.o),Y(b.c)),bw*.64,Math.max(1,Math.abs(Y(b.o)-Y(b.c))))})
   if(seat.id==='strategist')for(const [nn,col] of [[9,'#f3c74b'],[21,'#c9b8ff']] as [number,string][]){const mm=sma(bars.map(b=>b.c),nn);c.strokeStyle=col;c.lineWidth=.4*u;c.beginPath();let on=false;mm.forEach((v,i)=>{if(isNaN(v))return;const x=ch.x+(i+.5)*bw;on?c.lineTo(x,Y(v)):c.moveTo(x,Y(v));on=true});c.stroke()}
   text(fmt(hi),ch.x+ch.w,cy+1.2*u,2.5,'#7f9cc4','right');text(fmt(lo),ch.x+ch.w,cy+chh-1.2*u,2.5,'#7f9cc4','right')
   text(`last bar ${new Date(last.t).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})}`,ch.x,ch.y+ch.h-1.5*u,2.5,'#7f9cc4')
  }else text(fs?.error?`Feed unavailable (${fs.error})`:'Waiting for engine feed…',ch.x,ch.y+6*u,3.2,'#7f9cc4','left',400,false)
  // key numbers
  const kn=zone(Y0,Y1,.64,1,feed.focus,'#6a4fd0')
  const rows=bars.length>1?readouts(seat.id,bars,feed.tf,now):[]
  rows.forEach(([k,v,col],i)=>{const y=kn.y+2*u+i*12*u;text(k,kn.x,y,2.7,'#7f9cc4','left',400,false);text(v,kn.x,y+5*u,4.2,col??'#e4f0ff','left',700)})
  text(fs?`feed ${Math.max(0,Math.round((now-fs.at)/1000))} s ago`:'feed …',kn.x,kn.y+kn.h-1*u,2.5,'#6d86a8')
  // activity log + task status, across the wide agent-side edge
  logLines(zone(Y2,Y3,0,.62,'ACTIVITY LOG'),[seat.id,'engine'])
  const st=zone(Y2,Y3,.62,1,'TASK','#6a4fd0')
  text('No strategy assigned',st.x,st.y+2*u,3,'#cfe3f7','left',600,false,st.w)
  text(seat.job.toLowerCase()+' · awaiting work',st.x,st.y+7*u,2.6,'#7f9cc4','left',400,false,st.w)
  text('Click to open this agent',st.x,st.y+12*u,2.6,'#5f7ea6','left',400,false,st.w)
 }else if(screen.id==='d8'){
  // the operator's console: every agent's feed at a glance
  const tb=zone(Y0,Y1,0,.66,'AGENTS')
  SEATS.forEach((a,i)=>{const f=FEEDS[a.id],b=live.feeds.get(a.id)?.bars??[],y=tb.y+2*u+i*(tb.h-2*u)/6,last=b.at(-1),ch=b.length>1?(last!.c/b[0].c-1)*100:NaN
   text(a.name,tb.x,y,2.8,'#d6e8ff','left',600,false);text(`${f.symbol} ${f.tf}`,tb.x+tb.w*.45,y,2.6,'#8fb4e0')
   text(last?fmt(last.c):'—',tb.x+tb.w*.78,y,2.8,'#e4f0ff','right',700);text(isNaN(ch)?'':(ch>=0?'+':'')+ch.toFixed(2)+'%',tb.x+tb.w,y,2.6,ch>=0?CYAN:PURPLE,'right')})
  const lt=zone(Y0,Y1,.66,1,'ENGINE ROUND TRIP','#6a4fd0');latency({x:lt.x,y:lt.y+2*u,w:lt.w,h:lt.h-6*u})
  text(e.keys?'Alpaca keys present':'Alpaca keys missing',lt.x,lt.y+lt.h-1*u,2.5,e.keys?'#38e6a0':'#f3c74b')
  logLines(zone(Y2,Y3,0,1,'ACTIVITY LOG'),['engine',...SEATS.map(a=>a.id)])
 }else{
  const lt=zone(Y0,Y1,0,1,'ENGINE ROUND TRIP');latency({x:lt.x,y:lt.y+2*u,w:lt.w,h:lt.h-4*u})
  const nt=zone(Y2,Y3,0,1,'STATUS');text('Not assigned yet · click to open',nt.x,nt.y+2*u,3,'#cfe3f7','left',600,false)
  text(`engine checked ${e.at?Math.max(0,Math.round((now-e.at)/1000)):'–'} s ago`,nt.x,nt.y+7*u,2.6,'#7f9cc4')
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
type Block={screen:RoomScreen;canvas:HTMLCanvasElement;mask:HTMLCanvasElement;theta:number;x:number;y:number;box:{x:number;y:number;w:number;h:number};patch:THREE.CanvasTexture;at:THREE.Vector2}
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
  return {screen,canvas,mask,theta,x,y,box,patch,at:new THREE.Vector2(box.x,RING_PX-box.y-box.h)} // flipY: GL rows count from the bottom
 })
}
/** Composite one live region onto the CPU ring canvas over a fresh copy of the static base. */
function composeBlock(c:CanvasRenderingContext2D,base:HTMLCanvasElement,b:Block,now:number){
 drawConsole(b.canvas,b.screen,now)
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
  const tick=()=>{
   const t0=performance.now(),b=blocks[next++%blocks.length];composeBlock(c,base,b,Date.now())
   const pc=b.patch.image as HTMLCanvasElement,p=pc.getContext('2d')!
   p.globalCompositeOperation='copy';p.drawImage(cv,b.box.x,b.box.y,b.box.w,b.box.h,0,0,b.box.w,b.box.h)
   const t1=performance.now()
   if(uploaded)gl.copyTextureToTexture(b.patch,ring,null,b.at) // before the first upload the full canvas goes up anyway
   if(import.meta.env.DEV)Object.assign(window,{__ringTickMs:{draw:t1-t0,uploadCall:performance.now()-t1}})
  }
  if(import.meta.env.DEV)Object.assign(window,{__ringTick:tick,__ringBoxes:blocks.map(b=>[b.box.w,b.box.h])}) // perf probes
  const feeds=()=>{for(const id of Object.keys(FEEDS))pollFeed(id)}
  pollHealth();feeds()
  // each region once a second, run in the idle time after a frame so it never lands mid-frame
  const idle=(window as unknown as {requestIdleCallback?:(f:()=>void,o:{timeout:number})=>number}).requestIdleCallback
  const a=setInterval(()=>idle?idle(tick,{timeout:200}):tick(),Math.round(1000/blocks.length)),h=setInterval(pollHealth,3000),f=setInterval(feeds,15000)
  return()=>{clearInterval(a);clearInterval(h);clearInterval(f);for(const b of blocks)b.patch.dispose()}
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
