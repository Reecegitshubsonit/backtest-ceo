// Fake engine for front-end work without Alpaca keys. Same /api routes and error shape as engine/backtestceo/server.py.
// node scripts/mock_engine.mjs [--port 8020]   symbol FAIL -> ALPACA_REJECTED, symbol NONE -> EMPTY
import http from 'node:http'

const port = Number(process.argv[process.argv.indexOf('--port') + 1]) || 8020
const STEP = { '1Min': 1, '5Min': 5, '15Min': 15, '1Hour': 60, '1Day': 1440 }

function rng(seed) { let s = [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 7); return () => ((s = (s * 1103515245 + 12345) | 0) >>> 0) / 4294967296 }

function bars(asset, symbol, tf, start, end) {
  const r = rng(symbol + tf), out = []
  let price = asset === 'options' ? 4 + r() * 6 : asset === 'crypto' ? 60000 : 100 + r() * 500
  const step = STEP[tf]
  for (let d = new Date(start + 'T00:00:00Z'); d <= new Date(end + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + 1)) {
    const wd = d.getUTCDay()
    if (asset !== 'crypto' && (wd === 0 || wd === 6)) continue
    const [from, to] = tf === '1Day' ? [asset === 'crypto' ? 0 : 240, asset === 'crypto' ? 1 : 241] : asset === 'crypto' ? [0, 1440] : [810, 1200]
    for (let m = from; m < to; m += step) {
      const o = price, c = Math.max(0.05, o * (1 + (r() - 0.5) * 0.004 * Math.sqrt(step)))
      out.push({ t: new Date(d.getTime() + m * 60000).toISOString().replace('.000', ''), o, h: Math.max(o, c) * (1 + r() * 0.001), l: Math.min(o, c) * (1 - r() * 0.001), c, v: Math.round(1000 + r() * 50000) })
      price = c
    }
  }
  return out
}

function fridays(on, k) { const d = new Date(on + 'T00:00:00Z'), out = []; while (out.length < k) { d.setUTCDate(d.getUTCDate() + 1); if (d.getUTCDay() === 5) out.push(d.toISOString().slice(0, 10)) } return out }

const send = (res, status, body) => { res.writeHead(status, { 'content-type': 'application/json' }); res.end(JSON.stringify(body)) }

http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x'), q = Object.fromEntries(u.searchParams)
  if (u.pathname === '/api/health') return send(res, 200, { ok: true, alpaca_keys_present: false })
  if (u.pathname === '/api/bars') {
    const sym = (q.symbol || '').toUpperCase()
    if (sym === 'FAIL') return send(res, 400, { code: 'ALPACA_REJECTED', message: 'Alpaca answered 422: invalid symbol (mock)' })
    if (q.asset === 'options' && q.start < '2024-02-01') return send(res, 400, { code: 'OPTIONS_TOO_EARLY', message: 'Alpaca options history starts 2024-02-01.' })
    const b = sym === 'NONE' ? [] : bars(q.asset, sym, q.tf, q.start, q.end)
    if (!b.length) return send(res, 404, { code: 'EMPTY', message: `No bars for ${sym} between ${q.start} and ${q.end}.` })
    return send(res, 200, { symbol: sym, asset: q.asset, tf: q.tf, bars: b })
  }
  if (u.pathname === '/api/options/expirations') return send(res, 200, { underlying: q.underlying, on: q.on, expirations: fridays(q.on, 6) })
  if (u.pathname === '/api/options/chain') {
    const atm = 600, yy = q.expiration.slice(2, 4) + q.expiration.slice(5, 7) + q.expiration.slice(8, 10), contracts = []
    for (let s = atm - 25; s <= atm + 25; s++) for (const t of ['call', 'put'])
      contracts.push({ symbol: `${q.underlying}${yy}${t === 'call' ? 'C' : 'P'}${String(s * 1000).padStart(8, '0')}`, type: t, strike: s })
    return send(res, 200, { underlying: q.underlying, expiration: q.expiration, underlying_close: 600.4, contracts })
  }
  send(res, 404, { code: 'NOT_FOUND', message: 'unknown route' })
}).listen(port, () => console.log(`mock engine on http://127.0.0.1:${port}`))
