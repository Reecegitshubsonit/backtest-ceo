import type { Asset, BarsResponse, Chain, Timeframe } from '../model/types'

export class ApiFailure extends Error {
  constructor(public code: string, message: string) { super(message) }
}

const DOWN = 'The engine is not running (expected on port 8020). Start it from the dock launcher or run engine/run.sh.'

async function get<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const q = new URLSearchParams(params).toString()
  let r: Response
  try { r = await fetch(`/api/${path}${q ? `?${q}` : ''}`) } catch { throw new ApiFailure('ENGINE_DOWN', DOWN) }
  const body = await r.json().catch(() => null)
  if (r.ok && body) return body as T
  if (!body && r.status >= 500) throw new ApiFailure('ENGINE_DOWN', DOWN)
  throw new ApiFailure(body?.code ?? `HTTP_${r.status}`, body?.message ?? `Engine answered ${r.status}.`)
}

export const api = {
  health: () => get<{ ok: boolean; alpaca_keys_present: boolean }>('health'),
  bars: (asset: Asset, symbol: string, tf: Timeframe, start: string, end: string) =>
    get<BarsResponse>('bars', { asset, symbol, tf, start, end }),
  expirations: (underlying: string, on: string) =>
    get<{ underlying: string; on: string; expirations: string[] }>('options/expirations', { underlying, on }),
  chain: (underlying: string, expiration: string, on: string) => get<Chain>('options/chain', { underlying, expiration, on }),
}
