import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { SEATS } from '../config/seats'
import { onArc } from '../model/camera'
import { TABLE_H, TABLE_R } from '../config/room'

export interface LabelAnchor { id: string; lines: string[]; pos: [number, number, number]; big?: boolean }

/** Every text label in the room: the CEO's title on its chest and one per agent above its head. */
export const LABELS: LabelAnchor[] = [
  { id: 'ceo', lines: ['CEO AI', 'STRATEGIC OVERSIGHT', 'FINAL DECISION AUTHORITY'], pos: [0, TABLE_H + 2.15, 0.6], big: true },
  ...SEATS.map(s => {
    const [x, , z] = onArc(s.angleDeg, (TABLE_R + 0.75) * 1.04, 0)
    return { id: s.id, lines: [s.name, s.job, '● Live Feed'], pos: [x, 2.3, z] as [number, number, number] }
  }),
]

/** DOM nodes of the labels, filled by <Labels/> and moved every frame by <LabelProjector/>. */
const nodes = new Map<string, HTMLDivElement>()

/** Page-text labels over the canvas: always sharp, never blurred by the glow. */
export function Labels({ hidden }: { hidden: boolean }) {
  return (
    <div className="labels" aria-hidden style={{ visibility: hidden ? 'hidden' : 'visible' }}>
      {LABELS.map(l => (
        <div key={l.id} className={`label3d${l.big ? ' ceo' : ''}`} ref={el => { if (el) nodes.set(l.id, el); else nodes.delete(l.id) }}>
          <b>{l.lines[0]}</b>{l.lines.slice(1).map((t, i) => <span key={i}>{t}</span>)}
        </div>
      ))}
    </div>
  )
}

const v = new THREE.Vector3(), w = new THREE.Vector3()
/** Lives inside the Canvas: projects each label's 3D anchor to the screen. */
export function LabelProjector() {
  const { camera, size } = useThree()
  useFrame(() => {
    for (const l of LABELS) {
      const el = nodes.get(l.id)
      if (!el) continue
      v.set(...l.pos).project(camera)
      const behind = v.z > 1
      el.style.display = behind ? 'none' : ''
      // agents on the far side of the table fade, so their labels do not pile up over the CEO
      const far = l.big ? 0 : camera.position.distanceTo(w.set(...l.pos)) - camera.position.length()
      el.style.opacity = String(Math.min(1, Math.max(0.12, 1 - far / 2.5)))
      el.style.transform = `translate(-50%, -50%) translate(${((v.x + 1) / 2) * size.width}px, ${((1 - v.y) / 2) * size.height}px)`
    }
  })
  return null
}
