# Multi-city comparison: NYC vs Phoenix vs Las Vegas

Three station-specific max-temperature MOS models built from the **same** codebase
(config-only ports), backtested on the **same window** (Aug 2024 – Jan 2025, 184 days,
night-before `prev_evening_19` vintage) for an apples-to-apples comparison.

## Headline numbers

| City | NBM raw MAE | Best-model MAE | Best model | Within ±2 °F | Integer log-loss | Top-2 acc |
|---|---|---|---|---|---|---|
| **NYC** (KNYC) | 2.20 | 1.70 | boosting_residual (ML) | 66.7% | 2.91 | 35.1% |
| **Phoenix** (KPHX) | 1.62 | **1.11** | rolling_bias_30d | **90.2%** | **1.97** | 47.8% |
| **Las Vegas** (KLAS) | 1.45 | 1.45 | **raw_primary (none)** | 71.8% | 2.18 | 38.0% |

Strategy backtest (SIMULATED NBM-anchored market — behavior, not realized P&L):

| Strategy | NYC ROI | Phoenix ROI | Vegas ROI |
|---|---|---|---|
| edge_flat_8c | 20.5% | 27.4% | 12.8% |
| kelly_25pct | 14.6% | 19.9% | 9.8% |
| tail_fade | 5.7% | 4.3% | 6.0% |

## The key finding: the three cities are a spectrum of *when MOS helps*

The most valuable result isn't "which city is most accurate" — it's **what kind of
correction each city needs**, which turns out to be completely different:

| City | NBM bias | What beats raw NBM | Why |
|---|---|---|---|
| **NYC** | — | **nonlinear ML** (2.20→1.70, +23%) | Errors are structured (sea-breeze / regime); a tree model learns them. |
| **Phoenix** | **−1.36 °F (cool)** | **simple bias term** (1.62→1.11, +31%) | NBM systematically under-forecasts the desert-urban heat; one bias number fixes it. ML *overfits* (1.32). |
| **Las Vegas** | **+0.22 °F (none)** | **nothing** — raw NBM is best | NBM is already near-perfectly calibrated. Both the bias term (1.47) and ML (1.54) *hurt* by adding variance. |

This is the whole lesson of statistical post-processing in one table:
- **Big nonlinear structure → ML wins** (NYC).
- **Systematic bias → a bias correction wins; ML overfits** (Phoenix).
- **Already-calibrated baseline → leave it alone; every correction adds noise** (Vegas).

## Reading the accuracy ranking correctly

- **Raw NBM** is best in Vegas (1.45) > Phoenix (1.62) > NYC (2.20) — the desert is
  simply more forecastable, and Vegas's NBM is the best-calibrated of the three.
- **After post-processing**, Phoenix takes the lead (1.11) because it had a large,
  cleanly-removable bias; Vegas can't improve on its already-good 1.45; NYC's ML pulls
  it from 2.20 to 1.70 but coastal complexity keeps it last.

So "most accurate model" = Phoenix, but "best raw guidance" = Vegas, and "most value
added by modeling" = NYC. Three different answers to three different questions.

## Tradable-edge implication

Simulated-market ROI is highest for Phoenix and *lowest for Vegas* — consistent with the
accuracy story. Where the model can only match NBM (Vegas), and the real market is
efficient on an easy signal, **there is little edge to extract**. Phoenix's exploitable
edge is its NBM cool-bias (markets that anchor on NWS/NBM under-price the true high — we
saw this live: the KXHIGHTPHX board sat at 112–114 while NWS said 111). NYC's edge is the
sea-breeze regime uncertainty. **Vegas is the "accurate but not very tradable" case.**

## Port cost & reuse

All three share one codebase. Each city = 3 config files + external identifiers
(`MarketCfg`). Two shared-code bugs found via the ports (both fixed, NYC unchanged):
IEM station defaulted to NYC; QC ceiling was 115 °F (rejected legit desert 116–117 °F).

## Operational note

The multi-year-free NBM/HRRR/GFS archive builds run ~2 h per city and outlive the
container's idle-reclaim window — build them **chunked by month** (each chunk resumes),
or accept the auto-resume (archives + dataset both checkpoint, so nothing is lost).

## Bottom line

The infrastructure ports cleanly to any US CLI city (Vegas was config-only). The three
cities together are more instructive than any one: they show that a station-specific MOS
is only as valuable as the baseline's *residual structure* — huge in coastal NYC, a
simple bias in Phoenix, essentially nil in Vegas. Pick the expansion to the *goal*:
Vegas/Phoenix for accuracy and calibration; a coastal or convective city for tradable
model edge.
