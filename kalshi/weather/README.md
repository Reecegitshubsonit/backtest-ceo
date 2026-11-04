# Weather bot: Kalshi daily high and low temperature markets

Separate from the copy bot. It uses the same Kalshi client and paper or live machinery.

## The markets
- **Cities:** about 20 US cities have a daily **high** market (`KXHIGHNY`, `KXHIGHCHI`, ...), and about 10 have a
  daily **low** market (`KXLOWTNYC`, ...).
- **Brackets:** each day has 2°F brackets plus an open bracket at each end, e.g. "69° or below", "70° to 71°",
  "78° or above".
- **What settles them:** the official climate-report (CLI) station, such as Central Park for NYC (the
  `(CLINYC)` in the rules), as published by The Weather Company. The value is a whole °F over the **NWS
  climate day**: midnight to midnight *local standard time*, so 1am to 1am during daylight time.
- After settling, Kalshi records the actual value in `expiration_value`. Calibration uses that as ground truth.
- **When to trade:** each city-day trades from the morning before until 1am the next day. Volume is about
  $5–10K a day per bracket in big cities.

## How it estimates probabilities
1. **Ensemble forecasts:** Open-Meteo's GFS (31 members) and ECMWF (51 members). Hourly temperature at the
   station's coordinates.
2. **Each member's high or low:** taken over the exact climate-day window.
3. **Forecast distribution:** Normal(ensemble mean + bias, max(ensemble spread × 1.3, error floor for the lead time)).
   - Ensembles are under-dispersed.
   - An hourly grid misses the peak, so raw highs run low. The default bias is +0.8°F.
   - `calibrate` replaces the bias and error floor with errors measured per station.
4. **Same-day trading:** the temperature observed so far (NWS station observations) is a hard floor for the high
   (a ceiling for the low). Brackets it has already passed are worth 0 or 1. This is often the clearest edge
   late in the day.
5. **Bracket probabilities:** each bracket's probability is computed with the whole-degree rounding.
6. **Blending:** highs centre on 50% NWS point forecast and 50% ensemble. The bracket probability is then
   50% model and 50% market mid. Any remaining "edge" above 20¢ is logged as model error and skipped. Longshots
   under 10¢ are skipped.
7. **When it buys:** YES or NO, whichever beats the ask plus the taker fee by at least `min_edge` (6¢).

The first uncalibrated paper run (2026-11-04) bought six 5–8¢ longshots at "edges" of 20–37¢. That's the
signature of a model that's off by 2–3°F, which is why these guards exist.

## Use (from the `kalshi/` folder)
```bash
cp weather_config.example.json weather_config.json
```
Read-only: show mispriced brackets now.
```bash
.venv/bin/python -m weather scan
```
Measure forecast error per station against Kalshi's settled values (60 days):
```bash
.venv/bin/python -m weather calibrate --days 60
```
Paper trade, every 15 minutes:
```bash
.venv/bin/python -m weather paper
```
```bash
.venv/bin/python -m weather status
```
Live trading needs `"live": true` in `weather_config.json` **and** `--live`:
```bash
.venv/bin/python -m weather live --live
```

## Limits (defaults)
| Limit | Value |
|---|---|
| Per bet | $2 |
| Per market | $2 |
| Per city-day | $4 |
| Total | $8 |
| Price range | 5–92¢ |

The kill switch file `data/STOP` stops new buys for both bots. The weather bot and the copy bot share one Kalshi
balance, so weather losses also count toward the copy bot's drawdown limit.

## Caveats
- **Not yet validated.** Run `calibrate`, then paper trade for a week or two, before going live. Weather markets
  attract forecast-savvy traders, so a 6¢ model edge is often model error rather than mispricing.
- **The settlement source can differ from NWS.** It's The Weather Company's report of the CLI station, and
  preliminary readings can differ from the final value by rounding.
- **Station coordinates:** the bot uses the official ASOS site. Ensemble grid cells (about 25 km) smooth coastal
  and urban effects (LA, SF, Miami), and calibration absorbs some of that.
- **Data sources:**
  - Forecasts: `ensemble-api.open-meteo.com` and `previous-runs-api.open-meteo.com`, both free with no key.
  - Observations: `api.weather.gov`.
