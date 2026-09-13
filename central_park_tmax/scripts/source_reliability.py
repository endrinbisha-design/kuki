#!/usr/bin/env python3
"""Recompute every tally in ``SOURCE_RELIABILITY.md`` from primary data.

This script exists because hand-maintained counters have been wrong four times in this
project: the timestamp anomaly's "six for six" that was really 6/15, the backtest's
impossible 39 % benchmark, the falling-trace rule's "13 for 13" that a scripted audit put
at 14 correct / 3 wrong, and -- caught by the first run of this very script -- a
preliminary count of 19 that should have been 20. In every case the error was the same: a
number never re-derived, or re-derived from something that was not primary data.

That fourth one is the reason for the ``prelim_high_f`` field. The first version recovered
the preliminary by regex from the prose in ``actual_high_source``, one phrasing did not
match, and the day vanished silently -- the same failure as a hand-kept tally, just one
level down and wearing a script's authority. Parse structured fields, not your own writing.

So nothing here is carried forward. Groups and snapshots are re-parsed from the METAR
archive on each run; preliminary values come from ``prelim_high_f``; settlements come from
the log. Run it after adding a day and paste the output.

    python scripts/source_reliability.py
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}
START = dt.date(2026, 8, 1)
SIX = re.compile(r"(?:^|\s)1([01])(\d{3})(?:\s|$)")
# The preliminary value as recorded in actual_high_source, across the phrasings used.
PRE = re.compile(r"prelim\w*[^.]*?(\d{2,3})\s*at\s*\d|said\s+(\d{2,3})\s+at|prelim_CLI_(\d{2,3})_at",
                 re.I)


def c_to_f(tenths_c: int, sign: str) -> float:
    return round((1 if sign == "0" else -1) * tenths_c / 10 * 9 / 5 + 32, 2)


def load_metar(d1: dt.date, d2: dt.date, offset: int = -4):
    """(snapshots, groups) keyed by local date. Evening groups spanning 2 days excluded."""
    u = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=NYC&data=metar"
         "&tz=UTC&format=onlycomma&latlon=no&missing=M&trace=T"
         f"&year1={d1.year}&month1={d1.month}&day1={d1.day}"
         f"&year2={d2.year}&month2={d2.month}&day2={d2.day}")
    txt = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=300).read().decode()
    df = pd.read_csv(io.StringIO(txt), low_memory=False)
    df["valid"] = pd.to_datetime(df["valid"], utc=True)
    snap: dict[dt.date, dict[str, float]] = {}
    grp: dict[dt.date, dict[str, float]] = {}
    for _, r in df.iterrows():
        mm = str(r.get("metar", ""))
        v = r["valid"]
        loc = v + pd.Timedelta(hours=offset)
        g = re.search(r"\bT([01])(\d{3})", mm)
        if g and v.minute == 51:
            snap.setdefault(loc.date(), {})[loc.strftime("%H:%M")] = c_to_f(int(g.group(2)), g.group(1))
        if "RMK" in mm and v.minute == 51 and v.hour % 6 == 5:
            gg = SIX.search(mm.split("RMK", 1)[1])
            if gg:
                end = v + pd.Timedelta(minutes=9)
                sl = end - pd.Timedelta(hours=6) + pd.Timedelta(hours=offset)
                el = end + pd.Timedelta(hours=offset)
                if sl.date() == el.date():
                    grp.setdefault(sl.date(), {})[sl.strftime("%H")] = c_to_f(int(gg.group(2)), gg.group(1))
    return snap, grp


def half_up(x: float) -> int:
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def bucket(t: int) -> str:
    """KXHIGHNY bucket containing integer ``t``."""
    if t <= 81:
        return "<=81"
    if t >= 90:
        return ">=90"
    lo = t if t % 2 == 0 else t - 1
    return f"{lo}-{lo+1}"


def main() -> int:
    rows = [json.loads(l) for l in open(ROOT / "track_record/call_log.jsonl") if l.strip()]
    log = {r["target_date"]: r for r in rows if r.get("city") in (None, "nyc")}
    days = sorted(d for d in log
                  if d >= START.isoformat() and log[d].get("actual_high_f") is not None)
    snap, grp = load_metar(START, dt.date.fromisoformat(days[-1]) + dt.timedelta(days=2))

    n = mo = af = best = pre_n = pre_ok = 0
    err: dict[int, int] = {}
    same_bucket = same_ok = wide = strad = strad_63 = 0
    for ds in days:
        d = dt.date.fromisoformat(ds)
        if d not in grp:
            continue
        act = log[ds]["actual_high_f"]
        G = grp[d]
        m, a = G.get("08"), G.get("14")
        n += 1
        if m is not None:
            mo += half_up(m) == act
        if a is not None:
            af += half_up(a) == act
        best += half_up(max(v for v in (m or -99, a or -99))) == act
        # Prefer the structured field. The regex below is a fallback for older entries
        # and it silently missed 09-12, whose phrasing differed -- which is why the
        # value is now recorded as a field instead of being re-parsed out of prose.
        p = log[ds].get("prelim_high_f")
        if p is None:
            pm = PRE.search(log[ds].get("actual_high_source", "") or "")
            p = int(next(g for g in pm.groups() if g)) if pm else None
        if p is not None:
            pre_n += 1
            pre_ok += p == act
            err[act - p] = err.get(act - p, 0) + 1
            if bucket(p) == bucket(p + 1):
                same_bucket += 1
                same_ok += bucket(p) == bucket(act)
                if bucket(p) in ("<=81", ">=90"):
                    wide += 1
            else:
                strad += 1
                strad_63 += bucket(act) == bucket(p)

    print(f"days with groups: {n}   days with a recorded preliminary: {pre_n}\n")
    print("SOURCE ACCURACY (matches settlement)")
    print(f"  morning group   (1:51 PM)  {mo:>3}/{n}  = {mo/n:.0%}")
    print(f"  preliminary CLI (~4:40 PM) {pre_ok:>3}/{pre_n}  = {pre_ok/pre_n:.0%}")
    print(f"  afternoon group (7:51 PM)  {af:>3}/{n}  = {af/n:.0%}")
    print(f"  max of both groups         {best:>3}/{n}  = {best/n:.0%}")
    print("\nPRELIMINARY ERROR (settled - preliminary)")
    for k in sorted(err):
        print(f"  {k:+d} F : {err[k]:>3} days  ({err[k]/pre_n:.0%})")
    print("\nBUCKET REACH of the two-point split")
    print(f"  both integers in one bucket {same_bucket:>3}/{pre_n}   bucket correct {same_ok}/{same_bucket}")
    print(f"    ...of which open-ended    {wide:>3}   (certainty nearly free -- see EDGE_DECAY.md)")
    print(f"    ...genuine 2-wide bucket  {same_bucket-wide:>3}")
    print(f"  integers straddle a boundary {strad:>3}/{pre_n}   63% side won {strad_63}/{strad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
