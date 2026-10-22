import type { Timeframe } from './types'

const clock = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const day = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric' })

/** Axis label: ET clock time for intraday bars, month and day for daily bars. */
export const fmtTime = (t: string, tf: Timeframe): string => (tf === '1Day' ? day : clock).format(new Date(t))

export const fmtStamp = (t: string): string => `${day.format(new Date(t))} ${clock.format(new Date(t))} ET`

/** Options and cheap coins need a third decimal. */
export const fmtPrice = (v: number): string => v.toFixed(Math.abs(v) < 10 ? 3 : 2)
