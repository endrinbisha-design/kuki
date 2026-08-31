# The August strategies, traded with $100

`scripts/august_month_backtest.py`. Thirty consecutive logged days (2026-08-01 → 08-30),
real Kalshi prices from settled-market candlesticks, $10 flat stake from a $100 bankroll,
fills at the ask net of the taker fee.

**Result: nothing here is tradeable.** The one leg that shows a profit is 78 % one trade.
Details below, because two of the three interesting findings are about *why* the numbers
come out the way they do.

## Results

| strategy | bets | hit | $100 → | mean/bet | 95 % CI | P(≤0) |
|---|---|---|---|---|---|---|
| `MARKET_FAVOURITE` *(benchmark)* | 30 | 73 % | **$60.26** | −13.2 % | −33 … +6 | 0.90 |
| `GROUP_1351` | 28 | 43 % | **$18.48** | −29.1 % | −61 … +8 | 0.94 |
| `GROUP_1351_EDGE` | 10 | 60 % | **$128.49** | +28.5 % | −41 … +98 | 0.22 |
| `PRELIM_ALL` | 26 | 88 % | **$76.05** | −9.2 % | −23 … +2 | 0.94 |
| `PRELIM_FALLING` | 9 | **100 %** | **$100.00** | **+0.0 %** | +0 … +0 | 1.00 |
| `PRELIM_FALLING_DRY` | 8 | **100 %** | **$100.00** | **+0.0 %** | +0 … +0 | 1.00 |

## 1. The benchmark works, and it says the market is expensive

`MARKET_FAVOURITE` buys the market's own highest-priced bucket. It hits **73 %** and still
loses **13 % per bet**. That is the correct signature — a well-priced favourite wins often
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

**78 % of the profit is one day.** Ex-that-trade the leg returns +0.7 % per bet, which is
noise. The 95 % CI (−41 … +98) and P(≤0) = 0.22 say the same thing less vividly.

This also reproduces the failure mode recorded in `REAL_PRICE_BACKTEST.md`: apparent edge
concentrated where our probabilities are least calibrated. Four of the ten picks are wide
one-sided contracts (`≤79`, `≤84`, `≤89`) where `post_peak` assigns 0.75–0.99 and the market
prices 0.09–0.69 — the tail region the isotonic recalibration was built to fix, and which
this script does **not** apply. Treat the +28.5 % as miscalibration residue, not alpha.

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

The tell for the second was arithmetic, not intuition: 12 bets and 10 falling days in a
30-day sample should overlap about 4 times; observing 0 has probability under 1 %. An
impossible benchmark caught the first, an improbable overlap caught the second. Both belong
in every backtest here — this is now the third time a sanity check has caught a bug that
would otherwise have been reported as a strategy (after the $4.2M candle-timestamp error in
`bet_after_1351_backtest.py`).

## Honest limits

* **30 days, one city, one month.** Day-clustered CIs straddle zero on every leg that has
  enough bets to bootstrap. Nothing here could be significant at this sample size, and I
  said so before running it.
* **Calibration is not applied.** `models/contract_calibration` exists precisely for the
  tail problem visible in leg 3 and is not wired into this script. Applying it would very
  likely remove the +28.5 %, as it did in `REAL_PRICE_BACKTEST.md`.
* **Candles are hourly**, so the 14:00 and 17:00 fills approximate intra-hour timing.
* **Mid-to-ask only** — no slippage, no depth check. `PRELIM_FALLING`'s $1.00 fills may not
  even be available in size.
* **August is EDT throughout.** Every local hour in this script is DST-specific; see
  `SEASONAL_TRANSITION.md`. The script is not valid across 2026-11-01 without the offset
  fix.
