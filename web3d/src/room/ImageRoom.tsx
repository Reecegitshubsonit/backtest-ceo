import { useEffect, useMemo } from 'react'
import { COMPUTERS } from '../config/computers'
import { CEO_CHEST, CEO_LABEL, SUMMARY_LABEL, ROOM_IMAGE, SCREEN_RECTS, SEAT_SPOTS, zoomTo, type Rect } from '../config/imageRoom'
import { SEATS } from '../config/seats'
import type { PanelAction, PanelState } from '../model/panel'
import { Sparkles } from './Sparkles'

const { w: W, h: H } = ROOM_IMAGE
const pct = (r: Rect) => ({ left: `${(r.x / W) * 100}%`, top: `${(r.y / H) * 100}%`, width: `${(r.w / W) * 100}%`, height: `${(r.h / H) * 100}%` })

interface Props { panel: PanelState; dispatch: (a: PanelAction) => void }

/**
 * The room as the reference picture, brought to life: our agent labels over the picture's own, the wall screens as
 * clickable computers, data streams into the CEO, a pulsing table and sparkles. Clicking a screen zooms into it.
 */
export function ImageRoom({ panel, dispatch }: Props) {
  const reduced = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, [])
  const zoomed = (panel.phase === 'flying' || panel.phase === 'open') && panel.computer
  const z = zoomed ? zoomTo(SCREEN_RECTS[panel.computer!]) : { tx: 0, ty: 0, s: 1 }

  // without a transition there is no transitionend: advance the panel state machine straight away
  useEffect(() => {
    if (!reduced) return
    if (panel.phase === 'flying') dispatch({ type: 'arrived' })
    if (panel.phase === 'closing') dispatch({ type: 'returned' })
  }, [panel.phase, reduced, dispatch])

  const onEnd = (e: React.TransitionEvent) => {
    if (e.target !== e.currentTarget || e.propertyName !== 'transform') return
    if (panel.phase === 'flying') dispatch({ type: 'arrived' })
    if (panel.phase === 'closing') dispatch({ type: 'returned' })
  }

  return (
    <div className="imageroom">
      <div className="imageroom-bg" style={{ backgroundImage: `url(${ROOM_IMAGE.src})` }} />
      <div className="stage">
        <div className={`stage-inner${reduced ? ' still' : ''}`} onTransitionEnd={onEnd}
          style={{ transform: `translate(${z.tx}%, ${z.ty}%) scale(${z.s})` }}>
          <img src={ROOM_IMAGE.src} alt="CEO AI on the strategy table with six agents around it" draggable={false} />
          <svg className="overlay" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden>
            {SEATS.map((seat, i) => {
              const [x, y] = SEAT_SPOTS[seat.id].chest
              const d = `M${x},${y} Q${(x + CEO_CHEST[0]) / 2},${Math.min(y, CEO_CHEST[1]) - 60} ${CEO_CHEST[0]},${CEO_CHEST[1]}`
              return (
                <g key={seat.id}>
                  <path d={d} className="streambase" />
                  <path d={d} className="stream" style={{ animationDuration: `${2.2 + (i % 3) * 0.5}s` }} />
                </g>
              )
            })}
          </svg>
          <Sparkles active={panel.phase === 'closed'} />
          <div className="ceolabel" style={pct(CEO_LABEL)}>
            <b>CEO AI</b><span>STRATEGIC OVERSIGHT</span><span>FINAL DECISION AUTHORITY</span>
          </div>
          <div className="summarylabel" style={pct(SUMMARY_LABEL)}><b>EXECUTIVE SUMMARY</b><span>SYNTHESIZING AGENT REPORTS</span></div>
          {SEATS.map(seat => (
            <div key={seat.id} className="seatlabel" style={pct(SEAT_SPOTS[seat.id].label)}>
              <b className={seat.name.length > 14 ? 'long' : ''}>{seat.name}</b><span>{seat.job}</span><span className="live">● Live Feed</span>
            </div>
          ))}
          {COMPUTERS.map(c => (
            <button key={c.id} className="screenspot" style={pct(SCREEN_RECTS[c.id])} aria-label={`Open the ${c.label} computer`}
              disabled={panel.phase !== 'closed'} onClick={() => dispatch({ type: 'click', id: c.id })}>
              <span className="screentag">{c.label}<em>{c.live ? '● LIVE' : 'NEXT'}</em></span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
