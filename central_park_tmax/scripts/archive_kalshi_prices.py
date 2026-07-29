#!/usr/bin/env python3
"""Append today's Kalshi temperature boards to a durable price log.

Every strategy result so far is measured against a SIMULATED market — the single
biggest honesty gap in the project, and the blocker for real automation. This archiver
closes it going forward: run it any time (idempotent per snapshot-hour) and it appends
bid/ask/last/volume for every open KXHIGHNY / KXHIGHTPHX / KXHIGHTLV market to
backtest_datasets/kalshi_price_log.csv (committed; ~1 KB/day).

Run a few times per day (morning, ~2pm, post-peak, evening) — manually or from any
scheduler. After a few weeks this becomes the first REAL-price strategy backtest.
"""
from __future__ import annotations

import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backtest_datasets" / "kalshi_price_log.csv"
SERIES = ("KXHIGHNY", "KXHIGHTPHX", "KXHIGHTLV")
API = "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker={s}&status=open&limit=100"
FIELDS = ["snapshot_utc", "series", "ticker", "yes_bid", "yes_ask", "no_bid", "no_ask",
          "last_price", "volume", "open_interest"]


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00Z")   # hour granularity
    seen = set()
    if OUT.exists():
        with OUT.open() as fh:
            seen = {(r["snapshot_utc"], r["ticker"]) for r in csv.DictReader(fh)}
    rows = []
    for s in SERIES:
        try:
            req = urllib.request.Request(API.format(s=s), headers={"User-Agent": "cpt/0.1"})
            data = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as exc:  # noqa: BLE001
            print(f"{s}: fetch failed ({exc})")
            continue
        for m in data.get("markets", []):
            if (now, m["ticker"]) in seen:
                continue
            c = lambda k: (round(float(m[k]) * 100) if m.get(k) not in (None, "") else "")
            rows.append({"snapshot_utc": now, "series": s, "ticker": m["ticker"],
                         "yes_bid": c("yes_bid_dollars"), "yes_ask": c("yes_ask_dollars"),
                         "no_bid": c("no_bid_dollars"), "no_ask": c("no_ask_dollars"),
                         "last_price": c("last_price_dollars"),
                         "volume": m.get("volume_fp", ""),
                         "open_interest": m.get("open_interest_fp", "")})
    if rows:
        new = not OUT.exists()
        with OUT.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerows(rows)
    print(f"appended {len(rows)} rows @ {now}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
