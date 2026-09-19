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
sys.path.insert(0, str(ROOT / "src"))
# The canonical fee, not a local copy of it. The first version of the pricing block below
# reimplemented ceil(0.07*C*P*(1-P)) from memory, ceiled PER CONTRACT instead of per order
# and divided by 100 once too often, which understated the fee ~30x and turned a +1.1 %
# edge into a +1.5 % one. Import the formula; do not retype it.
from central_park_tmax.data.kalshi import kalshi_taker_fee  # noqa: E402

UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}
START = dt.date(2026, 8, 1)
SIX = re.compile(r"(?:^|\s)1([01])(\d{3})(?:\s|$)")
# Fallback only: the preliminary as phrased in actual_high_source on pre-09-13 entries.
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


_KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
_SUB = (
    (r"^(-?\d+)\s*(?:to|-)\s*(-?\d+)$", lambda m: (int(m.group(1)), int(m.group(2)))),
    (r"^(-?\d+)\s*or below$", lambda m: (-999, int(m.group(1)))),
    (r"^(-?\d+)\s*or above$", lambda m: (int(m.group(1)), 999)),
)
_TICKER_DATE = re.compile(r"-(\d{2}[A-Z]{3}\d{2})-")


def real_ladders() -> dict[dt.date, list[tuple[int, int]]]:
    """Per-day KXHIGHNY strike ladder, straight from the settled markets.

    The ladder RE-CENTRES DAILY and the strikes are not a fixed grid. An earlier version of
    this script hardcoded August's ladder (``<=81`` ... ``>=90``) and applied it to every
    day, which misclassified 11 of 23 days: it reported 16 days sitting in the wide
    open-ended bucket when only 7 actually were, because on a cool September day the
    open-ended bucket is ``<=69``, not ``<=81``. It also assumed 2-wide buckets always pair
    [even, even+1]; the real ladders include 83-84 and 78-79, so even the parity was wrong.
    Never assume the ladder -- look it up.
    """
    out: dict[dt.date, list[tuple[int, int]]] = {}
    try:
        with urllib.request.urlopen(urllib.request.Request(
                f"{_KALSHI}/markets?series_ticker=KXHIGHNY&status=settled&limit=1000",
                headers=UA), timeout=60) as r:
            markets = json.load(r).get("markets", [])
    except Exception:
        return out
    for m in markets:
        td = _TICKER_DATE.search(m.get("ticker", ""))
        if not td:
            continue
        sub = (m.get("yes_sub_title") or m.get("subtitle") or "").replace("\u00b0", "").strip()
        for pat, fn in _SUB:
            mm = re.match(pat, sub, re.I)
            if mm:
                day = dt.datetime.strptime(td.group(1), "%y%b%d").date()
                out.setdefault(day, []).append(fn(mm))
                break
    return out


def bucket_on(ladders, day: dt.date, t: int):
    """The real bucket containing ``t`` on ``day``, or None if the ladder is unknown."""
    for lo, hi in sorted(ladders.get(day, [])):
        if lo <= t <= hi:
            return (lo, hi)
    return None


def _candle_cents(node, field: str = "close"):
    """Candle price in cents, tolerant of both API encodings.

    Kalshi moved these from integer cents (``close``) to dollar STRINGS
    (``close_dollars``). Read both and expect a third. See data/kalshi.py.
    """
    if not node:
        return None
    v = node.get(field)
    if v is not None:
        return float(v)
    v = node.get(field + "_dollars")
    return float(v) * 100.0 if v is not None else None


def ask_1700(day: dt.date, lo: int, hi: int):
    """Yes-ask in cents for that day's ``lo``-``hi`` bucket on the 17:00 EDT candle.

    The price of the near-certainty was previously a hand-maintained block of numbers in
    SOURCE_RELIABILITY.md -- precisely the thing this script exists to abolish. Derived
    here instead so it cannot drift as days are added.
    """
    tick = f"KXHIGHNY-{day:%y%b%d}".upper()
    end = int(dt.datetime(day.year, day.month, day.day, 21, 0,
                          tzinfo=dt.timezone.utc).timestamp())   # 17:00 EDT
    for suffix in (f"-B{lo + 0.5}", f"-B{hi - 0.5}"):
        u = (f"{_KALSHI}/series/KXHIGHNY/markets/{tick}{suffix}"
             f"/candlesticks?start_ts={end - 3600}&end_ts={end}&period_interval=60")
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
                cs = json.load(r).get("candlesticks", [])
        except Exception:
            continue
        for c in cs:
            if c.get("end_period_ts") == end:
                a = _candle_cents(c.get("yes_ask")) or _candle_cents(c.get("price"))
                if a:
                    return a
    return None


def main() -> int:
    rows = [json.loads(l) for l in open(ROOT / "track_record/call_log.jsonl") if l.strip()]
    log = {r["target_date"]: r for r in rows if r.get("city") in (None, "nyc")}
    days = sorted(d for d in log
                  if d >= START.isoformat() and log[d].get("actual_high_f") is not None)
    snap, grp = load_metar(START, dt.date.fromisoformat(days[-1]) + dt.timedelta(days=2))

    n = mo = af = best = pre_n = pre_ok = 0
    err: dict[int, int] = {}
    same_bucket = same_ok = wide = strad = strad_63 = 0
    narrow: list[tuple[dt.date, tuple[int, int], bool]] = []
    daytime_fail: list[str] = []
    no_ladder = 0
    ladders = real_ladders()
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
        # ALL same-day groups, not just morning+afternoon. The first version used only
        # those two and scored 98%; 09-14 broke it -- an overnight-max day settling at 75
        # where morning 73.04 and afternoon 73.94 both round to 74, while the 2 AM-8 AM
        # group reads 75.02 and was simply never consulted. The 98% was under-specified,
        # not wrong: two of the three available same-day groups were being fed in.
        best += half_up(max(G.values())) == act
        if half_up(max(v for v in (m or -99, a or -99))) != act:
            daytime_fail.append(ds)
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
            b1, b2, ba = (bucket_on(ladders, d, p), bucket_on(ladders, d, p + 1),
                          bucket_on(ladders, d, act))
            if not (b1 and b2 and ba):
                no_ladder += 1
            elif b1 == b2:
                same_bucket += 1
                same_ok += ba == b1
                if b1[0] == -999 or b1[1] == 999:
                    wide += 1
                else:
                    narrow.append((d, b1, ba == b1))
            else:
                strad += 1
                strad_63 += ba == b1

    print(f"days with groups: {n}   days with a recorded preliminary: {pre_n}\n")
    # The afternoon group is NOT always an independent measurement. On a substantial minority
    # it reports exactly the morning group's value while exceeding every snapshot inside its
    # own 2 PM-8 PM window. Found 09-17, where that pattern was a value carried forward.
    #
    # BUT EXACT EQUALITY IS NOT SUFFICIENT, and 09-18 proved it inside 24 hours: a
    # DOUBLE-TOPPED day produces the same two symptoms honestly. The discriminator is the
    # CLI's peak TIME:
    #     peak time OUTSIDE 14:00-20:00  -> carried forward   (09-17, peak 12:55 PM)
    #     peak time INSIDE  14:00-20:00  -> genuine reading   (09-18, peak 2:16 PM)
    # so the count is split three ways below and the bare equality count is reported only as
    # an UPPER BOUND. Peak times come from actual_high_time_lst, which exists from 09-16
    # onward; the CLI archive retains about a week, so August can never be classified.
    dup = dup_hi = dup_ok = nondup = nondup_ok = 0
    carried = genuine = unknown = 0
    for ds in days:
        d = dt.date.fromisoformat(ds)
        if d not in grp:
            continue
        m, a = grp[d].get("08"), grp[d].get("14")
        if m is None or a is None:
            continue
        act = log[ds]["actual_high_f"]
        if abs(a - m) < 0.01:
            dup += 1
            dup_ok += half_up(a) == act
            sm = max((snap.get(d, {}).get(f"{h:02d}:51") for h in range(14, 20)
                      if snap.get(d, {}).get(f"{h:02d}:51") is not None), default=None)
            if sm is not None and a > sm + 0.01:
                dup_hi += 1
            pk = log[ds].get("actual_high_time_lst")
            if pk is None:
                unknown += 1
            elif 1400 <= int(pk) < 2000:
                genuine += 1          # double-topped day: the equality is honest
            else:
                carried += 1
        else:
            nondup += 1
            nondup_ok += half_up(a) == act
    print("AFTERNOON GROUP INDEPENDENCE")
    print(f"  duplicates the morning group exactly  {dup:>3}/{dup + nondup}   (UPPER BOUND)")
    print(f"    ...and exceeds every snapshot in its own window  {dup_hi:>3}")
    print(f"    classified by CLI peak time: carried forward {carried}, "
          f"genuine double-top {genuine}, unknown {unknown}")
    print(f"  afternoon group correct, duplicate days     {dup_ok:>3}/{dup}")
    print(f"  afternoon group correct, non-duplicate days {nondup_ok:>3}/{nondup}"
          f"  = {nondup_ok/nondup:.0%}" if nondup else "")
    print()
    print("SOURCE ACCURACY (matches settlement)")
    print(f"  morning group   (1:51 PM)  {mo:>3}/{n}  = {mo/n:.0%}")
    print(f"  preliminary CLI (~4:40 PM) {pre_ok:>3}/{pre_n}  = {pre_ok/pre_n:.0%}")
    print(f"  afternoon group (7:51 PM)  {af:>3}/{n}  = {af/n:.0%}")
    print(f"  max of ALL same-day groups {best:>3}/{n}  = {best/n:.0%}")
    print(f"  (daytime groups only would miss {len(daytime_fail)}: {', '.join(daytime_fail)})")
    print("\nPRELIMINARY ERROR (settled - preliminary)")
    for k in sorted(err):
        print(f"  {k:+d} F : {err[k]:>3} days  ({err[k]/pre_n:.0%})")
    print("\nBUCKET REACH of the two-point split")
    print(f"  both integers in one bucket {same_bucket:>3}/{pre_n}   bucket correct {same_ok}/{same_bucket}")
    print(f"    ...of which open-ended    {wide:>3}   (certainty nearly free -- see EDGE_DECAY.md)")
    print(f"    ...genuine 2-wide bucket  {same_bucket-wide:>3}")
    if no_ladder:
        print(f"  ({no_ladder} days skipped: real Kalshi ladder unavailable)")
    hold_pct = f"{pre_ok/pre_n:.0%}" if pre_n else "n/a"
    print(f"  integers straddle a boundary {strad:>3}/{pre_n}   "
          f"{hold_pct} side won {strad_63}/{strad}")

    # What the market charges for that near-certainty. Priced from the 17:00 EDT candle
    # on the day itself, so it is the ask an actual taker faced, not a settled-market
    # retrospective. Fee is Kalshi's taker fee, ceil(0.07*P*(1-P)) cents per contract.
    print("\nPRICE OF THE NARROW-BUCKET CERTAINTY (17:00 EDT ask, $10 flat stake)")
    asks, staked, ret = [], 0.0, 0.0
    for day, (lo, hi), ok in narrow:
        a = ask_1700(day, lo, hi)
        if a is None:
            print(f"  {day}  {lo}-{hi:<6}  no 17:00 candle")
            continue
        asks.append(a)
        n_ct = 1000.0 / a                        # $10 in cents / ask
        fee_c = kalshi_taker_fee(a / 100.0, n_ct) * 100.0   # whole-order fee, in cents
        staked += 1000.0
        ret += (100.0 * n_ct - fee_c) if ok else -fee_c
        print(f"  {day}  {lo}-{hi:<6} {a:5.0f}c   {'correct' if ok else 'WRONG'}")
    if asks:
        net = ret - staked
        print(f"  n={len(asks)}  mean ask {sum(asks)/len(asks):.1f}c   "
              f"net {net/100:+.2f} on ${staked/100:.0f} staked = {net/staked:+.1%} per bet")
        print("  (before slippage and any depth check -- see EDGE_DECAY.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
