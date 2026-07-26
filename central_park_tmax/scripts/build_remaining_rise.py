#!/usr/bin/env python3
"""Measure the empirical 'remaining rise' climatology per city.

The post-peak edge (POST_PEAK.md) needs one number: given the local hour and the max
observed so far, how much MORE can the day's max still rise? This measures it directly
from IEM ASOS hourly observations, warm seasons 2021-2025, per city:

    remaining_rise(h) = daily_max - max(obs up to and including hour h)

and stores its distribution by local hour. Output:
backtest_datasets/remaining_rise.json
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "backtest_datasets"
CACHE = OUT / "mos_raw"
UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}

# IEM station id, local tz offset used to bucket into local hours (fixed-offset is fine
# at hourly granularity; PHX has no DST, NYC/LAS shift but the peak window is unaffected).
CITIES = {"nyc": ("NYC", -4), "phoenix": ("PHX", -7), "vegas": ("LAS", -7)}
YEARS = (2021, 2026)          # [start, end)
MONTHS = (5, 6, 7, 8, 9)


def fetch(station: str) -> pd.DataFrame:
    cache = CACHE / f"iem_hourly_{station}.csv"
    if cache.exists() and cache.stat().st_size > 5000:
        return pd.read_csv(cache, low_memory=False)
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
           f"?station={station}&data=tmpf&tz=UTC&format=onlycomma&latlon=no"
           f"&missing=empty&trace=empty&year1={YEARS[0]}&month1=1&day1=1"
           f"&year2={YEARS[1]}&month2=1&day2=1")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        text = r.read().decode("utf-8", "replace")
    cache.write_text(text)
    return pd.read_csv(io.StringIO(text), low_memory=False)


def build(station: str, off: int) -> dict:
    raw = fetch(station)
    raw["valid"] = pd.to_datetime(raw["valid"], errors="coerce", utc=True)
    raw["tmpf"] = pd.to_numeric(raw["tmpf"], errors="coerce")
    raw = raw.dropna(subset=["valid", "tmpf"])
    raw = raw[raw["tmpf"].between(-40, 130)]
    local = raw["valid"] + pd.Timedelta(hours=off)
    raw["day"] = local.dt.date
    raw["hour"] = local.dt.hour
    raw = raw[local.dt.month.isin(MONTHS)]

    # Per day: running max by hour, and the day's max.
    out: dict[str, dict] = {}
    g = raw.groupby(["day", "hour"])["tmpf"].max().reset_index()
    daymax = g.groupby("day")["tmpf"].max().rename("daymax")
    g = g.join(daymax, on="day")
    g = g.sort_values(["day", "hour"])
    g["runmax"] = g.groupby("day")["tmpf"].cummax()
    g["remaining"] = g["daymax"] - g["runmax"]
    for hour, s in g.groupby("hour"):
        if hour < 9 or hour > 21 or len(s) < 100:
            continue
        r = s["remaining"]
        out[str(hour)] = {
            "n": int(len(r)),
            "mean": round(float(r.mean()), 2),
            "p50": round(float(r.quantile(0.50)), 2),
            "p90": round(float(r.quantile(0.90)), 2),
            "p95": round(float(r.quantile(0.95)), 2),
            "p99": round(float(r.quantile(0.99)), 2),
            "p_zero": round(float((r <= 0.05).mean()), 3),   # P(max already in)
            # Exact empirical CDF at integer rises: cdf[k] = P(remaining rise <= k).
            "cdf": [round(float((r <= k + 0.05).mean()), 4) for k in range(0, 11)],
        }
    return out


def main() -> int:
    res = {}
    for city, (station, off) in CITIES.items():
        print(f"building {city} ({station})...", flush=True)
        res[city] = build(station, off)
        h = res[city]
        for hh in ("12", "14", "15", "16", "17"):
            if hh in h:
                d = h[hh]
                print(f"   {hh}h: p50 +{d['p50']:.1f}  p90 +{d['p90']:.1f}  "
                      f"p99 +{d['p99']:.1f}  P(done)={d['p_zero']*100:.0f}%  n={d['n']}")
    (OUT / "remaining_rise.json").write_text(json.dumps(res, indent=1))
    print(f"\nwrote {OUT/'remaining_rise.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
