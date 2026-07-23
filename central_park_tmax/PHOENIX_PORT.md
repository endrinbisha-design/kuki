# Phoenix (KPHX) second-city port — results & comparison to NYC

A prototype expansion of the KNYC max-temperature MOS stack to **Phoenix Sky Harbor**
(Kalshi `KXHIGHTPHX`). Goal: reuse the NYC infrastructure verbatim, build a real
backtested/calibrated model, and measure how it compares.

## What was ported (config-only, ~100% code reuse)

The whole pipeline is CONUS-general, so the port is configuration, not new code:

- `configs/phoenix/` — Sky Harbor station (`USW00023183`), 8 Valley-of-the-Sun neighbor
  stations, `America/Phoenix` timezone (no DST), desert regime thresholds, separate
  `data_phoenix/` paths.
- Config-driven external identifiers via a new `MarketCfg` (defaults preserve KNYC):
  CLI location `PHX` (office is PSR), Kalshi series `KXHIGHTPHX`, IEM station `PHX`.

Two genuine port bugs were found and fixed in shared code (NYC behavior unchanged):

1. `build-dataset` intraday-obs fetch defaulted to the **KNYC** IEM station regardless
   of city → now uses `cfg.market.iem_station`.
2. The QC plausibility ceiling was **115 °F** (NYC-tuned), which flagged/rejected
   legitimate Phoenix highs of 116–117 °F (and would reject a real 116 °F CLI at
   settlement) → widened to 130 °F.

## Backtest window & scope

Aug 2024 – Jan 2025 (184 days), **night-before vintage (`prev_evening_19`)** — matched
to NYC's build window for an apples-to-apples comparison. Sources: NBM baseline +
HRRR/GFS consensus features. Rolling-origin monthly folds (Nov, Dec, Jan).
*(The 4 PM `target_16` vintage that NYC also has is a pending follow-on.)*

## Head-to-head — night-before model accuracy

| Metric | NYC (KNYC) | Phoenix (KPHX) | Winner |
|---|---|---|---|
| NBM raw MAE (°F) | 2.20 | **1.62** | PHX |
| **Best-model MAE (°F)** | 1.70 | **1.11** | **PHX (−35%)** |
| Best model | boosting_residual | rolling_bias_30d | — |
| Within ±2 °F | 66.7% | **90.2%** | PHX |
| ML (boosting) MAE | 1.70 | 1.32 | PHX |
| NBM bias | cool | −1.36 (cool) | — |
| Contract integer log-loss | 2.91 | **1.97** | PHX |
| Exact-integer accuracy | 18.9% | **25.0%** | PHX |
| Top-2 bucket accuracy | 35.1% | **47.8%** | PHX |

### Strategy backtest (SIMULATED market — behavior, not realized P&L)

| Strategy | NYC ROI | PHX ROI |
|---|---|---|
| edge_flat_8c | 20.5% | 27.4% |
| kelly_25pct | 14.6% | 19.9% |
| tail_fade | 5.7% | 4.3% |

> Both use a simulated NBM-anchored pseudo-market (historical Kalshi prices are not
> available in this environment). They measure model-vs-NBM edge, **not** profitability
> against the real, efficient Phoenix market.

## Findings

1. **Phoenix is meaningfully more accurate — the desert is easier, as hypothesized.**
   Model MAE 1.11 °F vs NYC 1.70 °F; 90% of days within ±2 °F vs 67%. Calibration is
   also better (log-loss 1.97 vs 2.91): on a predictable signal, fewer integer buckets
   are ever in play.

2. **The source of skill is different.** In Phoenix the winning model is a **simple
   30-day rolling bias correction (1.11)**, which *beats* the nonlinear ML (1.32). NBM
   carries a clean, systematic **−1.4 °F cool bias** in the desert that a bias term
   removes almost entirely (residual bias +0.09). In NYC the ML wins because the errors
   are nonlinear (sea-breeze / regime structure) — there is real structure for a tree
   model to learn. Phoenix confirms the prediction: *when the baseline is already good,
   there is little nonlinear signal left for ML to add, and it can overfit a small set.*

3. **Skill-over-NBM is actually higher for Phoenix via bias correction** (31% vs NYC's
   23%) precisely because the bias is so systematic — but **ML-specific skill is lower**
   (19% vs 23%). Different lever, same conclusion.

## Points of improvement

- **Use `rolling_bias_30d` as the Phoenix production correction** (or blend it with the
  ML), rather than the ML alone — the ML overfits on 184 rows.
- **More history.** 6 months is thin. A multi-summer archive would stabilize the ML and
  let it learn the desert's one hard regime (monsoon convection, Jul–Sep).
- **Add the 4 PM `target_16` vintage** to match NYC (pending; needs the Phoenix IEM
  intraday reconstruction that the bug-fix now enables).
- **Monsoon features.** The only low-predictability desert days are monsoon storm days;
  dewpoint-surge / PoP features + the regime add-on (thresholds already desert-tuned)
  would target them.
- **Verify live end-to-end** (`predict-tomorrow --config-dir configs/phoenix`) against a
  live Phoenix CLI once a same-day report is available.

## Bottom line

The port is a **success**: config-only, ~100% code reuse, and it produces a model that
is **honestly more accurate than the NYC model** (1.11 vs 1.70 °F). But "better" comes
with a caveat — Phoenix is *easier*, so most of the win is the baseline being good and a
simple bias correction finishing the job; there is less for the ML to contribute, and in
a real (efficient) Phoenix market the tradable edge would likely be thinner than the
simulated ROI suggests. Phoenix is the right **calibration/low-risk** expansion; an
inland-continental city with real convective variability would give the ML more to do.
