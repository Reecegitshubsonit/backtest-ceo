import { MeshReflectorMaterial } from '@react-three/drei'
import * as THREE from 'three'
import { ROOM_R } from '../config/room'

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const
const rad = (deg: number) => (deg * Math.PI) / 180
/** Half-width of the entrance at the front of the room (behind your chair), in degrees. */
const GAP = 15
const STRIPS = Array.from({ length: 20 }, (_, i) => (i / 20) * 360).filter(d => d > GAP + 3 && d < 360 - GAP - 3)

/** Circular dark room: wall with an entrance at the front, neon strips, ceiling rings and arcs, glossy floor with rings. */
export function Room() {
  return (
    <group>
      <mesh position={[0, 4, 0]}>
        <cylinderGeometry args={[ROOM_R, ROOM_R, 9, 96, 1, true, rad(GAP), rad(360 - 2 * GAP)]} />
        <meshStandardMaterial color={0x070a16} side={THREE.BackSide} metalness={0.4} roughness={0.7} />
      </mesh>
      {/* dark corridor behind the entrance: inside faces only, so the side facing the room is open */}
      <mesh position={[0, 3.5, ROOM_R + 1.9]}>
        <boxGeometry args={[2 * ROOM_R * Math.sin(rad(GAP)) + 0.2, 8, 4]} />
        <meshStandardMaterial color={0x04060d} side={THREE.BackSide} metalness={0.3} roughness={0.8} />
      </mesh>
      {[-1, 1].map(k => (
        <mesh key={k} position={[k * ROOM_R * Math.sin(rad(GAP)), 2.6, ROOM_R * Math.cos(rad(GAP))]}>
          <boxGeometry args={[0.06, 5.2, 0.06]} />
          <meshBasicMaterial color={0xa05cff} />
        </mesh>
      ))}
      {STRIPS.map((d, i) => (
        <mesh key={d} position={[Math.sin(rad(d)) * (ROOM_R - 0.1), 3, Math.cos(rad(d)) * (ROOM_R - 0.1)]}>
          <boxGeometry args={[0.05, 3.5, 0.05]} />
          <meshBasicMaterial color={i % 4 === 0 ? 0xa05cff : 0x2f8fff} />
        </mesh>
      ))}
      <mesh rotation-x={Math.PI / 2} position={[0, 8, 0]}>
        <torusGeometry args={[6.5, 0.03, 8, 128]} />
        <meshBasicMaterial color={0x3fc8ff} />
      </mesh>
      {Array.from({ length: 18 }, (_, i) => {
        const a = (i / 18) * Math.PI * 2
        return (
          <mesh key={i} position={[Math.sin(a) * 0.88 * ROOM_R, 8.3, Math.cos(a) * 0.88 * ROOM_R]} rotation-y={a + Math.PI / 2}>
            <boxGeometry args={[1.4, 0.04, 0.04]} />
            <meshBasicMaterial color={i % 2 ? 0xa05cff : 0x3fa8ff} />
          </mesh>
        )
      })}
      <mesh rotation-x={-Math.PI / 2}>
        <circleGeometry args={[ROOM_R, 96]} />
        <MeshReflectorMaterial resolution={1024} blur={[260, 80]} mixBlur={1} mixStrength={2.2} mirror={0.6}
          roughness={0.8} depthScale={0.6} minDepthThreshold={0.4} maxDepthThreshold={1.2} color="#04070f" metalness={0.6} />
      </mesh>
      {Array.from({ length: 7 }, (_, i) => {
        // long purple light arcs across the ceiling, like the reference
        const r = 4.5 + i * 0.7
        return (
          <mesh key={`arc${i}`} rotation-x={Math.PI / 2} rotation-z={Math.PI * (0.95 + (i % 2) * 0.55)} position-y={7.2 + (i % 3) * 0.35}>
            <torusGeometry args={[r, 0.035, 8, 96, Math.PI * 0.42]} />
            <meshBasicMaterial color={i % 3 === 1 ? 0x3fa8ff : 0xb04cff} />
          </mesh>
        )
      })}
      {[5, 6.6, 8.2, 9.6].map(r => (
        <mesh key={r} rotation-x={-Math.PI / 2} position-y={0.005}>
          <ringGeometry args={[r, r + 0.015, 128]} />
          <meshBasicMaterial color={0x2a5cff} opacity={0.25} {...additive} />
        </mesh>
      ))}
    </group>
  )
}
