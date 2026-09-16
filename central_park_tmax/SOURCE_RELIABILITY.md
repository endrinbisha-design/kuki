# Which source actually tells you the settlement, and when

Measured over the 46 consecutive logged KNYC days, 2026-08-01 → 09-15
(`track_record/call_log.jsonl`). **Every number below is produced by
`scripts/source_reliability.py`** — re-derived from the METAR archive on each run, never
incremented by hand. Re-run it after adding a day and paste the output; do not edit the
figures in place.

This document exists because on 09-11 I claimed the preliminary CLI had beaten the
six-hour group and that "the ordering is reversed." **Tested across all 46 days, that is
wrong.** The groups are settlement-grade and the preliminary is not.

## The scoreboard

| source | available | matches settlement |
|---|---|---|
| morning group (8 AM–2 PM) | 1:51 PM | 19/46 — **41 %** |
| preliminary CLI | ~4:31–5:05 PM | 15/23 — **65 %** |
| afternoon group (2 PM–8 PM) | 7:51 PM | 38/46 — **83 %** |
| **max of ALL same-day groups** | **7:51 PM** | **45/46 — 98 %** |

**That last row says "all same-day groups" for a reason, and the wording is a correction.**
It originally read "max of both groups" and was computed from the morning and afternoon
groups only. 2026-09-14 broke it: an overnight-max day settling at 75, where morning
(73.04) and afternoon (73.94) both round to 74, while the **2 AM–8 AM group reads 75.02**
and was never consulted. Across the 46 days, daytime-only would miss **two** — 08-27 and
09-14 — where all-same-day-groups misses one. The 98 % was under-specified, not wrong; two
of three available groups were going in, and no earlier day in the run stressed it.

Read the timing column before the accuracy column; these are not competing at the same
hour.

* **At 4:40 PM the preliminary is the best thing available** — 65 % against the morning
  group's 41 %. That much of the 09-11 observation survives.
* **Waiting until 7:51 PM beats it decisively.** Max of all same-day groups is 98 %. The claim that
  the preliminary supersedes the group was generalised from a single favourable day and
  does not hold.
* The one failure of max-of-all-same-day-groups is **2026-08-27**, the sensor-contamination day
  where a 9-minute spike during heavy rain entered the group and the CLI's QC rejected it
  (group 81, settled 77). That remains the only day in 46 where a group was wrong and the
  CLI right — so it is one exception, not a pattern, but it is the reason the 98 % is not
  100 %.

## The preliminary's error is a two-point distribution

This is the useful finding, and it was sitting in the data the whole time:

| settled − preliminary | days | share |
|---|---|---|
| **+0 °F** | 15 | **65 %** |
| **+1 °F** | 8 | **35 %** |
| anything else | **0** | **0 %** |

Never negative. Never +2. The eight misses are 08-03, 08-17, 08-25, 08-30, 09-01, 09-03,
09-06 and 09-13 — **every one low by exactly one degree.**

The split has read 63/37, 65/35, 62/38, 64/36 and **65/35** on five successive days.
Same finding, moving numbers; quote it from the script, never from memory. Zero mass
outside the two points is the part that has held across all four.

So the preliminary does not give a point estimate with unknown error; it gives a **tight
two-outcome distribution over adjacent integers**, known at ~4:40 PM:

```
P(settle = preliminary)     ≈ 0.65
P(settle = preliminary + 1) ≈ 0.35
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

## "Directly usable": the count was wrong, the conclusion survives

**Corrected 2026-09-16, and the error was mine.** This section previously reported that
only 4 days in 22 gave a genuine narrow-bucket certainty, and concluded that the split is
worthless because "the cases where it delivers certainty are mostly cases that were already
certain." Both the number and the reason were wrong.

The cause: `scripts/source_reliability.py` hardcoded **August's** strike ladder (`<=81` …
`>=90`) and applied it to every day. **The KXHIGHNY ladder re-centres daily.** On a cool
September day the open-ended bucket is `<=69`, not `<=81`, so a preliminary of 72–79 sat in
a normal 2-wide bucket while the script filed it under the wide one. That misclassified
**11 of 23 days** and inflated the open-ended count from 7 to 16. The script also assumed
2-wide buckets always pair `[even, even+1]`; the real ladders include `83-84` and `78-79`,
so even the parity was wrong. The script now looks the ladder up per day.

Against real ladders:

| | days | result |
|---|---|---|
| both integers in one bucket | 15/23 (65 %) | bucket correct **15/15** |
| …of which the open-ended bucket | **5** | certainty is nearly free |
| …**genuine 2-wide bucket** | **10** | **10/10 correct** |
| integers straddle a boundary | 8/23 (35 %) | majority side won **7/8** |

So the split delivers a genuine narrow-bucket near-certainty on **10 days in 23 — not 4 —
and was right on all ten.** The straddle days went 7/8 to the majority side, not 2/4.

**And it is still not tradeable, for the other reason.** Pricing those ten buckets from the
17:00 candle on the day:

```
08-01  86-87  100c     08-21  79-80  100c     08-22  77-78   97c
08-23  80-81   96c     09-03  83-84   96c     09-04  84-85  100c
09-06  75-76   98c     09-11  79-80  100c     09-13  78-79   97c
09-15  72-73  100c
```

10/10 correct, mean ask **98 ¢**, four of them at exactly 100 ¢. Net **+1.1 % per bet**,
+$1.13 on ten $10 stakes, before any slippage or depth check. That is `EDGE_DECAY.md`
again — the same wall `PRELIM_FALLING` hit at exactly $1.00, just a whisker above zero
instead of on it.

The honest summary: the two-point distribution is real, sharper than previously credited,
and correctly identifies a near-certain bucket on 43 % of days. The market charges 98 ¢ for
that certainty. The finding is sound; the trade is not there.

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

## Quantisation beats modelling near a rounding boundary

The single most useful result of the run, from 2026-09-15. Three consecutive `:51`
snapshots read 71.06 °F and the day looked finished; the banked value sat **0.44 °F** below
the 71.5 rounding boundary. The gap cannot take an arbitrary value — observations are
reported in 0.1 °C, so it lands on multiples of 0.18 °F, and across 46 logged days the
afternoon-group gap distribution is:

```
0.00 ×6    0.90 ×15    1.08 ×10    1.98 ×12    2.16 ×1    3.96 ×1
```

**Nothing exists between 0.00 and 0.90.** So the outcome was strictly binary — gap 0 →
settle 71, gap ≥ 0.90 → settle 72 — with no third possibility, and 39 of 45 prior days sat
on the favourable side. Called **72 at 87 %**; the afternoon group arrived at 71.96, a gap
of exactly **+0.90**, the modal value.

Two other methods were tried first on that day and both failed:

| method | call | outcome |
|---|---|---|
| `models/post_peak` | 70–71 at 75 % raw, 55 % calibrated | wrong |
| base rate on "rising through 13:51" | 74+ at 24 % | wrong — vanished once conditioned on the flat 14:51 |
| **gap quantisation** | **72 at 87 %** | **right** |

The lesson is not that the model is bad but that **the two failures were attempts to fit
the atmosphere while the winner was a statement about the instrument.** Whenever the banked
max lands within 0.44 °F of a `.5` boundary, the meteorology is nearly irrelevant: the
question reduces to whether the gap is zero, which is a 13 % event. That is checkable in
one line and does not decay with the season.

The market held 72–73 at 80–85 ¢ (~82 %) throughout, against the 87 % above — fairly
priced, and no trade was warranted.

## Honest limits

* **n = 23 for the preliminary**, not 46. Twenty-three of the logged days never recorded a
  preliminary-versus-final comparison, and the NWS CLI archive retains only about a week,
  so that evidence is permanently gone. The split rests on twenty-three days.
* A two-point distribution with zero mass elsewhere on n = 23 is exactly the kind of clean
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
