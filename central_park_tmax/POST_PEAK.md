# The post-peak edge — observation-anchored settlement probabilities

## Why this exists

Live results say one thing clearly. Forecast-driven bucket bets went **~4/13**; the one
observation-anchored bet — NYC 80–81 at 89 ¢ placed at 3:45 PM once 80.1 F was already
banked — **won as designed**. That is not luck, it is structural:

> Before the peak you are betting on a forecast. After the peak you are betting on
> arithmetic: how much more can it still rise, and how does it round?

Both remaining quantities are **measurable without any weather model**.

## The one empirical input

`scripts/build_remaining_rise.py` measures, from IEM ASOS hourly observations
(warm seasons 2021–2025, ~765 days per city per hour):

    remaining_rise(h) = daily_max − max(observations up to hour h)

**P(the day's max is already in), by local hour:**

| local hour | NYC | Phoenix | Vegas |
|---|---|---|---|
| 12 | 28% | 5% | 8% |
| 14 | 75% | 47% | 46% |
| 15 | 88% | 81% | 74% |
| 16 | **95%** | **96%** | **94%** |
| 17 | **99%** | **100%** | **99%** |

The deserts peak later than the coast — Phoenix at 2 PM is a coin flip, NYC is already
75 % done. This is exactly the kind of thing that should be measured per city rather
than assumed.

## What the module does

`models/post_peak.py` — `settlement_distribution(station, observed_max_f, local_hour)`:

1. Loads the measured remaining-rise CDF for that city and hour.
2. Convolves it with the observed max to get the distribution of the final max.
3. Applies **round-half-up** whole-degree settlement (the NWS CLI convention).
4. Returns per-integer probabilities, the top bucket, whether it is `determined`
   (default ≥ 90 %), and an explicit **rounding-boundary warning** when the observed max
   sits within 0.12 F of a .5 boundary.

`bucket_probability()` scores a contract range; `edge_vs_price()` compares it to a market
price and subtracts the Kalshi taker fee.

## Retro-validation on 2026-07-25

| situation | tool output | actual |
|---|---|---|
| NYC 3:45 PM, 80.1 F banked | P(80–81) = **96.2 %**, net edge **+6.2 ¢** vs the 89 ¢ price | 80 → **won** |
| NYC 11:30 AM, 76 F so far | **not determined**; P(82–83) = 9 % vs the 53 ¢ I recommended | 80 → that rec **lost** |
| PHX 2:45 PM, 116.6 F banked | P(117–118) = 75 %, **rounding-boundary warning** | 116.6 → settles **117** |

The tool would have endorsed the one winning bet and vetoed a losing one — and it flags
the 116.6 → 117 rounding trap that decided the Phoenix market.

## How to use it

- **Only take a bet when `determined` is True** (or the bucket probability clears your
  own bar), i.e. roughly **3 PM local for NYC, 4 PM for Phoenix/Vegas**.
- **Respect the boundary warning.** A max ending in ~.5 makes the settled integer a coin
  flip; that is a reason to skip, not to size up.
- **Expect grind, not windfall.** These bets price at 85–95 ¢, so risk/reward is ~9:1.
  The edge is real but small; size for a high-hit-rate grind.

## Two corrections made after live losses

**1. `determined` is now conditioned on the live trace.** The remaining-rise table is
*unconditional* climatology for an hour of day, so it cannot tell a banked max from one
that is still climbing. On 2025-07-29 it read `determined=True` in NYC, Phoenix and Vegas
at the same moment while all three were still rising. `settlement_distribution()` now
takes `recent_temps_f` (chronological, from the fast-METAR feed) and forces
`determined=False` whenever the last two observations are flat-or-rising within sensor
noise (0.2 °F). No trace supplied ⇒ treated as still rising.

**2. The margin is measured to the .5 boundary, not the whole degree.** Every outlook
carries `distance_to_boundary_f`: how far the current max is from the next round-half-up
settlement boundary. A "112–113" contract flips at **111.5 °F**. On 2025-07-30 Vegas the
banked 111.02 °F was 0.48 °F from settling one degree higher — half the margin a
whole-degree reading implied. The same mechanism turned a 116.60 °F Phoenix max into a
**117** settlement on 2025-07-25.

Related rule, learned on 2025-07-26: **do not talk the threshold up.** 89 % is not 90 %.
Overriding `determined=False` on a "peak then decline, it's banked" narrative lost both
legs when the temperature re-warmed.

## Honest limits

- Climatology is 2021–2025 warm seasons only (May–Sep). Winter and shoulder seasons are
  not covered and the table clamps to the measured hour range (9–21 local).
- It assumes the observed max feed is correct and complete. Use the METAR 6-hour max
  group as the cross-check — hourly snapshots can miss a brief spike.
- It is deliberately **model-free**: it says nothing about which bucket to buy in the
  morning, only when a bet has stopped being a forecast.
