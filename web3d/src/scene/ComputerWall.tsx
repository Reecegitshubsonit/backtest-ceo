import { useMemo, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { COMPUTERS, COMPUTER_H, COMPUTER_W, COMPUTER_Y, WALL_RADIUS, type Computer } from '../config/computers'
import { onArc } from '../model/camera'
import type { ComputerId } from '../model/types'
import { computerTexture, screenTexture } from './textures'

const additive = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide } as const
const DECOR_R = 7.9

function ComputerScreen({ c, index, onPick, disabled }: { c: Computer; index: number; onPick: (id: ComputerId) => void; disabled: boolean }) {
  const [hot, setHot] = useState(false)
  const tex = useMemo(() => computerTexture(c.label, c.live, hot, 300 + index), [c.label, c.live, hot, index])
  const pos = onArc(c.angleDeg, WALL_RADIUS, COMPUTER_Y)
  const yaw = (c.angleDeg * Math.PI) / 180 + Math.PI
  return (
    <group position={pos} rotation-y={yaw}>
      <mesh position-z={-0.03}>
        <planeGeometry args={[COMPUTER_W + 0.12, COMPUTER_H + 0.12]} />
        <meshBasicMaterial color={0x03060f} />
      </mesh>
      <mesh
        onClick={e => { e.stopPropagation(); if (!disabled) onPick(c.id) }}
        onPointerOver={e => { e.stopPropagation(); if (!disabled) { setHot(true); document.body.style.cursor = 'pointer' } }}
        onPointerOut={() => { setHot(false); document.body.style.cursor = '' }}>
        <planeGeometry args={[COMPUTER_W, COMPUTER_H]} />
        <meshBasicMaterial map={tex} opacity={hot ? 1 : 0.85} {...additive} />
      </mesh>
    </group>
  )
}

/** Curved wall of chart screens behind the CEO; three of them are the clickable computers. */
export function ComputerWall({ onPick, disabled }: { onPick: (id: ComputerId) => void; disabled: boolean }) {
  const decor = useMemo(() => {
    const out: { pos: [number, number, number]; yaw: number; tex: THREE.Texture; base: number; phase: number }[] = []
    for (let row = 0; row < 3; row++) for (let col = 0; col < 8; col++) {
      const deg = 130 + col * (100 / 7), y = 1.6 + row * 1.45
      out.push({ pos: onArc(deg, DECOR_R, y), yaw: (deg * Math.PI) / 180 + Math.PI,
        tex: screenTexture((row * 8 + col) % 7 === 0 ? '#a98bff' : '#5fc8ff', row * 8 + col),
        base: 0.32 + ((row * 8 + col) % 5) * 0.03, phase: row * 3.1 + col * 1.7 })
    }
    return out
  }, [])
  const mats = useMemo(() => decor.map(d => new THREE.MeshBasicMaterial({ map: d.tex, opacity: d.base, ...additive })), [decor])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    mats.forEach((m, i) => { const p = decor[i].phase; m.opacity = decor[i].base + Math.sin(t * 2 + p) * 0.05 + (Math.sin(t * 17 + p * 3) > 0.97 ? -0.25 : 0) })
  })
  return (
    <group>
      {decor.map((d, i) => (
        <mesh key={i} position={d.pos} rotation-y={d.yaw} material={mats[i]}>
          <planeGeometry args={[1.95, 1.22]} />
        </mesh>
      ))}
      {COMPUTERS.map((c, i) => <ComputerScreen key={c.id} c={c} index={i} onPick={onPick} disabled={disabled} />)}
    </group>
  )
}
