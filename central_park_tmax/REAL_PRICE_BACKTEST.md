# Real-price backtest — the simulated-market gap, closed

Every ROI number in this repo except `EDGE_DECAY.md` was against a **simulated** market: we
computed our own probability, assumed we could trade against it, and reported the
difference as edge. That is circular. `scripts/real_price_backtest.py` replaces the
simulated market with the actual order book — public candlesticks on settled markets, no
credentials, no lookahead.

**Result: no demonstrated edge.** Details below, because the headline number looks good
and is misleading.

## Setup

* 68 settled days × 3 cities (2026-05-24 → 2026-07-30), `between` markets only.
* Decision hours 13–18 local; **1,964** price/probability observations.
* Strategy: the observation-anchored post-peak tool only. The forecast-driven strategies
  cannot be backtested on this window — our MOS feature archive stops 2026-01-01 — so they
  are omitted rather than approximated.
* Leakage rules: snapshots usable at observation time; a 6-hour group usable only from its
  **transmission** time and only if its period lies in the local day (`LESSONS.md` #10).
  This is what keeps the afternoon genuinely blind.
* P&L settles against the market's real result, net of the Kalshi taker fee.

## Headline, and why it does not survive

| filter | ROI | 95 % CI (day-clustered) | P(ROI ≤ 0) | n | city-days |
|---|---|---|---|---|---|
| edge ≥ 5 % | **+8.28 %** | −4.2 % … +20.9 % | 0.10 | 507 | 173 |
| edge ≥ 10 % | **+6.79 %** | −11.2 % … +24.2 % | 0.24 | 380 | 163 |
| edge ≥ 15 % | **+5.94 %** | −16.3 % … +27.5 % | 0.30 | 313 | 153 |

The confidence interval **straddles zero at every threshold**. The trade count is
misleading: one city-day supplies up to 4 buckets × 6 hours of near-identical information,
so the effective sample is ~170 clusters, not 500 bets. Resampling city-days rather than
rows is what turns "+8 % on 507 trades" into "could easily be −4 %".

The by-hour breakdown confirms it is noise rather than a window effect:

| hour | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|
| ROI | +8 % | −10 % | +22 % | −0.3 % | +22 % | −24 % |

A real edge concentrated in a time window would be coherent across adjacent hours. This
alternates sign every hour. Same story by city: NYC +12.5 %, Phoenix −0.1 %, Vegas +7.2 %.

`determined=True` fired on only **4** trades in 204 city-days — far too few to say anything,
and a direct consequence of the (correct) still-rising and snapshot-provenance guards.

## The finding that actually matters: we are less calibrated than the market

| model bin | n | mean model p | realised | market price |
|---|---|---|---|---|
| 0.0–0.2 | 871 | 0.062 | **0.202** | 0.228 |
| 0.2–0.4 | 383 | 0.297 | **0.457** | 0.437 |
| 0.4–0.6 | 289 | 0.488 | 0.450 | 0.455 |
| 0.6–0.8 | 261 | 0.701 | 0.693 | 0.631 |
| 0.8–1.0 | 132 | 0.930 | **0.856** | 0.835 |

Our probabilities are pushed toward the extremes: we say 6 % when the truth is 20 %, and
93 % when the truth is 86 %. **The market price is closer to the realised frequency than
our model is in exactly the bins where we trade most.**

This is the mechanism that manufactures the apparent edge. "Edge" is defined as
`model_p − price`; a model that is too confident at the low end generates large negative
"edges" on cheap buckets and large positive ones elsewhere, entirely as an artifact. The
+6.8 % is best read as the residue of that miscalibration, not as alpha.

## What to do with this

1. **Do not size positions off `model_p − price`** until the integer PMF is recalibrated.
   The tails are the problem, and the tails are where the cheap contracts live.
2. **Recalibrating against realised frequencies is now possible** — this backtest produces
   the (model_p, outcome) pairs needed to fit an isotonic or Platt correction, per city.
   That is the obvious next piece of work.
3. **The market is a strong baseline.** In the 0.0–0.2 and 0.2–0.4 bins the price beat our
   probability. Any future claim of edge has to clear the price, not clear zero.
4. The observation-anchored logic is still the most defensible thing we have — it was
   right about *settlement mechanics* (`kalshi_settlement_validation.py`: 204/204). Being
   right about the mechanics and being right about the *probabilities* are different
   claims, and only the first is currently supported.

## Honest limits

* 68 days, one warm season, three cities. Short.
* `between` markets only; the wide one-sided ranges that actually worked live
  (`LESSONS.md` #4) are excluded — that instrument deserves its own study.
* Mid prices, not executable fills; real slippage would reduce every number above.
* Candles are hourly, so intra-hour timing is approximated.

---

# Recalibration result: the edge was miscalibration residue

`scripts/recalibrate_pmf.py` fits an **isotonic** correction (monotone, non-parametric)
from raw model probability to realised frequency, per city, with **day-blocked K-fold** —
folds split by date, never by row, so the calibrator never sees the day it is scored on.

## The correction works

| city | Brier raw | Brier calibrated | **Brier market** | LL raw | LL calibrated | **LL market** |
|---|---|---|---|---|---|---|
| KXHIGHNY | 0.194 | 0.182 | **0.147** | 0.614 | 0.558 | **0.444** |
| KXHIGHTLV | 0.197 | 0.182 | **0.122** | 0.593 | 0.546 | **0.385** |
| KXHIGHTPHX | 0.223 | 0.209 | **0.136** | 0.715 | 0.602 | **0.419** |

The calibrated probabilities now track reality closely:

| raw p | calibrated p | actual | market |
|---|---|---|---|
| 0.062 | 0.193 | 0.202 | 0.228 |
| 0.297 | 0.439 | 0.457 | 0.437 |
| 0.488 | 0.490 | 0.450 | 0.455 |
| 0.701 | 0.688 | 0.693 | 0.631 |
| 0.930 | 0.878 | 0.856 | 0.835 |

The 6 %-vs-20 % gap is gone. Calibration was a real, fixable defect and it is fixed.

## And the edge disappears with it

| filter | raw ROI | **calibrated ROI** | calibrated CI | P(ROI ≤ 0) |
|---|---|---|---|---|
| edge ≥ 5 % | +8.28 % | **+1.21 %** | −11.3 % … +14.4 % | 0.43 |
| edge ≥ 10 % | +6.79 % | **+3.10 %** | −14.2 % … +20.9 % | 0.37 |
| edge ≥ 15 % | +5.94 % | **−2.58 %** | −23.3 % … +19.4 % | 0.60 |

This is the decisive test and it came back negative. The hypothesis in the section above —
that the apparent profit was the residue of overconfident probabilities rather than alpha —
is confirmed: **make the probabilities honest and the profit goes away.**

## The bottom line

**The market is still materially better than we are, even after calibration.** Its Brier
score (0.12–0.15) beats our corrected model (0.18–0.21) in every city, and its log loss
beats ours by a wide margin. We are not close.

Do not trade `model_p − price` on these markets. The defensible use of this system is the
part that is measurably strong — settlement **mechanics** (204/204 in
`kalshi_settlement_validation.py`): knowing precisely what the banked observations imply
once the max is genuinely in, from a continuous source. That is arithmetic, not
forecasting, and it is a much narrower claim than "we can price these contracts."

---

# The 1:51 PM signal, traded with $100

`scripts/bet_after_1351_backtest.py` tests the most promising-looking setup we have: bet
right after the 13:51 EDT observation, which carries the 6-hour maximum group covering
8 AM–2 PM — the first **continuous-source** reading of the day, and the one that revealed a
1.08 °F spike on 2026-07-31 that hourly snapshots never showed.

$100 bankroll, 20 % staked per qualifying day, filled at the **ask** from the candle closing
at 14:00 local (~7 minutes after the signal), net of the Kalshi taker fee. NYC only — the
13:51 timing is specific to UTC-4.

| rule | final | bets | hit rate | max DD | mean/bet | 95 % CI | P(≤0) |
|---|---|---|---|---|---|---|---|
| MODEL_TOP | $12.04 | 62 | 56.5 % | 88 % | −5.4 % | −32.5 … +26.2 | 0.65 |
| MODEL_EDGE | $13.50 | 25 | 24.0 % | 95 % | −14.4 % | −77 … +69 | 0.68 |
| MARKET_FAVOURITE | $5.83 | 62 | 56.5 % | 97 % | −12.4 % | −37.7 … +19.2 | 0.80 |
| MODEL_BEATS_MKT | $99.88 | 7 | 42.9 % | 59 % | — | too few | — |

**The signal is already priced.** `MODEL_BEATS_MKT` fired on only **7 of 62 days** — our
model and the market pick the same bucket 89 % of the time, and their hit rates are
identical to three decimals (0.565). Whatever the 6-hour group reveals, the market has it
within minutes.

**A 56.5 % hit rate still loses** because it is a favourite-buying strategy: paying ~60 ¢
plus fee to win 56.5 % of the time bleeds ~5 % a bet.

**Sizing is a separate lesson.** −5.4 % per bet became −88 % of bankroll purely through
volatility drag at a 20 % stake. Even a break-even edge would have lost money at that size.

## The bug this run caught, and how

The first version returned **$100 → $4.2 million** and +207 % mean return per bet.

Cause: the 36-hour candle window contains **two** candles at local hour 14 — the market
closes at 00:59 local the *following* day — and the selector took the first match, i.e. the
**previous day's price**. It bought yesterday's 2 ¢ out-of-the-money buckets and settled them
against today's outcome. `fill_price()` now matches the exact target timestamp.

The tell was not the size of the profit but the **benchmark**: `MARKET_FAVOURITE` "won" only
29 % of the time, when buying the market's own favourite must hit near 50–60 %. That is the
reason to always carry a benchmark whose plausible range you know in advance — it catches
lookahead bugs that a headline return never will.
