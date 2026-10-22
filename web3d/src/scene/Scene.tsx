import { useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { SEATS } from '../config/seats'
import { roomPose } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'
import { AgentSeat } from './AgentSeat'
import { CameraRig } from './CameraRig'
import { Ceo } from './Ceo'
import { ComputerWall } from './ComputerWall'
import { Operator } from './Operator'
import { Room } from './Room'
import { Table } from './Table'

// glow is on by default; ?fx=low turns it off for slow graphics
const FX = new URLSearchParams(window.location.search).get('fx') !== 'low'

export function Scene({ panel, dispatch }: { panel: PanelState; dispatch: (a: PanelAction) => void }) {
  const controls = useRef<OrbitControlsImpl>(null)
  const start = roomPose(window.innerWidth / window.innerHeight)
  return (
    <Canvas className="scene" dpr={[1, 2]} camera={{ position: start.pos, fov: 48, near: 0.1, far: 200 }} gl={{ antialias: true }}>
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
      <ComputerWall onPick={id => dispatch({ type: 'click', id })} disabled={panel.phase === 'flying' || panel.phase === 'closing'} />
      <OrbitControls ref={controls} target={start.target} enableDamping enablePan={false}
        minPolarAngle={0.95} maxPolarAngle={1.6} minDistance={6} maxDistance={15} enabled={panel.phase === 'closed'} />
      <CameraRig panel={panel} dispatch={dispatch} controls={controls} />
      {FX && <EffectComposer><Bloom intensity={0.85} luminanceThreshold={0.4} luminanceSmoothing={0.3} mipmapBlur /></EffectComposer>}
    </Canvas>
  )
}
