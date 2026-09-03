# The August strategies, traded with $100

`scripts/august_month_backtest.py`. Thirty-one consecutive logged days (2026-08-01 → 08-31),
real Kalshi prices from settled-market candlesticks, $10 flat stake from a $100 bankroll,
fills at the ask net of the taker fee.

**Result: nothing here is demonstrated.** Five of six legs lose or return exactly zero. The
sixth, `GROUP_1351_EDGE`, beats its break-even but at P = 0.25 against a correctly-priced
market — promising, not proven, and far too small a sample to size a position on. It now
**survives calibration** (§3a), which is the one test it was most likely to fail. It is the
one thing in this project worth continuing to collect data on.

## Results

| strategy | bets | hit | $100 → | mean/bet | 95 % CI | P(≤0) |
|---|---|---|---|---|---|---|
| `MARKET_FAVOURITE` *(benchmark)* | 31 | 74 % | **$60.57** | −12.7 % | −33 … +5 | 0.90 |
| `GROUP_1351` | 28 | 43 % | **$18.48** | −29.1 % | −61 … +8 | 0.94 |
| `GROUP_1351_EDGE` | 10 | 60 % | **$128.49** | +28.5 % | −41 … +98 | 0.22 |
| `GROUP_1351_EDGE` *(calibrated)* | 8 | 50 % | **$119.70** | +24.6 % | −70 … +113 | 0.31 |
| `PRELIM_ALL` | 26 | 88 % | **$76.05** | −9.2 % | −23 … +2 | 0.94 |
| `PRELIM_FALLING` | 9 | **100 %** | **$100.00** | **+0.0 %** | +0 … +0 | 1.00 |
| `PRELIM_FALLING_DRY` | 8 | **100 %** | **$100.00** | **+0.0 %** | +0 … +0 | 1.00 |

Run raw with `python scripts/august_month_backtest.py`, calibrated with `--calibrated`.

## 1. The benchmark works, and it says the market is expensive

`MARKET_FAVOURITE` buys the market's own highest-priced bucket. It hits **74 %** and still
loses **12.7 % per bet**. That is the correct signature — a well-priced favourite wins often
and costs more than it returns once the fee is added. A benchmark that behaves sensibly is
what licenses reading anything else on the table.

It did not behave sensibly on the first two runs. See "Bugs caught" below.

## 2. `PRELIM_FALLING` is right nine times out of nine and earns exactly zero

This is the month's best forecasting finding — the falling-trace rule — traded. On days
where the `:51` trace declines into the 4 PM CLI validity cutoff, the preliminary CLI's max
is reliable (4/4 in the log; 9/9 here on bucket outcome).

Every one of those nine bets fills at **ask = $1.00**:

```
2026-08-01  implied 86  settled 86  ask=1.00  fee=0.00  cost=1.00  won  pnl +0.00
2026-08-04  implied 84  settled 84  ask=1.00  fee=0.00  cost=1.00  won  pnl +0.00
2026-08-05  implied 83  settled 83  ask=1.00  fee=0.00  cost=1.00  won  pnl +0.00
...  (all nine identical)
```

A 100 % hit rate and a 0.0 % return is not a strategy. It is a measurement: **by 5 PM on a
falling-trace day there is nothing left to buy.** You pay a dollar to win a dollar. The rule
is genuinely correct and genuinely worthless as a trade, which is `EDGE_DECAY.md` in its
purest observed form — sharper even than the 2026-08-01 case where the book moved 52 ¢ →
94 ¢ inside three minutes of the group transmitting.

The `_DRY` variant drops one wet day and changes nothing, because zero minus a wet day is
still zero.

## 3. The one profitable leg is a single trade

`GROUP_1351_EDGE` (model probability exceeds ask by ≥ 15 points) turns $100 into $128.49.
Decomposed:

| | |
|---|---|
| total P/L, 10 bets | **+$28.49** |
| best single trade (2026-08-14) | **+$22.26** |
| **total excluding that one trade** | **+$6.24** on 9 bets |

78 % of the profit is one day. **But that framing is weak and was overstated when first
written here.** This leg buys contracts at 9–69 ¢; a winner at 29 ¢ returns 2.4×, so
concentrated P/L is *structurally expected* for a strategy of this shape, not evidence
against it. Removing the best trade from a positive-skew strategy will always gut it.

The test that actually applies is whether the hit rate beats what the prices paid imply.
Treating each ask as the market's own probability and testing under the null that the
market is correctly priced (Poisson-binomial over the ten trades):

| | |
|---|---|
| market-implied expected wins | **4.49** |
| observed wins | **6** |
| **P(X ≥ 6 \| market correct)** | **0.246** |
| break-even hit rate at prices paid | 46.8 % |
| actual hit rate | 60 % |

So: the leg beat its break-even, and there is a **one-in-four chance of doing at least this
well by luck alone** if the market is perfectly priced. That is not significance. It is also
not nothing, and "noise" overstates the case against it.

**A second correction.** The first version of this document said "four of the ten picks are
wide one-sided contracts … treat the +28.5 % as miscalibration residue." Both halves were
wrong. Six of the ten are one-sided, not four; and the profit did **not** come from them:

| | n | expected wins | actual | P/L |
|---|---|---|---|---|
| one-sided (`≤X`) | 6 | 2.62 | 3 | **+$7.18** |
| `between` | 4 | 1.87 | 3 | **+$21.32** |

The `between` contracts — the better-calibrated instrument — carried three quarters of the
profit while the wide one-sided tails contributed little. The miscalibration story was a
plausible prior applied without checking, and the data does not support it.

### 3a. Calibration was applied, and the edge survived it

This was step 1 of "what would settle it" below, and it has now been run. `--calibrated`
passes the model PMF through `models/contract_calibration` before comparing it to the ask.

Two implementation points, because both were traps:

* **Calibrate the whole board, not the filtered subset.** `calibrate_contract_set`
  renormalises, so handing it only the buckets that passed the 3–90 ¢ price filter would
  rescale a partial board to 1.0 and inflate every probability on it. The script now
  computes probabilities across the full board, checks it is exhaustive (measured coverage:
  median 1.000, min 1.000 — every August board was a complete partition), calibrates there,
  and filters afterwards.
* **`GROUP_1351` is unchanged, and must be.** Isotonic is monotone, so it cannot reorder
  buckets; the model's top bucket is the same one. Calibration can only move the *edge
  threshold*. That the unfiltered leg came back bit-identical is the check that the
  calibration was wired in without disturbing anything else.

| | raw | calibrated |
|---|---|---|
| trades | 10 | 8 |
| wins | 6 | 4 |
| hit rate | 60 % | 50 % |
| break-even at prices paid | 46.8 % | 34.1 % |
| market-implied expected wins | 4.49 | 2.59 |
| **P(X ≥ wins \| market correct)** | **0.246** | **0.229** |
| total P/L | +$28.49 | +$19.70 |

**The edge is smaller but it does not disappear**, and the significance is essentially
unchanged (0.246 → 0.229). That is a genuinely different outcome from
`REAL_PRICE_BACKTEST.md`, where calibration erased the edge entirely (+8.3 % → +1.2 %). The
prediction made below — "applying it would very likely remove the +28.5 %" — was wrong, and
it was wrong in the direction of my own prior.

The churn underneath the summary matters more than the totals. Calibration dropped three
trades and added one:

| day | bucket | ask | change |
|---|---|---|---|
| 08-13 | ≤84 | 62 ¢ | dropped — **loser** |
| 08-24 | 78–79 | 66 ¢ | dropped — winner (+$4.71) |
| 08-29 | ≤78 | 69 ¢ | dropped — winner (+$4.08) |
| 08-05 | 84–85 | **7 ¢** | added — **loser** (−$10.00) |

The three drops are all expensive contracts (62–69 ¢), where isotonic pulls confident
probabilities *down* and the 15-point edge no longer clears. The addition is the module's
documented tail behaviour running in reverse: a 5 % raw tail lifted to 25 %, which
manufactured a 7 ¢ bet that lost. So calibration made the leg *more* selective at the
confident end and *less* selective in the tails — and the tail it opened is precisely the
region the module's own docstring says it cannot resolve.

Net: the leg is still worth collecting data on, and the case for it is now slightly better
supported than before, since it no longer depends on uncalibrated probabilities. It is still
a one-in-four-by-luck result on n = 8.

## 4. `GROUP_1351` is the worst leg and that is informative

Buying the model's top bucket at 14:00 with no edge filter: **$100 → $18.48**, 43 % hit.
Worse than following the market by a wide margin. The 13:51 group is real information — the
snapshot-gap work proves it — but the model's mapping from banked max to bucket probability
is not good enough to beat a price at 2 PM, when three to five hours of the day remain.

## Bugs caught, and how

Two defects, both found by cross-checks rather than by the output looking wrong. Both
produced publishable-looking numbers.

**1. The 90 ¢ price cap excluded winning favourites.** `MARKET_FAVOURITE` hit **39 %** —
impossible; following the market must land near 50–60 %. On 2026-08-15 the real favourite
was 82–83 at 91 ¢ (settled 83, won); the cap dropped it and the benchmark bought a 10 ¢
loser. Fixed by letting the benchmark see the whole board.

**2. The same cap gated the 17:00 leg, which never used it.** Near settlement the board is
often one bucket at 98 ¢ and the rest at 1 ¢, so the filtered list came back empty and the
whole day was skipped. `PRELIM_ALL` was starved to 12 bets and `PRELIM_FALLING` to **zero**,
against a standalone count of 26 and 9.

**3. The benchmark and the strategies were measured on different day sets.** Found while
adding calibration. The log filter had a lower bound (`>= 2026-08-01`) but no upper one, so
once daily logging carried into September the benchmark started taking bets on Sep 1–2 while
every signal leg skipped those days — the obs feed is loaded for August only. The benchmark
silently grew to 33 bets against the strategies' 30. It changed the headline barely
(−13.2 % → −12.7 %) which is exactly why it would have survived a glance; a comparison is
only a comparison if both sides see the same days. Fixed by bounding the window at 08-31.

The tell for the second was arithmetic, not intuition: 12 bets and 10 falling days in a
30-day sample should overlap about 4 times; observing 0 has probability under 1 %. An
impossible benchmark caught the first, an improbable overlap caught the second. Both belong
in every backtest here — this is now the fourth time a sanity check has caught a bug that
would otherwise have been reported as a strategy (after the $4.2M candle-timestamp error in
`bet_after_1351_backtest.py`). Note that the third was found only because the code was
touched again for an unrelated reason. Nothing was watching for it.

## Honest limits

* **30 days, one city, one month.** Day-clustered CIs straddle zero on every leg that has
  enough bets to bootstrap. Nothing here could be significant at this sample size, and I
  said so before running it.
* **Calibration is now applied** (`--calibrated`, §3a) and the edge survived, contrary to
  the prediction originally written on this line. But it survived on **eight** trades, and
  calibration's own tail behaviour manufactured one of them.
* **Candles are hourly**, so the 14:00 and 17:00 fills approximate intra-hour timing.
* **Mid-to-ask only** — no slippage, no depth check. `PRELIM_FALLING`'s $1.00 fills may not
  even be available in size.
* **August is EDT throughout.** Every local hour in this script is DST-specific; see
  `SEASONAL_TRANSITION.md`. The script is not valid across 2026-11-01 without the offset
  fix.

## What would settle `GROUP_1351_EDGE`

At P = 0.25 the leg is under-powered, not refuted. Three concrete next steps, cheapest
first:

1. ~~**Apply `models/contract_calibration` and re-run.**~~ **Done — see §3a.** The edge
   survived (+28.5 % → +24.6 %, P 0.246 → 0.229), unlike in `REAL_PRICE_BACKTEST.md`. That
   is meaningful and it does not close the question; it removes the cheapest way of
   closing it, which leaves only sample size.
2. **Keep logging.** The leg fires ~10 times per 30 days. Reaching ~50 qualifying trades —
   roughly the point where a true 60 % vs 47 % break-even edge separates from chance —
   needs about **five more months**. The daily logging already underway produces this at no
   extra cost.
3. **Check the September–October out-of-sample.** Those months behave like August
   (`SEASONAL_TRANSITION.md`), so they are a fair holdout; November is a regime change and
   should be analysed separately.

Do **not** size a position on ten trades. A 60 % hit rate on n = 10 has a 95 % interval of
roughly 26–88 %, which comfortably contains the 46.8 % break-even.
