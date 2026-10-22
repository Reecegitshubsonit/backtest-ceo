import { useEffect, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'

const vertexShader = `
varying vec3 vNormal;
varying vec3 vView;
varying vec3 vLocal;
varying vec2 vUv;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vNormal = normalize(normalMatrix * normal);
  vView = -mv.xyz;
  vLocal = position;
  vUv = uv;
  gl_Position = projectionMatrix * mv;
}`

const fragmentShader = `
uniform float uTime;
uniform float uWire;
uniform float uEye;
varying vec3 vNormal;
varying vec3 vView;
varying vec3 vLocal;
varying vec2 vUv;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }
void main() {
  float facing = abs(dot(normalize(vNormal), normalize(vView)));
  float rim = pow(1.0 - facing, 2.3);
  // Avoid burning the eye sockets and lip edges into white rings.
  float face = smoothstep(0.85, 0.88, vLocal.y) * (1.0 - smoothstep(0.965, 0.99, vLocal.y));
  float innerFace = 1.0 - smoothstep(0.025, 0.06, abs(vLocal.x));
  rim *= 1.0 - face * innerFace * 0.9 * abs(normalize(vView).z);
  float scan = 0.94 + 0.06 * sin(vLocal.y * 1650.0 - uTime * 2.0);
  vec2 cell = floor(vUv * 140.0);
  vec2 point = fract(vUv * 140.0) - 0.5;
  float dotLight = (1.0 - smoothstep(0.06, 0.19, length(point))) * step(0.88, hash(cell));
  float fade = smoothstep(0.03, 0.47, vLocal.y);
  float relief = max(0.0, dot(normalize(vNormal), normalize(vec3(-0.5, 0.6, 1.0))));
  float body = 0.04 + relief * 0.15 + rim * 0.80;
  // Lower legs dissolve into the projector rather than showing solid feet.
  float alpha = mix(body + dotLight * 0.70, 0.003, uWire) * fade * scan * mix(1.0, 0.18, uEye);
  vec3 blue = mix(vec3(0.04, 0.40, 1.0), vec3(0.43, 0.86, 1.0), rim);
  gl_FragColor = vec4(blue * (0.8 + rim * 0.5), alpha);
}`

/** A posed CC0 human GLB. No generated body shapes or particle-cloud anatomy. */
export function CeoModel() {
  const { scene } = useGLTF('/models/ceo-standing.glb')
  const material = useMemo(() => new THREE.ShaderMaterial({
    vertexShader, fragmentShader, uniforms: { uTime: { value: 0 }, uWire: { value: 0 }, uEye: {value: 0} },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }), [])
  const wire = useMemo(() => new THREE.ShaderMaterial({
    vertexShader, fragmentShader,
    uniforms: {uTime: {value: 0}, uWire: {value: 1}, uEye: {value: 0}},
    wireframe: true, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }), [])
  const eyes = useMemo(() => {
    const m = material.clone()
    m.uniforms.uEye.value = 1
    return m
  }, [material])
  const model = useMemo(() => {
    const root = new THREE.Group()
    scene.traverse(object => {
      if (!(object instanceof THREE.Mesh)) return
      const isEye = object.name.startsWith('CEO_eye') || object.name.startsWith('CEO eye')
      const surface = new THREE.Mesh(object.geometry, isEye ? eyes : material)
      surface.matrix.copy(object.matrixWorld); surface.matrixAutoUpdate = false
      root.add(surface)
      if (!isEye) {
        const lines = new THREE.Mesh(object.geometry, wire)
        lines.matrix.copy(object.matrixWorld); lines.matrixAutoUpdate = false
        root.add(lines)
      }
    })
    return root
  }, [scene, material, wire, eyes])
  useFrame(({ clock }) => {
    material.uniforms.uTime.value = clock.getElapsedTime()
    wire.uniforms.uTime.value = clock.getElapsedTime()
    eyes.uniforms.uTime.value = clock.getElapsedTime()
  })
  useEffect(() => () => { material.dispose(); wire.dispose(); eyes.dispose() }, [material, wire, eyes])
  return <primitive object={model} />
}
