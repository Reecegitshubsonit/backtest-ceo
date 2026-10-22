import type { PanelState } from '../model/panel'
import { Slot } from './Slot'

/** Full-screen panel over the room, showing the focused screen's view (moved in, not re-created). */
export function ComputerPanel({ panel, host }: { panel: PanelState; host: HTMLElement }) {
  if (panel.phase !== 'expanded') return null
  return <section className="computerpanel" role="dialog" aria-label="Screen"><Slot host={host} className="slotfill" /></section>
}
