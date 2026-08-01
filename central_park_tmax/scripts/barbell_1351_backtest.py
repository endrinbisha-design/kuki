#!/usr/bin/env python3
"""Barbell staking on the 13:51 signal: big on the model's favourite, small on the tails.

The flat-stake test (bet_after_1351_backtest.py) treated every qualifying bet the same and
found breakeven. This asks a different question: does it help to size by CONVICTION?

  CORE      the bucket our observation-anchored model ranks highest — the "most likely
            temperature" — staked large.
  SATELLITE any bucket whose model probability exceeds its ask by >= 15 pts, staked small.
            These are the cheap tails; the flat test showed a single 11c winner on
            2026-07-26 carried that whole leg, so they are lottery tickets and are sized
            accordingly.

Regime split. ``models/daily_strategy.REGIME_STATS`` measures NYC forecast error as
MAE 1.88 F on dry days vs 2.53 F on wet ones, with the cool tail fattening 15% -> 23%. Wet
days are structurally harder, so the CORE leg is reported separately for each regime to see
whether conviction sizing only works when the atmosphere is cooperating. Regime is taken
from IEM hourly precipitation (any measurable precip on the local day = wet), the same
definition REGIME_STATS was fitted with (GHCN prcp > 0).

Reads the cached day-rows written by bet_after_1351_backtest.py. Fills at the ask, net of
the Kalshi taker fee, $100 start.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backtest_datasets"
ROWS = OUT / "bet_after_1351_rows.json"
UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}

START = 100.0
CORE_STAKE = 20.0        # dollars on the model's favourite
SAT_STAKE = 3.0          # dollars on each >=15pt-edge tail
SAT_EDGE = 0.15
MAX_PRICE = 0.90
MIN_PRICE = 0.03


def fee(p: float) -> float:
    return math.ceil(0.07 * p * (1 - p) * 100) / 100.0


def wet_days(days: list[dt.date]) -> set[dt.date]:
    """Local days with measurable precipitation at KNYC (IEM hourly p01i)."""
    lo, hi = min(days) - dt.timedelta(days=1), max(days) + dt.timedelta(days=2)
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=NYC"
           "&data=p01i&tz=UTC&format=onlycomma&latlon=no&missing=M&trace=T"
           f"&year1={lo.year}&month1={lo.month}&day1={lo.day}"
           f"&year2={hi.year}&month2={hi.month}&day2={hi.day}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                df = pd.read_csv(io.StringIO(r.read().decode()), low_memory=False)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  retry precip: {str(exc)[:60]}", flush=True)
            time.sleep(3 * (attempt + 1))
    else:
        print("  precip unavailable — treating all days as dry (regime split disabled)")
        return set()
    df["valid"] = pd.to_datetime(df["valid"], errors="coerce", utc=True)
    df["p01i"] = pd.to_numeric(df["p01i"].replace("T", 0.001), errors="coerce")
    df = df.dropna(subset=["valid"])
    day = (df["valid"] + pd.Timedelta(hours=-4)).dt.date
    tot = df.groupby(day)["p01i"].sum()
    return {d for d, v in tot.items() if v and v > 0.0}


def run(rows, wet: set, core_stake: float, sat_stake: float, regime_filter=None):
    """Returns (final_bank, n_core, core_hits, core_pnl, n_sat, sat_hits, sat_pnl, rets)."""
    bank = START
    n_core = core_hits = n_sat = sat_hits = 0
    core_pnl = sat_pnl = 0.0
    rets = []
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        is_wet = d in wet
        if regime_filter == "dry" and is_wet:
            continue
        if regime_filter == "wet" and not is_wet:
            continue
        ok = [c for c in r["cands"] if MIN_PRICE <= c["ask"] <= MAX_PRICE]
        if not ok:
            continue
        # CORE: model's most likely bucket
        if core_stake > 0:
            core = max(ok, key=lambda x: x["p"])
            unit = core["ask"] + fee(core["ask"])
            pnl = core_stake * ((1.0 if core["won"] else 0.0) / unit - 1.0)
            bank += pnl
            core_pnl += pnl
            n_core += 1
            core_hits += int(core["won"])
            rets.append(pnl / core_stake)
        # SATELLITE: every >=15pt edge tail, excluding the core pick
        if sat_stake > 0:
            core_b = max(ok, key=lambda x: x["p"])["bucket"] if core_stake > 0 else None
            for c in ok:
                if c["bucket"] == core_b:
                    continue
                if c["p"] - c["ask"] < SAT_EDGE:
                    continue
                unit = c["ask"] + fee(c["ask"])
                pnl = sat_stake * ((1.0 if c["won"] else 0.0) / unit - 1.0)
                bank += pnl
                sat_pnl += pnl
                n_sat += 1
                sat_hits += int(c["won"])
    return bank, n_core, core_hits, core_pnl, n_sat, sat_hits, sat_pnl, rets


def boot(rets):
    if len(rets) < 8:
        return None
    a = np.array(rets)
    rng = np.random.default_rng(0)
    b = np.array([rng.choice(a, size=len(a), replace=True).mean() for _ in range(4000)])
    return float(a.mean()) * 100, np.percentile(b, 2.5) * 100, np.percentile(b, 97.5) * 100, \
        float((b <= 0).mean())


def main() -> int:
    if not ROWS.exists():
        print("run scripts/bet_after_1351_backtest.py first")
        return 1
    rows = json.loads(ROWS.read_text())
    days = [dt.date.fromisoformat(r["date"]) for r in rows]
    wet = wet_days(days)
    print(f"{len(rows)} days | {len(wet & set(days))} wet, {len(days) - len(wet & set(days))} dry\n")

    res = {}
    print(f"=== BARBELL: ${CORE_STAKE:.0f} core (model favourite) + "
          f"${SAT_STAKE:.0f} per >={SAT_EDGE:.0%}-edge tail ===")
    for label, filt in (("all days", None), ("DRY only", "dry"), ("WET only", "wet")):
        bank, nc, ch, cp, ns, sh, sp, rets = run(rows, wet, CORE_STAKE, SAT_STAKE, filt)
        print(f"\n  {label}:  final ${bank:,.2f}")
        print(f"    core     : {nc:3} bets, {ch:2} wins ({ch/nc:.0%})   P/L {cp:+8.2f}" if nc else "    core: none")
        print(f"    satellite: {ns:3} bets, {sh:2} wins ({sh/ns:.0%})   P/L {sp:+8.2f}" if ns else "    satellite: none")
        res[label] = {"final": round(bank, 2), "n_core": nc, "core_hits": ch,
                      "core_pnl": round(cp, 2), "n_sat": ns, "sat_hits": sh,
                      "sat_pnl": round(sp, 2)}

    print("\n=== CORE LEG ALONE (no tails), per-bet return ===")
    for label, filt in (("all days", None), ("DRY only", "dry"), ("WET only", "wet")):
        bank, nc, ch, cp, _, _, _, rets = run(rows, wet, CORE_STAKE, 0.0, filt)
        b = boot(rets)
        if b is None:
            print(f"  {label:9} too few bets ({nc})")
            continue
        m, lo, hi, ple = b
        print(f"  {label:9} ${bank:8,.2f}  n={nc:3}  hit {ch/nc:.0%}  "
              f"mean {m:+6.2f}%/bet  CI [{lo:+.1f},{hi:+.1f}]  P(<=0)={ple:.2f}")
        res[f"core_{label}"] = {"final": round(bank, 2), "n": nc,
                                "mean_pct": round(m, 2),
                                "ci95": [round(lo, 2), round(hi, 2)], "p_le_0": round(ple, 3)}

    print("\n=== SIZING SWEEP (core only, all days) ===")
    for cs in (5, 10, 20, 30, 40):
        bank, nc, ch, cp, _, _, _, _ = run(rows, wet, float(cs), 0.0, None)
        print(f"  ${cs:2}/day core -> final ${bank:9,.2f}")

    (OUT / "barbell_1351.json").write_text(json.dumps(res, indent=1))
    print(f"\nwrote {OUT/'barbell_1351.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
