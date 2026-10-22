export type Asset = 'stocks' | 'etfs' | 'crypto' | 'options'
export type Timeframe = '1Min' | '5Min' | '15Min' | '1Hour' | '1Day'
export type ComputerId = 'scanner' | 'backtests' | 'strategies'

export const ASSET_TABS: { id: Asset; label: string }[] = [
  { id: 'stocks', label: 'Stocks' }, { id: 'etfs', label: 'ETFs' }, { id: 'crypto', label: 'Crypto' }, { id: 'options', label: 'Options' },
]
export const TIMEFRAMES: Timeframe[] = ['1Min', '5Min', '15Min', '1Hour', '1Day']

/** One OHLCV bar from the engine; `t` is the bar start, UTC ISO. */
export interface Bar { t: string; o: number; h: number; l: number; c: number; v: number }
export interface BarsResponse { symbol: string; asset: Asset; tf: Timeframe; bars: Bar[] }
export interface Contract { symbol: string; type: 'call' | 'put'; strike: number }
export interface Chain { underlying: string; expiration: string; underlying_close: number | null; contracts: Contract[] }
