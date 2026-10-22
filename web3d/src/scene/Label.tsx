import { useMemo } from 'react'
import { labelTexture, type LabelLine } from './textures'

interface Props { lines: LabelLine[]; color: string; position: [number, number, number]; scale?: number }

/** Camera-facing text sprite. */
export function Label({ lines, color, position, scale = 1 }: Props) {
  const key = lines.map(l => l.text).join('|')
  const tex = useMemo(() => labelTexture(lines, color), [key, color]) // eslint-disable-line react-hooks/exhaustive-deps
  const img = tex.image as HTMLCanvasElement
  return (
    <sprite position={position} scale={[(img.width / 230) * scale, (img.height / 230) * scale, 1]}>
      <spriteMaterial map={tex} transparent depthWrite={false} />
    </sprite>
  )
}
