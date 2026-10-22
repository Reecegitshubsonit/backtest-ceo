import * as THREE from 'three'
import { mulberry32 } from './particles'

let dot: THREE.Texture | null = null
/** Soft round sprite for particles. */
export function dotTexture(): THREE.Texture {
  if (dot) return dot
  const c = document.createElement('canvas'); c.width = c.height = 64
  const g = c.getContext('2d')!, gr = g.createRadialGradient(32, 32, 0, 32, 32, 32)
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.3, 'rgba(255,255,255,.6)'); gr.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64)
  return (dot = new THREE.CanvasTexture(c))
}

/** Canvas textures are drawn at this multiple of their logical size so text and lines stay sharp up close. */
export const SHARP = 3

/** Wrap a canvas as a crisp texture; logical (pre-SHARP) size goes in userData for sizing sprites. */
export function finish(c: HTMLCanvasElement, w: number, h: number): THREE.CanvasTexture {
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 8
  t.userData = { w, h }
  return t
}

export interface LabelLine { text: string; big?: boolean }

/** White first line, coloured lines under it; sized so 230 px = 1 world unit. */
export function labelTexture(lines: LabelLine[], color: string): THREE.CanvasTexture {
  const c = document.createElement('canvas'), big = !!lines[0]?.big
  const w = 512, h = 40 + lines.length * 44 + (big ? 24 : 0)
  c.width = w * SHARP; c.height = h * SHARP
  const g = c.getContext('2d')!
  g.scale(SHARP, SHARP)
  g.textAlign = 'center'; g.shadowColor = 'rgba(0,0,0,.9)'; g.shadowBlur = 6
  lines.forEach((l, i) => {
    g.font = (i === 0 ? `700 ${l.big ? 64 : 34}` : '500 26') + 'px "Segoe UI", Helvetica, Arial, sans-serif'
    g.fillStyle = i === 0 ? '#ffffff' : color
    g.fillText(l.text, 256, 52 + i * 42 + (big && i > 0 ? 24 : 0))
  })
  return finish(c, w, h)
}

function drawChartLines(g: CanvasRenderingContext2D, w: number, h: number, y0: number, color: string, seed: number) {
  const r = mulberry32(seed)
  g.strokeStyle = color; g.fillStyle = color
  g.globalAlpha = 0.18; g.lineWidth = 1
  for (let x = 30; x < w - 10; x += 34) { g.beginPath(); g.moveTo(x, y0); g.lineTo(x, h - 20); g.stroke() }
  for (let y = y0 + 10; y < h - 20; y += 28) { g.beginPath(); g.moveTo(14, y); g.lineTo(w - 14, y); g.stroke() }
  g.globalAlpha = 0.95; g.shadowColor = color; g.shadowBlur = 6
  const kind = r()
  if (kind < 0.55) {
    g.lineWidth = 2.5; g.beginPath(); let y = (y0 + h) / 2
    for (let x = 16; x < w - 14; x += 4) { y = Math.max(y0 + 8, Math.min(h - 25, y + (r() - 0.5) * 18)); g.lineTo(x, y) }
    g.stroke()
  } else if (kind < 0.8) {
    let y = (y0 + h) / 2
    for (let x = 22; x < w - 18; x += 12) {
      const o = y, c = Math.max(y0 + 10, Math.min(h - 30, y + (r() - 0.5) * 30))
      const hi = Math.min(o, c) - r() * 12, lo = Math.max(o, c) + r() * 12
      g.fillRect(x + 3, hi, 1.5, lo - hi); g.fillRect(x, Math.min(o, c), 7, Math.max(2, Math.abs(c - o))); y = c
    }
  } else {
    for (let y = y0 + 6; y < h - 30; y += 13) { g.fillRect(18, y, 70, 4); g.fillRect(110, y, 40 + r() * 60, 4); g.fillRect(260, y, 30 + r() * 80, 4) }
  }
  g.shadowBlur = 0
}

/** Decorative wall screen: frame plus a random chart. */
export function screenTexture(color: string, seed: number): THREE.CanvasTexture {
  const c = document.createElement('canvas'); c.width = 384 * SHARP; c.height = 240 * SHARP
  const g = c.getContext('2d')!
  g.scale(SHARP, SHARP)
  g.strokeStyle = color; g.fillStyle = color
  g.globalAlpha = 0.1; g.fillRect(6, 6, 372, 228); g.globalAlpha = 0.9; g.lineWidth = 2; g.strokeRect(6, 6, 372, 228)
  drawChartLines(g, 384, 240, 20, color, seed)
  return finish(c, 384, 240)
}

/** Chart screen at rest, sized to the screen: longer side 768..1536 px, so it stays sharp from anywhere in the room. */
export function restTexture(w: number, h: number, color: string, seed: number): THREE.CanvasTexture {
  const L = 384, lw = w >= h ? L : Math.round((L * w) / h), lh = w >= h ? Math.round((L * h) / w) : L
  const k = Math.min(1536, Math.max(768, Math.max(w, h) * 360)) / L
  const c = document.createElement('canvas'); c.width = Math.round(lw * k); c.height = Math.round(lh * k)
  const g = c.getContext('2d')!
  g.scale(k, k)
  g.fillStyle = color; g.globalAlpha = 0.1; g.fillRect(0, 0, lw, lh); g.globalAlpha = 1
  drawChartLines(g, lw, lh, 14, color, seed)
  const t = finish(c, lw, lh)
  t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; t.anisotropy = 16
  return t
}
