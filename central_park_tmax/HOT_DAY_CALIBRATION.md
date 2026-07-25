# Hot-day tail calibration — learnings from live losses, measured on 9 years

## How this started

Live bucket bets went 4/11 while the point model stayed accurate (MAE 1.30 °F on live
days). The losses clustered in one pattern, and my in-the-moment explanations for them
were wrong twice — in opposite directions:

| Date | City | Model point | Actual | Bet | Result | My same-day "lesson" |
|---|---|---|---|---|---|---|
| Jul 22 | NYC | 84.7 | 85 | 86–87 YES | loss | "never bet above centre" |
| Jul 23 | NYC | 81.0 | 79 | 83–84 YES | loss | (reinforced) |
| Jul 23 | PHX | 112.0 | 114 | 112–113 YES | loss | "market's warm lean is informed" |
| Jul 24 | NYC | 82.5 | 83 | 81–82 + **83–84 hedge** | **hedge won** | trajectory hedging works |
| Jul 24 | PHX | 115.0 | **117** (record) | 115–116 YES | loss | "shift PHX up ~2 °F" |

Rather than keep patching rules from anecdotes, I measured the actual error distribution
on the committed 3,283-day multi-year MOS backtest per city.

## What the data says (hot days = forecast ≥ city 90th-pct, n ≈ 400/city, 2015–2025)

`err = actual − forecast`; positive means guidance ran **cool**.

| City | threshold | median err | mean | **P(err ≥ +2 °F)** | **P(err ≤ −2 °F)** |
|---|---|---|---|---|---|
| **Phoenix** | 108.6 °F | **+0.9** | +0.63 | **24%** | 7% |
| **NYC** | 86.0 °F | 0.0 | +0.19 | 23% | 17% |
| **Vegas** | 107.0 °F | **−1.0** | −0.86 | 6% | **28%** |

Three findings that no amount of same-day reasoning would have produced:

1. **The effect is city-specific and sign-flipped.** Phoenix guidance runs cool in heat;
   Vegas guidance runs *warm* in heat. A rule learned in one desert city is actively
   harmful in the other 300 miles away.
2. **My "+2 °F Phoenix shift" was an overcorrection.** The median shift is only +0.9 °F.
3. **The real structure is the tail asymmetry, not the centre.** On hot Phoenix days
   there is a **24%** chance of finishing ≥2 °F above guidance vs **7%** below. That is
   why the market's warm bucket kept winning, and why declining it "on principle" —
   a rule correctly learned in NYC — was wrong in Phoenix.
4. NYC hot days are genuinely **centred but wide** (23% up / 17% down): do not shift,
   widen. This retro-justifies the Jul 24 hedge, which is the one live bet that won.

## What was built

`models/hot_day_calibration.py`
- `HOT_DAY_STATS` — the measured table above (refresh with
  `scripts/hot_day_calibration_fit.py` after extending the archive).
- `assess_hot_day(station, forecast_f)` → whether today is a hot day for that station,
  the measured point shift, and both tail probabilities, with a plain-English rationale.
- `reweight_integer_pmf(pmf, adj, strength)` → shifts the integer PMF by the measured
  offset and nudges the ≥+2/≤−2 tails toward their measured frequencies.

Wired into `predict_one` as **advisory** output (`hot_day_*` fields) and surfaced in the
forecast report. It does not alter the trained model. 7 new tests; 127 pass.

## Practical rules now encoded

- **Phoenix, hot day:** shift ~+0.9 °F; give the bucket above centre real weight (~24%).
  Consider the centre+1 bucket a legitimate value bet, not a trap.
- **Vegas, hot day:** shift ~−1 °F; the warm bucket is a trap (6%). Fade it.
- **NYC, hot day:** don't shift; widen. When the intraday trajectory runs warm of the
  night-before centre **and** no sea-breeze signal is present, hedge the adjacent warm
  bucket (validated live: 77 ¢ pair → 100 ¢).

## Honest limits

- Hot-day thresholds are the 90th percentile *of the forecast*, i.e. relative to each
  city's own climate — not an absolute temperature.
- Statistics come from GFS-MOS guidance; NBM/HRRR biases are correlated but not
  identical, so treat the numbers as the shape of the bias, not exact per-model values.
- Two live Phoenix losses are consistent with this distribution but do not by themselves
  prove it; the 402-day sample is the evidence, the losses were the prompt.
