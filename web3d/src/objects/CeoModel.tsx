import { useEffect, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { useGLTF, useTexture } from '@react-three/drei'
import * as THREE from 'three'

const vertexShader = `
varying vec3 vNormal, vView, vLocal;
varying vec2 vReference;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vNormal = normalize(mat3(modelMatrix) * normal);
  vView = cameraPosition - world.xyz;
  vLocal = position;
  vReference = uv;
  gl_Position = projectionMatrix * viewMatrix * world;
}`

const fragmentShader = `
uniform sampler2D uReference;
uniform float uTime;
varying vec3 vNormal, vView, vLocal;
varying vec2 vReference;
float hash(vec3 p) { return fract(sin(dot(p, vec3(127.1,311.7,74.7))) * 43758.5453); }
void main() {
  vec3 normal = normalize(vNormal), view = normalize(vView);
  float rim = pow(1.0 - max(0.0, dot(normal, view)), 2.4);
  vec2 grid = (abs(normal.z) > 0.5 ? vLocal.xy : vLocal.zy) * 160.0;
  vec2 cell = floor(grid);
  vec2 center = vec2(hash(vec3(cell, 0.0)), hash(vec3(cell, 1.0)));
  float dotLight = (1.0 - smoothstep(0.025, 0.16, length(fract(grid) - center)))
    * step(0.65, hash(vec3(cell, 2.0)));
  vec2 edge = abs(fract(grid) - 0.5);
  float wire = 1.0 - smoothstep(0.008, 0.035, min(min(edge.x, edge.y), abs(edge.x-edge.y)));
  float scan = 0.98 + 0.02 * sin(vLocal.y * 1600.0 - uTime * 2.0);
  vec3 meshColor = vec3(0.002, 0.009, 0.025)
    + vec3(0.025, 0.28, 0.75) * rim
    + vec3(0.04, 0.32, 0.68) * dotLight
    + vec3(0.003, 0.018, 0.045) * wire;
  // Original artwork is a UV texture on the fitted volume, not a billboard.
  // It supplies the front likeness; inferred sides/back use the mesh material.
  vec3 reference = texture2D(uReference, vReference).rgb;
  float front = smoothstep(-0.2, 0.20, normal.z) * smoothstep(0.1, 0.65, view.z);
  vec3 color = mix(meshColor, reference, front) * scan;
  float bodyFade = smoothstep(0.27, 0.51, vLocal.y);
  float hands = smoothstep(0.11, 0.18, abs(vLocal.x)) * smoothstep(0.18, 0.30, vLocal.y);
  float fade = max(bodyFade, hands);
  gl_FragColor = vec4(color, fade);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`

/** Sculpted human volume, fitted and front-textured from the actual reference. */
export function CeoModel() {
  const { scene } = useGLTF('/models/ceo-standing.glb')
  const reference = useTexture('/room.jpg')
  const material = useMemo(() => {
    reference.colorSpace = THREE.SRGBColorSpace
    return new THREE.ShaderMaterial({
      vertexShader, fragmentShader,
      uniforms: {uReference: {value: reference}, uTime: {value: 0}},
      transparent: true, depthWrite: true, toneMapped: false,
      blending: THREE.NormalBlending,
    })
  }, [reference])
  const model = useMemo(() => {
    const root = new THREE.Group()
    scene.updateMatrixWorld(true)
    scene.traverse(object => {
      if (!(object instanceof THREE.Mesh)) return
      const surface = new THREE.Mesh(object.geometry, material)
      surface.matrix.copy(object.matrixWorld)
      surface.matrixAutoUpdate = false
      root.add(surface)
    })
    return root
  }, [scene, material])
  useFrame(({ clock }) => { material.uniforms.uTime.value = clock.getElapsedTime() })
  useEffect(() => () => material.dispose(), [material])
  return <primitive object={model} />
}
