import { Component, Suspense, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { Html, OrbitControls } from '@react-three/drei'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import type { OrbitControls as Controls } from 'three-stdlib'
import * as THREE from 'three'
import { CeoModel } from '../objects/CeoModel'
import './ceoReview.css'

class ModelBoundary extends Component<{children: ReactNode}, {failed: boolean}> {
  state = {failed: false}
  static getDerivedStateFromError() { return {failed: true} }
  render() { return this.state.failed ? <p role="alert">The CEO model could not load. Reload to try again.</p> : this.props.children }
}

function Camera({ detail, reset }: {detail: boolean; reset: number}) {
  const {camera, size} = useThree()
  const controls = useRef<Controls>(null)
  useLayoutEffect(() => {
    const cam = camera as THREE.PerspectiveCamera
    cam.position.set(0, 0.67, 2.20)
    if (detail) cam.setViewOffset(1280, 720, 480, 156.4, 320, 400)
    else cam.setViewOffset(1280, 720, 0, 86.4, 1280, 720)
    cam.updateProjectionMatrix()
    controls.current?.target.set(0, 0.50, 0)
    controls.current?.update()
  }, [camera, size.width, size.height, detail, reset])
  return <OrbitControls ref={controls} makeDefault enablePan={false} enableDamping
    target={[0, 0.50, 0]} minDistance={0.55} maxDistance={3.3}
    minPolarAngle={0.12} maxPolarAngle={Math.PI / 2} />
}

/** Object review only. The other objects remain untouched until this CEO is approved. */
export function CeoReview() {
  const [detail, setDetail] = useState(true)
  const [reset, setReset] = useState(0)
  return <main className="ceo-review">
    <header>
      <div><h1>CEO hologram · first object</h1><p>Compare the shape, face and blue glow. Drag the 3D model to inspect every side; scroll to zoom.</p></div>
      <a href="/">Return to current room</a>
    </header>
    <nav aria-label="Comparison view">
      <button aria-pressed={!detail} onClick={() => {setDetail(false); setReset(n => n + 1)}}>Reference framing</button>
      <button aria-pressed={detail} onClick={() => {setDetail(true); setReset(n => n + 1)}}>Inspect detail</button>
      <button onClick={() => setReset(n => n + 1)}>Reset camera</button>
    </nav>
    <div className={`ceo-comparison${detail ? ' detail' : ''}`}>
      <figure>
        <figcaption>Reference</figcaption>
        <div className={`ceo-reference${detail ? ' detail' : ''}`}>
          <img src={detail ? '/room.jpg' : '/reference/grok-room-wide.jpg'} alt="Reference: blue human hologram above the round table" />
        </div>
      </figure>
      <figure>
        <figcaption>3D revision</figcaption>
        <div className="ceo-model" role="img" aria-label="Interactive 3D CEO hologram; drag to orbit and scroll to zoom">
          <ModelBoundary>
            <Canvas dpr={[1, 2]} camera={{position: [0, 0.67, 2.2], fov: 48, near: 0.01, far: 20}} gl={{antialias: true}}>
              <color attach="background" args={['#02050d']} />
              <Suspense fallback={<Html center>Loading CEO…</Html>}><CeoModel /></Suspense>
              <Camera detail={detail} reset={reset} />
              <EffectComposer><Bloom intensity={0.35} luminanceThreshold={0.65} mipmapBlur /></EffectComposer>
            </Canvas>
          </ModelBoundary>
        </div>
      </figure>
    </div>
    <p className="ceo-review-note">Only the CEO is being reviewed here. The room, table, chairs and agents have not been replaced.</p>
  </main>
}
