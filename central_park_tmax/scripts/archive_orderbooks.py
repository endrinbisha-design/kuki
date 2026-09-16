#!/usr/bin/env python3
"""One-shot public full-depth collection with raw payloads/receipt times. No trades.

Retains per-market rules/series fee metadata separately. Sequential requests do
not form an atomic board. Polling is not a substitute for a sequenced websocket.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from central_park_tmax.evaluation.execution_research import validate_book
BASE = "https://external-api.kalshi.com/trade-api/v2"


def fetch(path):
    started = datetime.now(timezone.utc).isoformat()
    with urllib.request.urlopen(BASE+path,timeout=20) as response:
        raw = response.read()
        server_date = response.headers.get("Date")
    return {"request_started_utc": started, "received_utc": datetime.now(timezone.utc).isoformat(),
            "url": BASE+path, "server_http_date": server_date,
            "sha256": hashlib.sha256(raw).hexdigest(), "payload": json.loads(raw)}


def collect(series):
    metadata = [fetch("/series/" + urllib.parse.quote(series,safe=""))]
    markets, cursor, seen = [], "", set()
    while True:
        page = fetch("/markets?" + urllib.parse.urlencode({"series_ticker":series,"status":"open","limit":100,"cursor":cursor}))
        metadata.append(page)
        markets.extend(page["payload"]["markets"])
        cursor = page["payload"].get("cursor","")
        if not cursor:
            break
        if cursor in seen:
            raise ValueError("Repeated pagination cursor.")
        seen.add(cursor)
    records=[]
    for market in markets:
        ticker=market["ticker"]
        started=datetime.now(timezone.utc).isoformat()
        try:
            record=fetch("/markets/"+urllib.parse.quote(ticker,safe="")+"/orderbook?depth=0")
            validate_book(record["payload"])
            record.update({"ticker":ticker,"series":series,"schema_version":1,"depth_requested":0})
        except Exception as exc:
            record={"ticker":ticker,"series":series,"request_started_utc":started,
                    "received_utc":datetime.now(timezone.utc).isoformat(),"error":str(exc)}
        records.append(record)
    return records,metadata


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--series",default="KXHIGHNY")
    p.add_argument("--output-dir",type=Path,default=ROOT / "data/orderbook_research")
    args=p.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        records,metadata=collect(args.series)
    except Exception as exc:
        failure={"status":"collection_failed","series":args.series,"attempted_utc":stamp,
                 "base_url":BASE,"error":str(exc),"successful_books":0}
        (args.output_dir / f"{stamp}_failure.json").write_text(json.dumps(failure,indent=2)+"\n")
        print(json.dumps(failure))
        return 1
    for suffix,rows in (("books",records),("metadata",metadata)):
        (args.output_dir / f"{stamp}_{suffix}.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
    successful=sum("error" not in r for r in records)
    print(json.dumps({"markets":len(records),"successful_books":successful,"errors":len(records)-successful,"output_dir":str(args.output_dir)}))
    return 0 if records and successful==len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
