import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Seat } from '../config/seats'
import { onArc } from '../model/camera'
import { Figure, Halo, pointsMaterial } from './Figure'
import { Label } from './Label'
import { TABLE_R } from './Table'
import { CEO_CHEST } from './Ceo'

const SEAT_R = TABLE_R + 0.75
const AGENT_HOLO = { intensity: 1.3 }
const chairMat = new THREE.MeshStandardMaterial({ color: 0x0a0d18, metalness: 0.6, roughness: 0.45 })
const edgeMat = new THREE.LineBasicMaterial({ color: 0x4fb8ff, transparent: true, opacity: 0.35 })

function Part({ geo, pos, rx = 0 }: { geo: THREE.BufferGeometry; pos: [number, number, number]; rx?: number }) {
  const edges = useMemo(() => new THREE.EdgesGeometry(geo), [geo])
  return (
    <group position={pos} rotation-x={rx}>
      <mesh geometry={geo} material={chairMat} />
      <lineSegments geometry={edges} material={edgeMat} />
    </group>
  )
}

/** Office chair facing +z, dark with faint holo edges. */
function Chair() {
  const g = useMemo(() => ({
    seat: new THREE.BoxGeometry(0.62, 0.09, 0.58), back: new THREE.BoxGeometry(0.6, 0.5, 0.07),
    arm: new THREE.BoxGeometry(0.06, 0.05, 0.42), post: new THREE.CylinderGeometry(0.04, 0.04, 0.38, 12),
    base: new THREE.CylinderGeometry(0.3, 0.3, 0.03, 5),
  }), [])
  return (
    <group>
      <Part geo={g.seat} pos={[0, 0.46, 0.05]} />
      <Part geo={g.back} pos={[0, 0.78, -0.33]} rx={-0.12} />
      <Part geo={g.arm} pos={[-0.34, 0.68, 0.02]} />
      <Part geo={g.arm} pos={[0.34, 0.68, 0.02]} />
      <Part geo={g.post} pos={[0, 0.22, 0.05]} />
      <Part geo={g.base} pos={[0, 0.03, 0.05]} />
    </group>
  )
}

/** Seated agent looking up at the CEO, with a label and a data stream arcing to the CEO's chest. */
export function AgentSeat({ seat, index }: { seat: Seat; index: number }) {
  const [x, , z] = onArc(seat.angleDeg, SEAT_R, 0)
  const yaw = (seat.angleDeg * Math.PI) / 180 + Math.PI
  const mat = useMemo(() => pointsMaterial(0x4fb8ff, 0.026), [])
  const head = useRef<THREE.Group>(null)
  const curve = useMemo(() => {
    const start = new THREE.Vector3(x, 0.85, z)
    const mid = start.clone().lerp(CEO_CHEST, 0.5).add(new THREE.Vector3(0, 1.0, 0))
    return new THREE.CatmullRomCurve3([start, mid, CEO_CHEST])
  }, [x, z])
  const streamLine = useMemo(() => new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(60)),
    new THREE.LineBasicMaterial({ color: 0x4fa8ff, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending })), [curve])
  const flow = useMemo(() => new Float32Array(18 * 3), [])
  const flowGeo = useRef<THREE.BufferGeometry>(null)
  const flowMat = useMemo(() => pointsMaterial(0xa8e0ff, 0.085), [])
  const speed = 0.12 + (index % 3) * 0.025
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    mat.opacity = 0.8 + Math.sin(t * 3 + index * 1.3) * 0.12
    const p = new THREE.Vector3()
    for (let j = 0; j < 18; j++) { curve.getPoint((t * speed + j / 18) % 1, p); flow.set([p.x, p.y, p.z], j * 3) }
    if (flowGeo.current) flowGeo.current.attributes.position.needsUpdate = true
  })
  return (
    <group>
      <group position={[x, 0, z]} rotation-y={yaw}>
        <Chair />
        <Halo position={[0, 0.85, 0]} scale={[1.6, 1.9]} opacity={0.2} />
        <group ref={head}>
          <Figure seated color={0x4fb8ff} density={1.6} size={0.024} headTilt={-0.6} seed={10 + index} material={mat} holo={AGENT_HOLO} />
        </group>
      </group>
      <mesh rotation-x={-Math.PI / 2} position={[x, 0.01, z]}>
        <ringGeometry args={[0.45, 0.5, 64]} />
        <meshBasicMaterial color={0x3fa8ff} opacity={0.4} transparent blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <Label lines={[{ text: seat.name }, { text: seat.job }, { text: '● Live Feed' }]} color="#6cc8ff"
        position={[x * 1.04, 2.35, z * 1.04]} scale={0.6} />
      <primitive object={streamLine} />
      <points material={flowMat}>
        <bufferGeometry ref={flowGeo}><bufferAttribute attach="attributes-position" args={[flow, 3]} /></bufferGeometry>
      </points>
    </group>
  )
}
