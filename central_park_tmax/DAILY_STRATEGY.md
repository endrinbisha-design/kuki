# Daily strategy selector — which play is reliable for THIS day

## Why

Live results split cleanly: **forecast-driven bucket bets went 5/16**, while
**observation-anchored post-peak bets won**. But "always wait for the peak" is not the
whole answer — the right play depends on the day's regime, and those effects are
*measurable*, not anecdotal.

## Measured regime statistics

9-year MOS series joined to GHCN precipitation, warm season (May–Sep).
`err = actual − forecast`; positive = guidance ran **cool**.
Refresh with `scripts/regime_stats_fit.py`.

| City | Regime | n | bias | **MAE** | P(err ≥ +2) | P(err ≤ −2) |
|---|---|---|---|---|---|---|
| NYC | wet | 583 | +0.49 | **2.53** | 30% | 23% |
| NYC | dry | 1097 | +0.43 | **1.88** | 26% | 15% |
| Phoenix | wet | 146 | −0.37 | **2.74** | 26% | **31%** |
| Phoenix | dry | 1534 | **+0.75** | **1.46** | 25% | **6%** |
| Vegas | wet | 86 | **−1.54** | **2.89** | 12% | **41%** |
| Vegas | dry | 1594 | −0.47 | **1.67** | 10% | 24% |

Three findings drive the rules:

1. **Wet days are much harder everywhere** — MAE rises **35%** (NYC), **88%** (Phoenix),
   **73%** (Vegas), and both tails fatten. Narrow bucket bets should be avoided outright.
2. **Phoenix's bias flips sign with moisture.** Dry: guidance runs cool (+0.75, cool tail
   only **6%**) so the warm bucket carries weight. Wet: guidance runs slightly warm
   (−0.37) and the cool tail explodes **6% → 31%**. A rule learned on dry desert days is
   *actively wrong* on a monsoon day — this is exactly the trap that cost the Jul 24/25
   Phoenix bets.
3. **Vegas guidance runs warm in every regime** (−0.47 dry, −1.54 wet) with a persistently
   fat cool tail — the mirror image of Phoenix, 300 miles away.

## The strategies

| Strategy | When | Confidence | Play |
|---|---|---|---|
| **POST_PEAK_LOCK** | max is banked (`determined=True`) | **high** | Buy the banked bucket. Outcome is arithmetic + rounding, not weather. |
| **WET_DAY_AVOID** | PoP ≥ 40% | low | No narrow buckets. Fade anything priced > ~85% — overconfidence is the edge. |
| **DRY_LEAN_WARM** | dry day, bias ≥ +0.6 (Phoenix) | medium | Give the bucket at/above centre real weight. **Never two buckets above** — the bias is ~1 °F, not 3 °F. |
| **DRY_LEAN_COOL** | dry day, bias ≤ −0.4 (Vegas) | medium | Fade the warm bucket; lean at or one below centre. |
| **WAIT_FOR_PEAK** | pre-peak, no measured bias (NYC dry) | low | No trade. Re-check at ~15h NYC / ~16h desert. |

Priority is strict: a banked max overrides every regime rule.

## Live example (2026-07-28)

| City | Max so far | Strategy | Why |
|---|---|---|---|
| NYC | 78.98 (6-h group, **+0.9 F above hourly**) | **WET_DAY_AVOID** | PoP 78%; MAE 2.53 vs 1.88 dry |
| Phoenix | 104.0 | **DRY_LEAN_WARM** | dry; guidance cool +0.75, cool tail only 6% |
| Vegas | 105.98 | **DRY_LEAN_COOL** | dry; guidance warm −0.47, cool tail 24% |

Two desert cities, same day, **opposite leans** — decided by measurement, not intuition.

## Data integration

The selector consumes the **low-latency settlement max** (`data/fast_metar.py`):
aviationweather.gov METARs (~1 h fresher than api.weather.gov) including the **6-hour
maximum group**, which captures peaks between hourly snapshots. On 2026-07-28 that gap
was **+0.9 °F** in NYC — the difference between the 77–78 and 79–80 buckets.

Both are wired into `predict_one` and the forecast report; advisory only, never sizing.
