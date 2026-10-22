import type { ComputerId } from '../model/types'

export interface Computer { id: ComputerId; label: string; live: boolean }

/** What the three computer screens open. Where they hang is in screens3d.ts. */
export const COMPUTERS: Computer[] = [
  { id: 'scanner', label: 'SCANNER', live: false },
  { id: 'backtests', label: 'BACKTESTS', live: true },
  { id: 'strategies', label: 'STRATEGIES', live: false },
]

export const computerById = (id: ComputerId): Computer => COMPUTERS.find(c => c.id === id)!
