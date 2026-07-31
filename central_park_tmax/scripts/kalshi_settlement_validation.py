#!/usr/bin/env python3
"""Validate our settlement reconstruction against REAL Kalshi settlements.

Kalshi's settled markets are the only public record of *the number we actually get paid
on*. Our models are trained and validated against GHCN / METAR-derived maxima, which is a
different pipeline than the NWS CLI that settles the contract. Nothing so far has checked
that those two agree — and 2026-07-29 (our 79 vs the market's, and the CLI's, 80) showed
the disagreement is not hypothetical.

Method, per city-day in the settled Kalshi history:

  * Kalshi truth: the ``between`` market that resolved YES gives the settled value to
    within a 2-degree bucket [floor, cap]; the ``less``/``greater`` markets bound the
    tails. This is 2-degree resolution — Kalshi cannot pin the exact integer — but it is
    enough to catch a reconstruction that lands outside the paying bucket.
  * Our reconstruction: max over the local day of (hourly/SPECI snapshots, 6-hour maximum
    groups) from IEM ASOS, rounded half-up — i.e. exactly what data/fast_metar.py +
    models/reporting_convention.py would produce.

Two numbers come out:

  1. **Agreement rate** — how often our reconstructed integer falls inside the bucket that
     actually paid. Anything below ~100% is money.
  2. **Snapshot-only agreement** — the same test using ONLY hourly snapshots, quantifying
     what the 6-hour groups buy us (see LESSONS.md #9 / snapshot_gap_study.py).

Output: backtest_datasets/kalshi_settlement_validation.json (+ printed summary).
"""
from __future__ import annotations

import datetime as dt
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
BASE = "https://api.elections.kalshi.com/trade-api/v2"

# Kalshi series -> (IEM station, local UTC offset during the warm season)
CITIES = {"KXHIGHNY": ("NYC", -4), "KXHIGHTPHX": ("PHX", -7), "KXHIGHTLV": ("LAS", -7)}

_SIX_HOUR_MAX = re.compile(r"\b1([01])(\d{3})\b")
_TICKER_DATE = re.compile(r"-(\d{2}[A-Z]{3}\d{2})-")


def _get(url: str) -> dict:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return {}


def settled_by_day(series: str) -> dict[dt.date, dict]:
    """day -> {'lo','hi'} inclusive integer bounds implied by the settled markets."""
    rows, cursor, pages = [], None, 0
    while pages < 40:
        url = f"{BASE}/markets?series_ticker={series}&status=settled&limit=1000"
        if cursor:
            url += f"&cursor={cursor}"
        d = _get(url)
        ms = d.get("markets", [])
        rows += ms
        cursor = d.get("cursor")
        pages += 1
        if not ms or not cursor:
            break
        time.sleep(0.2)

    out: dict[dt.date, dict] = {}
    for m in rows:
        mm = _TICKER_DATE.search(m["ticker"])
        if not mm:
            continue
        day = dt.datetime.strptime(mm.group(1), "%y%b%d").date()
        res = (m.get("result") or "").lower()
        if res != "yes":
            continue
        st, lo, hi = m.get("strike_type"), m.get("floor_strike"), m.get("cap_strike")
        if st == "between" and lo is not None and hi is not None:
            out[day] = {"lo": int(lo), "hi": int(hi), "kind": "between"}
        elif st == "less" and hi is not None:
            # "N or below" -> cap_strike is N+1 in this series; bound conservatively.
            out.setdefault(day, {"lo": -99, "hi": int(hi), "kind": "less"})
        elif st == "greater" and lo is not None:
            out.setdefault(day, {"lo": int(lo) + 1, "hi": 999, "kind": "greater"})
    return out


def six_hour_max_f(metar: str) -> float | None:
    if not isinstance(metar, str):
        return None
    parts = metar.split(" RMK ", 1)
    if len(parts) < 2:
        return None
    m = _SIX_HOUR_MAX.search(parts[1])
    if not m:
        return None
    c = int(m.group(2)) / 10.0
    if m.group(1) == "1":
        c = -c
    return c * 9 / 5 + 32


def observed(station: str, offset: int, start: dt.date, end: dt.date) -> pd.DataFrame:
    url = (f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={station}"
           f"&data=tmpf&data=metar&tz=UTC&format=onlycomma&latlon=no&missing=M&trace=T"
           f"&report_type=3&report_type=4"
           f"&year1={start.year}&month1={start.month}&day1={start.day}"
           f"&year2={end.year}&month2={end.month}&day2={end.day}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                raw = pd.read_csv(io.StringIO(r.read().decode()), low_memory=False)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  retry {station}: {str(exc)[:60]}", flush=True)
            time.sleep(3 * (attempt + 1))
    else:
        return pd.DataFrame()

    raw["valid"] = pd.to_datetime(raw["valid"], errors="coerce", utc=True)
    raw["tmpf"] = pd.to_numeric(raw["tmpf"], errors="coerce")
    raw = raw.dropna(subset=["valid"])
    raw["six"] = raw["metar"].map(six_hour_max_f)
    raw["day"] = (raw["valid"] + pd.Timedelta(hours=offset)).dt.date

    # A 6-hour group covers the period ENDING at the synoptic hour, which may belong to
    # the previous local day even though the report timestamp lands on this one. Attribute
    # each group to the local day its PERIOD falls in, not the day it was transmitted.
    # (See data/fast_metar.six_hour_group_covers_local_day — same rule, same reason.)
    end = raw["valid"].dt.ceil("h")
    period_start_local = end - pd.Timedelta(hours=6) + pd.Timedelta(hours=offset)
    period_end_local = end + pd.Timedelta(hours=offset)
    valid_group = (raw["six"].notna() & (end.dt.hour % 6 == 0)
                   & (period_start_local.dt.date == period_end_local.dt.date))
    grp = raw[valid_group].copy()
    grp["gday"] = period_end_local[valid_group].dt.date

    snap = raw.groupby("day")["tmpf"].max()
    six = grp.groupby("gday")["six"].max()
    return pd.DataFrame({"snapshot_max_f": snap, "six_max_f": six})


def half_up(x: float) -> int:
    return int(np.floor(x + 0.5))


def main() -> int:
    results = {}
    for series, (station, off) in CITIES.items():
        truth = settled_by_day(series)
        if not truth:
            print(f"{series}: no settled markets")
            continue
        days = sorted(truth)
        obs = observed(station, off, days[0] - dt.timedelta(days=1),
                       days[-1] + dt.timedelta(days=2))
        if obs.empty:
            print(f"{series}: no observations")
            continue

        rec = {"n": 0, "combined_in_bucket": 0, "snapshot_in_bucket": 0, "misses": []}
        for day in days:
            if day not in obs.index:
                continue
            row = obs.loc[day]
            snap, six = row["snapshot_max_f"], row["six_max_f"]
            if not np.isfinite(snap):
                continue
            combined = max([v for v in (snap, six) if np.isfinite(v)])
            b = truth[day]
            rec["n"] += 1
            ci, si = half_up(combined), half_up(snap)
            ok_c = b["lo"] <= ci <= b["hi"]
            ok_s = b["lo"] <= si <= b["hi"]
            rec["combined_in_bucket"] += int(ok_c)
            rec["snapshot_in_bucket"] += int(ok_s)
            if not ok_c:
                rec["misses"].append({
                    "date": str(day), "kalshi_bucket": f"{b['lo']}-{b['hi']}",
                    "our_integer": ci, "combined_f": round(float(combined), 2),
                    "snapshot_f": round(float(snap), 2),
                    "six_f": round(float(six), 2) if np.isfinite(six) else None})
        n = rec["n"] or 1
        rec["combined_agreement"] = round(rec["combined_in_bucket"] / n, 4)
        rec["snapshot_agreement"] = round(rec["snapshot_in_bucket"] / n, 4)
        results[series] = rec
        print(f"\n=== {series} ({station}) — {rec['n']} settled days ===")
        print(f"  6h-group + snapshots : {rec['combined_in_bucket']}/{rec['n']} "
              f"= {rec['combined_agreement']:.1%} inside the paying bucket")
        print(f"  snapshots only       : {rec['snapshot_in_bucket']}/{rec['n']} "
              f"= {rec['snapshot_agreement']:.1%}")
        for m in rec["misses"][:12]:
            print(f"    MISS {m['date']}: paid {m['kalshi_bucket']}, we said {m['our_integer']} "
                  f"(snap {m['snapshot_f']}, 6h {m['six_f']})")

    (OUT / "kalshi_settlement_validation.json").write_text(json.dumps(results, indent=1))
    print(f"\nwrote {OUT/'kalshi_settlement_validation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
