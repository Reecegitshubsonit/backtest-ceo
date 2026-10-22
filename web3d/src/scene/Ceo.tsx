import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { Figure, pointsMaterial } from './Figure'
import { Label } from './Label'
import { TABLE_H } from './Table'

export const CEO_SCALE = 1.75
export const CEO_CHEST = new THREE.Vector3(0, TABLE_H + 1.25 * CEO_SCALE, 0)
const RAIN = 700

/** The CEO: a blue particle hologram standing full-body on the table, with data rising through it. */
export function Ceo() {
  const body = useRef<THREE.Group>(null)
  const mat = useMemo(() => pointsMaterial(0x6fdcff, 0.032), [])
  const rainMat = useMemo(() => pointsMaterial(0x6fd4ff, 0.035, 0.5), [])
  const rainPos = useMemo(() => {
    const a = new Float32Array(RAIN * 3)
    for (let i = 0; i < RAIN; i++) {
      const ang = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * 0.85
      a.set([Math.cos(ang) * r, Math.random() * 4.4, Math.sin(ang) * r], i * 3)
    }
    return a
  }, [])
  const rainGeo = useRef<THREE.BufferGeometry>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (body.current) body.current.position.y = TABLE_H + 0.02 + Math.sin(t * 0.8) * 0.025
    mat.size = 0.032 + Math.sin(t * 2.2) * 0.004
    for (let i = 0; i < RAIN; i++) { let y = rainPos[i * 3 + 1] + 0.012 + (i % 7) * 0.002; if (y > 4.4) y = 0; rainPos[i * 3 + 1] = y }
    if (rainGeo.current) rainGeo.current.attributes.position.needsUpdate = true
  })
  return (
    <group>
      <group ref={body} scale={CEO_SCALE} position-y={TABLE_H}>
        <Figure color={0x6fdcff} density={6} size={0.032} seed={1} material={mat} />
      </group>
      <points material={rainMat} position-y={TABLE_H}>
        <bufferGeometry ref={rainGeo}><bufferAttribute attach="attributes-position" args={[rainPos, 3]} /></bufferGeometry>
      </points>
      <Label lines={[{ text: 'CEO AI', big: true }, { text: 'STRATEGIC OVERSIGHT' }, { text: 'FINAL DECISION AUTHORITY' }]}
        color="#a8e6ff" position={[0, TABLE_H + 2.0, 0.9]} scale={0.6} />
    </group>
  )
}
