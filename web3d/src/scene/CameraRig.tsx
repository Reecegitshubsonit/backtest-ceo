import { useEffect, useMemo, type RefObject } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { computerById, WALL_RADIUS } from '../config/computers'
import { fovFor, poseDistance, roomPose, screenPose, type CamPose } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void; controls: RefObject<OrbitControlsImpl | null> }

/** Flies the camera to a computer and back. Orbit controls own the camera only while the panel is closed. */
export function CameraRig({ panel, dispatch, controls }: Props) {
  const { camera, size } = useThree()
  const aspect = size.width / Math.max(1, size.height)
  const reduced = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, [])

  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera
    cam.fov = fovFor(aspect); cam.updateProjectionMatrix()
  }, [camera, aspect])

  useFrame((_, dt) => {
    if (panel.phase === 'closed' || panel.phase === 'open') return
    const want: CamPose = panel.phase === 'flying' && panel.computer
      ? (c => screenPose(c.angleDeg, WALL_RADIUS, c.y, 3.2))(computerById(panel.computer))
      : roomPose(aspect)
    const target = controls.current?.target ?? new THREE.Vector3()
    const k = reduced ? 1 : 1 - Math.exp(-dt * 6)
    camera.position.lerp(new THREE.Vector3(...want.pos), k)
    target.lerp(new THREE.Vector3(...want.target), k)
    camera.lookAt(target)
    const now: CamPose = { pos: camera.position.toArray() as CamPose['pos'], target: target.toArray() as CamPose['target'] }
    if (poseDistance(now, want) < 0.03) {
      camera.position.set(...want.pos); target.set(...want.target); camera.lookAt(target)
      dispatch({ type: panel.phase === 'flying' ? 'arrived' : 'returned' })
    }
  })
  return null
}
