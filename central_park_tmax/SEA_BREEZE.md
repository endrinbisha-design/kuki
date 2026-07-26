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

## 3. HRRR hourly afternoon shape (piece 4 — BUILT AND FALSIFIED)

`data/hrrr_hourly.py` pulls the hourly 2 m temp + 10 m wind trace at CP+JFK and distills
`hrrr_peak_hour_local`, `hrrr_afternoon_range_f`, `hrrr_sees_cap`, `hrrr_onshore_hours`,
`hrrr_cp_jfk_gap_pm_f`. Opt-in at predict time (`CPT_HRRR_SHAPE=1`). It works
mechanically — the 2026-07-24 live run resolved a 3 PM sea-breeze passage explicitly
(CP peaking 84 F at 14h, wind veering NE→SSE at 15h with a 2.6 F drop).

**But the case-control backtest falsified it as a bust predictor. Do not trade it.**

144 days with usable traces (12Z runs; 2018-2025 bust days + month-matched controls):

| signal | result |
|---|---|
| `hrrr_sees_cap` days (n=13) | bust rate **46%** |
| no-cap days (n=131) | bust rate **50%** |
| AUC `hrrr_onshore_hours` | **0.506** (coin flip) |
| AUC `hrrr_cp_jfk_gap_pm_f` | **0.366** (inverted) |
| AUC `hrrr_afternoon_range_f` | **0.438** (inverted) |

All AUCs sit at or below 0.5, and the correlations that exist carry the *opposite* sign
to the physical hypothesis (`peak_hour` r=−0.28; `cp_jfk_gap` r=+0.21). Nothing supports
the intended use.

Two honest reasons it failed:

1. **Label mismatch.** The label is "MOS busted ≥2.5 F cool", not "a sea breeze
   happened". When HRRR sees a cap, MOS usually saw it too — so a capped day is not a
   MOS bust. On the 13 cap-flag days MOS error averaged only −0.93 F vs −2.04 F overall:
   MOS was *more* accurate exactly when HRRR flagged a cap.
2. **The flag selects the wrong days.** Cap-flag days averaged an actual max of 71.9 F
   vs 77.9 F overall — `hrrr_sees_cap` fires on generally cool/cloudy days, not warm
   sea-breeze days.

A fairer future test would score HRRR's own point forecast against MOS on flagged days,
rather than treating shape as a predictor of another model's error. Artifacts:
`backtest_datasets/hrrr_shape_backtest.csv`, `scripts/hrrr_shape_backtest.py`.
