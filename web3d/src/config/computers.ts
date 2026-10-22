import type { ComputerId } from '../model/types'

export interface Computer { id: ComputerId; label: string; angleDeg: number; live: boolean }

/** The three clickable computers on the wall behind the CEO (180 degrees = straight behind). */
export const COMPUTERS: Computer[] = [
  { id: 'scanner', label: 'SCANNER', angleDeg: 158, live: false },
  { id: 'backtests', label: 'BACKTESTS', angleDeg: 180, live: true },
  { id: 'strategies', label: 'STRATEGIES', angleDeg: 202, live: false },
]

export const WALL_RADIUS = 7.4
export const COMPUTER_Y = 3.0
export const COMPUTER_W = 2.6
export const COMPUTER_H = 1.6

export const computerById = (id: ComputerId): Computer => COMPUTERS.find(c => c.id === id)!
