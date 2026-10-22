import { useMemo, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { COMPUTERS, WALL_RADIUS, type Computer } from '../config/computers'
import { onArc } from '../model/camera'
import type { ComputerId } from '../model/types'
import { computerTexture, screenTexture } from './textures'

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const
const DECOR_R = 7.7
const DECOR: [number, number, number, number][] = [
  [167, 3.4, 2.1, 1.5], [193, 3.4, 2.1, 1.5], [180, 5.3, 3.2, 1.1],
  [210, 2.35, 3.0, 1.5], [128, 3.3, 2.0, 2.6], [232, 3.3, 2.0, 2.6],
]

function ComputerScreen({ c, index, onPick, disabled }: { c: Computer; index: number; onPick: (id: ComputerId) => void; disabled: boolean }) {
  const [hot, setHot] = useState(false)
  const tex = useMemo(() => computerTexture(c.label, c.live, hot, 300 + index), [c.label, c.live, hot, index])
  const pos = onArc(c.angleDeg, WALL_RADIUS, c.y)
  const yaw = (c.angleDeg * Math.PI) / 180 + Math.PI
  return (
    <group position={pos} rotation-y={yaw}>
      <mesh position-z={-0.03}>
        <planeGeometry args={[c.w + 0.12, c.h + 0.12]} />
        <meshBasicMaterial color={0x03060f} />
      </mesh>
      <mesh
        onClick={e => { e.stopPropagation(); if (!disabled) onPick(c.id) }}
        onPointerOver={e => { e.stopPropagation(); if (!disabled) { setHot(true); document.body.style.cursor = 'pointer' } }}
        onPointerOut={() => { setHot(false); document.body.style.cursor = '' }}>
        <planeGeometry args={[c.w, c.h]} />
        <meshBasicMaterial map={tex} opacity={hot ? 1 : 0.85} {...additive} />
      </mesh>
    </group>
  )
}

/** Curved wall of chart screens behind the CEO; three of them are the clickable computers. */
export function ComputerWall({ onPick, disabled }: { onPick: (id: ComputerId) => void; disabled: boolean }) {
  // a few large screens, like the reference: dim ones behind the CEO and further out on both sides
  const decor = useMemo(() => DECOR.map(([deg, y, w, h], k) => ({
    pos: onArc(deg, DECOR_R, y), yaw: (deg * Math.PI) / 180 + Math.PI, w, h,
    tex: screenTexture(k % 3 === 2 ? '#a98bff' : '#5fc8ff', 40 + k), base: 0.3 + (k % 3) * 0.05, phase: k * 2.3,
  })), [])
  const mats = useMemo(() => decor.map(d => new THREE.MeshBasicMaterial({ map: d.tex, opacity: d.base, ...additive })), [decor])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    mats.forEach((m, i) => { const p = decor[i].phase; m.opacity = decor[i].base + Math.sin(t * 2 + p) * 0.05 + (Math.sin(t * 17 + p * 3) > 0.97 ? -0.25 : 0) })
  })
  return (
    <group>
      {decor.map((d, i) => (
        <mesh key={i} position={d.pos} rotation-y={d.yaw} material={mats[i]}>
          <planeGeometry args={[d.w, d.h]} />
        </mesh>
      ))}
      {COMPUTERS.map((c, i) => <ComputerScreen key={c.id} c={c} index={i} onPick={onPick} disabled={disabled} />)}
    </group>
  )
}
