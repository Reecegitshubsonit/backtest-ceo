import * as THREE from 'three'
import { TABLE_R } from '../config/room'

const dark = new THREE.MeshStandardMaterial({ color: 0x020307, metalness: 0.3, roughness: 0.8 })

/** You: a dark silhouette in a chair, back to the camera, in the foreground. */
export function Operator() {
  return (
    <group position={[0, -0.35, TABLE_R + 2.6]} scale={1.25}>
      <mesh material={dark} position={[0, 0.95, 0.12]}><boxGeometry args={[0.85, 0.8, 0.14]} /></mesh>
      <mesh material={dark} position={[0, 0.5, -0.3]}><boxGeometry args={[0.95, 0.12, 0.85]} /></mesh>
      <mesh material={dark} position={[0, 0.22, -0.3]}><cylinderGeometry args={[0.06, 0.06, 0.45, 12]} /></mesh>
      <mesh material={dark} position={[0, 1.25, -0.18]} scale={[1, 1, 0.7]}><cylinderGeometry args={[0.36, 0.27, 0.8, 20]} /></mesh>
      <mesh material={dark} position={[-0.36, 1.56, -0.18]}><sphereGeometry args={[0.15, 16, 12]} /></mesh>
      <mesh material={dark} position={[0.36, 1.56, -0.18]}><sphereGeometry args={[0.15, 16, 12]} /></mesh>
      <mesh material={dark} position={[0, 1.7, -0.2]}><cylinderGeometry args={[0.07, 0.08, 0.16, 12]} /></mesh>
      <mesh material={dark} position={[0, 1.86, -0.2]} scale={[1, 1.15, 1]}><sphereGeometry args={[0.17, 24, 16]} /></mesh>
    </group>
  )
}
