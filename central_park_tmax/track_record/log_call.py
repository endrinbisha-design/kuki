#!/usr/bin/env python3
"""Append to and analyze the live call track record (track_record/call_log.jsonl).

Standalone (no project deps). Usage:
  python track_record/log_call.py summary
  python track_record/log_call.py confirm --date 2026-07-22 --actual 87 --source cli_confirmed
  python track_record/log_call.py add --json '{"target_date": "...", ...}'

The JSONL is the source of truth; this script only reads/appends/rewrites it safely.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LOG = Path(__file__).with_name("call_log.jsonl")


def _read() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]


def _write(rows: list[dict]) -> None:
    LOG.write_text("\n".join(json.dumps(r, sort_keys=False) for r in rows) + "\n")


def cmd_add(args):
    rec = json.loads(args.json)
    assert "target_date" in rec, "record needs target_date"
    rows = _read()
    rows = [r for r in rows if r.get("target_date") != rec["target_date"]] + [rec]
    rows.sort(key=lambda r: r["target_date"])
    _write(rows)
    print(f"logged {rec['target_date']} ({len(rows)} total)")


def cmd_confirm(args):
    rows = _read()
    hit = False
    for r in rows:
        if r.get("target_date") == args.date:
            r["actual_high_f"] = args.actual
            r["actual_high_source"] = args.source
            mp = (r.get("guidance") or {}).get("model_point_f")
            if mp is not None:
                r["model_error_f"] = round(args.actual - mp, 2)
            hit = True
    if not hit:
        raise SystemExit(f"no record for {args.date}")
    _write(rows)
    print(f"confirmed {args.date}: actual={args.actual}F")


def cmd_summary(args):
    rows = _read()
    if not rows:
        print("no records yet")
        return
    print(f"days logged: {len(rows)}  ({rows[0]['target_date']} .. {rows[-1]['target_date']})")

    # call win rate
    calls = [c for r in rows for c in r.get("calls", []) if c.get("result") in ("win", "loss")]
    wins = sum(1 for c in calls if c["result"] == "win")
    if calls:
        print(f"contract calls: {wins}/{len(calls)} won ({wins/len(calls)*100:.0f}%)")

    # model error on confirmed days
    errs, abserrs = [], []
    for r in rows:
        e = r.get("model_error_f")
        if e is not None:
            errs.append(e)
            abserrs.append(abs(e))
    if abserrs:
        print(f"model on live days: MAE {sum(abserrs)/len(abserrs):.2f}F, "
              f"mean error {sum(errs)/len(errs):+.2f}F (n={len(abserrs)})")

    # per-regime guidance accuracy (which source was closest to actual)
    print("\nregime breakdown (which forecast source was closest to actual):")
    from collections import Counter, defaultdict
    by_regime = defaultdict(list)
    for r in rows:
        a = r.get("actual_high_f")
        g = r.get("guidance") or {}
        if a is None:
            continue
        cand = {(k[:-2] if k.endswith("_f") else k).replace("_forecast", ""): v
                for k, v in g.items() if k.endswith("_f") and isinstance(v, (int, float))}
        if not cand:
            continue
        closest = min(cand, key=lambda k: abs(cand[k] - a))
        by_regime[r.get("regime", "unknown")].append(closest)
    for regime, closest_list in by_regime.items():
        c = Counter(closest_list)
        print(f"  {regime:18} closest source: {dict(c)}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("--json", required=True); a.set_defaults(func=cmd_add)
    c = sub.add_parser("confirm")
    c.add_argument("--date", required=True); c.add_argument("--actual", type=float, required=True)
    c.add_argument("--source", default="cli_confirmed"); c.set_defaults(func=cmd_confirm)
    s = sub.add_parser("summary"); s.set_defaults(func=cmd_summary)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
