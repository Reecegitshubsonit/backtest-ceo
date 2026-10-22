export type Phase = 'closed' | 'flying' | 'focused' | 'expanded' | 'closing'
/** `screen` is the id of the screen clicked (see config/screens3d). */
export interface PanelState { phase: Phase; screen: string | null }
export type PanelAction = { type: 'click'; id: string } | { type: 'arrived' } | { type: 'expand' } | { type: 'back' } | { type: 'returned' }

export const PANEL_CLOSED: PanelState = { phase: 'closed', screen: null }

/** closed -> flying (camera moves) -> focused (live preview on the screen) -> expanded (full panel); back steps out one level. */
export function panelReduce(s: PanelState, a: PanelAction): PanelState {
  switch (a.type) {
    case 'click': return s.phase === 'closed' || s.phase === 'focused' ? { phase: 'flying', screen: a.id } : s
    case 'arrived': return s.phase === 'flying' ? { ...s, phase: 'focused' } : s
    case 'expand': return s.phase === 'focused' ? { ...s, phase: 'expanded' } : s
    case 'back': return s.phase === 'expanded' ? { ...s, phase: 'focused' } : s.phase === 'focused' || s.phase === 'flying' ? { ...s, phase: 'closing' } : s
    case 'returned': return s.phase === 'closing' ? PANEL_CLOSED : s
  }
}
