# Live call track record

A persistent, honest log of **live forecast calls vs. actual outcomes** for KNYC Central
Park daily maximum temperature and the associated Kalshi `KXHIGHNY` contract calls. Committed
to git so it survives (the trained model bundle and datasets are gitignored/ephemeral; this
is not).

## Why keep it
1. **Evidence / calibration.** Each entry is a genuinely out-of-sample live day: the model's
   forecast + raw guidance (NBM/HRRR/GFS) + NWS + regime → the *actual* high and whether each
   contract call won. Accumulated, this is a real-world validation set no backtest can fake.
2. **Model improvement.** The clearest signal emerging (see below) is **regime-dependent model
   trust**, which the current model does *not* explicitly encode. This log is the labeled data
   to build and validate that.
3. **Honesty ledger.** It records where the *model* was right and where *my in-the-moment
   overrides* were wrong — so the pattern is visible, not forgotten.

## Format (`call_log.jsonl`, one JSON object per target date)
| field | meaning |
|---|---|
| `target_date`, `weekday` | the forecast target day (local) |
| `call_issued` | when the call was made (`night_before`, `morning`, `intraday_HHMM`) |
| `regime` | `storm_convective` \| `clean_warm` \| `frontal` \| … (post-hoc label) |
| `storm_risk` | bool: were storms/clouds a suppression risk that day |
| `guidance` | `nbm_f`, `hrrr_f`, `gfs_f`, `nws_forecast_f`, `model_point_f`, `model_80_interval_f` |
| `actual_high_f` | the settled/observed high (prefer the NWS CLI value) |
| `actual_high_source` | `cli_and_obs_confirmed` \| `user_reported_pending_cli` \| … |
| `model_error_f` | `actual_high_f − model_point_f` (fill once actual is confirmed) |
| `calls` | list of `{market, side, entry_c, result: win/loss}` |
| `notes`, `lesson` | narrative + the takeaway |

## Scorecard so far

| date | regime | NBM | HRRR/GFS | NWS | model | **actual** | calls | result |
|---|---|---|---|---|---|---|---|---|
| Jul 21 | storm | 78 | 84/85 | 80 | 79 | **80** | NO ≤78 | ✅ |
| Jul 22 | clean warm | 83 | 85/84 | 84 | 84.7 | **86–87** | NO ≤83, YES 86–87 | ✅ ✅ |

> **Accuracy note (honesty first):** I have logged the **two** call-days I can verify directly
> from the conversation (Jul 21, Jul 22). You mentioned **three** winning nights — if there's a
> third call-day I under-counted, give me the date + the call and I'll add it. This ledger is
> only worth keeping if every entry is real, so I won't pad the count. Also: Jul 22's actual
> high is **user-reported (86–87)**; replace with the exact NWS CLI value once it publishes
> (`python -m central_park_tmax ingest-nws-report`).

## The emerging, actionable insight — regime-dependent model trust
- **Storm / cloud-suppressed days** (Jul 20, Jul 21): **NBM + NWS run cooler and win**; raw
  HRRR/GFS 2 m temps run too hot (they under-resolve convective cloud/rain cooling).
- **Clean / sunny warm days** (Jul 22): the **high-res HRRR/GFS warmth verifies**; NBM/NWS
  come in too cool.

The current model uses NBM as a fixed baseline + inter-model spread features but does **not**
switch its trust by regime. A concrete next improvement: a **regime feature** (storm/PoP,
cloud cover, dewpoint depression) interacted with the model choice — or a **regime-conditional
blend** that up-weights NBM on convective days and HRRR/GFS on clear days. This log is the
ground truth to fit and validate it against.

Second recurring lesson: **the night-before model read has beaten my intraday caution three
times running** — cool stalled mornings kept triggering over-cautious reversals/trims, and the
temperature broke out to the warm side every time. Weight the model's issued forecast; don't
let the sleepy morning re-litigate it.

## Appending a new day
Use the helper so the schema stays consistent:
```bash
python -m central_park_tmax.track_record.log_call --help
```
or append a JSON line by hand matching the format above. Once the actual high is confirmed,
fill `actual_high_f`, `actual_high_source`, and `model_error_f`, and set each call's `result`.
