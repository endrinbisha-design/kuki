# Sea-breeze / marine-cap risk add-on (KNYC)

NYC's ~2.3 F irreducible night-before error (MOS_MULTIYEAR_BACKTEST.md) is dominated by
marine-air intrusion days: the sea breeze caps Central Park's afternoon peak below
guidance (e.g. 2026-07-23: guidance 80-82, actual ~78-79, peak at 12:51 EDT). This
add-on attacks that failure mode with two instruments — both **advisory**, wired into
`predict_one` output for coastal configs (any config whose locations include a `jfk`
neighbor), never changing the point forecast.

## 1. Night-before risk classifier

`scripts/sea_breeze_classifier.py` trains on 2015-2025 warm seasons (May-Sep, 1,269
days): P(actual CP max busts >= 2.5 F below the 00Z GFS-MOS forecast) from
night-before-known inputs — forecast max, **forecast CP-JFK gradient** (strongest
predictor, +0.65 std coef: the gradient the breeze erases), MOS afternoon wind
direction/speed, NY-Harbor buoy 44065 SST -> land-sea contrast, and seasonality.

**Honest out-of-sample performance (yearly folds 2018-2025):**

| metric | value |
|---|---|
| pooled AUC | 0.609 |
| base bust rate | 13.0% |
| bust rate on top-15%-risk days | 20.2% (1.7x lift) |
| mean forecast error, flagged days | -0.26 F vs +0.39 F unflagged |
| warm-season MAE fixed by flag-shift | none (2.05 -> 2.05) |

Interpretation: the flag **identifies elevated-risk days but cannot time the breeze**
from night-before data — MOS already embeds KNYC's marine climatology, so what's left
is genuinely hard. Use it for **risk management, not point correction**: on flagged
days widen the downside of the distribution and avoid warm-tail bucket bets (a flagged
day is precisely where the 2026-07-23 "83-84 YES" loss came from).

## 2. Intraday coastal divergence (the sharper instrument)

Marine air reaches JFK/LGA 1-3 h before Central Park. `coastal_divergence` scores live
obs: JFK running >= 2-4 F cooler than CP, JFK wind onshore (SE-S, 90-200 deg), CP wind
already onshore, LGA-JFK spread. Score >= 0.5 => "MARINE INTRUSION UNDERWAY" in the
forecast report. This is the 1-3 h early warning that was missing on Jul 23, when CP's
own observations still looked like clean warming at 10:30 AM.

## Live wiring

- `features/sea_breeze.py` — distilled logistic (coefficients embedded with provenance),
  divergence scorer, NDBC realtime SST parser. Missing inputs mean-impute (z=0) so the
  score degrades gracefully.
- `pipelines/predict.py::_sea_breeze_advisory` — attaches `sea_breeze_risk` /
  `sea_breeze_flagged` (+ live `sea_breeze_underway` for same-day targets, from
  KNYC/KJFK/KLGA latest obs) to every non-synthetic coastal prediction. Best-effort;
  never blocks a forecast.
- Artifacts: `backtest_datasets/sea_breeze_classifier.json` (folds + distilled model),
  `backtest_datasets/nyc_seabreeze_frame.csv` (daily training frame).

## Deferred (piece 4)

HRRR hourly wind/temperature-shape extraction (does HRRR itself flatten the afternoon
curve?) — the only GRIB-heavy piece; expected to sharpen timing, deferred until the
archive machinery is chunked.
