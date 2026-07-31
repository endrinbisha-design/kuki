# Lessons — what live trading actually taught us

Everything here was learned by losing money, winning money, or being contradicted by the
market on a specific dated day. Each entry says what happened, what the rule is, and
**where it lives in code** so it survives without anyone remembering it.

The measured statistics behind these rules are in `MOS_MULTIYEAR_BACKTEST.md`,
`HOT_DAY_CALIBRATION.md`, `DAILY_STRATEGY.md`, `POST_PEAK.md`, `EDGE_DECAY.md`,
`SEA_BREEZE.md`; the day-by-day record is `track_record/call_log.jsonl`.

---

## 1. Settlement is round-half-up, so measure to the .5 — never to the whole degree

The NWS CLI reports whole degrees. A contract labelled **112–113 wins at a true max of
111.5 °F**, not 112.0 °F.

* **2025-07-25 Phoenix.** A NO position at 117–118 lost because 116.60 °F settled as
  **117**. The bet looked ~1.4 °F safe; it was 0.1 °F safe.
* **2025-07-30 Vegas.** The banked max was 111.02 °F and the position needed 111.5, not
  112 — a 0.48 °F gap, which in sensor units is 43.9 °C needing 44.2 °C. Three tenths, not
  a full degree. Same mechanism, opposite side of the trade.

**Rule:** before sizing anything post-peak, compute the distance to the nearest .5
boundary above the current max. That number is the real margin.

*In code:* `models/post_peak.py` returns `distance_to_boundary_f` and
`near_rounding_boundary` on every outlook; `models/daily_strategy.py` puts it in the
POST_PEAK_LOCK action list.

---

## 2. `determined` from hourly climatology is wrong while the temperature is still rising

The remaining-rise table answers *"across all days, how much more did it rise after this
hour?"* — an **unconditional** question. On a day that is still climbing at 4 PM, that is
the wrong reference class.

* **2025-07-29.** The raw flag read `determined=True` in NYC, Phoenix and Vegas
  *simultaneously* while all three were still rising. That simultaneity is the tell: a
  genuine post-peak lock is a local weather fact, not a synchronized national event.

**Rule:** if the last two observations are flat-or-rising (within sensor noise, 0.2 °F),
the max is **not** determined regardless of what the hourly climatology says. No trace
available ⇒ treat as still rising.

*In code:* `post_peak.is_still_rising()`, enforced inside `settlement_distribution()`;
the live trace comes from `data/fast_metar.py` (`SettlementMax.recent_temps_f`) and is
passed through by `pipelines/predict.py`.

---

## 3. Do not override the post-peak tool with a narrative

* **2025-07-26 NYC.** `determined` was False (89 % vs the 90 % threshold). I overrode it
  because the trace showed "peak, then decline — the max is banked." The temperature
  re-warmed to 84.02 °F and **both recommended legs lost.**

**Rule:** the threshold is mechanical. 89 % is not 90 %. A plausible story about why the
day is over is exactly the input that has no measured skill.

*In code:* the threshold is the only gate; nothing in the pipeline can talk it up.
*In the record:* `track_record/call_log.jsonl`, 2025-07-26.

---

## 4. "Avoid" applies to the instrument, not to the day

* **2025-07-30 NYC.** The selector said WET_DAY_AVOID and I said no trade. The user traded
  **≤77 °F** — a wide one-sided range, not a bucket — and cashed **+$50.**

Wet days have MAE ~2× dry days and fat tails *both* ways. That destroys a 2-degree bucket
and simultaneously creates the edge in a half-line, because the market prices the point
forecast while the tail is 23 % (NYC), 31 % (Phoenix), 41 % (Vegas).

**Rule:** on a wet day, refuse narrow buckets and *look for* the wide one-sided range on
the fat-tail side.

*In code:* the WET_DAY_AVOID branch of `models/daily_strategy.py` now carries the
wide-range action explicitly.

---

## 5. Two anecdotes are not a calibration

I applied a **+2 °F Phoenix warm shift** after two hot days ran above guidance. Measured
over nine years, the dry-desert reality is **+0.9 °F median with a 24 % warm tail** — the
shift was more than double the true bias.

**Rule:** no adjustment enters the recommendation path until it has been fitted on the
multi-year series. Anecdotes open a research ticket, never a position.

*In code:* `models/hot_day_calibration.py` (`HOT_DAY_STATS`), fitted by
`scripts/hot_day_calibration_fit.py`.

---

## 6. The observation feed we trade on must be the one settlement derives from

Two independent defects were found on 2025-07-28 after the market repeatedly out-priced
our data:

1. `api.weather.gov` lagged the real feed by **~1 hour**. Trading off it means acting on
   information the market already has.
2. Hourly `:51` snapshots miss peaks *between* observations. The CLI settles on the
   continuous trace, carried publicly in the METAR **6-hour maximum group** (`1sTTT`).

Worked example: Jul 28 KNYC hourly peaked at 78.08 °F (implying a 78 settlement, a bucket
priced near zero) while the 6-hour group read `10261` = 26.1 °C = **79.0 °F** — exactly the
79–80 bucket the market held at 93¢. The market was not wrong; our data was.

**Rule:** settlement max = max(hourly snapshots, 6-hour groups), from
aviationweather.gov. Never trade an intraday disagreement before checking the 6-hour group.

*In code:* `data/fast_metar.py`, wired into `pipelines/predict.py` (only ever *raises* the
observed max).

---

## 7. The tradeable window is 15–17 h local, and it closes fast

From 360 **real settled markets** (candlesticks, not simulation): market |price − outcome|
falls steeply through the afternoon, and winners first cross 80 % around the mid-afternoon
hours. A mispricing observed after that is usually already gone — the Phoenix 119–120
anecdote (11¢ → 20¢ inside an hour) is representative, not exceptional.

**Rule:** the post-peak edge is real but short-lived; act inside the window or skip.

*In code / data:* `scripts/edge_decay_study.py`, `backtest_datasets/edge_decay.json`,
write-up in `EDGE_DECAY.md`.

---

## 8. Falsified ideas, kept falsified

Recorded so they are not re-tried on intuition:

* **HRRR afternoon-shape as a bust predictor** — mechanically works, no skill. Marked
  do-not-trade in `data/hrrr_hourly.py`; results in `backtest_datasets/hrrr_shape_backtest.csv`.
* **EMOS / quantile-regression distributional post-processing** — did not beat the
  rolling-bias Gaussian baseline on integer log-loss or top-2 accuracy across
  2019–2025 for any of the three cities.
  `scripts/conditional_distribution_backtest.py`, `backtest_datasets/conditional_distribution_backtest.json`.

The general shape: **observation-anchored edges have survived; forecast-anchored ones
mostly have not.** Live bucket bets driven by the point forecast went 5/16 while the point
forecast itself stayed accurate (MAE ~1.53 °F, mean error −0.24 °F). Being right about the
temperature is not the same as being right about the bucket.

---

## 9. Open — not yet resolved

* **2025-07-29 NYC, 79 vs 80.** Our computed max was 78.98 °F (→ 79) from two agreeing
  sources; the market held 80–81 at 99/100¢ on 73k volume and settled against us.
  One-minute ASOS is not published for KNYC, so the discrepancy could not be reconciled.
  Treat a high-volume market disagreement at ≥95¢ as evidence we are missing data, not as
  an edge — that is the only defensible reading until this is explained.
* **All strategy ROI figures except the edge-decay study are against a simulated market.**
  `scripts/archive_kalshi_prices.py` runs on a schedule accumulating real prices; the first
  real-price strategy backtest is still pending.
