import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { screenTexture } from './textures'

export const TABLE_H = 0.95
export const TABLE_R = 3

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const
const RINGS: [number, number, number, number][] = [
  [0.3, 0.35, 0x8fe4ff, 0.95], [0.5, 0.54, 0x5fd8ff, 0.8], [0.72, 0.77, 0x5fd8ff, 0.7], [0.95, 0.99, 0x3fa8ff, 0.6],
  [1.25, 1.31, 0xb070ff, 0.85], [1.6, 1.62, 0x5fd8ff, 0.4], [2.15, 2.18, 0x3fa8ff, 0.35],
]

function summaryTexture() {
  const c = document.createElement('canvas'); c.width = 512; c.height = 220
  const g = c.getContext('2d')!
  g.strokeStyle = g.fillStyle = '#6cc8ff'; g.lineWidth = 3
  g.globalAlpha = 0.12; g.fillRect(4, 4, 504, 212); g.globalAlpha = 1; g.strokeRect(4, 4, 504, 212)
  g.textAlign = 'center'; g.fillStyle = '#ffffff'; g.font = '700 30px "Segoe UI", Arial, sans-serif'; g.fillText('EXECUTIVE SUMMARY', 256, 50)
  g.fillStyle = '#6cc8ff'; g.font = '500 18px "Segoe UI", Arial, sans-serif'; g.fillText('SYNTHESIZING AGENT REPORTS', 256, 78)
  g.lineWidth = 2; g.beginPath()
  for (let x = 30; x < 482; x += 3) g.lineTo(x, 150 + Math.sin(x * 0.09) * 18 * Math.sin(x * 0.013) + Math.sin(x * 1.7) * 6)
  g.stroke()
  return new THREE.CanvasTexture(c)
}

/** Round strategy table: glowing edge, spinning rings, light column, rim dashboards, executive summary panel. */
export function Table() {
  const rings = useRef<(THREE.Mesh | null)[]>([])
  const beam = useRef<THREE.MeshBasicMaterial>(null)
  const dash = useMemo(() => Array.from({ length: 10 }, (_, i) => screenTexture('#5fc8ff', 100 + i)), [])
  const summary = useMemo(summaryTexture, [])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    rings.current.forEach((m, i) => { if (m) m.rotation.z = t * (i % 2 ? -0.15 : 0.25) * (1 + i * 0.1) })
    if (beam.current) beam.current.opacity = 0.02 + Math.sin(t * 1.5) * 0.008
  })
  return (
    <group>
      <mesh position-y={TABLE_H / 2}>
        <cylinderGeometry args={[TABLE_R, TABLE_R + 0.2, TABLE_H, 72]} />
        <meshStandardMaterial color={0x0a0d1a} metalness={0.75} roughness={0.3} />
      </mesh>
      <mesh rotation-x={Math.PI / 2} position-y={TABLE_H}>
        <torusGeometry args={[TABLE_R, 0.022, 8, 128]} />
        <meshBasicMaterial color={0x5fd8ff} />
      </mesh>
      {RINGS.map(([a, b, c, o], i) => (
        <mesh key={i} ref={m => { rings.current[i] = m }} rotation-x={-Math.PI / 2} position-y={TABLE_H + 0.01 + i * 0.002}>
          <ringGeometry args={[a, b, 96, 1, 0, i % 2 === 0 ? Math.PI * 1.6 : Math.PI * 2]} />
          <meshBasicMaterial color={c} opacity={o} {...additive} />
        </mesh>
      ))}
      <mesh rotation-x={-Math.PI / 2} position-y={TABLE_H + 0.008}>
        <circleGeometry args={[1, 48]} />
        <meshBasicMaterial color={0x1f6fff} opacity={0.25} {...additive} />
      </mesh>
      <mesh position-y={TABLE_H + 2.3}>
        <cylinderGeometry args={[0.55, 0.9, 4.6, 48, 1, true]} />
        <meshBasicMaterial ref={beam} color={0x3fa8ff} opacity={0.05} {...additive} />
      </mesh>
      {dash.map((tex, i) => {
        const a = (i / 10) * Math.PI * 2 + 0.3
        return (
          <mesh key={i} position={[Math.sin(a) * 2.45, TABLE_H + 0.03, Math.cos(a) * 2.45]} rotation={[-Math.PI / 2 + 0.25, a, 0, 'YXZ']}>
            <planeGeometry args={[0.8, 0.5]} />
            <meshBasicMaterial map={tex} opacity={0.55} {...additive} />
          </mesh>
        )
      })}
      <mesh position={[0, TABLE_H + 0.32, TABLE_R - 0.15]} rotation-x={-0.35}>
        <planeGeometry args={[1.6, 0.69]} />
        <meshBasicMaterial map={summary} opacity={0.95} {...additive} />
      </mesh>
    </group>
  )
}
