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
1. **Forecast:** GFS and ECMWF deterministic forecasts (Open-Meteo), averaged. It takes each model's
   climate-day high or low at the station's coordinates.
2. **Calibration:** `calibrate` measures, per station, the error of *the same two models* one and two days ahead
   against Kalshi's settled values. The forecast distribution is Normal(model average + bias, error sd).
   - The first version calibrated a different forecast (Open-Meteo "best match") from the one it traded, which
     shifted the centre by up to 3°F. Calibration files now record their models, and mismatched ones are ignored.
3. **Lead time:** tomorrow's markets only, by default. Same-day isn't calibrated, and the market there has live
   observations.
4. **Bracket probabilities:** computed with the whole-degree rounding. Each is then 50% model and 50% market mid.
   - "Edges" above 20¢ are logged as model error and skipped.
   - Longshots under 10¢ are skipped.
   - It buys YES or NO only when the edge clears the ask plus the taker fee by `min_edge` (6¢).

## Backtest before trusting it
`backtest` replays the last ~58 days, which is all Kalshi keeps outside its archive.
- **Decision time:** 20:00 UTC the day before.
- **Prices:** real Kalshi bid and ask from hourly candles.
- **Forecast:** the day-ahead forecast that existed then.
- **Bias and spread:** fitted on the station's *other* days only.
- **Rules:** the same buying rules as live.

It prints P&L, ROI and t for several settings, per city. It also reports a Brier score for the model and for
the market, on every quoted bracket. If the market's Brier is lower, the market already forecasts better than
this model, and any "edge" is noise.

## Use (from the `kalshi/` folder)
```bash
cp weather_config.example.json weather_config.json
```
Read-only: show mispriced brackets now.
```bash
.venv/bin/python -m weather scan
```
Measure forecast error per station against Kalshi's settled values (60 days), then backtest:
```bash
.venv/bin/python -m weather calibrate --days 60
```
```bash
.venv/bin/python -m weather backtest
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

## Result, 2026-11-04: do not trade
Settings: 58 days, 31 series, 10,249 quoted brackets, decisions the day before.
- **Brier score:** the model scored **0.1286**, the market **0.1065**. The market forecasts temperature
  brackets better than GFS+ECMWF with station bias correction.
- **Every variant lost 16–20% ROI, with t from −3 to −6.5.** That covers model-only and 50/50 blends, and
  minimum edges of 3, 6 and 10¢.
- **The few cities with positive ROI (ATL, MIA, SEA, SFO) are noise.** All have t < 1.7, and 21 cities would
  produce a few positives by chance.
- **Calibration itself is now sane.** One-day and two-day errors are similar, at 1.6–2.5°F sd for most stations.

Beating these markets would need inputs the free global models don't have. Examples are station-level National
Blend of Models (NBM) probabilities, HRRR or MOS guidance, and same-day observation trends. Any new model
should beat the market's Brier score in `backtest` before it trades.

## NBM retest, 2026-11-04: also loses
The National Blend of Models (NWS station forecast: TXN with its own XND spread, 12Z run the day before),
with leave-one-out bias and spread, across 19 series and 6,268 brackets:
- **Brier score:** NBM 0.1337 vs market 0.1051.
- **ROI:** −14% to −19% in every variant, t from −2.7 to −5.1.

Public forecasts do not beat these markets the day before.
