#!/usr/bin/env python3
"""How much does the hourly-snapshot max UNDER-READ the settlement max — and when?

Motivation (2026-07-29 NYC, resolved 2026-07-31): our observed max read 78.98 F while the
market held 80-81 at 99c on 73k volume and the CLI settled **80**. The market was right.
The cause is structural, not a bug:

  * The METAR **6-hour maximum group** carries the continuous trace that the CLI settles
    on, but it is transmitted only in the 05:51/11:51/17:51/23:51Z reports. The group
    covering the AFTERNOON (18Z-00Z) therefore does not exist until 23:51Z — 7:51 PM EDT,
    hours after the 15-17h local trading window closes (EDGE_DECAY.md).
  * Inside that window the only afternoon data we have is the :51 hourly snapshots, which
    miss any spike BETWEEN observations. On Jul 29 every snapshot after 14:51 read 78 F
    while the continuous trace hit 80.06 F at ~4:23 PM.

So during exactly the hours we trade, our observed max is a lower bound that is biased
low. This script measures that bias so the post-peak tool can price it instead of
assuming the observed max is exact.

Method: for each warm-season day, take the day's four 6-hour maximum groups (the
continuous truth) and the max of the hourly/SPECI snapshots, and record

    gap = continuous_max - snapshot_max                      (whole day)
    gap_afternoon = max(afternoon 6h group) - (snapshot max through the same period)

The afternoon figure is the one that matters: it is the error we carry while trading.

NOTE this is the same defect class as the remaining-rise climatology
(scripts/build_remaining_rise.py), which derives ``daily_max`` from hourly snapshots too
and therefore CANNOT see this gap. That is why it needs measuring separately.

Output: backtest_datasets/snapshot_gap.json (+ printed summary).
"""
from __future__ import annotations

import io
import json
import re
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "backtest_datasets"
UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}

# station -> local UTC offset used to place the "afternoon" 6-hour period.
STATIONS = {"NYC": -4, "PHX": -7, "LAS": -7}
YEARS = range(2021, 2026)

_SIX_HOUR_MAX = re.compile(r"\b1([01])(\d{3})\b")


def fetch(station: str, year: int) -> pd.DataFrame:
    url = (f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={station}"
           f"&data=tmpf&data=metar&tz=UTC&format=onlycomma&latlon=no&missing=M&trace=T"
           f"&report_type=3&report_type=4"
           f"&year1={year}&month1=5&day1=1&year2={year}&month2=10&day2=1")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return pd.read_csv(io.StringIO(r.read().decode()), low_memory=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  retry {station} {year}: {str(exc)[:70]}", flush=True)
            time.sleep(3 * (attempt + 1))
    return pd.DataFrame()


def six_hour_max_f(metar: str) -> float | None:
    """Decode the 1sTTT six-hour maximum group to F (None when absent)."""
    if not isinstance(metar, str):
        return None
    # Only look in the remarks section: 1nnnn also appears in altimeter-like contexts.
    rmk = metar.split(" RMK ", 1)
    if len(rmk) < 2:
        return None
    m = _SIX_HOUR_MAX.search(rmk[1])
    if not m:
        return None
    c = int(m.group(2)) / 10.0
    if m.group(1) == "1":
        c = -c
    return c * 9 / 5 + 32


def main() -> int:
    results: dict[str, dict] = {}
    for station, off in STATIONS.items():
        frames = []
        for y in YEARS:
            df = fetch(station, y)
            if not df.empty:
                frames.append(df)
            print(f"{station} {y}: {len(df)} obs", flush=True)
        if not frames:
            continue
        raw = pd.concat(frames, ignore_index=True)
        raw["valid"] = pd.to_datetime(raw["valid"], errors="coerce", utc=True)
        raw["tmpf"] = pd.to_numeric(raw["tmpf"], errors="coerce")
        raw = raw.dropna(subset=["valid"])
        raw["six"] = raw["metar"].map(six_hour_max_f)
        # Local day and local hour.
        local = raw["valid"] + pd.Timedelta(hours=off)
        raw["day"] = local.dt.date
        raw["lhour"] = local.dt.hour

        # The 6-hour group in a report at HH:51Z summarises the period ENDING at HH+1 Z.
        # The afternoon period (18Z-00Z) arrives in the 23:51Z report.
        utc_hour = raw["valid"].dt.hour
        afternoon_group = raw[(utc_hour == 23) & raw["six"].notna()]
        agg_day, agg_gap, whole_gap = [], [], []
        by_day_snapshot = raw.dropna(subset=["tmpf"]).groupby("day")["tmpf"].max()
        by_day_six = raw.dropna(subset=["six"]).groupby("day")["six"].max()

        for day, cont in by_day_six.items():
            snap = by_day_snapshot.get(day)
            if snap is None or not np.isfinite(snap):
                continue
            whole_gap.append(cont - snap)

        # Afternoon-specific, measured on EXACTLY the same window the group summarises
        # (18Z-00Z): did the snapshots taken inside that period miss the period's true
        # max? Comparing against a differently-bounded snapshot window produces spurious
        # negative "gaps", which is why the window is matched here rather than approximated
        # with local hours.
        in_period = raw[(utc_hour >= 18) & raw["tmpf"].notna()]
        snap_in_period = in_period.groupby("day")["tmpf"].max()
        for _, r in afternoon_group.iterrows():
            day = r["day"]
            snap = snap_in_period.get(day)
            if snap is None or not np.isfinite(snap):
                continue
            agg_day.append(str(day))
            agg_gap.append(float(r["six"]) - float(snap))

        w = np.array(whole_gap, dtype=float)
        a = np.array(agg_gap, dtype=float)
        w = w[np.isfinite(w)]
        a = a[np.isfinite(a)]
        # A gap can only be >= 0 in truth; small negatives are rounding of the 0.1C group.
        results[station] = {
            "n_days_whole": int(w.size),
            "whole_day_gap_mean_f": round(float(np.mean(w)), 3) if w.size else None,
            "whole_day_gap_p90_f": round(float(np.percentile(w, 90)), 3) if w.size else None,
            "n_days_afternoon": int(a.size),
            "afternoon_gap_mean_f": round(float(np.mean(a)), 3) if a.size else None,
            "afternoon_gap_p50_f": round(float(np.percentile(a, 50)), 3) if a.size else None,
            "afternoon_gap_p90_f": round(float(np.percentile(a, 90)), 3) if a.size else None,
            "afternoon_gap_p99_f": round(float(np.percentile(a, 99)), 3) if a.size else None,
            # The trading-relevant probabilities: how often the snapshot under-reads enough
            # to move the settled integer.
            "p_afternoon_gap_ge_0_5f": round(float((a >= 0.5).mean()), 4) if a.size else None,
            "p_afternoon_gap_ge_1_0f": round(float((a >= 1.0).mean()), 4) if a.size else None,
            # Full empirical distribution at 1% steps, so consumers can CONVOLVE the gap
            # into a settlement PMF instead of hand-picking bins. Percentiles are equally
            # weighted by construction. Small negatives are 0.1C-vs-0.1F rounding, not
            # signal; they are kept rather than clipped so the distribution stays honest.
            "afternoon_gap_percentiles_f": (
                [round(float(np.percentile(a, q)), 3) for q in range(0, 101)]
                if a.size else None),
        }
        r = results[station]
        print(f"\n=== {station} ===")
        print(f"  whole-day gap  : mean {r['whole_day_gap_mean_f']}F  "
              f"p90 {r['whole_day_gap_p90_f']}F  (n={r['n_days_whole']})")
        print(f"  AFTERNOON gap  : mean {r['afternoon_gap_mean_f']}F  "
              f"p50 {r['afternoon_gap_p50_f']}F  p90 {r['afternoon_gap_p90_f']}F  "
              f"p99 {r['afternoon_gap_p99_f']}F  (n={r['n_days_afternoon']})")
        print(f"  P(gap >= 0.5F) = {r['p_afternoon_gap_ge_0_5f']}   "
              f"P(gap >= 1.0F) = {r['p_afternoon_gap_ge_1_0f']}")

    (OUT / "snapshot_gap.json").write_text(json.dumps(results, indent=1))
    print(f"\nwrote {OUT/'snapshot_gap.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
