# Which source actually tells you the settlement, and when

Measured over the 43 consecutive logged KNYC days, 2026-08-01 → 09-12
(`track_record/call_log.jsonl`). **Every number below is produced by
`scripts/source_reliability.py`** — re-derived from the METAR archive on each run, never
incremented by hand. Re-run it after adding a day and paste the output; do not edit the
figures in place.

This document exists because on 09-11 I claimed the preliminary CLI had beaten the
six-hour group and that "the ordering is reversed." **Tested across all 42 days, that is
wrong.** The groups are settlement-grade and the preliminary is not.

## The scoreboard

| source | available | matches settlement |
|---|---|---|
| morning group (8 AM–2 PM) | 1:51 PM | 19/43 — **44 %** |
| preliminary CLI | ~4:31–5:05 PM | 13/20 — **65 %** |
| afternoon group (2 PM–8 PM) | 7:51 PM | 36/43 — **84 %** |
| **max of both groups** | **7:51 PM** | **42/43 — 98 %** |

Read the timing column before the accuracy column; these are not competing at the same
hour.

* **At 4:40 PM the preliminary is the best thing available** — 65 % against the morning
  group's 44 %. That much of the 09-11 observation survives.
* **Waiting until 7:51 PM beats it decisively.** Max-of-both-groups is 98 %. The claim that
  the preliminary supersedes the group was generalised from a single favourable day and
  does not hold.
* The one failure of max-of-both-groups is **2026-08-27**, the sensor-contamination day
  where a 9-minute spike during heavy rain entered the group and the CLI's QC rejected it
  (group 81, settled 77). That remains the only day in 42 where a group was wrong and the
  CLI right — so it is one exception, not a pattern, but it is the reason the 98 % is not
  100 %.

## The preliminary's error is a two-point distribution

This is the useful finding, and it was sitting in the data the whole time:

| settled − preliminary | days | share |
|---|---|---|
| **+0 °F** | 13 | **65 %** |
| **+1 °F** | 7 | **35 %** |
| anything else | **0** | **0 %** |

Never negative. Never +2. The seven misses are 08-03, 08-17, 08-25, 08-30, 09-01, 09-03
and 09-06 — **every one low by exactly one degree.**

Note the split is **65/35 as of 09-12**, not the 63/37 first computed on 09-11. It will
keep moving; quote it from the script, not from memory.

So the preliminary does not give a point estimate with unknown error; it gives a **tight
two-outcome distribution over adjacent integers**, known at ~4:40 PM:

```
P(settle = preliminary)     ≈ 0.65
P(settle = preliminary + 1) ≈ 0.35
P(anything else)            ≈ 0
```

**This is worth more than the rules built on top of it.** `SEASONAL_TRANSITION.md` documents
two rules (trace shape, 71 %; the mechanism, 79 %) that try to predict *which* of these two
outcomes occurs, and an agreement band at 83 % on 18 days. All three are attempts to
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
| both integers in one bucket | 16/20 (80 %) | bucket correct **16/16** |
| …of which the wide open-ended `<=81` | **12** | certainty is nearly free |
| …genuine 2-wide bucket | **4** | 4/4 |
| integers straddle a boundary | 4/20 (20 %) | 65 % side won 2 of 4 |

**Twelve of the sixteen are the open-ended `<=81` bucket.** On those days the preliminary
was 80 or below, so the bucket was near-certain from the banked max alone — no distribution
needed, and a market with the max already banked under 81 will be quoting that bucket near
99 ¢. That is `EDGE_DECAY.md` territory, and the same wall `PRELIM_FALLING` hit when all
nine of its fills came in at exactly $1.00.

Strip those out and the split makes a *genuine* narrow bucket near-certain on **4 days in
20**, all four correct. Four days is not a strategy. On the 4 straddling days the 63 % side
won twice, which is consistent with 63/37 and also consistent with almost anything at
n = 4.

So the honest version: the two-point distribution is a real and clean property of the
preliminary, and it is a better *description* of what is knowable at 4:40 PM than any of
the rules. Whether it is *tradeable* is unresolved and the base rates argue against it —
the cases where it delivers certainty are mostly cases that were already certain.

## Honest limits

* **n = 20 for the preliminary**, not 43. Twenty-three of the logged days never recorded a
  preliminary-versus-final comparison, and the NWS CLI archive retains only about a week,
  so that evidence is permanently gone. The split rests on twenty days.
* A two-point distribution with zero mass elsewhere on n = 20 is exactly the kind of clean
  result that gets ragged with more data. The direction (never high) is better supported
  than the magnitudes.
* One station, one warm season. Nothing checked at KPHX or KLAS.
* The 98 % for max-of-both-groups is what makes the 204/204 settlement reconstruction
  credible, but it is measured on the same kind of days that reconstruction used. 08-27
  shows the failure mode is sensor contamination, which autumn frontal precipitation should
  make *more* common, not less.
* Evening groups spanning two local days are excluded throughout, per
  `six_hour_group_covers_local_day()`.
