/** Replay clock for a loaded bar series. `index` is the last revealed bar; speed is bars per second. */
export interface ReplayState { index: number; playing: boolean; speed: number; acc: number }

export const SPEEDS = [1, 2, 5, 10, 25, 50]

const clampIndex = (i: number, n: number) => Math.min(Math.max(0, n - 1), Math.max(0, Math.round(i)))

/** A freshly loaded series shows every bar, paused. */
export const initialReplay = (n: number): ReplayState => ({ index: Math.max(0, n - 1), playing: false, speed: 5, acc: 0 })

export function tick(s: ReplayState, n: number, dtSec: number): ReplayState {
  if (!s.playing || n === 0) return s
  const acc = s.acc + dtSec * s.speed
  const steps = Math.floor(acc)
  const index = Math.min(n - 1, s.index + steps)
  return { ...s, index, acc: acc - steps, playing: index < n - 1 }
}

/** Play; from the last bar it rewinds to the first. */
export function play(s: ReplayState, n: number): ReplayState {
  return { ...s, playing: n > 1, index: s.index >= n - 1 ? 0 : s.index, acc: 0 }
}

export const pause = (s: ReplayState): ReplayState => (s.playing ? { ...s, playing: false } : s)

export const seek = (s: ReplayState, n: number, i: number): ReplayState => ({ ...s, index: clampIndex(i, n), acc: 0 })

export const step = (s: ReplayState, n: number, delta: number): ReplayState => seek(pause(s), n, s.index + delta)

/** Bars the chart may draw: never any past the replay clock. */
export const revealed = <T>(bars: T[], s: ReplayState): T[] => bars.slice(0, s.index + 1)
