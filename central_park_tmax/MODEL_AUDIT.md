# Model audit and improvements

Audit date: 2026-09-16. Base: `1c001a522a6ecdfbb43632a04ee8d80884b2e8c3` on
`claude/central-park-temp-forecast-u9gsw8`. The original audit was local on
`codex/model-validation-improvements`; it was subsequently published to the original
project branch as `22438345840c2eacc5e6e458a326dc95dbd03b7f` at the user's request.
See [MODEL_FOLLOWUP.md](MODEL_FOLLOWUP.md) for the next experiments and collection status.
No trades or scheduled collection were started.

## Bottom line

The repository has useful weather ingestion, observation-provenance handling, settlement
logic, and an existing test suite. It does not yet demonstrate executable trading alpha.
The major weakness is not a shortage of complex models. It is disagreement between
historical information sets, modeled targets, calibration procedures, and executable prices.

This audit fixes several concrete software/validation defects and adds two research models.
The new conditional remaining-rise model improves a weather forecasting subproblem in
every annual test fold. The market-anchored probability model substantially improves on
standalone weather probabilities, but does not convincingly beat the market benchmark.
Neither research model has been promoted into live settlement probabilities or trading.

## Findings and implemented fixes

| Priority | Finding | Change and remaining boundary |
| --- | --- | --- |
| High | `FeatureMatrix.from_frame` filled missing features using each input batch's own medians; the live path used zero. Predictions could depend on other test rows. | Models now fit and retain training-only median imputers; live inputs preserve missingness. Legacy fitted artifacts must be retrained when missing features occur. |
| High | Hyperparameter selection and uncertainty estimation reused the same validation tail. | Separate chronological train, tune, and calibration partitions, by whole date. The model card records each range and actual fit counts. This reduces the already-small fit sample and can worsen point accuracy. |
| High | `recalibrate_pmf.py` randomized dates among folds, allowing future labels to calibrate past predictions. | Expanding chronological folds with a two-calendar-day embargo proxy. New outputs use a different filename and are not silently loaded into the live model. Actual resolution timestamps are still required for proof of availability. |
| High | The candle loader queried 36 hours but keyed prices only by hour, allowing different calendar dates to overwrite each other. | Keys now include the local date. The old archived CSV has no original candle timestamps, so this fix does not retroactively validate its prices. |
| High | Previous-evening features could include that same local day's final temperature/rainfall, although the day had not ended. | Feature building excludes unfinished local days. Multi-year MOS and conditional-distribution scripts use a two-calendar-day error lag. Revised GHCN values still lack publication/vintage provenance; saved feature CSVs were not silently rewritten. |
| High | Quote collection rounded arrival backward to the hour, discarded intra-hour updates, and rounded away sub-cent prices. | A separate v2 archive preserves per-response receipt/request timestamps and dollar strings, and paginates. It remains REST summary data, not full depth or guaranteed current executable quotes. No live collection was run here. |
| Medium | Fold validation omitted the last or sole fold; date splitting could split repeated dates. | Validate every fold and preserve whole dates across splits. |
| Medium | Fold metrics were equally averaged regardless of sample count, and integer scoring used Python rounding instead of the configured rule. | Pool continuous scores by observation count, reconstruct pooled RMSE correctly, and use the configured reporting convention. |
| Medium | The sklearn booster could silently create a random early-stopping subset when no explicit validation frame existed. | Disable that implicit random split. Other backends retain their explicit chronological tuning data. |
| Medium | Passing an alternate target name could include that label as a numeric feature. | Exclude the active target/baseline and reject an explicitly requested target feature. |

The standard backtester now uses the same hyperparameter selection routine as training,
but it still does not reproduce every live OOD/post-peak/advisory transformation. Do not
interpret its scores as end-to-end trading performance.

## Experiment 1: conditional remaining rise

Implementation: `models/conditional_rise.py`; runner: `scripts/audit_conditional_rise.py`.

Instead of asking only “how much more does it usually warm after 4 PM?”, condition on:

- The exact decision hour.
- How far current temperature is below the maximum observed so far.
- Recent warming or cooling rate, adjusted for elapsed time between observations.

Fixed physical bins define comparable historical conditions. Sparse groups shrink toward
the hour-only distribution, using a fixed prior strength of 30. No hyperparameter search
was performed. At 13:00, only observations stamped at or before 13:00 are available;
the 13:51 observation is not included. New York timezone conversion handles DST.

Both candidates are fitted only on earlier years and tested on identical eligible days.
The comparator is a freshly fitted, time-aligned hour-only table, not the old frozen
`remaining_rise.json`. This isolates the benefit of conditioning.

846 evaluation days, 4,919 snapshots, annual folds 2021-2026; the last evaluation day is
2026-08-01. Scores give equal weight to days, not to the number of intraday observations.

| Metric, lower is better | Hour-only baseline | Conditional model | Reduction |
| --- | ---: | ---: | ---: |
| Average Brier score across eight remaining-rise thresholds | 0.05726 | 0.05460 | 4.64% |
| Brier score for no further sampled rise, tolerance 0.05 F | 0.13574 | 0.12709 | 6.37% |
| Remaining-rise mean absolute error, F | 0.55647 | 0.53890 | 3.16% |

The average-threshold score improves in all six annual folds. The paired difference is
-0.002656, with a descriptive 95% block-bootstrap interval [-0.003290, -0.002044].
Resampling uses seven observed days within each year; missing dates are not reconstructed.

**Important target limitation:** this forecasts the remaining high of hourly observations,
not the continuous sensor high or official CLI settlement. It returns a conditional CDF
at specified rise thresholds and a conditional mean, not a deployable settlement PMF.
Reception latency is unknown. Day-coverage filters may introduce selection bias. This
is retrospective research on previously available data, not a fresh prospective holdout.

## Experiment 2: market-anchored probabilities

Implementation: `models/market_anchor.py`; runner: `scripts/audit_probability_models.py`.

For each city, learn a single weather weight between zero and one:

`probability = market_proxy + weight * (weather_probability - market_proxy)`

Fit only on earlier eligible dates, weight each date equally, and apply a fixed 0.01
quadratic penalty toward the market. A zero weather weight is an acceptable finding.
Refit daily after at least 30 eligible dates, assuming a two-day settlement-information
delay. The archive lacks actual settlement receipt timestamps, so that assumption remains
a limitation. A single common weight preserves a complete partition only if both input
boards are themselves complete normalized distributions. Partial boards are not normalized.

1,016 scored observations, 108 city-days, 37 calendar days, 2026-06-24 through 2026-07-30.

| Model | Date-balanced Brier | Date-balanced log loss |
| --- | ---: | ---: |
| Raw weather probabilities | 0.19356 | 0.61590 |
| Chronological isotonic calibration | 0.18148 | 0.57056 |
| Market price proxy | 0.13975 | 0.42396 |
| Market-anchored challenger | 0.13967 | 0.42570 |

The challenger learns an average weather weight of 7.86%. Its Brier improvement over
market alone is only 0.000085; the paired interval for candidate minus market is
[-0.002380, +0.002204]. Its log loss is worse. In the final 14-day descriptive slice,
both Brier and log loss are worse than market alone. This does not pass an alpha or
deployment gate. Do not advertise the large improvement over the raw weather model as
an advantage over the market: most of it comes from using the market itself.

The legacy price-join defect, midpoint/last-trade prices, missing depth/receipt times,
and incomplete contract boards limit the experiment. It is a diagnostic conditional
on archived inputs, not an executable-price backtest. No P&L was computed here.

## Core regression benchmark, including regressions

Runner: `scripts/audit_core_backtest.py`. Before and after use identical committed feature
CSVs, sklearn, 100 boosting iterations, and no hyperparameter search. Core changes reduce
fit data to make room for an independent calibration set. Scores need not improve.

| Boosting point forecast MAE, F | Before | After |
| --- | ---: | ---: |
| NYC previous evening | 1.712 | 1.806 |
| NYC 4 PM | 1.257 | 1.254 |
| Phoenix previous evening | 1.221 | 1.617 |
| Las Vegas previous evening | 1.638 | 1.620 |

The previous-evening regressions are real and reported, not hidden. The existing archive
is only 184 days per vintage and is poorly suited to splitting a large feature set into
three parts. It uses final GHCN research labels and previously generated features, so
this is a software regression benchmark, not a point-in-time settlement study. Rebuild
features from timestamped/vintage inputs before making new deployment claims.

## Remaining weaknesses that block deployment

1. **Multi-city clock handling:** core `time_utils.py` is anchored to New York, while
   Phoenix/Las Vegas configs advertise their own local times. Several callers use those
   NY helpers. Merely loading a different config does not establish a correct city port.
   The new conditional experiment is explicitly NYC-only. Audit all day boundaries,
   issuance times, report windows, and station-specific settlement rules before expansion.
2. **Live calibration differs from evaluation:** live code renormalizes independently
   calibrated bucket probabilities, but the original isotonic study scored marginal
   outputs before renormalization. Normalization does not establish calibration. Evaluate
   complete boards through the exact live transformation before promotion.
3. **Observation/settlement mismatch:** final GHCN, sampled hourly maxima, six-hour group
   maxima, and the official settlement report are different targets. The new conditional
   model intentionally does not pretend they are interchangeable.
4. **Hour-end climatology:** the old remaining-rise builder includes observations up to
   the end of hour h, whereas some callers predict at h:00. Its CDF is also converted
   into integer rises, discarding sub-degree boundary information. Rebuild from exact
   decision cutoffs and retain continuous rise samples before settlement conversion.
5. **Live rising-day probabilities:** the old post-peak code changes its `determined`
   flag when observations are rising, but leaves the probability distribution itself
   unconditional. The conditional research model addresses this mechanism on a simpler
   target; it is not yet a validated replacement for the settlement distribution.
6. **Execution and risk:** hourly candles/midpoints do not establish fills. Existing
   strategy utilities do not provide a complete portfolio cash/collateral, depth,
   correlated-position, stale-quote, and latency simulator. Kelly sizing from uncertain
   standalone probabilities is not supported by these results.
7. **Uncertainty estimation:** the separate conditional-distribution script fits a scale
   model to in-sample mean-model residuals, which can understate uncertainty. Cross-fit
   those residuals chronologically before relying on its distribution scores.

## Next hypotheses worth testing

### 1. Joint remaining-rise and measurement-gap model

This is the strongest continuation of the measured conditional-model improvement.
Build each training example at an exact cutoff, preserving max-source provenance,
current temperature, drop from peak, recent slope, observation age, and forecast
remaining warming. Target the eventual eligible CLI integer directly, or jointly model
remaining rise and the gap between sampled and continuous maxima. Do not assume the two
components are independent: both can depend on clouds, wind, and how quickly temperature
changes. Include contract rounding, source coverage, and revised-report rules.

Test coherent full-board probabilities against both the current hour-only model and
contemporaneous market proxies. Promote only if the complete deployed transformation
improves chronological scoring and forward executable-price evidence.

### 2. Market disagreement conditional on physical state

Test whether the market responds differently to a weather-model update on rising,
stalled, cooling, or marine-intrusion days. Use the market as a baseline and seek
incremental information from the weather state. Freeze a small hypothesis set; do not
mine dozens of city/hour/bucket combinations and report the best one.

The current market blend supplies a conservative null benchmark. A state-specific
challenger must beat that benchmark and market alone, not merely the standalone model.

### 3. Forecast-update event study

Pair exact data-arrival times with order-book snapshots before and after the update.
Measure executable-price changes after realistic compute/network delays and whether
the advantage survives available depth and fees. A profitable settlement forecast can
still be untradeable if quotes move before the system can act. The v2 collector fixes
timestamp and precision loss, but full-depth collection is still needed.

### 4. One-sided contracts and explicit no-trade regions

After the observation/report provenance is validated, test whether wider one-sided
threshold contracts are less sensitive to the approximately one-degree measurement gap
than narrow buckets. This is a hypothesis, not an established edge. Price/volume limits,
model disagreement, unobserved intervals, and revised-report risk should create no-trade
states rather than forced signals. Keep all city-day exposure limits explicit.

## Reproduction and handoff

From `central_park_tmax`, with project dependencies and pytest installed:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python scripts/audit_conditional_rise.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python scripts/audit_probability_models.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python scripts/audit_core_backtest.py
```

Verification: 187 tests passed; module compilation and `git diff --check` passed.
The test run emitted 12 existing pandas FutureWarnings from `ghcn_daily.py`.

Outputs are in `reports/model_audit/`, including full per-year/per-city scores, input
hashes, row-level predictions, and before/after core benchmarks. The baseline benchmark
was run against an isolated `git archive` of the base commit using `--source-root`.
Do not rerun the old real-price fetch as though it will reproduce its original sample:
API historical coverage and live/historical endpoints can change.

Train-only imputers are stored inside newly fitted models. Existing joblib artifacts
should be retrained; models lacking fitted imputers reject missing input rather than
silently recreating test-batch statistics. Neither experimental model is wired into
the existing live trading probability path.

Official references consulted:

- [scikit-learn chronological splitting](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [Kalshi candle timestamps and historical endpoint routing](https://docs.kalshi.com/api-reference/market/get-market-candlesticks)
- [Kalshi historical candles](https://docs.kalshi.com/api-reference/historical/get-historical-market-candlesticks)
- [Kalshi YES and NO order-book conventions](https://docs.kalshi.com/getting_started/orderbook_responses)
