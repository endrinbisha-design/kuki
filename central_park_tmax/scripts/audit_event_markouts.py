#!/usr/bin/env python3
"""Score frozen timestamped signals against depth snapshots; hypothetical quotes only.

Signals JSONL fields: ticker, side (yes/no), quantity (decimal string),
signal_received_utc (aware ISO timestamp). Fee budget is explicit and round-trip.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from central_park_tmax.evaluation.execution_research import event_markout


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--signals",type=Path,required=True)
    p.add_argument("--books",type=Path,nargs="+",required=True)
    p.add_argument("--latency-seconds",type=float,required=True)
    p.add_argument("--horizon-seconds",type=float,required=True)
    p.add_argument("--round-trip-fee-budget-per-contract",required=True)
    p.add_argument("--max-wait-seconds",type=float,default=5)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    records=[json.loads(line) for path in args.books for line in path.read_text().splitlines() if line.strip()]
    signals=[json.loads(line) for line in args.signals.read_text().splitlines() if line.strip()]
    rows=[{"signal":s,"result":event_markout(s,records,latency_seconds=args.latency_seconds,horizon_seconds=args.horizon_seconds,
            fee_budget_per_contract=args.round_trip_fee_budget_per_contract,max_wait_seconds=args.max_wait_seconds)} for s in signals]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({"kind":"hypothetical quote markouts, not fills or portfolio P&L",
        "protocol":{"latency_seconds":args.latency_seconds,"horizon_seconds":args.horizon_seconds,
                    "max_wait_seconds":args.max_wait_seconds,"round_trip_fee_budget_per_contract":args.round_trip_fee_budget_per_contract},
        "results":rows},indent=2)+"\n")
    print(f"Wrote {len(rows)} event diagnostics to {args.output}")


if __name__ == "__main__":
    main()
