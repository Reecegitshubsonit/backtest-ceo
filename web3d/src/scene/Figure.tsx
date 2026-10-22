import { useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { figurePoints, mulberry32 } from './particles'
import { bodyGeometry, headGeometry, holoMaterial, type HoloOptions } from './hologram'
import { dotTexture } from './textures'

interface Props {
  seated?: boolean; color: number; density: number; size: number; headTilt?: number; seed: number
  material?: THREE.PointsMaterial
  /** glow shell options; fade heights are world y */
  holo?: HoloOptions
  /** drop particles below this local height (legs fading into the beam) */
  particlesFrom?: number
}

export function pointsMaterial(color: number, size: number, opacity = 0.9) {
  return new THREE.PointsMaterial({ color, size, map: dotTexture(), transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false })
}

/** Hologram of a person facing +z: a glowing see-through body with sparkling particles on it. */
export function Figure({ seated = false, color, density, size, headTilt = 0, seed, material, holo, particlesFrom }: Props) {
  const pts = useMemo(() => {
    const p = figurePoints(seated, density, mulberry32(seed))
    if (particlesFrom == null) return p
    const keep: number[] = []
    for (let i = 0; i < p.body.length; i += 3) if (p.body[i + 1] >= particlesFrom) keep.push(p.body[i], p.body[i + 1], p.body[i + 2])
    return { ...p, body: new Float32Array(keep) }
  }, [seated, density, seed, particlesFrom])
  const mat = useMemo(() => material ?? pointsMaterial(color, size), [material, color, size])
  const shell = useMemo(() => holoMaterial(color, holo), [color, holo])
  useFrame(({ clock }) => { shell.uniforms.uTime.value = clock.getElapsedTime() })
  return (
    <group>
      <mesh geometry={bodyGeometry(seated)} material={shell} />
      <points material={mat}>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[pts.body, 3]} /></bufferGeometry>
      </points>
      <group position={pts.headPivot} rotation-x={headTilt}>
        <mesh geometry={headGeometry()} material={shell} />
        <points material={mat}>
          <bufferGeometry><bufferAttribute attach="attributes-position" args={[pts.head, 3]} /></bufferGeometry>
        </points>
      </group>
    </group>
  )
}
