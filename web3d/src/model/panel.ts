import type { ComputerId } from './types'

export type Phase = 'closed' | 'flying' | 'open' | 'closing'
export interface PanelState { phase: Phase; computer: ComputerId | null }
export type PanelAction = { type: 'click'; id: ComputerId } | { type: 'arrived' } | { type: 'close' } | { type: 'returned' }

export const PANEL_CLOSED: PanelState = { phase: 'closed', computer: null }

/** closed -> flying (camera moves) -> open (panel shown) -> closing (camera returns) -> closed. */
export function panelReduce(s: PanelState, a: PanelAction): PanelState {
  switch (a.type) {
    case 'click': return s.phase === 'closed' || s.phase === 'open' ? { phase: 'flying', computer: a.id } : s
    case 'arrived': return s.phase === 'flying' ? { ...s, phase: 'open' } : s
    case 'close': return s.phase === 'open' || s.phase === 'flying' ? { ...s, phase: 'closing' } : s
    case 'returned': return s.phase === 'closing' ? PANEL_CLOSED : s
  }
}
