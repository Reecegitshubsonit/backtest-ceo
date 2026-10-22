import { SPEEDS } from '../model/replay'
import { fmtStamp } from '../model/format'
import type { useReplay } from '../hooks/useReplay'

interface Props { n: number; replay: ReturnType<typeof useReplay>; time?: string }

/** Play, pause, step, speed and a scrubber for the replay clock. */
export function ReplayBar({ n, replay, time }: Props) {
  const { state } = replay
  return (
    <div className="replaybar" role="toolbar" aria-label="Replay">
      <button onClick={() => replay.step(-1)} aria-label="Step back">◀︎</button>
      {state.playing
        ? <button onClick={replay.pause} aria-label="Pause">❚❚ Pause</button>
        : <button onClick={replay.play} aria-label="Play">▶ Play</button>}
      <button onClick={() => replay.step(1)} aria-label="Step forward">▶︎</button>
      <label>Speed
        <select value={state.speed} onChange={e => replay.setSpeed(Number(e.target.value))}>
          {SPEEDS.map(s => <option key={s} value={s}>{s}x</option>)}
        </select>
      </label>
      <input type="range" min={0} max={Math.max(0, n - 1)} value={state.index} aria-label="Replay position"
        onChange={e => replay.seek(Number(e.target.value))} />
      <span className="muted">bar {Math.min(n, state.index + 1)} of {n}{time ? ` · ${fmtStamp(time)}` : ''}</span>
    </div>
  )
}
