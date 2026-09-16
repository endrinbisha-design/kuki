# Report-based forecasting and the next alpha experiments

Research date: 2026-09-16. Initial audit published to
`claude/central-park-temp-forecast-u9gsw8` as commit
`22438345840c2eacc5e6e458a326dc95dbd03b7f`. This follow-up extends that branch.

The strongest new result is improved prediction of archived CLI report highs. A blend
of that forecast with market prices is promising on a small existing sample, but does
not establish alpha. Physical-state-specific blending did not improve on the simpler
blend. No experimental model has been substituted into the live settlement-probability
path, no orders were sent, and no scheduled collector was started.

## 1. Model the report high directly

### Data and day boundaries

Archived 2,813 KNYC daily report labels for 2019-2026 from IEM's parsed NWS CLI service.
The saved table includes report ID, issue timestamp, source link, and retrieval timestamp;
the manifest records response hashes and URLs. These are the archive's current revisions,
not a version history or proof of the specific report used by Kalshi.

The IEM [CLI documentation](https://mesonet.agron.iastate.edu/nws/clitable.php) specifies
midnight-to-midnight local **standard** time. For NYC, the model groups observations on
fixed UTC-5 report days while retaining 13:00-18:00 America/New_York decision times.
Thus 00:51 EDT belongs to the preceding CLI day. All features use observations at or
before the exact decision cutoff. This correction applies to the new research builders;
it is not a claim that all legacy live/multi-city day-boundary code has been corrected.

### Implementation

`models/conditional_report.py` learns the empirical distribution of:

`CLI integer high - rounded maximum observed by the decision cutoff`

This jointly captures later warming and the gap between snapshots and the reported high.
It avoids separately estimating those components and assuming independence. It preserves
negative differences instead of deleting inconvenient report/rounding discrepancies.

The model uses the same fixed hour/drop/slope bins as the first audit, with a fixed
prior strength of 30 toward the hour-only distribution. It returns a coherent integer
PMF. Unsupported tails fail explicitly rather than silently clipping probability mass.
The rounding phase and richer observation provenance remain candidates for improvement.

### Chronological results

844 held-out days, 4,907 decisions, annual evaluation folds 2021-2026. Fit only on earlier
years and exclude training labels whose recorded report issuance is after the fold
boundary. This uses report issue times, not verified historical receipt times.

| Model | Report median MAE, F | Ranked probability score | Integer log loss |
| --- | ---: | ---: | ---: |
| Conditional hourly-snapshot model, ignoring report gap | 1.0592 | 0.82249 | 2.55364 |
| Report target, hour-only | 0.7354 | 0.54310 | 1.37417 |
| Report target, conditional | **0.7291** | **0.53481** | **1.36326** |

Lower is better. The snapshot comparator is fitted on the same standard-time days with
the same conditional structure, replacing the report label with the rounded sampled high.
It is not the entire existing live pipeline, which already has other gap adjustments.
Most of the improvement comes from modeling the correct report target. Conditioning
adds a smaller 1.53% ranked-score improvement over the report hour-only baseline.
Ranked score improves in all six annual folds; MAE does not improve in every fold.

Paired conditional-minus-hour ranked-score difference: -0.00829; descriptive 95% interval
[-0.01110, -0.00554]. Bootstrap uses seven observed-day blocks within each year, so missing
dates are compressed. Data previously inspected, coverage filtering, and unknown receipt
latency prevent treating this as a prospective confirmation.

Rounded full-day hourly highs disagree with report integers on 63.6% of these evaluation
days; the mean report-minus-sampled gap is 0.744 F. This is a measurement/target finding,
not the probability of losing a contract. At two-degree contract resolution, the new CLI
labels match all 154 distinct archived NYC binary contract outcomes across 65 days.
That limited check uses partial historical between-contract boards and existing outcome
records; it is not fresh exchange verification or evidence of exact report-vintage match.

Results: `reports/model_followup/report_high_audit.json` and row-level predictions.

## 2. Does it add information beyond the market?

`scripts/audit_report_market.py` converts the new PMF into probabilities for the archived
inclusive between buckets. The weather model is fixed at the start of each test year.
Market blending and isotonic calibration are fitted only on earlier eligible dates,
with a minimum of 30 dates and a two-calendar-day label-delay assumption.

On the identical 230 matched observations across 33 NYC days:

| Model | Brier score | Binary log loss |
| --- | ---: | ---: |
| Existing weather probabilities | 0.15714 | 0.48801 |
| New report model alone | 0.15924 | 0.47180 |
| Chronologically calibrated report model | 0.16733 | 0.53407 |
| Market proxy | 0.14473 | 0.43907 |
| Market + report model blend | **0.14095** | **0.42937** |

The new model alone worsens Brier relative to the old weather output, despite improving
log loss. Isotonic calibration also worsens results. Do not treat a better temperature
forecast as automatically better contract probabilities.

The blend learns a mean weather weight of 9.69%, with the remaining weight on market
prices. Its Brier improvement versus market is about 2.61%. The paired difference is
-0.00378, with descriptive 95% interval [-0.01067, +0.00140], which includes zero.
The bootstrap uses seven observed-day blocks and compresses two missing calendar dates.

The legacy candle date-join problem is unresolved in these archived prices. Midpoints,
missing depth, observation receipt uncertainty, partial boards, and the small previously
examined sample block any executable-alpha conclusion. This candidate merits a frozen
forward test, not automatic promotion or a profitability claim.

## 3. Physical-state-dependent market blending

`scripts/audit_market_states.py` aligns observations to archived NYC quotes at exact
hour cutoffs, using three fixed states: rising, below peak, and near-peak flat/cooling.
Rising takes precedence if temperatures rebound below an earlier peak. Each state weight
shrinks toward a common weather weight; all buckets in the same state use that weight.
The script passes no remaining-rise/final-high features to the probability learner.

This experiment uses the **existing** weather probabilities to isolate state-dependent
blending, rather than mixing that change with the new report model.

On the same 33-day, 230-row matched sample, global blending has Brier 0.14379 and state
blending 0.14391. State blending's difference versus market has a 95% interval crossing
zero. It does not beat the simpler blend. The per-state table is exploratory; selecting
a favorable state after reading it would need a new test. Cloud/marine-intrusion states
were not tested because this input lacks appropriately aligned historical covariates.

## 4. Execution-data work

Added `scripts/archive_orderbooks.py` to request all book levels (`depth=0`) and preserve
fixed-point prices/quantities, request and receipt times, HTTP date, response hashes,
market rules, and series metadata. It handles pagination and records partial failures.
Sequential REST requests are not an atomic multi-contract board or a sequenced websocket.

`evaluation/execution_research.py` and `scripts/audit_event_markouts.py` provide:

- Opposite-side bid conversion for buys; same-side bids for sells.
- Depth consumption with decimal arithmetic and insufficient-depth rejection.
- A frozen signal timestamp and configurable latency before the first eligible request.
- Exit quotes after a holding horizon measured from entry receipt.
- An explicit round-trip fee budget; this is not a verified exchange/account fee engine.
- Rejection of malformed/crossed books and naive/misordered timestamps.

The live smoke attempt at the documented public endpoint returned **HTTP 403** before any
books were collected. The failure is recorded in `reports/model_followup/collection_smoke/`.
Consequently no real forecast-update event study or executable P&L result was produced.
Logic was tested with synthetic books; live collection remains unverified in this runtime.

Even with successful collection, these are hypothetical quote markouts, not fills:
cancellation, queue priority, multi-order competition for the same depth, market impact,
cash/collateral, correlated exposure, and actual fee/rebate accounting are not implemented.
The tool deliberately does not sum overlapping events into a claimed strategy return.

Official references:
[full-depth orderbooks](https://docs.kalshi.com/api-reference/market/get-market-orderbook),
[binary bid/ask conventions](https://docs.kalshi.com/getting_started/orderbook_responses),
[public data](https://docs.kalshi.com/getting_started/quick_start_market_data),
[current fee rounding](https://docs.kalshi.com/getting_started/fee_rounding).

## 5. Ranked ideas after this work

### First: establish the incremental value of faster observations

The report gap is much larger than the gain from extra state complexity. Obtain
timestamped sub-hourly/one-minute observations and report-consistent maxima, where station
coverage permits. Compare the existing snapshot model against a finer-sampling challenger
using identical report targets and decision times. Include coverage, sensor quantization,
and source receipt latency. Test whether one extra observation actually changes a
tradeable contract probability before the market reprices.

Success criterion: improvement against the report-only baseline **and** incremental
predictive value versus contemporaneous market quotes after realistic delays. A faster
feed is useful only if it supplies information the market has not already incorporated.

### Second: learn when to abstain, with a boundary-risk model

Keep continuous observed temperatures and their distance to contract integer boundaries.
Model observation age, coverage gaps, disagreement among eligible maximum sources,
rounding phase, and forecast dispersion. A point forecast can barely change while a
narrow bucket's probability changes substantially. Test wider one-sided thresholds and
narrow buckets separately; contract type alone does not imply an edge.

Use a simple uncertainty/no-trade rule trained on earlier dates. Report coverage versus
loss and executable opportunity count, not only accuracy on the most favorable subset.
Sparse observations or source conflicts should widen uncertainty rather than produce a
false "high locked in" signal.

### Third: recover training data through chronological cross-fitting

The first audit exposed core-model regressions when tuning and calibration received
separate slices of a short archive. Generate out-of-fold residuals from expanding windows,
with publication/label-availability delays, and study rolling calibration on those
residuals. This can retain more useful training information without reusing in-sample
errors. Refitting changes the error distribution; validate the entire refit/calibration
procedure chronologically instead of assuming cross-fit residuals transfer perfectly.

Start with the evening/Phoenix regression and the separate conditional-scale model's
in-sample residual problem. Predefine the comparison against the current honest split.

### Fourth: test probability consistency across the full contract board

Collect all mutually exclusive buckets plus available threshold contracts with exact
rules and nearly synchronized books. Check whether a coherent report PMF identifies
inconsistent relative prices or cheaper ways to express the same forecast. Check actual
ask depth and fees on every leg. Sequential snapshots and incomplete ladders can create
fake arbitrage; flag candidates for investigation without assuming simultaneous fills.

### Fifth: freeze a small forward experiment before more model searching

Freeze three forecasts: market-only, current weather/market blend, and new report/market
blend. Archive inputs, receipt timestamps, predictions, code commit, model ID, full rules,
eligible settlement versions, and quotes. Freeze the decision rule, latency assumptions,
fee scenarios, horizons, and primary day-balanced metric before collecting outcomes.

Choose an evaluation period/sample requirement in advance; do not stop when results look
positive. Keep every eligible decision, including no-trades and missing-data rejections.
Compare probability scores, calibration, capacity, and quote-based opportunities, then
validate actual execution separately. Resample by day to retain correlated buckets and
intraday observations. Do not promote based solely on the 33-day retrospective result.

## Reproduction and verification

From `central_park_tmax`:

```bash
# Offline: uses the committed labels and input archives.
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python scripts/audit_report_high.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python scripts/audit_market_states.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python scripts/audit_report_market.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m pytest -q

# Optional network refresh: current revisions may change the label file and its hash.
python scripts/archive_cli_labels.py --output-dir data/cli_refresh

# One-shot public book collection; does not schedule anything or place orders.
python scripts/archive_orderbooks.py
```

The event-study runner's `--help` describes its frozen-signal JSONL schema and requires
explicit latency, holding horizon, and round-trip fee-budget assumptions. Run it only on
real recorded signals/books for market conclusions; synthetic tests validate code only.

200 tests passed, including 13 new follow-up cases; compilation and diff formatting
checks passed. Twelve existing pandas FutureWarnings remain in GHCN parsing tests.
The initial audit's changes and this follow-up are published to the original project
branch. Experimental report and market models remain research candidates; existing
trained core artifacts require retraining to receive the preprocessing changes.
