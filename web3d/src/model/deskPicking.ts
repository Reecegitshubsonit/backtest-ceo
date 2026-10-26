import { ROOM_SCREENS } from '../config/roomScreens'
/** The entire instrument annulus belongs to the nearest console, including its fine secondary displays. */
export function deskScreenAt({x,y,z}:{x:number;y:number;z:number}) {
 const r=Math.hypot(x,z)
 if(y<1.55||y>1.65||r<1.4||r>2.8)return null
 const a=Math.atan2(x,z)
 const distance=(s:typeof ROOM_SCREENS[number])=>{
  const delta=a-Math.atan2(s.center[0],s.center[2])
  return Math.abs(Math.atan2(Math.sin(delta),Math.cos(delta)))
 }
 return ROOM_SCREENS.filter(s=>s.kind==='desk').reduce((best,s)=>distance(s)<distance(best)?s:best)
}
