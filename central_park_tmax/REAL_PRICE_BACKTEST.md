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
8 AM–2 PM — the first **continuous-source** reading of the day. On 2026-07-31 that group
read 84.02 °F while hourly snapshots had only reached 82.94; on 2026-08-01 it read 86.00 vs
84.92, and the official CLI later confirmed **86 at 12:50 PM**. The signal is real and it is
correct. The question is whether it is *tradeable*.

Fill at the **ask** from the candle closing at 14:00 local (~7 min after the signal), net of
the Kalshi taker fee, price capped at 90 ¢, NYC only, 62 days.

## Reasonable staking, reasonable rules

| rule | final | bets | hit | mean/bet | 95 % CI | P(≤0) |
|---|---|---|---|---|---|---|
| EDGE ≥ 5 % | $101.64 | 27 | 30 % | +0.6 % | −63 … +85 | 0.52 |
| EDGE ≥ 15 % | $143.34 | 11 | 36 % | +39 % | −76 … +200 | 0.33 |
| EDGE ≥ 25 % | $60.00 | 4 | **0 %** | −100 % | — | 1.00 |
| **LOCK** | **never fires** | **0** | — | — | — | — |
| MARKET_FAVOURITE | $61.86 | 55 | 45 % | −6.9 % | −44 … +42 | 0.65 |

Quarter-Kelly produces the same bets with gentler paths ($107.75 on EDGE ≥ 5 %).

## Three findings

**1. `LOCK` never fires — zero opportunities in 62 days.** That rule buys only when the
banked 6-hour group makes a bucket ≥ 90 % likely *and* it is still priced ≥ 5 ¢ below that.
It never happened. Watched live on 2026-08-01: the group transmitted ~13:52 and the book
was **89/90 ¢ on 86–87 by 13:53**, reaching 94 ¢ by 13:56 from 52 ¢ at 13:14. The arithmetic
certainty is genuine; the market simply has it first. **Being right at the same moment as
the market is worth nothing.**

**2. The edge thresholds run backwards.** +0.6 % at 5 %, +39 % at 15 %, **−100 % at 25 %**
(0 for 4). A real signal improves as you demand more edge. Instead the largest apparent
gaps lost every time — precisely what the tail miscalibration documented above predicts,
since the biggest gaps arise where our probabilities are worst. The +39 % on 11 bets with a
CI of −76 to +200 is noise, not a result.

**3. Sizing was doing most of the damage, but it was not hiding an edge.** An earlier run
staked 20 % of bankroll per day and finished at **$12** (−88 %). The same signal at a flat
$10 stake finishes at **$101.64**. That is a real lesson about volatility drag destroying a
near-breakeven edge — but breakeven is what lies underneath, and P(≤0) = 0.52 is a coin
flip.

## Verdict

**There is no reasonable way to trade the 1:51 signal profitably.** The observation is
accurate and timely; the market prices it within a minute of transmission. This is the
`EDGE_DECAY.md` finding in its sharpest form.

## Bug caught in the first version (kept as a warning)

The initial run reported **$100 → $4.2 million** and +207 % per bet. The 36-hour candle
window contains TWO candles at local hour 14 (the market closes at 00:59 local the next
day) and the code took the first — the PREVIOUS day's price. It was buying yesterday's 2 ¢
out-of-the-money buckets and settling them against today's outcome.

The tell was in the output: `MARKET_FAVOURITE` "won" only **29 %** of the time. Buying the
market's own favourite must hit near 50–60 %. A benchmark that behaves impossibly is the
cheapest bug detector available, which is why one belongs in every backtest here.
