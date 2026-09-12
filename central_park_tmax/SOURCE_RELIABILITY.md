# Which source actually tells you the settlement, and when

Measured over the 42 consecutive logged KNYC days, 2026-08-01 → 09-11
(`track_record/call_log.jsonl`). Every value re-derived from the METAR archive by script;
preliminary values come from the log entries that recorded them.

This document exists because on 09-11 I claimed the preliminary CLI had beaten the
six-hour group and that "the ordering is reversed." **Tested across all 42 days, that is
wrong.** The groups are settlement-grade and the preliminary is not.

## The scoreboard

| source | available | matches settlement |
|---|---|---|
| morning group (8 AM–2 PM) | 1:51 PM | 18/42 — **43 %** |
| preliminary CLI | ~4:31–5:05 PM | 12/19 — **63 %** |
| afternoon group (2 PM–8 PM) | 7:51 PM | 35/42 — **83 %** |
| **max of both groups** | **7:51 PM** | **41/42 — 98 %** |

Read the timing column before the accuracy column; these are not competing at the same
hour.

* **At 4:40 PM the preliminary is the best thing available** — 63 % against the morning
  group's 43 %. That much of the 09-11 observation survives.
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
| **+0 °F** | 12 | **63 %** |
| **+1 °F** | 7 | **37 %** |
| anything else | **0** | **0 %** |

Never negative. Never +2. The seven misses are 08-03, 08-17, 08-25, 08-30, 09-01, 09-03
and 09-06 — **every one low by exactly one degree.**

So the preliminary does not give a point estimate with unknown error; it gives a **tight
two-outcome distribution over adjacent integers**, known at ~4:40 PM:

```
P(settle = preliminary)     ≈ 0.63
P(settle = preliminary + 1) ≈ 0.37
P(anything else)            ≈ 0
```

**This is worth more than the rules built on top of it.** `SEASONAL_TRANSITION.md` documents
two rules (trace shape, 70 %; the mechanism, 78 %) that try to predict *which* of these two
outcomes occurs, and an agreement band at 82 % on 17 days. All three are attempts to
collapse a distribution that is already sharp into a point call — and all three are worse
than 100 %, so collapsing it loses information rather than adding any. For a market quoted
in whole-degree buckets, a 63/37 split across two adjacent integers is directly usable:
when both integers sit inside one bucket the bucket is ~certain, and when they straddle a
boundary the split *is* the price.

## "Directly usable" needs heavy qualification

The claim above — that when both integers fall in one bucket the bucket is near-certain —
is true and also much less useful than it sounds. Checked against the real KXHIGHNY bucket
layout (`<=81`, `82-83`, `84-85`, `86-87`, `88-89`, `>=90`):

| | days | result |
|---|---|---|
| both integers in one bucket | 15/19 (79 %) | bucket correct **15/15** |
| …of which the wide open-ended `<=81` | **11** | certainty is nearly free |
| …genuine 2-wide bucket | **4** | 4/4 |
| integers straddle a boundary | 4/19 (21 %) | 63 % side won 2 of 4 |

**Eleven of the fifteen are the open-ended `<=81` bucket.** On those days the preliminary
was 80 or below, so the bucket was near-certain from the banked max alone — no distribution
needed, and a market with the max already banked under 81 will be quoting that bucket near
99 ¢. That is `EDGE_DECAY.md` territory, and the same wall `PRELIM_FALLING` hit when all
nine of its fills came in at exactly $1.00.

Strip those out and the split makes a *genuine* narrow bucket near-certain on **4 days in
19**, all four correct. Four days is not a strategy. On the 4 straddling days the 63 % side
won twice, which is consistent with 63/37 and also consistent with almost anything at
n = 4.

So the honest version: the two-point distribution is a real and clean property of the
preliminary, and it is a better *description* of what is knowable at 4:40 PM than any of
the rules. Whether it is *tradeable* is unresolved and the base rates argue against it —
the cases where it delivers certainty are mostly cases that were already certain.

## Honest limits

* **n = 19 for the preliminary**, not 42. Twenty-three of the logged days never recorded a
  preliminary-versus-final comparison, and the NWS CLI archive retains only about a week,
  so that evidence is permanently gone. The 63/37 split rests on nineteen days.
* A two-point distribution with zero mass elsewhere on n = 19 is exactly the kind of clean
  result that gets ragged with more data. The direction (never high) is better supported
  than the magnitudes.
* One station, one warm season. Nothing checked at KPHX or KLAS.
* The 98 % for max-of-both-groups is what makes the 204/204 settlement reconstruction
  credible, but it is measured on the same kind of days that reconstruction used. 08-27
  shows the failure mode is sensor contamination, which autumn frontal precipitation should
  make *more* common, not less.
* Evening groups spanning two local days are excluded throughout, per
  `six_hour_group_covers_local_day()`.
