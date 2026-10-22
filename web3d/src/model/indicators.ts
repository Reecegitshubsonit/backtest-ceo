import type { Bar } from './types'

/** One chart indicator. `compute` gets only revealed bars and returns one value (or null) per bar. */
export interface Indicator {
  id: string
  name: string
  color: string
  pane: 'overlay' | 'lower'
  compute: (bars: Bar[]) => (number | null)[]
}

/** Empty on purpose: each indicator will be added with the strategy that uses it. */
export const INDICATORS: Indicator[] = []
