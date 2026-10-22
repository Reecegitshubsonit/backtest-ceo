import type { ComputerId } from '../model/types'

export interface Computer { id: ComputerId; label: string; angleDeg: number; y: number; w: number; h: number; live: boolean }

/** The three clickable computers: big chart screens on the wall either side of the CEO (180 degrees = straight behind). */
export const COMPUTERS: Computer[] = [
  { id: 'scanner', label: 'SCANNER', angleDeg: 150, y: 2.35, w: 3.0, h: 1.5, live: false },
  { id: 'backtests', label: 'BACKTESTS', angleDeg: 150, y: 4.25, w: 3.0, h: 1.8, live: true },
  { id: 'strategies', label: 'STRATEGIES', angleDeg: 210, y: 4.25, w: 3.0, h: 1.8, live: false },
]

export const WALL_RADIUS = 7.4

export const computerById = (id: ComputerId): Computer => COMPUTERS.find(c => c.id === id)!
