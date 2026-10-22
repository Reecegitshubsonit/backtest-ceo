import { useMemo } from 'react'
import * as THREE from 'three'
import { figurePoints, mulberry32 } from './particles'
import { dotTexture } from './textures'

interface Props { seated?: boolean; color: number; density: number; size: number; headTilt?: number; seed: number; material?: THREE.PointsMaterial }

export function pointsMaterial(color: number, size: number, opacity = 0.9) {
  return new THREE.PointsMaterial({ color, size, map: dotTexture(), transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false })
}

/** Particle hologram of a person facing +z. */
export function Figure({ seated = false, color, density, size, headTilt = 0, seed, material }: Props) {
  const pts = useMemo(() => figurePoints(seated, density, mulberry32(seed)), [seated, density, seed])
  const mat = useMemo(() => material ?? pointsMaterial(color, size), [material, color, size])
  return (
    <group>
      <points material={mat}>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[pts.body, 3]} /></bufferGeometry>
      </points>
      <group position={pts.headPivot} rotation-x={headTilt}>
        <points material={mat}>
          <bufferGeometry><bufferAttribute attach="attributes-position" args={[pts.head, 3]} /></bufferGeometry>
        </points>
      </group>
    </group>
  )
}
