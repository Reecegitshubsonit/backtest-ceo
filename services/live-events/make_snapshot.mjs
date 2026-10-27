// node make_snapshot.mjs > <repo>/web3d/src/room3d/resultsSnapshot.ts
import { loadResults } from './results.mjs'
const r = loadResults(), round = v => typeof v === 'number' ? Math.round(v * 10000) / 10000 : v
const json = JSON.stringify(r.strategies, (k, v) => Array.isArray(v) && typeof v[0] === 'number' ? v.map(round) : typeof v === 'number' ? round(v) : v)
process.stdout.write(`// SNAPSHOT of /workspace/backtests/results.json (generated ${r.generated}), grouped into its 6 strategies.
// Real backtest output, embedded because the room cannot read files on the box. Regenerate with
// /workspace/live-events/make_snapshot.mjs. A live strategy_result event for the same strategy replaces it.
import type { StrategyResult } from './liveFeed'
export const RESULTS_SNAPSHOT_AT = ${JSON.stringify(r.generated)}
export const RESULTS_COSTS: Record<string, string> = ${JSON.stringify(r.costs)}
export const RESULTS_SNAPSHOT: StrategyResult[] = ${json}
`)
