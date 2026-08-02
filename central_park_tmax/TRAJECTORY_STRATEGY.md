# Estimating the day's max from the :51 reports

`scripts/trajectory_tmax_strategy.py`. The question: how much of the day's maximum is
predictable from the hourly `:51` METAR trace, and at what time of day does that
information become worth more than an overnight forecast?

This is the largest honest test in the repo — **1,166 warm-season days (2019–2026)**,
fit on 2019–2023 and scored on **401 held-out days (2024–2026)** that no fit ever saw.
Compare with the Kalshi-era studies, which are stuck at 68 days because that is all the
settled-market history there is.

## Setup

**Truth** = the settlement-grade max: all instantaneous reports plus day-attributed 6-hour
maximum groups. This is the reconstruction validated at 204/204 against real Kalshi
settlements (`kalshi_settlement_validation.py`).

**Leakage rules**, identical to every other study here: at decision hour *h* only `:51`
observations at or before *h*, and 6-hour groups only from their **transmission** time.
The 8 AM–2 PM group exists only from 13:51.

**Estimators**

| name | what it is |
|---|---|
| `CLIMO` | running max + the training years' median remaining rise for that hour — what `models/post_peak.py` does today, i.e. the incumbent |
| `RIDGE` | linear model on [running max, current temp, 3-hour rise, day-of-year harmonics] |
| `ANALOG` | k-NN (k=25) on the z-scored trace shape + season; prediction = median of neighbours' actual maxima |
| `MOS` | the 00Z statistical forecast, knowable ~1 AM, using **no** intraday data — the control |
| `MOS+TRAJ` | ridge on the MOS forecast plus the trajectory features |

**Metrics.** `MAE` in °F. `P(|err|≤1)` — how often within a degree. `bucket-hit` — how
often the predicted and actual integers fall in the same Kalshi 2-degree bucket
(80–81, 82–83, …). Bucket-hit is the tradeable number; the others describe the physics.

## Results (test set, 2024–2026)

| estimator | 9:51 AM | 11:51 AM | 1:51 PM |
|---|---|---|---|
| CLIMO | 2.66 / 25 % | 1.59 / 41 % | 0.94 / **56 %** |
| RIDGE | 2.36 / 29 % | 1.56 / 41 % | **0.87 / 60 %** |
| ANALOG | 2.83 / 26 % | 2.05 / 31 % | 1.23 / 52 % |
| MOS | 2.02 / 27 % | 2.03 / 26 % | 2.03 / 26 % |
| MOS+TRAJ | **1.92 / 33 %** | **1.53 / 36 %** | 0.89 / 58 % |

*(MAE °F / bucket-hit. MOS is constant by construction — it is the same overnight number
all day.)*

## Significance — RIDGE vs the incumbent CLIMO

Paired bootstrap over test days, 4,000 resamples:

| hour | MAE gain | 95 % CI | P(no gain) | bucket gain | 95 % CI | P(no gain) |
|---|---|---|---|---|---|---|
| 11:51 | +0.026 °F | −0.044 … +0.099 | **0.23** | +0.5 pts | −3.3 … +4.3 | **0.41** |
| 13:51 | +0.066 °F | +0.022 … +0.112 | 0.002 | +3.8 pts | +0.3 … +7.4 | 0.023 |

**RIDGE only genuinely beats CLIMO at 13:51**, and the bucket gain there is marginal — the
interval nearly touches zero. At 11:51 the apparent improvement is noise.

## Findings

**1. The information timeline of a day.** Before ~10 AM the trace is nearly worthless: the
static overnight forecast (MAE 2.02) beats every trajectory method. Noon is the crossover —
by 11:51 the trace alone (1.56) beats MOS (2.03). By 13:51 the observation is everything
(0.87) and adding MOS no longer helps at all (0.89).

**2. The snapshot gap, independently reconfirmed on 394 days.** At 13:51 the 6-hour group
exceeds the hourly-snapshot max by a **median +0.96 °F on 76 % of days**. That is a clean
out-of-sample replication of the ~0.98 °F median measured by `snapshot_gap_study.py` on a
different window, and it is the single most reliable quantitative fact this project has
produced.

**3. ANALOG is not competitive as implemented** — worse than plain climatology at every
hour. Matching trace *shape* appears to discard the level information a running max keeps.
Recorded so it is not re-attempted on intuition; it is not proof that no analog method
could work.

## Honest limits

* **The MOS control is weak.** It is a *midnight* forecast. A real competitor would use the
  latest NWS gridpoint / NBM / HRRR guidance, which updates through the day. "Trajectory
  beats the forecast by noon" is really "trajectory beats a twelve-hour-old forecast by
  noon" — a materially softer claim, and the comparison a live trader cares about is
  untested here.
* **The two accuracy metrics disagree at 13:51.** CLIMO is more often within 1 °F (77 % vs
  70 %) yet lands in the right bucket less often (56 % vs 60 %). Bucket-hit is discrete and
  turns on which side of an even boundary a prediction falls, so a small systematic offset
  moves it a lot. RIDGE's bucket advantage may be partly a rounding artifact rather than
  better physics, which is a further reason to treat the +3.8 points cautiously.
* **No wet/dry split.** Wet days have measured MAE 2.53 °F vs 1.88 °F dry
  (`DAILY_STRATEGY.md`), and the barbell study found wet days carried the entire trading
  loss. The aggregate here hides that.
* **Days within a season are autocorrelated** — heat waves persist — so the simple day
  bootstrap above overstates effective sample size somewhat.
* **One station, three test seasons.** Nothing here has been checked at KPHX or KLAS.
* **Truth is our reconstruction**, not the CLI text itself, though the two agree at
  204/204 on bucket assignment.

## What this changes

`RIDGE` should replace the `CLIMO` logic inside the post-peak path **from 13:51 onward**,
where the gain is real. Before noon, prefer forecast guidance over the trace.

**What it does not change:** 60 % bucket-hit at 13:51 is close to the market favourite's own
~56.5 % hit rate in the 68-day price study. Those are different samples and not directly
comparable, but the direction is consistent with everything else measured this week — this
is better forecasting machinery, not a demonstrated trading edge. The test of whether the
extra bucket accuracy survives contact with the ask is a separate piece of work, not yet
done.
