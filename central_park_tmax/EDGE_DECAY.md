# Edge decay & information arrival — measured on 360 real settled markets

The first analysis in this repo that uses **real Kalshi prices** rather than the
simulated market. Source: public candlesticks on settled KXHIGHNY / KXHIGHTPHX /
KXHIGHTLV markets (120 each), hourly candles over the 36 h to close.
Rebuild with `scripts/edge_decay_study.py`.

## 1. When does the market actually learn?

Mean |YES price − outcome| by **local** hour (lower = better informed):

| local hour | mean error | |
|---|---|---|
| 06–11 | 0.185–0.200 | flat |
| 12 | 0.192 | flat |
| 13 | 0.197 | flat |
| 14 | 0.185 | |
| **15** | **0.170** | starts falling |
| **16** | **0.159** | |
| **17** | **0.132** | steep drop |
| 18–23 | 0.112–0.118 | converged |

**The market learns essentially nothing between 6 AM and 2 PM.** Its error at 2 PM
(0.185) is statistically the same as at 6 AM (0.197). All the information arrives
between **15h and 18h local**, then the curve flattens.

## 2. When do winners get priced?

For markets that settled YES, the first local hour the price crossed:

| threshold | median hour | IQR |
|---|---|---|
| ≥ 50% | 13h | 12–16h |
| ≥ 80% | **16h** | 14–17h |
| ≥ 90% | **17h** | 16–17h |

## 3. What this changes

**a) The "edges decay in minutes" worry was wrong — for mornings.** The single anecdote
that prompted this study (Phoenix 119–120 moving 11 ¢ → 20 ¢ within an hour) is not the
norm: morning price movement is mostly noise, not information. There is **no rush** to
trade a morning signal. But there is also **no edge** in one — which is the flip side.

**b) It explains the live record.** Forecast-driven morning bets went 5/16 while the one
post-peak bet won. Morning prices are ~equally uninformative for everyone; there is no
systematic advantage to extract without genuinely better information. The post-peak bet
won because by then *we* had information (the banked max) that the price had not absorbed.

**c) There is a real, measurable edge window: ~15h–17h local.** Our post-peak tool knows
the max is banked at **15h (NYC, 88 %)** and **16h (desert, 96 %)**, while the market
does not price ≥ 90 % until a **median of 17h**. That 1–2 hour gap is the only interval
where we hold information the price lacks — and it is exactly where the one winning trade
was placed.

**d) Convergence is not perfection.** Residual error stays at ~0.112 even late, so some
markets remain genuinely uncertain to the end (rounding boundaries, late changes). Late
entry is safer but not free money.

## Practical rule

> Do not trade before ~14h local. Work the **15h–17h local window**, where the post-peak
> tool has resolved the outcome and the market has not yet fully repriced. After 18h the
> information advantage is gone.

## Caveats

- 360 settled markets over recent weeks; a summer-only sample.
- Candle mid-prices use bid/ask close, falling back to last trade; thin books add noise.
- Fixed UTC offsets per city (adequate at hourly granularity).
