# Which source actually tells you the settlement, and when

Measured over the 45 consecutive logged KNYC days, 2026-08-01 → 09-14
(`track_record/call_log.jsonl`). **Every number below is produced by
`scripts/source_reliability.py`** — re-derived from the METAR archive on each run, never
incremented by hand. Re-run it after adding a day and paste the output; do not edit the
figures in place.

This document exists because on 09-11 I claimed the preliminary CLI had beaten the
six-hour group and that "the ordering is reversed." **Tested across all 45 days, that is
wrong.** The groups are settlement-grade and the preliminary is not.

## The scoreboard

| source | available | matches settlement |
|---|---|---|
| morning group (8 AM–2 PM) | 1:51 PM | 19/45 — **42 %** |
| preliminary CLI | ~4:31–5:05 PM | 14/22 — **64 %** |
| afternoon group (2 PM–8 PM) | 7:51 PM | 37/45 — **82 %** |
| **max of ALL same-day groups** | **7:51 PM** | **44/45 — 98 %** |

**That last row says "all same-day groups" for a reason, and the wording is a correction.**
It originally read "max of both groups" and was computed from the morning and afternoon
groups only. 2026-09-14 broke it: an overnight-max day settling at 75, where morning
(73.04) and afternoon (73.94) both round to 74, while the **2 AM–8 AM group reads 75.02**
and was never consulted. Across the 45 days, daytime-only would miss **two** — 08-27 and
09-14 — where all-same-day-groups misses one. The 98 % was under-specified, not wrong; two
of three available groups were going in, and no earlier day in the run stressed it.

Read the timing column before the accuracy column; these are not competing at the same
hour.

* **At 4:40 PM the preliminary is the best thing available** — 64 % against the morning
  group's 42 %. That much of the 09-11 observation survives.
* **Waiting until 7:51 PM beats it decisively.** Max of all same-day groups is 98 %. The claim that
  the preliminary supersedes the group was generalised from a single favourable day and
  does not hold.
* The one failure of max-of-all-same-day-groups is **2026-08-27**, the sensor-contamination day
  where a 9-minute spike during heavy rain entered the group and the CLI's QC rejected it
  (group 81, settled 77). That remains the only day in 45 where a group was wrong and the
  CLI right — so it is one exception, not a pattern, but it is the reason the 98 % is not
  100 %.

## The preliminary's error is a two-point distribution

This is the useful finding, and it was sitting in the data the whole time:

| settled − preliminary | days | share |
|---|---|---|
| **+0 °F** | 14 | **64 %** |
| **+1 °F** | 8 | **36 %** |
| anything else | **0** | **0 %** |

Never negative. Never +2. The eight misses are 08-03, 08-17, 08-25, 08-30, 09-01, 09-03,
09-06 and 09-13 — **every one low by exactly one degree.**

The split has read 63/37, 65/35, 62/38 and **64/36** on four successive days.
Same finding, moving numbers; quote it from the script, never from memory. Zero mass
outside the two points is the part that has held across all four.

So the preliminary does not give a point estimate with unknown error; it gives a **tight
two-outcome distribution over adjacent integers**, known at ~4:40 PM:

```
P(settle = preliminary)     ≈ 0.64
P(settle = preliminary + 1) ≈ 0.36
P(anything else)            ≈ 0
```

**This is worth more than the rules built on top of it.** `SEASONAL_TRANSITION.md` documents
two rules (trace shape, 72 %; the mechanism, 80 %) that try to predict *which* of these two
outcomes occurs, and an agreement band at 84 % on 19 days. (Neither rule reasons about
anything but the afternoon, so on an overnight-max day like 09-14 both are simply mute.)
All three are attempts to
collapse a distribution that is already sharp into a point call — and all three are worse
than 100 %, so collapsing it loses information rather than adding any. For a market quoted
in whole-degree buckets the split has an obvious reading — when both integers sit inside one
bucket the bucket is ~certain, and when they straddle a boundary the split *is* the price —
but see the next section before believing that is worth anything. It mostly is not.

## "Directly usable" needs heavy qualification

The claim above — that when both integers fall in one bucket the bucket is near-certain —
is true and also much less useful than it sounds. Checked against the real KXHIGHNY bucket
layout (`<=81`, `82-83`, `84-85`, `86-87`, `88-89`, `>=90`):

| | days | result |
|---|---|---|
| both integers in one bucket | 18/22 (82 %) | bucket correct **18/18** |
| …of which the wide open-ended `<=81` | **14** | certainty is nearly free |
| …genuine 2-wide bucket | **4** | 4/4 |
| integers straddle a boundary | 4/22 (18 %) | 64 % side won 2 of 4 |

**Fourteen of the eighteen are the open-ended `<=81` bucket.** On those days the preliminary
was 80 or below, so the bucket was near-certain from the banked max alone — no distribution
needed, and a market with the max already banked under 81 will be quoting that bucket near
99 ¢. That is `EDGE_DECAY.md` territory, and the same wall `PRELIM_FALLING` hit when all
nine of its fills came in at exactly $1.00.

Strip those out and the split makes a *genuine* narrow bucket near-certain on **4 days in
22**, all four correct. Four days is not a strategy. On the 4 straddling days the majority
side won twice, which is consistent with 64/36 and also consistent with almost anything at
n = 4.

So the honest version: the two-point distribution is a real and clean property of the
preliminary, and it is a better *description* of what is knowable at 4:40 PM than any of
the rules. Whether it is *tradeable* is unresolved and the base rates argue against it —
the cases where it delivers certainty are mostly cases that were already certain.

## The minimum is the mirror image, and far worse

Every cutoff finding in this project has been about the maximum. The 4 PM validity cutoff
truncates the **minimum** window identically, so the same mechanism should apply with the
sign flipped. Measured on the seven days where both products are still in the NWS archive
(it retains about a week, so this is all that can be checked):

| | error (final − preliminary) | bound |
|---|---|---|
| **maximum** | +0 on 6 days, +1 on 1 | never negative, never worse than **+1 °F** |
| **minimum** | 0 on 5 days, −3 on 1, −4 on 1 | never positive, but as far as **−4 °F** |

Both are one-sided in the direction the cutoff predicts — the preliminary can only be
*beaten* by what happens after 4 PM, so its max can only be too low and its min only too
high. **But the magnitudes are not comparable.** A late max can exceed the 4 PM value by a
fraction of a degree; a clear evening can drop several degrees below the morning minimum.
Both miss days did exactly that:

```
09-11   min 70 at 10:27 AM  →  67 at 11:59 PM   (−3)
09-14   min 67 at  7:36 AM  →  63 at 11:20 PM   (−4)
```

On both, the true minimum arrived within an hour of midnight. So the preliminary minimum is
**materially less trustworthy than the preliminary maximum**, and the two-point
distribution above does *not* transfer to it — a min needs a wider, one-sided spread of at
least four degrees.

This should get worse, not better, through autumn: the failure mode is hard radiational
cooling after dark, which is exactly what shorter days and drier air produce. Relevant if a
low-temperature market is ever priced from a preliminary CLI.

**n = 7.** The direction is unambiguous and the magnitudes are large enough to matter, but
seven days cannot pin the spread. Going forward, `prelim_low_f` should be recorded
alongside `prelim_high_f` so this can be re-derived rather than re-discovered — the
evidence expires in about a week.

## Honest limits

* **n = 22 for the preliminary**, not 45. Twenty-three of the logged days never recorded a
  preliminary-versus-final comparison, and the NWS CLI archive retains only about a week,
  so that evidence is permanently gone. The split rests on twenty-two days.
* A two-point distribution with zero mass elsewhere on n = 22 is exactly the kind of clean
  result that gets ragged with more data. The direction (never high) is better supported
  than the magnitudes.
* One station, one warm season. Nothing checked at KPHX or KLAS.
* The 98 % for max-of-all-same-day-groups is what makes the 204/204 settlement reconstruction
  credible, but it is measured on the same kind of days that reconstruction used. 08-27
  shows the failure mode is sensor contamination, which autumn frontal precipitation should
  make *more* common, not less.
* **Spanning evening groups stay excluded, and 09-14 confirms that is right.** The
  8 PM 09-13 – 2 AM 09-14 group reads 75.92 °F, which rounds to 76 and exceeds the
  settlement of 75 — because that 75.92 is Sep 13's evening warmth (18:51 read 75.92),
  not Sep 14's 12:52 AM peak. The window straddles both days and belongs to neither. A
  naive "just include the evening group" fix would have returned 76 and been wrong.
* Evening groups spanning two local days are excluded throughout, per
  `six_hour_group_covers_local_day()`.
