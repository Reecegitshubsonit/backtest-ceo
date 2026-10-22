import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiFailure } from '../src/net/api'

const respond = (status: number, body: unknown) =>
  vi.stubGlobal('fetch', vi.fn(async () => new Response(body == null ? 'x' : JSON.stringify(body), { status })))

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('builds the query and returns the body', async () => {
    respond(200, { symbol: 'SPY', bars: [] })
    await api.bars('etfs', 'SPY', '5Min', '2026-10-20', '2026-10-20')
    const url = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(url).toBe('/api/bars?asset=etfs&symbol=SPY&tf=5Min&start=2026-10-20&end=2026-10-20')
  })
  it('turns engine errors into ApiFailure with the code and message', async () => {
    respond(404, { code: 'EMPTY', message: 'No bars' })
    await expect(api.bars('etfs', 'SPY', '5Min', '2026-10-20', '2026-10-20')).rejects.toMatchObject({ code: 'EMPTY', message: 'No bars' })
  })
  it('reports a missing engine plainly', async () => {
    respond(502, null)
    const e = await api.health().catch(x => x)
    expect(e).toBeInstanceOf(ApiFailure)
    expect(e.code).toBe('ENGINE_DOWN')
  })
})
