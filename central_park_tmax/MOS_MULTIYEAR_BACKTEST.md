# Multi-year MOS backtest (2015–2025): NYC / Phoenix / Las Vegas

The 184-day NBM backtest window was too thin to trust the model comparisons
(MULTI_CITY_COMPARISON.md). This backtest re-runs the same three-way comparison on
**~3,283 out-of-sample days per city** (test years 2017–2025, expanding-window yearly
folds) using **GFS-MOS** night-before guidance from IEM's bulk text archive as the
baseline and GHCN-Daily as labels.

Baseline honesty note: GFS-MOS is *itself* a statistically post-processed product
(that's what "MOS" means), so this measures what our corrections add **on top of an
already-corrected baseline** — a tougher, fairer test than correcting raw model output.
Labels are GHCN (research label), not the CLI settlement value.

## Pooled results (MAE °F, n=3,283 days per city)

| City | raw GFS-MOS | + rolling bias (30d) | + boosting ML | Winner |
|---|---|---|---|---|
| NYC | 2.30 | 2.27 | 2.29 | ~tie (nothing helps) |
| Phoenix | 1.61 | **1.40** | 1.53 | **rolling bias** |
| Vegas | 1.94 | **1.61** | 1.70 | **rolling bias** |

## What 18× more data settled

1. **Phoenix's "bias-correction city" finding replicates emphatically.** Nine straight
   test years where the rolling bias term wins or ties. Most telling: in 2023–2024 raw
   GFS-MOS *degraded* to 1.91/2.15 MAE (a real drift — the guidance ran increasingly
   cool vs the warming station) while the rolling-bias model stayed at 1.31/1.35. A
   30-day bias window self-heals against baseline drift; a static model doesn't.

2. **The ML never beats the simple bias term at scale — even with 8 years of training
   data.** Pooled, it loses to rolling-bias in all three cities (and in NYC-2017 it was
   *worse than raw* by 0.5 °F). With only baseline+calendar+lag features there is no
   nonlinear structure for it to find beyond what the bias term captures. This
   retroactively explains the 184-day results: the NYC ML's win there (2.20→1.70) came
   from its *richer feature set* (HRRR/GFS consensus, trajectory shape, spatial
   gradients), *not* from residual-learning magic. **ML earns its keep through
   features, not through fitting harder.**

3. **NYC is hard for everyone.** Nothing improves on GFS-MOS's 2.30 MAE without extra
   information. Coastal mesoscale error (sea breeze) is irreducible from a single
   baseline series — consistent with the NYC NBM-ML win coming specifically from
   multi-model + trajectory features.

4. **Vegas re-ranked once the baseline got older.** Against NBM (184d), raw was
   unbeatable; against GFS-MOS (9y), the bias term buys 0.33 °F. NBM has effectively
   *already applied* the corrections that older GFS-MOS still needs — i.e., "which
   correction wins" depends on how much statistical work the baseline already embeds.

## Production implications

- **Default correction = 30-day rolling bias, everywhere.** It never lost a fold, it
  self-heals drift, and it costs nothing. The ML should be the production point model
  only where its feature set demonstrably pays (NYC with multi-model features).
- **Keep NBM as the live baseline** (it dominates GFS-MOS where compared); use this
  MOS series as (a) a long-history evaluation harness and (b) a candidate extra
  feature for the NYC model.
- Next data upgrades in value order: archive **real Kalshi settled prices** going
  forward (fixes the simulated-market caveat); extend the **NBM GRIB archive**
  backward in monthly chunks; add **NBM-MOS text** (post-2020) as a fast baseline.

## Artifacts

- `backtest_datasets/mos_multiyear_backtest.json` — per-fold + pooled metrics
- `backtest_datasets/{nyc,phoenix,vegas}_mos_multiyear.csv` — daily forecast/actual series
- `scripts/mos_multiyear_backtest.py` — fully re-runnable (bulk cache re-fetches in minutes)
