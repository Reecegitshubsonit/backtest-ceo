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

export interface LabelLine { text: string; big?: boolean }

/** White first line, coloured lines under it; sized so 230 px = 1 world unit. */
export function labelTexture(lines: LabelLine[], color: string): THREE.CanvasTexture {
  const c = document.createElement('canvas'), big = !!lines[0]?.big
  c.width = 512; c.height = 40 + lines.length * 44 + (big ? 24 : 0)
  const g = c.getContext('2d')!
  g.textAlign = 'center'; g.shadowColor = 'rgba(0,0,0,.9)'; g.shadowBlur = 6
  lines.forEach((l, i) => {
    g.font = (i === 0 ? `700 ${l.big ? 64 : 34}` : '500 26') + 'px "Segoe UI", Helvetica, Arial, sans-serif'
    g.fillStyle = i === 0 ? '#ffffff' : color
    g.fillText(l.text, 256, 52 + i * 42 + (big && i > 0 ? 24 : 0))
  })
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace
  return t
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
  const c = document.createElement('canvas'); c.width = 384; c.height = 240
  const g = c.getContext('2d')!
  g.strokeStyle = color; g.fillStyle = color
  g.globalAlpha = 0.1; g.fillRect(6, 6, 372, 228); g.globalAlpha = 0.9; g.lineWidth = 2; g.strokeRect(6, 6, 372, 228)
  drawChartLines(g, 384, 240, 20, color, seed)
  return new THREE.CanvasTexture(c)
}

/** A clickable computer: big title bar, chart body, LIVE or NEXT badge. */
export function computerTexture(label: string, live: boolean, hot: boolean, seed: number): THREE.CanvasTexture {
  const c = document.createElement('canvas'); c.width = 640; c.height = 400
  const g = c.getContext('2d')!, col = hot ? '#bfefff' : '#6cc8ff'
  g.fillStyle = 'rgba(20,70,140,0.35)'; g.fillRect(0, 0, 640, 400)
  g.strokeStyle = col; g.lineWidth = hot ? 7 : 4; g.strokeRect(4, 4, 632, 392)
  g.fillStyle = 'rgba(40,140,255,0.35)'; g.fillRect(4, 4, 632, 78)
  g.font = '700 50px "Segoe UI", Helvetica, Arial, sans-serif'; g.textAlign = 'left'; g.fillStyle = '#ffffff'
  g.shadowColor = col; g.shadowBlur = 12; g.fillText(label, 26, 62); g.shadowBlur = 0
  g.font = '700 24px "Segoe UI", Helvetica, Arial, sans-serif'; g.textAlign = 'right'
  g.fillStyle = live ? '#2fd27a' : '#9fb4d8'; g.fillText(live ? '● LIVE' : 'NEXT', 612, 56)
  drawChartLines(g, 640, 400, 100, col, seed)
  g.font = '500 22px "Segoe UI", Helvetica, Arial, sans-serif'; g.textAlign = 'center'; g.fillStyle = '#d8f2ff'
  g.fillText('click to open', 320, 384)
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace
  return t
}
