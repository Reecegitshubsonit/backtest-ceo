import * as THREE from 'three'

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const

/** Circular dark room: walls with neon strips, ceiling ring and light bars, floor grid rings. */
export function Room() {
  return (
    <group>
      <mesh position={[0, 5, 0]}>
        <cylinderGeometry args={[13, 13, 12, 64, 1, true]} />
        <meshStandardMaterial color={0x070a16} side={THREE.BackSide} metalness={0.4} roughness={0.7} />
      </mesh>
      {Array.from({ length: 16 }, (_, i) => {
        const a = (i / 16) * Math.PI * 2
        return (
          <mesh key={i} position={[Math.sin(a) * 12.7, 3, Math.cos(a) * 12.7]}>
            <boxGeometry args={[0.05, 3.5, 0.05]} />
            <meshBasicMaterial color={i % 4 === 0 ? 0xa05cff : 0x2f8fff} />
          </mesh>
        )
      })}
      <mesh rotation-x={Math.PI / 2} position={[0, 8, 0]}>
        <torusGeometry args={[6.5, 0.03, 8, 128]} />
        <meshBasicMaterial color={0x3fc8ff} />
      </mesh>
      {Array.from({ length: 18 }, (_, i) => {
        const a = (i / 18) * Math.PI * 2
        return (
          <mesh key={i} position={[Math.sin(a) * 9.5, 8.6, Math.cos(a) * 9.5]} rotation-y={a + Math.PI / 2}>
            <boxGeometry args={[1.4, 0.04, 0.04]} />
            <meshBasicMaterial color={i % 2 ? 0xa05cff : 0x3fa8ff} />
          </mesh>
        )
      })}
      <mesh rotation-x={-Math.PI / 2}>
        <circleGeometry args={[13, 64]} />
        <meshStandardMaterial color={0x04060c} metalness={0.3} roughness={0.85} />
      </mesh>
      {[5, 6.6, 8.2, 9.8, 11.4].map(r => (
        <mesh key={r} rotation-x={-Math.PI / 2} position-y={0.005}>
          <ringGeometry args={[r, r + 0.015, 96]} />
          <meshBasicMaterial color={0x2a5cff} opacity={0.25} {...additive} />
        </mesh>
      ))}
    </group>
  )
}
