import { useMemo, useState } from 'react'
import { Html } from '@react-three/drei'
import { useThree, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'
import { SCREENS, screenName, type Screen3D } from '../config/screens3d'
import { flyDistance, htmlDistanceFactor, projectedWidthPx } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'
import { Slot } from '../panels/Slot'
import { summaryTexture } from './Table'
import { restTexture } from './textures'

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const
/** Pointer travel (px) above which a press is a drag of the view, not a click. */
const DRAG_PX = 6

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void; host: HTMLElement; onHover: (id: string | null) => void }

function Screen({ s, index, hot, live, onHot, onPick }: { s: Screen3D; index: number; hot: boolean; live: boolean; onHot: (on: boolean) => void; onPick: () => void }) {
  const tex = useMemo(() => s.id === 'd8' ? summaryTexture() : restTexture(s.w, s.h, index % 4 === 3 ? '#a98bff' : '#5fc8ff', 300 + index), [s, index])
  const click = (e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); if (e.delta <= DRAG_PX) onPick() }
  return (
    <group position={s.center} rotation={[-s.pitch, s.yaw, 0, 'YXZ']}>
      <mesh position-z={-0.02}>
        <planeGeometry args={[s.w + 0.08, s.h + 0.08]} />
        <meshBasicMaterial color={0x7fd8ff} opacity={hot ? 0.45 : 0} {...additive} />
      </mesh>
      <mesh onClick={click} onPointerOver={e => { e.stopPropagation(); onHot(true) }} onPointerOut={() => onHot(false)}>
        <planeGeometry args={[s.w, s.h]} />
        <meshBasicMaterial map={tex} opacity={live ? 0 : hot ? 1 : 0.85} {...additive} />
      </mesh>
      {hot && !live && <Html position={[0, s.h / 2 + 0.12, 0]} center className="screentag3d" pointerEvents="none">{screenName(s)}</Html>}
    </group>
  )
}

/** Live preview on the focused screen: real DOM, sized so it is drawn at about 1:1 on the display. */
function Preview({ s, host, dispatch }: { s: Screen3D; host: HTMLElement; dispatch: Props['dispatch'] }) {
  const { camera, size } = useThree()
  const fov = (camera as THREE.PerspectiveCamera).fov, aspect = size.width / Math.max(1, size.height)
  const px = projectedWidthPx(s.w, flyDistance(s.w, s.h, fov, aspect), fov, aspect, size.width)
  const rotation = useMemo(() => new THREE.Euler(-s.pitch, s.yaw, 0, 'YXZ'), [s])
  return (
    <Html transform position={s.center} rotation={rotation} distanceFactor={htmlDistanceFactor(s.w, px)} zIndexRange={[20, 10]}>
      <div className="screenpreview" style={{ width: px, height: (px * s.h) / s.w }}
        onDoubleClick={e => { if ((e.target as HTMLElement).closest('header')) dispatch({ type: 'expand' }) }}>
        <Slot host={host} className="slotfill" />
      </div>
    </Html>
  )
}

/** All 26 screens: click to fly in, hover to glow and show the name; the focused one shows the live preview. */
export function Screens({ panel, dispatch, host, onHover }: Props) {
  const [hot, setHot] = useState<string | null>(null)
  const canPick = panel.phase === 'closed' || panel.phase === 'focused'
  const setHover = (id: string | null) => { setHot(id); onHover(id); document.body.style.cursor = id ? 'pointer' : '' }
  const focused = panel.phase === 'focused' ? SCREENS.find(s => s.id === panel.screen) : undefined
  return (
    <group>
      {SCREENS.map((s, i) => (
        <Screen key={s.id} s={s} index={i} hot={hot === s.id && canPick} live={focused?.id === s.id}
          onHot={on => setHover(on && canPick ? s.id : hot === s.id ? null : hot)}
          onPick={() => { if (canPick && panel.screen !== s.id) { setHover(null); dispatch({ type: 'click', id: s.id }) } }} />
      ))}
      {focused && <Preview s={focused} host={host} dispatch={dispatch} />}
    </group>
  )
}
