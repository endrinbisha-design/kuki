#!/usr/bin/env python3
"""Edge decay / information-arrival study from real Kalshi candlesticks.

Two questions this answers with REAL prices (not the simulated market used everywhere
else in this repo):

  1. **When does the market learn?** For each settled temperature market, track the YES
     price against the eventual outcome and compute mean |price - outcome| by local hour.
     That curve is the market's information-arrival profile: where it is still wrong is
     where an edge can exist; where it has converged, there is nothing left to win.

  2. **How fast does a mispricing decay?** For markets that eventually settled YES,
     find the first local hour the price crossed 50/80/90%. The gap between "our signal
     fires" and "the price has moved" is the practical trading window — measured, rather
     than the single anecdote (Phoenix 119-120 going 11c -> 20c within an hour) that
     prompted the question.

Uses the public candlesticks endpoint on SETTLED markets, so no credentials and no
lookahead concerns. Output: backtest_datasets/edge_decay.json (+ printed summary).
"""
from __future__ import annotations

import json
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "backtest_datasets"
UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}
BASE = "https://api.elections.kalshi.com/trade-api/v2"

# series -> local UTC offset (fixed; adequate at hourly granularity for a summer study)
SERIES = {"KXHIGHNY": -4, "KXHIGHTPHX": -7, "KXHIGHTLV": -7}
PERIOD = 60          # minutes per candle


def _get(url: str) -> dict:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {}


def settled_markets(series: str, limit: int = 200) -> list[dict]:
    out, cursor = [], None
    while len(out) < limit:
        url = f"{BASE}/markets?series_ticker={series}&status=settled&limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        d = _get(url)
        ms = d.get("markets", [])
        if not ms:
            break
        out.extend(ms)
        cursor = d.get("cursor")
        if not cursor:
            break
        time.sleep(0.3)
    return out[:limit]


def candles(series: str, ticker: str, close_iso: str) -> list[dict]:
    """Hourly candles for the 36h ending at market close."""
    try:
        end = int(datetime.fromisoformat(close_iso.replace("Z", "+00:00")).timestamp())
    except Exception:
        return []
    start = end - 36 * 3600
    d = _get(f"{BASE}/series/{series}/markets/{ticker}/candlesticks"
             f"?start_ts={start}&end_ts={end}&period_interval={PERIOD}")
    return d.get("candlesticks", [])


def mid_price(c: dict) -> float | None:
    """Best available price for a candle: bid/ask mid, else last trade."""
    try:
        b = c.get("yes_bid", {}).get("close_dollars")
        a = c.get("yes_ask", {}).get("close_dollars")
        if b not in (None, "") and a not in (None, ""):
            b, a = float(b), float(a)
            if 0 <= b <= 1 and 0 <= a <= 1 and a >= b:
                return (a + b) / 2
        p = c.get("price", {}).get("close_dollars")
        if p not in (None, ""):
            return float(p)
    except Exception:
        return None
    return None


def main() -> int:
    by_hour_err: dict[int, list[float]] = defaultdict(list)
    cross_hours: dict[str, list[int]] = {"p50": [], "p80": [], "p90": []}
    per_series_err: dict[str, dict[int, list[float]]] = {s: defaultdict(list) for s in SERIES}
    n_markets = 0

    for series, off in SERIES.items():
        ms = settled_markets(series, limit=120)
        print(f"{series}: {len(ms)} settled markets", flush=True)
        for m in ms:
            res = (m.get("result") or "").lower()
            if res not in ("yes", "no"):
                continue
            outcome = 1.0 if res == "yes" else 0.0
            cs = candles(series, m["ticker"], m.get("close_time", ""))
            if len(cs) < 6:
                continue
            n_markets += 1
            crossed = {k: None for k in cross_hours}
            for c in cs:
                p = mid_price(c)
                ts = c.get("end_period_ts")
                if p is None or ts is None:
                    continue
                lt = datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=off)
                h = lt.hour
                if not (6 <= h <= 23):
                    continue
                by_hour_err[h].append(abs(p - outcome))
                per_series_err[series][h].append(abs(p - outcome))
                if outcome == 1.0:
                    for key, thr in (("p50", 0.5), ("p80", 0.8), ("p90", 0.9)):
                        if crossed[key] is None and p >= thr:
                            crossed[key] = h
            if outcome == 1.0:
                for k, v in crossed.items():
                    if v is not None:
                        cross_hours[k].append(v)
            time.sleep(0.15)

    res = {"n_markets": n_markets,
           "information_arrival_all": {}, "information_arrival_by_series": {},
           "yes_price_crossing_hour": {}}
    print(f"\n=== INFORMATION ARRIVAL: mean |price - outcome| by local hour "
          f"({n_markets} settled markets) ===")
    for h in sorted(by_hour_err):
        v = by_hour_err[h]
        if len(v) < 20:
            continue
        res["information_arrival_all"][str(h)] = {"n": len(v), "mae": round(float(np.mean(v)), 4)}
        bar = "#" * int(round(np.mean(v) * 60))
        print(f"  {h:02d}h  n={len(v):5d}  {np.mean(v):.3f}  {bar}")
    for s in SERIES:
        res["information_arrival_by_series"][s] = {
            str(h): {"n": len(v), "mae": round(float(np.mean(v)), 4)}
            for h, v in sorted(per_series_err[s].items()) if len(v) >= 20}
    print("\n=== WHEN WINNERS CROSS (local hour, YES-settling markets) ===")
    for k, v in cross_hours.items():
        if v:
            res["yes_price_crossing_hour"][k] = {
                "n": len(v), "median_hour": float(np.median(v)),
                "p25": float(np.percentile(v, 25)), "p75": float(np.percentile(v, 75))}
            print(f"  first hour price >= {k[1:]}%: median {np.median(v):.0f}h "
                  f"(IQR {np.percentile(v,25):.0f}-{np.percentile(v,75):.0f}h, n={len(v)})")
    (OUT / "edge_decay.json").write_text(json.dumps(res, indent=1))
    print(f"\nwrote {OUT/'edge_decay.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
