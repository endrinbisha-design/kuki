#!/usr/bin/env python3
"""Append precisely timestamped market summaries to a new v2 archive.

The old archive rounded arrival times backward to the hour, skipped intra-hour
updates and rounded away sub-cent prices. Preserve it unchanged. New records
carry request and receipt times and exact dollar strings in kalshi_price_log_v2.csv.
REST summaries have no guaranteed depth/quote age: they are not executable fills.
No background process is started and no orders are placed by this script.
"""
from __future__ import annotations

import csv
import json
import urllib.request
import urllib.parse
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backtest_datasets" / "kalshi_price_log_v2.csv"
SERIES = ("KXHIGHNY", "KXHIGHTPHX", "KXHIGHTLV")
API = "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker={s}&status=open&limit=100"
PRICE_FIELDS = ["yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars",
                "last_price_dollars"]
FIELDS = ["schema_version", "request_started_utc", "snapshot_utc", "series", "ticker",
          *PRICE_FIELDS, "volume", "open_interest"]


def snapshot_row(m: dict, series: str, request_started: datetime, received: datetime) -> dict:
    if request_started.tzinfo is None or received.tzinfo is None or received < request_started:
        raise ValueError("Snapshot times must be aware and chronologically ordered.")
    row = {"schema_version": 2, "request_started_utc": request_started.astimezone(timezone.utc).isoformat(),
           "snapshot_utc": received.astimezone(timezone.utc).isoformat(),
           "series": series, "ticker": m["ticker"],
           "volume": m.get("volume_fp", ""), "open_interest": m.get("open_interest_fp", "")}
    for name in PRICE_FIELDS:
        value = m.get(name)
        if value in (None, ""):
            row[name] = ""
        else:
            price = Decimal(str(value))
            if not price.is_finite() or not 0 <= price <= 1:
                raise ValueError(f"Invalid market price in {name}.")
            row[name] = str(value)
    return row


def main() -> int:
    rows = []
    for s in SERIES:
        cursor, cursors = "", set()
        while True:
            try:
                url = API.format(s=s) + ("&" + urllib.parse.urlencode({"cursor": cursor}) if cursor else "")
                started = datetime.now(timezone.utc)
                req = urllib.request.Request(url, headers={"User-Agent": "cpt/0.1"})
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.load(response)
                received = datetime.now(timezone.utc)
                for m in data.get("markets", []):
                    rows.append(snapshot_row(m, s, started, received))
            except Exception as exc:  # noqa: BLE001
                print(f"{s}: partial collection failed ({exc})")
                break
            cursor = data.get("cursor", "")
            if not cursor:
                break
            if cursor in cursors:
                raise RuntimeError("Repeated pagination cursor; refusing infinite collection.")
            cursors.add(cursor)
    if rows:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        new = not OUT.exists()
        with OUT.open("a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerows(rows)
    print(f"appended {len(rows)} precisely timestamped rows to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
