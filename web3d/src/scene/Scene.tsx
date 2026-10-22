import { useEffect, useRef, useState, type RefObject } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { ROOM_R } from '../config/room'
import { SEATS } from '../config/seats'
import { clampToRoom, roomPose, type Vec3 } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'
import { AgentSeat } from './AgentSeat'
import { CameraRig } from './CameraRig'
import { Ceo } from './Ceo'
import { Operator } from './Operator'
import { Room } from './Room'
import { Screens } from './Screens'
import { Table } from './Table'
import { LabelProjector } from './labels'

// glow is on by default (labels are page text, so it does not blur them); ?fx=low turns it off for slow graphics
const FX = new URLSearchParams(window.location.search).get('fx') !== 'low'
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches
/** Auto-rotate starts after this long without touching the room. */
const IDLE_MS = 6000

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void; host: HTMLElement; resetKey: number }

export function Scene({ panel, dispatch, host, resetKey }: Props) {
  const controls = useRef<OrbitControlsImpl>(null)
  const [hover, setHover] = useState<string | null>(null)
  const start = roomPose(window.innerWidth / window.innerHeight)
  return (
    <Canvas className="scene" dpr={[1, 2]} camera={{ position: start.pos, fov: 48, near: 0.05, far: 200 }} gl={{ antialias: true }}>
      <color attach="background" args={['#03050b']} />
      <fogExp2 attach="fog" args={['#03050b', 0.028]} />
      <ambientLight color={0x4060ff} intensity={0.3} />
      <pointLight color={0x5fd8ff} intensity={2.4} distance={14} decay={1} position={[0, 4, 1.5]} />
      <pointLight color={0x3a7bff} intensity={1.8} distance={18} decay={1} position={[0, 6, -6]} />
      <Room />
      <Table />
      <Ceo />
      {SEATS.map((s, i) => <AgentSeat key={s.id} seat={s} index={i} />)}
      <Operator />
      <Screens panel={panel} dispatch={dispatch} host={host} onHover={setHover} />
      <OrbitControls ref={controls} target={start.target} enableDamping enablePan={false} zoomToCursor
        minDistance={1.2} maxDistance={9} minPolarAngle={0.05} maxPolarAngle={1.52}
        autoRotateSpeed={0.35} enabled={panel.phase === 'closed'} />
      <Orbiting controls={controls} panel={panel} hover={hover} resetKey={resetKey} />
      <CameraRig panel={panel} dispatch={dispatch} controls={controls} />
      <LabelProjector />
      {FX && <EffectComposer><Bloom intensity={1.1} luminanceThreshold={0.45} luminanceSmoothing={0.25} mipmapBlur /></EffectComposer>}
    </Canvas>
  )
}

/** Auto-rotates while nobody is touching the room, keeps the camera inside it, and snaps home on reset. */
function Orbiting({ controls, panel, hover, resetKey }: { controls: RefObject<OrbitControlsImpl | null>; panel: PanelState; hover: string | null; resetKey: number }) {
  const { camera, size } = useThree()
  const last = useRef(0)
  useEffect(() => {
    const c = controls.current
    if (!c) return
    const touch = () => { last.current = performance.now() }
    c.addEventListener('start', touch); c.addEventListener('end', touch)
    return () => { c.removeEventListener('start', touch); c.removeEventListener('end', touch) }
  }, [controls])
  useEffect(() => {
    const c = controls.current
    if (!resetKey || !c) return
    const p = roomPose(size.width / Math.max(1, size.height))
    camera.position.set(...p.pos); c.target.set(...p.target); c.update()
    last.current = performance.now()
  }, [resetKey]) // eslint-disable-line react-hooks/exhaustive-deps
  useFrame(() => {
    const c = controls.current
    if (!c || panel.phase !== 'closed') { if (c) c.autoRotate = false; return }
    c.autoRotate = !hover && !REDUCED && performance.now() - last.current > IDLE_MS
    camera.position.set(...clampToRoom(camera.position.toArray() as Vec3, ROOM_R - 0.7, 0.4, 7.6))
    c.target.set(...clampToRoom(c.target.toArray() as Vec3, 6, 0.6, 6))
  })
  return null
}
