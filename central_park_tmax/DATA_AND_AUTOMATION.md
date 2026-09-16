# Automated paper research, data sources, and strategy comparisons

Implemented 2026-09-16 on the existing temperature project branch. The goal is an
unattended collect/forecast/decide/evaluate workflow with an auditable path to later
execution work. This implementation supports **paper research only**. It has no exchange
order-submission client, no production credentials, and rejects any mode other than
`paper`. No background service has been enabled in this workspace.

## What now runs without manual decisions

`scripts/run_paper_cycle.py` runs one cycle:

1. Lock the process so two workers cannot run the same account concurrently. Verify the
   frozen model hash/ID and the portfolio configuration.
2. Retrieve KNYC METARs, save their raw JSON fields and actual request/receipt times.
   Construct features only from observations at/before the latest exact-hour cutoff.
3. Forecast a coherent report-high PMF during the trained May-September, 13:00-18:00
   New York windows. Allow at most five minutes after the cutoff for collection/decision.
4. Collect full order books and market metadata; save rules, receipt timestamps and
   errors. Reject incomplete, stale, slow, malformed or overlapping contract boards.
5. Simulate fills of **previously frozen** paper intents only using a later qualifying
   snapshot, after the configured latency and within the original price limit.
6. For a complete event board, normalize midpoint proxies, combine them with the weather
   PMF, apply the selected strategy and risk limits, and persist new pending intents.
7. Reconcile funded positions against explicit `settled` exchange results. Never invent
   settlement from the forecast or a preliminary weather report.
8. Save a heartbeat, portfolio summary, inputs, forecasts, decisions and an append-only
   SQLite journal. On data failure, cancel unfilled intents and record degraded health.

All orders and money in this workflow are simulated. Quotes can disappear before a real
order reaches the exchange. The paper fill mechanism does not establish real queue
priority, cancellation survival, or execution capacity.

### Portfolio and operational controls

`src/central_park_tmax/paper.py` uses SQLite transactions and integer millionths of a
dollar for accounting. It reserves cash when an intent is created, funds purchases fully,
and persists through restarts. Replaying the same signal or settlement does not double
spend or double credit. Conflicting settlement results fail for explicit reconciliation.

Defaults in `configs/paper.json` are **simulation settings**, not personal capital advice:

| Setting | Default |
| --- | ---: |
| Starting paper cash | $1,000 |
| Maximum combined open/pending cost exposure | $50 |
| Maximum cost exposure per event | $10 |
| Maximum daily spending | $20 |
| Daily realized-loss halt | $10 |
| Entries per day / contracts per entry | 20 / 1 |
| Assumed entry fee / additional slippage per contract | $0.02 / $0.01 |
| Required edge after assumed costs | 3 cents |
| Robust probability haircut | at least 3 percentage points |
| Weather weight in the blend | fixed 10% |
| Maximum quoted spread / book age | 8 cents / 15 seconds |
| Minimum latency / pending-intent expiry | 2 / 180 seconds |

Day-based ledger limits use UTC. Event limits aggregate the whole NYC report date, so
correlated buckets share a budget. An active or settled ticker cannot be entered again
within a portfolio. Pending intents count against cash and exposure. Configuration and
model IDs are pinned to the database; use a new database for a different experiment.

The daily-loss control uses **realized** losses, not mark-to-market loss. Open positions
remain bounded by fully funded cost limits. Holding to settlement avoids inventing an
exit fill; it also ties up capital until an actual result is available.

Creating `data/paper/run/STOP` cancels pending intents on the next cycle and halts the
worker. It does not liquidate funded positions or cancel real orders (none exist here).
With an interrupted feed, unresolved positions remain unresolved rather than receiving
an assumed payout. Check `heartbeat.json` and the systemd journal for outages.

## New data: what was actually retrieved and learned

The IEM one-minute source returned **Central Park data**, plus data for EWR/JFK/LGA in a
one-day probe. Its documentation says the NCEI-based archive has roughly a **24-hour
delay**. That delay rules out using the archive as a same-day trading feed.

`scripts/audit_minute_data.py` retrieved NYC observations for May-September 2025 and
May 1-August 1, 2026. Raw cached responses total about 10.7 MB. Request provenance and
hashes are recorded. Of 236 days matched to the existing hourly/CLI data, 90 passed the
predefined coverage rule: at least 1,000 distinct observed minutes and no gap, including
day edges, exceeding 60 minutes.

On those **identical 90 dates**:

| Direct maximum used as report estimate | Exact rounded report match | MAE versus CLI |
| --- | ---: | ---: |
| Hourly observations | 43.3% | 0.651 F |
| Raw one-minute observations | 40.0% | 0.756 F |

More samples did not produce a better uncalibrated report estimate. The one-minute max
averaged 1.407 F above the hourly max. Quantization, sensor/report aggregation, missingness,
and source differences need investigation; these results do not identify a single cause.
Do not replace the station report target with the minute maximum or silently feed these
delayed data into historical intraday predictions. Better uses include measurement-model
research, coverage diagnostics, and carefully availability-lagged historical features.

The five-minute HFMETAR probe for 2026-07-29 returned rows for EWR, JFK and LGA, but no NYC
rows. Many temperature values in the sample were missing. Nearby stations remain
candidates for wind shifts/cloud changes, not interchangeable settlement thermometers.
This is a one-day availability finding, not a claim that NYC never has five-minute data.

Results and daily coverage: `reports/automation_research/minute_data_audit.json` and
`minute_daily_comparison.csv`. Raw bulk weather downloads are excluded from git and
can be fetched again with the documented script; source revisions may change hashes.

## Data-source priorities

| Source | What it can add | Availability and required checks |
| --- | --- | --- |
| [IEM/NCEI one-minute ASOS](https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?help=) | Historical measurement gaps, source calibration, coverage | NYC availability confirmed in this sample; about 24h delayed; not a live signal |
| [IEM METAR/HFMETAR](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help=) | Nearby wind, dew point, clouds, rain and temperature histories | Report types 1/3/4 distinguish high-frequency/routine/specials; verify each variable's missingness and archive latency |
| [NWS Aviation Weather API](https://aviationweather.gov/data/api/) | Live station METAR/SPECI reports and temperature remarks | Successfully retrieved by the paper-cycle smoke test; log first local receipt, not just observation time; API supplies recent history, not years |
| [NWS CLI via IEM](https://mesonet.agron.iastate.edu/nws/clitable.php) | Report high labels and report IDs | Already archived; retain versions/issue/receipt times; CLI current revision is not automatically the exchange's settlement version |
| [NOAA HRRR](https://registry.opendata.aws/noaa-hrrr-pds/) | Hourly forecast updates, clouds, radiation, advection and remaining warming | Forecast initialization/valid time alone is insufficient; archive file availability and local receipt; use station/grid representativeness corrections |
| [NOAA NBM](https://registry.opendata.aws/noaa-nbm/) | Strong forecast baseline and distribution/ensemble information | Verify field availability and issue vintages; compare incremental information to existing guidance rather than counting correlated models as independent evidence |
| [NOAA GOES](https://registry.opendata.aws/noaa-goes/) | Cloud clearing/movement and solar-heating conditions | Prospective feature idea; requires parallax/quality checks, exact scan/availability times, and a tested spatial aggregation |
| [Kalshi historical API](https://docs.kalshi.com/getting_started/historical_data) | Market outcomes, trades, candlesticks and contract metadata | Query `/historical/cutoff` and use the appropriate historical/live route. Candles do not reconstruct the full executable order book |
| [Kalshi order-book websocket](https://docs.kalshi.com/websockets/orderbook-updates) | Sequenced depth snapshots/deltas for forward execution research | Authentication required; detect sequence gaps and resnapshot; not implemented in this REST paper runner |
| [Synoptic time-series/latency services](https://docs.synopticdata.com/services/time-series) | Potential alternate station feeds and explicit latency diagnostics | Requires a token; verify KNYC coverage, actual observation cadence, latency, entitlement and cost before choosing a plan; not purchased or tested |

The direct NCEI [ASOS archive](https://www.ncei.noaa.gov/products/land-based-station/automated-surface-weather-observing-systems)
is also useful for checking original one-/five-minute files against IEM's processed
representation. It is a historical-source validation task, not a guaranteed faster feed.

I checked Dome as a possible third-party market-history source. Its [current documentation](https://docs.domeapi.io/)
announces API end-of-life on April 28, 2026, so it is not recommended for this project.
No paid data subscription or outside account was created.

## Strategy comparisons completed

Four rules are implemented: report-only flat entries, a fixed 10% weather/90% market
blend, the blend with quality gates, and a conservative blend with a probability haircut.
The forward runner uses complete boards and normalized market proxies. The historical
scenario script uses incomplete archived midpoint probabilities; it is not a replay of
the exact forward board transformation.

`scripts/audit_strategy_scenarios.py` compared these rules on the existing 230 rows/33
days under three **synthetic** spread/fee scenarios. Each scenario assumes one contract
of depth and an unchanged quote after latency. Cash, cost exposure, duplicate entries
and delayed settlement are accounted for, but those synthetic quotes are not historical
execution evidence. The original price-join provenance problem still applies.

| Assumed full spread / entry fee | Report-only entries / hypothetical net | Blend entries / hypothetical net | Gated / robust entries |
| --- | ---: | ---: | ---: |
| 1c / 1c | 67 / $7.60 | 12 / $0.53 | 0 / 0 |
| 3c / 2c | 63 / $6.18 | 2 / -$0.15 | 0 / 0 |
| 5c / 3c | 63 / $4.98 | 0 / $0.00 | 0 / 0 |

These are hypothetical, non-compounding one-contract outcomes; they are not profit
forecasts. The raw-model result cannot repair bad price provenance. The practical finding
is that the blend's already-small apparent opportunity disappears with greater friction,
and the conservative rules currently abstain. We did not loosen the gates until a
profitable-looking strategy appeared. The full assumptions/results are saved in
`reports/automation_research/strategy_scenarios.json`.

The complete-board diagnostic also reports the gross cost of one YES contract in each
mutually exclusive outcome. It is a consistency check only: fees, depth, asynchronous
snapshots and multi-leg execution risk can eliminate apparent opportunities.

## Model-validation work

Added an expanding-window cross-fit helper and used it to replace **in-sample** mean
errors in the conditional-scale model. Each residual is generated by a model trained on
earlier dates with a two-calendar-day embargo. Mean-model refitting can now use all
available training rows while scale fitting uses only eligible out-of-fold errors.
Random implicit early stopping is disabled for those mean/scale fits.

Regression tests verify future-label perturbations do not alter earlier predictions.
The full multi-city MOS distribution experiment was not rerun, so this is a validation
fix, not a newly measured accuracy improvement. Final/revised historical labels and
actual publication delays remain a separate data-provenance limitation.

## Run on a persistent Linux host

The supplied user-level systemd service assumes the checkout is at `~/kuki`. Adjust
`WorkingDirectory` and `ExecStart` in `deploy/central-park-paper.service` if it is elsewhere.
The service/timer files are templates, not an already deployed service.

```bash
cd ~/kuki/central_park_tmax
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/prepare_forward_model.py
.venv/bin/python scripts/run_paper_cycle.py

# Once this host can retrieve valid weather and complete Kalshi books:
mkdir -p ~/.config/systemd/user
cp deploy/central-park-paper.service deploy/central-park-paper.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now central-park-paper.timer
systemctl --user status central-park-paper.timer
journalctl --user -u central-park-paper.service
```

For operation while logged out, the host must support a persistent user service manager
(for example, appropriately configured user lingering). This is not configured here.
Back up `data/paper/run/paper.sqlite` using SQLite's backup API and retain the input
archives/model artifact; do not copy only the main database file while ignoring WAL.

```bash
# Stop generating new paper activity:
touch data/paper/run/STOP
systemctl --user stop central-park-paper.timer

# Reproduce research without placing any orders:
.venv/bin/python scripts/audit_minute_data.py
.venv/bin/python scripts/audit_strategy_scenarios.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q
```

The model preparation command trains on eligible historical reports, freezes the model,
and writes input/source hashes plus a model card. Only load trusted locally built joblib
artifacts. This worker does not automatically retrain and change the experiment midstream.

## Actual status and what remains before live execution

A real cycle retrieved weather, wrote its archive/heartbeat, then received **HTTP 403**
from Kalshi. It recorded degraded health with zero intents, fills or spending. No
attempt was made to circumvent the endpoint restriction. A simulated integration test
exercised forecast -> intent -> later fill -> exchange-result settlement, duplicate
prevention, and outage handling. That validates control logic, not live connectivity.

Remaining operational requirements are a persistent host, working authorized market-data
access, monitored forward collection, exact fee/rule reconciliation, and sufficient
fresh outcome evidence. Source failures and no-trade reasons should be measured as part
of the experiment rather than discarded from the sample.

Before implementing live order submission, test client-order IDs, order/fill reconciliation,
partial fills, cancellation races, position limits, and restart behavior in the
[Kalshi demo environment](https://docs.kalshi.com/getting_started/demo_env). Demo funds and
credentials are separate from production; demo prices are not evidence of real alpha.
Then separately validate executable opportunity/capacity on production data. Live capital
limits, authenticated execution and a production deployment are not configured here.

The next data-driven experiment should be a source-calibrated measurement model and
timestamped nearby-station/cloud features, compared against the frozen report/market
baseline. Predeclare train/test dates, latency/cost assumptions, probability and execution
metrics, and stopping rules. Do not search dozens of rules on the same 33-day archive.

Verification: **216 tests passed**, including restart, idempotency, cash/exposure limits,
stale/future quote rejection, STOP handling, daily-loss halt, complete-board checks,
standard-time feature windows, future-label isolation, and the mocked end-to-end cycle.
Compilation and diff-format checks passed. Twelve pre-existing pandas FutureWarnings
remain in GHCN parser tests. The live connectivity limitation is documented separately
from these successful code tests.
