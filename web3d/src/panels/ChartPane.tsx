import { useMemo } from 'react'
import type { Bar, Timeframe } from '../model/types'
import { revealed } from '../model/replay'
import { useReplay } from '../hooks/useReplay'
import { ChartView } from './ChartView'
import { ReplayBar } from './ReplayBar'

interface Props { title: string; tf: Timeframe; bars: Bar[]; companion?: { title: string; bars: Bar[] } }

/** Main chart under the replay clock; an optional companion (the option's underlying) is cut to the same time. */
export function ChartPane({ title, tf, bars, companion }: Props) {
  const replay = useReplay(bars.length, title + tf + (bars[0]?.t ?? ''))
  const shown = useMemo(() => revealed(bars, replay.state), [bars, replay.state])
  const now = shown[shown.length - 1]?.t
  const companionShown = useMemo(
    () => (companion && now ? companion.bars.filter(b => b.t <= now) : []),
    [companion, now],
  )
  return (
    <div className="chartpane">
      <ReplayBar n={bars.length} replay={replay} time={now} />
      {companion && <ChartView bars={companionShown} tf={tf} title={companion.title} height={170} />}
      <ChartView bars={shown} tf={tf} title={title} height={companion ? 330 : 440} />
    </div>
  )
}
