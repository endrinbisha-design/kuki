# Carrying the August findings into autumn

Thirty consecutive days of KNYC logging (2026-08-01 → 08-30, `track_record/call_log.jsonl`)
produced a set of findings. This document asks which of them survive the change of season,
which decay, and what breaks outright on a fixed calendar date.

The short version: the findings about **how NWS publishes** carry over unchanged; the
findings about **when the atmosphere peaks** do not; and one piece of code has a hard
deadline of **2026-11-01**.

## 1. What breaks: DST ends Sunday 2026-11-01

Every standalone script written during the August run hardcoded a `-4` UTC offset. That is
correct only under EDT. After 2026-11-01 the same code silently shifts every local
timestamp by an hour.

This is not cosmetic. Six-hour maximum groups are transmitted at fixed **UTC** synoptic
hours, so their **local** windows move:

| | under EDT (through Oct 31) | under EST (from Nov 1) |
|---|---|---|
| overnight group | 02:00–08:00 | 01:00–07:00 |
| morning group | **08:00–14:00** | **07:00–13:00** |
| afternoon group | **14:00–20:00** | **13:00–19:00** |
| evening group (spans 2 local days, excluded) | 20:00–02:00 | 19:00–01:00 |
| the "13:51 report" | 1:51 PM | **12:51 PM** |

Two consequences:

* **Day attribution.** `six_hour_group_covers_local_day()` takes the offset as an argument
  and is correct if given the right one. Passing a hardcoded `-4` after Nov 1 reintroduces
  exactly the bug class that held settlement reconstruction at 58/68 until it was fixed to
  204/204 in July. It would fail silently — no exception, just wrong days.
* **Vocabulary.** Every phrase used throughout the August log — "the 1:51 group", "the
  8am–2pm window", "peak after 2 PM" — is DST-specific and stops meaning what it says.
  When reading those entries after November, translate.

**Status:** `scripts/nyc_live_update.py` is fixed — it now resolves the offset per
timestamp via `time_utils.to_local()` and prints the correct zone abbreviation. The library
path (`pipelines/predict.py`) was already DST-aware. Still hardcoded and needing the same
treatment before they are next run across the boundary:
`scripts/trajectory_tmax_strategy.py`, `scripts/barbell_1351_backtest.py`,
`scripts/august_month_backtest.py` (August-only by construction, documented in-file).

The recurring hourly cron is specified in UTC and stays correct; only its human-readable
labels shift.

## 2. What carries over: the instrument findings

These are properties of the observing and publishing system, not the weather.

* **The 4 PM preliminary-CLI validity cutoff.** Fixed by the product, not the season.
* **Product-page propagation lag (~7–10 min).** Measured Aug 20 (7 min) and Aug 21
  (8 min). Fetch after 5:00 PM local, and never read a miss as "not issued".
* **Preliminary CLI can be wrong on value, not only on time.** Aug 17, 25, 30.
* **Six-hour groups can be contaminated.** Aug 27: a 9-minute sensor spike during heavy
  rain that the group ingested and the CLI's QC rejected. First and only case where a
  group was wrong and the CLI right. Autumn brings more frontal precipitation, so if
  anything this risk rises.
* **The 1:09–1:52 PM timestamp anomaly**, at its corrected rate of **6/15 testable days
  (40 %)**, one-sided — when the quoted time errs it errs early, never late. Note the band
  is stated in EDT clock time; whether it tracks the clock or the solar day is untested and
  November is the experiment that would tell us.

## 3. What decays: the weather findings

Measured on KNYC instantaneous observations, 2024 and 2025:

| | median peak | peak ≥ 2 PM | peak ≥ 4 PM |
|---|---|---|---|
| **Aug 2026** (this log) | ~2:45 PM | 47 % | **17 %** |
| Sep 2024 / 2025 | 2:50 PM | 50 % | 3 % / 10 % |
| Oct 2024 / 2025 | 2:50 PM | 55 % / 61 % | 0 % / 13 % |
| Nov 2024 / 2025 | **1:50 PM** | 38 % / 31 % | 7 % / 10 % |

September and October behave like August. **November is the break**: the median peak moves
an hour earlier and afternoon peaks drop ~20 points.

The practical effect is favourable. The 4 PM blind spot that produced the three
preliminary-CLI value errors (Aug 17, 25, 30) becomes rarer as peaks move earlier, so the
preliminary should get *more* reliable. The falling-trace rule should hold and cover a
larger share of days — but note it is **not one rule, it is two, and only one of them
works.** A scripted re-derivation on 2026-09-05 (see that day's log entry) put the record
at 14 correct / 3 wrong across the 17 days where the log actually records a
preliminary-versus-final comparison, replacing a hand-maintained "13 for 13" that had never
computed its own denominator:

| | n | record |
|---|---|---|
| falling → preliminary held | 8 | **8/8** |
| non-falling → preliminary reads low | 9 | 6/9 (67 %) |

The reliable half is the half that says *nothing is wrong*. The predictive half is the weak
one. Twenty of the 36 logged days can never be adjudicated at all: the early entries cite
only the preliminary, and the NWS CLI archive reaches back only about a week.

**Updated 2026-09-07.** Two advance predictions have now been recorded before any CLI
product existed: 09-06 correct, 09-07 wrong. The weak half is **7/11 (64 %)**, the falling
half still 8/8, overall **15/19**. From here the rule should only be scored on calls made in
advance.

**A rival rule was tested and tied.** The mechanism below suggests a more direct test: do
the 2 PM and 3 PM snapshots exceed the morning group? If not, nothing is hidden and the
preliminary holds. Scripted over the same 19 evidence days:

| rule | score (22 evidence days, through 09-10) |
|---|---|
| mechanism (afternoon snapshots vs morning group) | 17/22 (77 %) |
| trace shape (falling into the cutoff) | 16/22 (73 %) |
| both rules agree | **14/17 (82 %)**, abstaining on 5 |

09-08 was the first call under this criterion and was correct; **09-10 was the second and
was wrong**, taking the band from 88 % to 82 %. One miss moving the figure six points is
the measure of how little seventeen days supports, and is a caution against the weight put
on the 88 % when it was first computed.

**The mechanism below does not survive 09-10.** It assumes the preliminary cannot see the
afternoon maximum because the 2 PM–8 PM group has not transmitted at issuance. On 09-10 the
afternoon group *was* higher (84.02 vs 82.94), the premise held, and the preliminary
reported the correct 84 regardless — because the CLI reads the continuous trace directly
and does not wait for the group. The earlier story (maxima after the 4 PM cutoff) fails on
09-06, where a 3:09 PM peak was missed. **Two mid-afternoon peaks, opposite outcomes: there
is currently no mechanism that explains both days**, and the rules below should be read as
empirical regularities of unknown cause, not as consequences of a understood process.

**And the mechanism is not the 4 PM cutoff.** Every earlier preliminary-low day was
explained by the peak landing after the validity cutoff. On 2026-09-06 the peak was at
**3:09 PM — inside the window — and the preliminary missed it anyway**, quoting 75 at
2:53 PM against a final of 76. The operative constraint is that the preliminary is issued
*before the 2 PM–8 PM six-hour group transmits*: that group carried 75.92 °F and went out at
23:51 Z, hours after the 5:05 PM preliminary. Anything the continuous trace records after
about 2 PM can be missed whether or not it falls before 4 PM, because the product that would
reveal it does not yet exist.

This matters for the autumn projection in §3 below. The favourable effect predicted there —
earlier peaks clearing the 4 PM blind spot — is **weaker than stated**, because the blind
spot is not anchored at 4 PM. It is anchored at the *2 PM group boundary*, which under EST
moves to **1 PM**, i.e. earlier, partially offsetting the earlier peaks.

The **75 % afternoon-window dominance** measured in August is the finding most exposed to
the season, and it is doubly exposed: peaks move earlier *and* the window boundary itself
moves from 2 PM to 1 PM. Do not carry the number forward; re-measure.

## 4. Recalibrate: the snapshot gap

`(6h group max) − (best :51 snapshot inside the same window)`, KNYC:

| | Aug | Sep | Oct | Nov |
|---|---|---|---|---|
| median, 2024 | +0.90 | +0.90 | +0.90 | +0.90 |
| median, 2025 | +1.08 | +0.90 | +0.90 | **+0.00** |
| zero-gap share, 2024 | 34 % | 38 % | 37 % | 47 % |
| zero-gap share, 2025 | 30 % | 36 % | 44 % | **54 %** |

The **zero-gap share rises monotonically in both years** — that trend is solid. Shorter
days and sharper radiational cooling produce a narrower, better-sampled peak, so the
hourly feed misses less.

The **median collapse to 0.00 appears in 2025 only**, so treat the trend as established and
the magnitude as not. The convolution currently in `models/post_peak.py` is fitted on an
August window and will over-correct by November. It should be re-measured monthly rather
than inherited.

Gap values are quantised: observations are reported in 0.1 °C, so gaps land on multiples of
0.18 °F, and the common values (+0.90 = 0.5 °C, +1.98 = 1.1 °C) are lattice points, not
coincidences.

## 5. Honest limits

* Two autumn seasons (2024, 2025). The November divergence between them is exactly the
  kind of thing two years cannot settle.
* One station. Nothing here has been checked at KPHX or KLAS, whose seasonal cycles differ
  more sharply.
* The August sample is 30 days of one warm, convective month, and the second half of it was
  already cooling — the peak-timing and window statistics from it are a snapshot of a
  regime, not a climatology.
* Peak times are computed from instantaneous observations, which is the same feed the
  snapshot gap says under-reads. The true peak time can sit between obs; these are the
  observed peak times, not the continuous-trace peak times.
