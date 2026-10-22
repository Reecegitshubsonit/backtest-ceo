import { useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { bodyGeometry, headGeometry, headPivot, holoMaterial, surfacePoints, type HoloOptions } from './hologram'
import { dotTexture } from './textures'

interface Props {
  seated?: boolean; color: number; density: number; size: number; headTilt?: number; seed: number
  material?: THREE.PointsMaterial
  /** glow shell options; fade heights are world y */
  holo?: HoloOptions
  /** drop particles below this local height (legs fading into the beam) */
  particlesFrom?: number
}

/** Soft additive halo behind a hologram. */
export function Halo({ position, scale, color = 0x3f9fff, opacity = 0.22 }: { position: [number, number, number]; scale: [number, number]; color?: number; opacity?: number }) {
  return (
    <sprite position={position} scale={[scale[0], scale[1], 1]}>
      <spriteMaterial map={dotTexture()} color={color} opacity={opacity} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
    </sprite>
  )
}

export function pointsMaterial(color: number, size: number, opacity = 0.9) {
  return new THREE.PointsMaterial({ color, size, map: dotTexture(), transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false })
}

function Cloud({ points, links, mat, linkMat }: { points: Float32Array; links: Float32Array; mat: THREE.PointsMaterial; linkMat: THREE.LineBasicMaterial }) {
  return (
    <>
      <points material={mat}>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[points, 3]} /></bufferGeometry>
      </points>
      <lineSegments material={linkMat}>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[links, 3]} /></bufferGeometry>
      </lineSegments>
    </>
  )
}

/** Hologram of a person facing +z: glowing see-through body, particles on its surface, faint links between them. */
export function Figure({ seated = false, color, density, size, headTilt = 0, seed, material, holo, particlesFrom }: Props) {
  const body = useMemo(() => surfacePoints(bodyGeometry(seated), Math.round(2600 * density), seed, particlesFrom), [seated, density, seed, particlesFrom])
  const head = useMemo(() => surfacePoints(headGeometry(), Math.round(700 * density), seed + 7), [density, seed])
  const mat = useMemo(() => material ?? pointsMaterial(color, size), [material, color, size])
  const linkMat = useMemo(() => new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false }), [color])
  const shell = useMemo(() => holoMaterial(color, holo), [color, holo])
  useFrame(({ clock }) => { shell.uniforms.uTime.value = clock.getElapsedTime() })
  return (
    <group>
      <mesh geometry={bodyGeometry(seated)} material={shell} />
      <Cloud {...body} mat={mat} linkMat={linkMat} />
      <group position={headPivot(seated)} rotation-x={headTilt}>
        <mesh geometry={headGeometry()} material={shell} />
        <Cloud {...head} mat={mat} linkMat={linkMat} />
      </group>
    </group>
  )
}
