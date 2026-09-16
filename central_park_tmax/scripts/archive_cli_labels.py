#!/usr/bin/env python3
"""Archive IEM-parsed NWS CLI highs with report identifiers and retrieval provenance.

This is the archive's CURRENT revision, not a history of what Kalshi used to settle.
Product issuance time is not a verified first receipt/resolution timestamp.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def fetch_year(year):
    url = f"https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year={year}"
    started = datetime.now(timezone.utc).isoformat()
    with urllib.request.urlopen(url, timeout=45) as response:
        raw = response.read()
    received = datetime.now(timezone.utc).isoformat()
    data = json.loads(raw)
    rows = []
    for row in data["results"]:
        high = row.get("high")
        if high is None or row.get("station") != "KNYC":
            continue
        product = row["product"]
        issued = pd.to_datetime(product.split("-")[0], format="%Y%m%d%H%M", utc=True)
        rows.append({"date": row["valid"], "station": "KNYC", "cli_high": high,
                     "product_id": product, "product_issued_utc": issued.isoformat(),
                     "source_url": "https://mesonet.agron.iastate.edu" + row["link"],
                     "retrieved_utc": received})
    return rows, {"year": year, "url": url, "request_started_utc": started,
                  "received_utc": received, "response_sha256": hashlib.sha256(raw).hexdigest(),
                  "n_labels": len(rows)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-year", type=int, default=2019)
    p.add_argument("--end-year", type=int, default=2026)
    p.add_argument("--output-dir", type=Path, default=ROOT / "backtest_datasets/cli_research")
    args = p.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        fetched = list(pool.map(fetch_year, range(args.start_year, args.end_year + 1)))
    frame = pd.DataFrame([r for rows, _ in fetched for r in rows]).sort_values("date")
    if frame.duplicated(["station", "date"]).any():
        raise ValueError("Ambiguous duplicate CLI days.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output_dir / "knyc_cli_highs.csv", index=False)
    (args.output_dir / "manifest.json").write_text(json.dumps({
        "target": "IEM-parsed current-revision NWS CLI daily high, not verified Kalshi payout",
        "day_basis": "midnight-to-midnight fixed EST (UTC-5)",
        "sources": [meta for _, meta in fetched]}, indent=2) + "\n")
    print(f"Archived {len(frame)} report-based labels to {args.output_dir}")


if __name__ == "__main__":
    main()
