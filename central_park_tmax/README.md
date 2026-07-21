# central_park_tmax

Station-specific **model-output-statistics (MOS)** system that predicts **tomorrow's maximum
temperature at NY City Central Park (KNYC / GHCN `USW00094728` / WBAN 94728)** and converts a
continuous predictive distribution into **calibrated integer-Fahrenheit report probabilities**
and **exact NHIGH temperature-contract probabilities**.

> ⚠️ **This project produces forecasts only. It never declares an official settlement.**
> Contract settlement is determined by the NWS Daily Climate Report, a separate process
> modeled explicitly here. Probabilities are forecasts, not guarantees. The project does not
> execute trades.

---

## 1. Scientific motivation

Numerical weather prediction (NWP) models have systematic, location-specific errors. Central
Park is a **park-interior observing site** (instruments near Belvedere Castle / Turtle Pond,
surrounded by vegetation, trees, exposed rock, and water) whose reported maximum frequently
differs from hotter, more urban or airport locations elsewhere in NYC. A station-specific MOS
model that **corrects NWP guidance for Central Park** — rather than modeling raw temperature
history — is the right tool. The **National Blend of Models (NBM)** is already statistically
post-processed and is a strong benchmark; our models learn the *residual* correction on top of
it (or another baseline when NBM archives are unavailable).

### Five quantities we deliberately keep separate

1. The **latent continuous** maximum air temperature.
2. The maximum **published in the NWS Daily Climate Report** (whole °F) — the contract underlying.
3. Later **revised / QC'd** climatological values (e.g. GHCN-Daily final).
4. The report value **available at contract expiration**.
5. The **contract payout outcome** implied by that report value.

The final GHCN-Daily `TMAX` is **not** automatically the contract target. See §4.

---

## 2. Contract target & settlement semantics

**Authoritative underlying:** the maximum temperature for the target date published in the
**NWS Daily Climate Report for Central Park** — *Temperature* section, *Yesterday* column,
*Maximum* row, whole °F.

**Timing** (`configs/contracts.yaml`):
- **Last trading:** 11:59 p.m. ET on the target date.
- **Normal expiration:** the first applicable **7:00 or 8:00 a.m. ET** after the report for the
  target date is released.
- **Delayed determination (→ 11:00 a.m. ET)** may apply when (1) the reported high is
  inconsistent with relevant 6-hour / 24-hour METAR highs, or (2) the final reported high is
  lower than an earlier report.

**Settlement state machine** (`contracts/settlement_state.py`) states:
`forecast_open → trading_closed → awaiting_report → preliminary_report_available →
[consistency_review] → expiration_value_locked`, plus
`later_revision_ignored_for_settlement` and `outcome_under_review`.

**Leakage rules that are enforced in code and tests:**
- Every retrieved report version is stored append-only and **never overwritten**
  (`data/report_archive.py`).
- **Revisions after expiration do not change the settlement value.**
- **Revisions before expiration replace** the earlier eligible value.
- We **never silently combine** GHCN final values with contemporaneous NWS report values.

### Contract-boundary semantics (exact)
`greater_than(K)` is strict (`> K`); `less_than(K)` is strict (`< K`);
`between_inclusive(A,B)` includes both endpoints. Examples (see `tests/test_contract_boundaries.py`):
a reported **90** does **not** satisfy `greater_than(90)`, **does** satisfy
`between_inclusive(88,90)`, and does **not** satisfy `less_than(90)`.

---

## 3. Station setting (documented, not blindly modeled)

`configs/locations.yaml` records Central Park and surrounding points (LaGuardia, JFK, Newark,
lower Manhattan, NY Harbor, coastal & inland NJ, western Long Island, lower Hudson Valley).
Because this is a **single-station** model, static site attributes (elevation ≈ 42.7 m,
park-interior siting, canopy, nearby water, distance to park edge / roads / buildings) **do not
vary over time** and are **not** fed uncritically into a single-station regression. They are
used to interpret dynamic effects, document representativeness, and build **physically
defensible spatial-gradient features** (e.g. Central-Park-minus-JFK, inland-minus-coastal,
harbor-minus-inland) that *do* vary day to day. We do **not** invent a time-varying
building-effect variable without a defensible source.

---

## 4. Data sources (honest capability matrix)

See `configs/data_sources.yaml` for the authoritative flags. Summary:

| Source | Implemented | Current data | Historical archive | Needs credentials | Needs GRIB |
|---|---|---|---|---|---|
| GHCN-Daily (NCEI + AWS mirror fallback) | ✅ | ✅ | ✅ (1869→) | no | no |
| NWS Daily Climate Report (CLI) | ✅ | ✅ | partial | no | no |
| NWS observations API (hourly/METAR) | ✅ | ✅ | ✅ | no | no |
| **NWS gridpoint forecast** | ✅ | ✅ | ❌ | no | no |
| **NBM** (preferred residual baseline) | ✅ | ✅ | ✅ (~2020-09→) | no | **yes** |
| HRRR / GFS / GEFS | ✅ | ✅ | ✅ | no | **yes** |
| Synthetic (demo/tests only) | ✅ | ✅ | ✅ | no | no |

- **GHCN-Daily** tries the NCEI `access` CSV first and automatically falls back to the NOAA
  Open Data AWS mirror (`noaa-ghcn-pds`, long format). *Caveat:* the AWS mirror can lag NCEI
  by days to months — the loader logs the max available date; prefer NCEI where reachable.
- **NBM/HRRR/GFS/GEFS** read NOAA Open Data on AWS via Herbie + cfgrib with `priority=['aws']`.
  Byte-range subsetting downloads **only the 2 m temperature message** per forecast hour
  (~1–2 MB) and deletes each GRIB subset after extraction, so multi-month archive builds use
  only megabytes of disk. Point extraction is self-contained (no cartopy): nearest grid point
  on both curvilinear (NBM/HRRR) and rectilinear (GFS/GEFS) grids. Without the GRIB deps these
  sources raise a documented `ForecastSourceUnavailable`; the pipeline then **falls back
  explicitly** (see §9) — it never fabricates data.
- **Synthetic** data are physically-plausible simulations for offline demos/CI/tests **only**,
  always tagged `synthetic_*` in provenance. Never mistaken for a real forecast or report.

> We **never** substitute reanalysis, analysis fields, later model runs, final observed data, or
> revised reports for forecasts/report-values that were unavailable at the historical prediction
> time.

---

## 4b. Robustness guards against out-of-envelope corrections

A residual booster extrapolates its learned correction *flat* into feature space it never
trained on, so a model trained on one season can over-correct in another. Observed live: an
Aug–Jan model applied a **+4.05 °F** warm correction to a July frontal-cooldown day that NBM,
HRRR, and GFS all placed within 0.9 °F of each other (and the market priced correctly). Three
layers address this, most-fundamental first:

1. **Inter-model features in training** (`pipelines/merge_forecast_archives.py`). HRRR/GFS
   point archives are joined onto the dataset as `intermodel_spread_f`, `intermodel_range_f`,
   and `baseline_minus_{hrrr,gfs}_f`. The booster then *learns* "tight NWP consensus ⇒ small
   correction" natively. On the live case this alone pulled the raw correction from **+4.05 →
   +1.45 °F** — the fix at the source, no runtime clamp needed. (Aggregate MAE barely moves,
   because these features matter on rare tail days, not the average day.)
2. **Consensus cap** (`models/ood_guard.py`, predict-time). When live secondary-model maxima
   are supplied, the correction is clipped to `2 × inter-model-spread` (min ±1.5 °F). A
   redundant safety net once (1) is trained in, but active whenever the archive is thin.
3. **Out-of-distribution shrink** (`models/ood_guard.py`, predict-time). Each trained model
   stores its feature envelope (`FeatureStats`); at predict time, corrections shrink toward
   the raw baseline (floor 0.25×) as key features leave that envelope. Reported per forecast
   (`ood_score`, `ood_shrink`) so a shrunk prediction is visibly flagged.

Guards only ever **attenuate toward the trustworthy baseline** — they never add.

### Real-time temperature-trend (nowcasting) features

Motivated live (2026-07-21): the temperature stalled at 75 °F all morning under pre-storm
clouds while the model — running off NBM forecast cycles — still expected ~80 °F, and the
market (watching the live thermometer) correctly leaned lower. The model was blind to the
observation *trajectory*. Added leakage-safe intraday features: recent warming rate
(1/2/3 h), time-since-observed-max, drop-from-peak, a `stalled_before_peak_flag`, and a
`headroom_minus_trend_support_f` (how much of NBM's remaining warming the live trend
actually supports). A fixed-hyperparameter, rolling-origin **ablation** decided their fate
honestly:

| vintage | without trend | with trend |
|---|---|---|
| noon (target_12) | 1.564 | 1.545 (neutral) |
| **4 PM (target_16)** | 1.368 | **1.106 (~19 % better)** |

They clearly help the 4 PM model (post-peak cooling + time-since-peak confirm the high is
locked in) and are neutral at noon, so they are **kept as model inputs**. They are *also*
surfaced in every prediction's `trend_diagnostics` block so a human sees "stalled" on a
day like Jul 21 regardless of how the model weights it. (An initial single-subset read
hinted at overfitting on the 35-day stall slice; the full-vintage ablation did not bear
that out — a reminder to ablate on the whole vintage, not a cherry-picked subset.)

### Intraday vintages

Dedicated same-day models converge as the day progresses (rolling-origin MAE): prev-evening
**1.70** → noon **1.60** → 4 PM **1.17** °F. The 4 PM model hits the exact published integer
~42 % of the time (top-two ~69 %) because by mid-afternoon the observed max is largely
locked in — reconstructed from METAR 6-hour max groups and the intraday CLI, not coarse
hourly snapshots (see §4c).

---

## 5. Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # core (no GRIB, no boosting extras needed to run)
# optional extras:
pip install -e ".[boosting]"     # xgboost + lightgbm (else sklearn HistGBR fallback)
pip install -e ".[dev]"          # pytest
pip install -e ".[grib]"         # xarray + cfgrib + eccodes + Herbie + s3fs
```

### GRIB / ecCodes setup (only needed for NBM/HRRR/GFS/GEFS)
Modern `eccodes` pip wheels **bundle the ecCodes binary library** — on most Linux/macOS
platforms `pip install -e ".[grib]"` is all you need (verified working). If your platform has
no binary wheel, install ecCodes via conda or apt first:
```bash
conda install -c conda-forge eccodes cfgrib herbie-data s3fs   # alternative route
```
If ecCodes is missing, GRIB sources raise a clear error and the pipeline uses the NWS gridpoint
source + fallback hierarchy.

Secrets (only `.env`, never in configs): copy `.env.example` → `.env`. The core pipeline needs
**no credentials**.

---

## 6. Verified real-data results (reference run)

The full real-data path has been exercised end-to-end against live NOAA sources:

- **Observations:** 57,014 real GHCN-Daily records for USW00094728 (1869 → mirror max date).
- **Forecasts:** live point extraction verified for all four GRIB models (NBM, HRRR, GFS,
  GEFS ensemble mean) plus the NWS gridpoint source.
- **Training set:** 184 consecutive days of archived NBM runs (2024-08-01 → 2025-01-31,
  previous-evening vintage, 3-hourly trajectory, zero gaps), labels = GHCN final
  (provenance `ghcn_daily_final`).
- **Rolling-origin backtest** (3 folds, 111 out-of-sample days), by forecast vintage:

  | vintage | model | MAE (°F) | within ±2 °F | exact-integer | top-two |
  |---|---|---|---|---|---|
  | prev-evening (7 PM) | raw NBM | 2.20 | 50 % | — | — |
  | prev-evening (7 PM) | **boosted residual** | **1.70** | 67 % | 18.9 % | 35.1 % |
  | **target-day 4 PM** | obs-constrained NBM | 1.40 | 82 % | — | — |
  | **target-day 4 PM** | **boosted residual** | **1.24** | **84 %** | **41.4 %** | **67.6 %** |

  The prev-evening model beats raw NBM by 22 % and removes its −1.6 °F cold bias. The
  **intraday 4 PM model** is far sharper — by mid-afternoon the observed max is largely
  locked in (reconstructed from METAR 6-hour max groups + the intraday CLI, not just coarse
  hourly snapshots), so it nails the exact published integer ~42 % of the time and is
  top-two ~68 %. Its observation-constrained baseline `max(observed-so-far, forecast-remaining)`
  is 1.40 °F MAE before any ML correction.
- **Strategy backtest** (walk-forward PMFs, simulated market — see §11b): edge-flat
  +20.5 % ROI on risked capital over 310 trades; 25 % Kelly +$277 net with ~7× the
  drawdown; tail-fade 96.9 % win rate on 128 small NO trades.
- **Live forecast:** trained model + latest NBM run produced a full probabilistic forecast
  for the next local day (continuous distribution, integer PMF summing to 1, exact contract
  probabilities), `fallback_level: 1`.

*Caveats of this reference run:* labels are GHCN research labels, not archived CLI report
values (provenance is tagged; the two are never conflated); part of the learned correction
compensates 3-hourly trajectory sampling (`fxx_step=1` removes it); strategy P&L is against
a **simulated** counterparty anchored on the same NBM guidance — it demonstrates the model
can exploit a *less-calibrated* pricer, not that real Kalshi markets (which are sharper and
watch live observations) offer the same edge. One season of data; extend the archive for
seasonal robustness.

## 6b. Quickstart — fully offline synthetic demo

```bash
make demo            # or: python -m central_park_tmax demo --synthetic
```
This runs the entire pipeline end-to-end **without network or GRIB**: builds a synthetic dataset,
rolling-origin backtest (+ MAE plot), trains XGBoost residual models per vintage, produces a
probabilistic forecast (continuous + integer + contract probabilities), and a settlement record.
Artifacts land under `data/` and `reports/`. On a laptop this completes in ~1–2 minutes.

---

## 7. Real-data workflow

```bash
# 1. Observations (GHCN-Daily final QC values + 1991-2020 normals)
python -m central_park_tmax build-observations

# 2. Archive the NWS Daily Climate Report (append-only, versioned)
python -m central_park_tmax build-report-archive               # live retrieval
python -m central_park_tmax build-report-archive --from-file report.txt   # archive a saved text product

# 3. (optional) Archive numerical forecast point-features for a date range
python -m central_park_tmax build-forecast-archive --source nbm --start 2023-01-01 --end 2023-12-31

# 4. Build a leakage-safe dataset from the real NBM archive (AWS). ~20-25 s per
#    (date, vintage) for byte-range GRIB extraction; start with one vintage:
python -m central_park_tmax build-dataset --source nbm \
    --start 2024-11-15 --end 2025-01-31 --vintage prev_evening_19
#    Builds are RESUMABLE: rows checkpoint to data/processed/dataset.csv after every
#    date, and a rerun skips (date, vintage) pairs already present — safe to interrupt.
#    Widen the range / add vintages incrementally as your archive grows.

# 5. Rolling-origin backtest (metrics JSON + plots under reports/)
python -m central_park_tmax backtest

# 6. Train residual models (saved with config, feature names, git hash, model card)
python -m central_park_tmax train

# 7. Forecast tomorrow (all vintages) from current public data
python -m central_park_tmax predict-tomorrow

# 8. Forecast at an arbitrary issue time
python -m central_park_tmax predict-at-time --target-date 2025-07-16 --issue-time 2025-07-16T12:00:00

# 9. Settlement monitoring for a target date
python -m central_park_tmax monitor-settlement --target-date 2025-07-15
python -m central_park_tmax determine-expiration-value --target-date 2025-07-15

# convenience: end-to-end daily run
python -m central_park_tmax run-daily
```
Append `--synthetic` to any command to run offline against the synthetic generator.

---

## 8. Modeling strategy

**Primary strategy — predict the model error:**
```
residual        = report_tmax - baseline_model_tmax
predicted_tmax  = baseline_model_tmax + predicted_residual
```
Baseline = NBM when usable, else HRRR → GFS → GEFS → NWS gridpoint (configurable preference).

**Models** (`models/`): climate-normal, persistence, observed-max-so-far, raw primary, rolling
14/30/60-day bias correction, linear/ridge residual regressions, and **gradient-boosted residual**
models (XGBoost → LightGBM → sklearn HistGBR auto-fallback, early stopping). MAE is the primary
deterministic selection metric.

**Uncertainty:** quantile gradient boosting **and** empirical residual calibration (out-of-sample
residuals only). Quantiles are made **non-crossing** by monotone sorting.

**Intraday constraint:** for same-day issue times,
`final_daily_max = max(observed_max_so_far, predicted_remaining_max)` — the prediction (and the
entire predictive distribution) can never fall below the maximum already observed.

**Reporting convention layer** (`models/reporting_convention.py`): the NWS integer is **not**
assumed to be naive rounding. ASOS computes internally and the CLI value is generally the *max of
already-rounded* hourly observations. We default to a documented `round_half_up` and provide
`truncate`, `ceil`, `round_half_even`, and `max_of_rounded` as configurable, empirically
evaluated alternatives.

**Integer & contract probabilities:** simulate from the calibrated continuous distribution, map
each draw through the reporting convention to an integer PMF (guaranteed to sum to 1), then sum
PMF mass under exact strict/inclusive contract rules.

**Blending** (`models/blend.py`): optional convex blend with nonnegative weights summing to one,
estimated **only** from validation predictions, falling back to the single best model.

---

## 9. Operational fallback hierarchy

Every prediction reports `fallback_level`, `data_sources_used`, `missing_sources`, model name,
training range, issue timestamps, and uncertainty method.

1. Full model (preferred baseline + residual ML)
2. Residual model on a fallback baseline source
3. Primary baseline + rolling bias correction
4. Raw primary numerical forecast
5. NWS point forecast
6. Climate-normal (last resort)

Missing forecast sources are **never** silently imputed as normal weather.

---

## 10. Validation & leakage prevention

Rolling-origin / expanding-window folds only (never a random split); configured in
`configs/default.yaml`. All transforms — imputation, scaling, feature selection, hyperparameter
tuning, residual calibration, interval calibration, blend weights — are fit on the **training
portion of each fold only**. Forecast runs initialized after the prediction time and observations
released after it are **rejected** (`evaluation/diagnostics.py`, tests in
`tests/test_forecast_availability.py`, `tests/test_no_leakage.py`). Backtests are reported
**separately by forecast vintage**.

### Evaluation targets (kept separate)
- **Meteorological:** continuous / final QC daily maximum.
- **NWS reporting:** the integer CLI maximum.
- **Contract:** the settlement-eligible integer at expiration.

Metrics: MAE/RMSE/bias/±1–3 °F hit rates/correlations (continuous); pinball loss, interval
coverage/width, CRPS (quantile); log-loss, RPS, Brier, reliability, exact & top-two integer
accuracy (integer); Brier/log-loss/calibration (contract). Disagreement rates among reconstructed
METAR max, GHCN, initial vs revised CLI, and settlement-eligible values are reported
(`evaluation/report_revision_analysis.py`).

---

## 11. Output formats

Predictions (`data/predictions/prediction_<date>_<vintage>.json`) contain the continuous point &
distribution, integer report PMF, exact contract probabilities, baseline & bias correction,
model name, `fallback_level`, sources used/missing, top model attributions (labeled as
*model attribution, not causal*), model training range, and reporting/contract rule versions.

Settlement records (`data/settlement/settlement_<date>.json`) contain all report versions with
eligibility flags, the settlement-eligible value + provenance category, later-revision value
(with `later_revision_affects_settlement: false`), delay flag & reason, and the state-machine
state.

---

## 11b. Strategy backtesting (research only — no order placement)

`python -m central_park_tmax backtest-strategies [--real-market]` evaluates three
strategies on Kalshi-style NYC-high bucket ladders (low tail "K or below", inclusive
2 °F bands, high tail "K or above" — exact NHIGH boundary semantics):

1. **`edge_flat_8c`** — buy 1 contract of YES/NO whenever the model's probability beats
   the ask by >8¢. Flat stakes.
2. **`kelly_25pct`** — same signal, stake = 25% fractional Kelly, capped at 10 contracts.
3. **`tail_fade`** — buy NO on longshot buckets priced 5–20¢ that the model deems at
   most half as likely (favorite–longshot-bias harvesting).

Mechanics: model PMFs are strictly **walk-forward out-of-sample** (each test day is
predicted by a model trained only on earlier days); ladders center on the issue-time NBM
baseline (no lookahead); settlement uses the recorded integer outcome and Kalshi taker
fees `ceil(0.07·C·P·(1−P))`; metrics include win rate, net P&L, ROI on risked capital,
and max drawdown.

Market prices come from `data/kalshi.py`:
- `--real-market` uses the **public Kalshi trade API** (settled KXHIGHNY markets +
  candlestick entry prices at/before the issue time). Requires network access to
  `api.elections.kalshi.com` — some sandboxes block it.
- default is a **clearly-labeled simulated market maker** (Normal pricer anchored on the
  same NBM guidance, daily mispricing noise, spread; deterministic per date). Results
  against it are *research diagnostics of strategy behavior*, **not** realized-P&L claims.

The project never automates trading or order placement.

## 12. Reproducibility

Pinned dependency lower bounds; fixed random seeds; deterministic options where available; saved
resolved config + feature names + training range + git commit hash + a JSON **model card** with
every trained bundle; dataset schema + manifest with SHA-256 checksums; explicit
reporting-convention and contract-rule version tags on every artifact.

---

## 13. Testing

```bash
make test      # or: python -m pytest -q
```
Meaningful tests (not import smoke tests) cover: local-day = America/New_York; DST 23/25-hour
days; rejection of future model runs & future observations; wind encoding across the 0/360
boundary; rolling bias using only prior errors; non-overlapping time folds; report versions never
overwritten; post-expiration revisions not altering settlement; pre-expiration revisions
replacing the eligible value; the 90 °F boundary examples; integer PMF summing to one; ordered
quantiles; temperature conversions; the intraday observed-max constraint; explicit missing-data
fallbacks; required prediction-output fields; and delayed-determination flagging.

---

## 14. Storage requirements & troubleshooting

- Core pipeline (GHCN + reports + NBM point extraction): **megabytes** — byte-range GRIB
  subsetting + delete-after-extract keeps even multi-month archive builds tiny on disk.
  Full-grid GRIB retention (`keep_grib=True`) can require many GB; leave it off.
- **`cannot find eccodes`** → `pip install eccodes` (wheels bundle the library) or conda (§5).
- **`ForecastSourceUnavailable`** → expected without GRIB extras; use NWS gridpoint or `--synthetic`.
- **NWS API 403 / rate limits** → set a contact email in `.env` (`NWS_API_USER_AGENT_EMAIL`) and
  respect the retry/backoff (configured in `configs/default.yaml`).
- **Partially blocked egress** (some sandboxes): NCEI, api.weather.gov, and IEM may be
  unreachable while **AWS Open Data buckets still work** — in that case observations come from
  the GHCN AWS mirror and forecasts from NBM/HRRR/GFS/GEFS on AWS; only live CLI-report
  retrieval and the NWS gridpoint source are unavailable (archive reports via `--from-file`).
- **Fully blocked egress** → run `--synthetic`.
- **AWS GHCN mirror lag** → the mirror's most recent date can trail NCEI; training labels stop
  at the mirror's max date. Use NCEI where reachable for fresher labels.

---

## 15. Limitations (read this)

- Central Park is a park-interior site; its reported max may differ from hotter NYC locations.
- NBM is already post-processed — beating it consistently is hard; treat it as the benchmark.
- Forecast archives and operational model versions change over time; **point-in-time
  availability** is essential and enforced.
- The NWS value used at expiration can differ from a later revised climate record.
- **Weather prediction and contract settlement determination are separate processes.**
- Synthetic mode is for development only and is **not real weather**.
- Probabilities are forecasts, not guarantees. The project does **not** execute trades.

---

## 16. Repository layout

```
central_park_tmax/
  configs/            default.yaml, locations.yaml, data_sources.yaml, contracts.yaml
  src/central_park_tmax/
    time_utils.py constants.py config.py logging_config.py main.py
    data/           ghcn_daily, hourly_observations, metar, nws_api, nws_climate_report,
                    report_archive, forecast_base, nbm/hrrr/gfs/gefs, nws_gridpoint,
                    synthetic, sources, storage
    features/       wind, radiation, precipitation, climatology, spatial, intraday, build_features
    models/         baselines, linear, boosting, quantiles, discrete_outcomes,
                    reporting_convention, blend, calibration, features_frame
    contracts/      nhigh_rules, probabilities, settlement_state, outcome_review
    evaluation/     splits, metrics, backtest, diagnostics, report_revision_analysis
    pipelines/      build_observations, build_report_archive, build_forecast_archive,
                    build_dataset, train, predict, evaluate, ingest_settlement, context
    reporting/      forecast_report, contract_report, plots
  tests/            20+ focused test modules + fixtures
  notebooks/        (audit / exploration placeholders)
```
