import { useCallback, useEffect, useRef, useState } from 'react'
import { initialReplay, pause, play, seek, step, tick, type ReplayState } from '../model/replay'

/** Replay clock driven by requestAnimationFrame. Resets whenever a new series (length `n`, key `key`) loads. */
export function useReplay(n: number, key: string) {
  const [state, setState] = useState<ReplayState>(() => initialReplay(n))
  const last = useRef<number | null>(null)

  useEffect(() => { setState(initialReplay(n)) }, [n, key])

  useEffect(() => {
    if (!state.playing) { last.current = null; return }
    let raf = 0
    const loop = (now: number) => {
      const dt = last.current == null ? 0 : (now - last.current) / 1000
      last.current = now
      setState(s => tick(s, n, Math.min(dt, 0.25)))
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [state.playing, n])

  return {
    state,
    play: useCallback(() => setState(s => play(s, n)), [n]),
    pause: useCallback(() => setState(pause), []),
    seek: useCallback((i: number) => setState(s => seek(s, n, i)), [n]),
    step: useCallback((d: number) => setState(s => step(s, n, d)), [n]),
    setSpeed: useCallback((speed: number) => setState(s => ({ ...s, speed })), []),
  }
}
