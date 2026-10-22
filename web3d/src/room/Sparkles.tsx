import { useEffect, useRef } from 'react'
import { BEAM, CEO_CHEST, ROOM_IMAGE, SEAT_SPOTS } from '../config/imageRoom'

interface Mote { x: number; y: number; v: number; r: number; life: number; kind: 'rise' | 'twinkle' }

// regions (image px) where twinkles appear: the CEO's body and each agent's upper body
const BODIES: [number, number, number, number][] = [
  [CEO_CHEST[0], CEO_CHEST[1] + 20, 72, 150],
  ...Object.values(SEAT_SPOTS).map(s => [s.chest[0], s.chest[1], 34, 50] as [number, number, number, number]),
]

function spawn(kind: Mote['kind']): Mote {
  if (kind === 'rise') return { kind, x: BEAM.x + Math.random() * BEAM.w, y: BEAM.y + BEAM.h * (0.3 + Math.random() * 0.7), v: 8 + Math.random() * 18, r: 0.5 + Math.random() * 0.9, life: Math.random() }
  const [cx, cy, rx, ry] = BODIES[Math.floor(Math.random() * BODIES.length)]
  const a = Math.random() * Math.PI * 2, d = Math.sqrt(Math.random())
  return { kind, x: cx + Math.cos(a) * rx * d, y: cy + Math.sin(a) * ry * d, v: 0.6 + Math.random() * 1.2, r: 0.4 + Math.random() * 0.8, life: 0 }
}

/** Animated light over the picture: motes rising through the beam and twinkles on the holograms. */
export function Sparkles({ active }: { active: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv || !active || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const motes: Mote[] = [...Array.from({ length: 70 }, () => spawn('rise')), ...Array.from({ length: 110 }, () => spawn('twinkle'))]
    let raf = 0, last = performance.now()
    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now
      const w = cv.clientWidth, h = cv.clientHeight, dpr = Math.min(2, devicePixelRatio || 1)
      if (cv.width !== Math.round(w * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr) }
      const g = cv.getContext('2d')!, k = (w / ROOM_IMAGE.w) * dpr
      g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, cv.width, cv.height)
      g.globalCompositeOperation = 'lighter'
      for (let i = 0; i < motes.length; i++) {
        const m = motes[i]
        let alpha: number
        if (m.kind === 'rise') {
          m.y -= m.v * dt; m.life += dt * 0.25
          if (m.y < BEAM.y) motes[i] = spawn('rise')
          alpha = 0.35 + 0.35 * Math.sin(m.life * 9)
        } else {
          m.life += dt * m.v
          if (m.life >= 1) { motes[i] = spawn('twinkle'); continue }
          alpha = Math.sin(m.life * Math.PI)
        }
        const x = m.x * k, y = m.y * (cv.height / ROOM_IMAGE.h), r = m.r * k
        const gr = g.createRadialGradient(x, y, 0, x, y, r * 3)
        gr.addColorStop(0, `rgba(200,240,255,${alpha})`); gr.addColorStop(1, 'rgba(80,170,255,0)')
        g.fillStyle = gr; g.beginPath(); g.arc(x, y, r * 3, 0, Math.PI * 2); g.fill()
      }
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [active])
  return <canvas ref={ref} className="sparkles" aria-hidden />
}
