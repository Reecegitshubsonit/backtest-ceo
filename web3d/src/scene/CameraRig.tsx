import { useEffect, useMemo, useRef, type RefObject } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { screenById } from '../config/screens3d'
import { flyPose, fovFor, poseDistance, roomPose, type CamPose, type Vec3 } from '../model/camera'
import type { PanelAction, PanelState } from '../model/panel'

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void; controls: RefObject<OrbitControlsImpl | null> }

/** Flies the camera square to a screen and back to where the orbit was. Orbit controls own the camera only while closed. */
export function CameraRig({ panel, dispatch, controls }: Props) {
  const { camera, size } = useThree()
  const aspect = size.width / Math.max(1, size.height)
  const reduced = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, [])
  const home = useRef<CamPose | null>(null)

  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera
    cam.fov = fovFor(aspect); cam.updateProjectionMatrix()
  }, [camera, aspect])

  useFrame((_, dt) => {
    if (panel.phase !== 'flying' && panel.phase !== 'closing') return
    const target = controls.current?.target ?? new THREE.Vector3()
    if (!home.current) home.current = { pos: camera.position.toArray() as Vec3, target: target.toArray() as Vec3 }
    const s = panel.screen ? screenById(panel.screen) : undefined
    const want: CamPose = panel.phase === 'flying' && s ? flyPose(s, (camera as THREE.PerspectiveCamera).fov, aspect) : home.current ?? roomPose(aspect)
    const k = reduced ? 1 : 1 - Math.exp(-dt * 5)
    camera.position.lerp(new THREE.Vector3(...want.pos), k)
    target.lerp(new THREE.Vector3(...want.target), k)
    camera.lookAt(target)
    const now: CamPose = { pos: camera.position.toArray() as Vec3, target: target.toArray() as Vec3 }
    if (poseDistance(now, want) < 0.01) {
      camera.position.set(...want.pos); target.set(...want.target); camera.lookAt(target)
      if (panel.phase === 'closing') home.current = null
      dispatch({ type: panel.phase === 'flying' ? 'arrived' : 'returned' })
    }
  })
  return null
}
