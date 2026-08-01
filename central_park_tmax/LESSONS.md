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

* **2026-07-25 Phoenix.** A NO position at 117–118 lost because 116.60 °F settled as
  **117**. The bet looked ~1.4 °F safe; it was 0.1 °F safe.
* **2026-07-30 Vegas.** The banked max was 111.02 °F and the position needed 111.5, not
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

* **2026-07-29.** The raw flag read `determined=True` in NYC, Phoenix and Vegas
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

* **2026-07-26 NYC.** `determined` was False (89 % vs the 90 % threshold). I overrode it
  because the trace showed "peak, then decline — the max is banked." The temperature
  re-warmed to 84.02 °F and **both recommended legs lost.**

**Rule:** the threshold is mechanical. 89 % is not 90 %. A plausible story about why the
day is over is exactly the input that has no measured skill.

*In code:* the threshold is the only gate; nothing in the pipeline can talk it up.
*In the record:* `track_record/call_log.jsonl`, 2026-07-26.

---

## 4. "Avoid" applies to the instrument, not to the day

* **2026-07-30 NYC.** The selector said WET_DAY_AVOID and I said no trade. The user traded
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

Two independent defects were found on 2026-07-28 after the market repeatedly out-priced
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

## 9. The observed max is biased LOW during exactly the hours we trade

*Resolved 2026-07-31. This was the open "79 vs 80" mystery, and the answer is structural.*

**2026-07-29 NYC.** Our max read 78.98 °F (→ 79) from two agreeing sources. The market held
80–81 at 99/100¢ on 73k volume. The CLI settled **80** at 4:23 PM. The market was right.

Why we could not see it:

1. The METAR **6-hour maximum group** — the continuous trace the CLI settles on — is
   transmitted only at 05:51/11:51/17:51/23:51 Z. The group covering the **afternoon**
   (18Z–00Z) does not exist until **7:51 PM EDT**, hours after the trading window closes.
2. Inside the window the afternoon has only `:51` hourly snapshots, which miss between-obs
   spikes. On Jul 29 every snapshot after 14:51 read 78 while the trace hit 80.06 at
   ~4:23 PM.

Measured over 2021–2025 warm seasons (`scripts/snapshot_gap_study.py`), the afternoon
snapshot max under-reads the continuous max by a **median of ~1.0 °F** in all three cities;
P(gap ≥ 1 °F) = 50 % NYC, 58 % Phoenix, 45 % Vegas.

**Rules:**
- Between ~2 PM and ~7:50 PM local, the observed max is a **lower bound biased low by
  about a degree** — not a fact. Never quote it as "the day's max".
- A high-volume market pricing **one bucket above** our observed max is evidence we are
  behind the data, not a mispricing to fade. (This was the right instinct on Jul 29 —
  I declined to trade it — but for the wrong reason, and only luck made that free.)
- **Use the ~4:35 PM EDT preliminary CLI.** It is the settlement product, published inside
  the trading window; the Jul 29 20:32 Z product already said `MAXIMUM 80 at 227 PM`. It
  beats any METAR reconstruction. Caveat: it is a max-so-far, not a final — Jul 30's
  4:36 PM preliminary said 73 and the day finished 74 at 5:53 PM.

*In code:* `post_peak.snapshot_gap_percentiles()` + `CONTINUOUS_SOURCES`;
`settlement_distribution(observed_max_source=...)` convolves the measured gap unless the
max came from a continuous source, and an unknown source is treated as a snapshot.
`_try_intraday_cli_max()` in `pipelines/predict.py` already pulls the preliminary CLI —
the Jul 29 failure was operational, not a missing code path.

*Caveat inherited:* the remaining-rise climatology
(`scripts/build_remaining_rise.py`) derives its `daily_max` from hourly snapshots too, so
it cannot see this gap either — that is why it is measured and applied separately.

---

## 10. Kalshi's own settlements are free ground truth — and they caught a live bug

The settled markets are on the public API (no credentials, no manual entry):
`/markets?series_ticker=KXHIGHNY&status=settled`. Each day's winning `between` market
pins the settled value to a 2-degree bucket — the number **we actually get paid on**,
which no other source in this repo was validating against.

Running our settlement reconstruction against all 68 settled days × 3 cities
(`scripts/kalshi_settlement_validation.py`) immediately failed for NYC: **58/68**, with all
ten misses in the same direction — we read too high, once by 6 °F.

**Cause:** a 6-hour maximum group covers the period *ending* at the synoptic hour. At KNYC
(UTC-4) the 05:51 Z report is issued at 01:51 local and carries the 00–06 Z max — **8 PM to
2 AM of the previous day**. We were attributing it to today, so on any day cooler than the
one before it, yesterday's evening warmth became today's "observed max". Phoenix and Vegas
scored 100 % throughout: at UTC-7 the synoptic periods happen to land inside the local day,
which is precisely why the bug stayed hidden for three cities' worth of work.

This was **not** just a backtest artifact — `settlement_max_so_far()` had the same rule, so
it would have inflated the live observed max intraday and pushed us to buy a bucket too
high. After the fix: **204/204, 100 % in all three cities.**

The same run quantifies why the 6-hour group matters at all — agreement using *only*
hourly snapshots: **NYC 71 %, Phoenix 59 %, Vegas 63 %**. Trading off snapshots alone puts
you outside the paying bucket a third to
40 % of the time.

**Rule:** attribute a 6-hour group to the local day its **period** falls in, never the day
it was transmitted. And validate any settlement logic against Kalshi's settled markets —
it is the only free check on the number that actually pays.

*In code:* `data/fast_metar.six_hour_group_covers_local_day()`, enforced in
`settlement_max_so_far()`; validation in `scripts/kalshi_settlement_validation.py` ->
`backtest_datasets/kalshi_settlement_validation.json`.

---

## 11. At real prices, we have no demonstrated edge — and we are less calibrated than the market

The simulated-market caveat is now closed. `scripts/real_price_backtest.py` runs the
observation-anchored strategy against the actual order book (public candlesticks on 68
settled days × 3 cities, leakage-respecting, net of fees). Full write-up:
`REAL_PRICE_BACKTEST.md`.

Headline ROI looks positive (+8.3 % at edge ≥ 5 %) and **does not survive scrutiny**:

* Day-clustered bootstrap CI **straddles zero at every threshold** (−4.2 % … +20.9 %).
  One city-day supplies up to 4 buckets × 6 hours of near-identical information, so 507
  "trades" are ~173 independent clusters. Resampling rows instead of days would have
  reported false significance.
* By-hour ROI alternates sign every hour (+8, −10, +22, −0.3, +22, −24). A real
  time-window edge would be coherent; this is noise.

The substantive finding is the calibration table: our integer PMF is **overconfident**.
We say 6 % where the truth is 20 %, and 93 % where the truth is 86 %. In the low bins —
where the cheap contracts we trade most live — **the market price is closer to the realised
frequency than our model is**.

That matters because "edge" is defined as `model_p − price`. An overconfident model
manufactures edge as an artifact. The apparent +6.8 % is best read as the residue of
miscalibration.

**Rules:**
- Do not size off `model_p − price` until the PMF is recalibrated against realised
  frequencies (the backtest now emits the pairs needed to fit it, per city).
- **The market is the baseline, not zero.** A claim of edge must beat the price.
- Being right about settlement *mechanics* (204/204 in
  `kalshi_settlement_validation.py`) is a different claim from being right about
  *probabilities*. Only the first is currently supported.

---

**Recalibration outcome (done):** an isotonic correction with day-blocked folds fixes the
calibration (the 6 %-vs-20 % gap closes; Brier 0.19→0.18, 0.22→0.21) — **and the edge
vanishes with it**: +8.3 % → +1.2 %, and −2.6 % at the tightest filter. That confirms the
profit was miscalibration residue, not alpha. The market still beats our corrected model on
Brier (0.12–0.15 vs 0.18–0.21) in every city. **Do not trade `model_p − price` here.**

---

## 12. Always carry a benchmark whose plausible range you know

The 1:51 PM signal backtest (`REAL_PRICE_BACKTEST.md`) first returned **$100 → $4.2 million**,
+207 % per bet. The cause was a lookahead bug: the 36-hour candle window contains two candles
at local hour 14 (the market closes at 00:59 local the *next* day) and the selector took the
first — the **previous day's price**. It was buying yesterday's 2 ¢ out-of-the-money buckets
and settling them against today's outcome.

Nothing about the profit itself proved it was wrong; spectacular backtests are exactly what
a lookahead bug produces. **The benchmark caught it**: `MARKET_FAVOURITE` — buy whatever the
market likes most — "won" only 29 % of the time, and buying a market favourite *must* hit
near 50–60 %. An impossible benchmark result is the cheapest bug detector available.

**Rule:** every backtest carries a control whose plausible range is known in advance. Check
the control before reading the strategy. A headline return can't falsify itself.

**Corrected result, for the record:** the strategy loses. −5.4 % per bet, and the model picks
the same bucket as the market on 55 of 62 days — by 1:51 PM the 6-hour group is fully priced.

*In code:* `scripts/bet_after_1351_backtest.py` (`fill_price` matches the exact target
timestamp; four rules including the market-favourite control).

---

## 13. Open — not yet resolved
* **The wide one-sided ranges** that actually worked live (lesson #4) are excluded from the
  real-price backtest, which covers `between` markets only. That instrument is untested at
  real prices.
