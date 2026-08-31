#!/usr/bin/env python3
"""One-shot live NYC status: observations, post-peak state, and the real Kalshi board.

Built for the half-hourly checkpoints on 2026-07-31 so every update is produced the same
way instead of being reassembled by hand each time.

**Why prices come from candlesticks, not /markets.** On 2026-07-31 the ``/markets`` and
``/markets/{ticker}`` endpoints returned ``null`` for every price and liquidity field
(yes_bid, yes_ask, volume, open_interest, last_price) while ``/trades`` returned 404 — the
public quote fields appear to be gated. Read naively, those nulls look exactly like a market
with no volume, and that is precisely the mistake this script exists to prevent: it was
reported live as "there is no volume" when the board was in fact quoted 69/70c. The
candlesticks endpoint still serves bid/ask/last unauthenticated, so it is the source here,
and an all-null board is reported as UNAVAILABLE rather than as zero.

Nothing in this script recommends a position. It prints state; the judgement stays outside.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from central_park_tmax.data.fast_metar import (  # noqa: E402
    parse_metar_block, settlement_max_so_far)
from central_park_tmax.models.contract_calibration import (  # noqa: E402
    calibration_report, resolution_warning)
from central_park_tmax.models.post_peak import (  # noqa: E402
    bucket_probability, settlement_distribution)
from central_park_tmax.time_utils import to_local  # noqa: E402

UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}
BASE = "https://api.elections.kalshi.com/trade-api/v2"


def offset_at(when_utc: dt.datetime) -> int:
    """NY UTC offset in whole hours at ``when_utc``: -4 under EDT, -5 under EST.

    Resolved per-timestamp rather than hardcoded. DST ends 2026-11-01, after which a
    fixed -4 silently shifts every local timestamp by an hour -- which would corrupt the
    six-hour-group day attribution (the bug class that took 58/68 to 204/204 to fix) and
    relabel the 13:51 transmission as 12:51 local without anything appearing to fail.
    """
    return int(round(to_local(when_utc).utcoffset().total_seconds() / 3600))


def tzname_at(when_utc: dt.datetime) -> str:
    return to_local(when_utc).tzname() or "ET"

# suffix -> (label, floor, cap); None bound = open-ended contract
BUCKETS = {"T82": ("<=81", None, 81), "B82.5": ("82-83", 82, 83),
           "B84.5": ("84-85", 84, 85), "B86.5": ("86-87", 86, 87),
           "B88.5": ("88-89", 88, 89), "T89": (">=90", 90, None)}


def _get(url: str, timeout: int = 45):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return json.load(r)
    except Exception as exc:  # noqa: BLE001
        return {"_error": repr(exc)[:120]}


def _text(url: str, timeout: int = 45) -> str:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read().decode()
    except Exception as exc:  # noqa: BLE001
        return f"_error {exc}"


def board(day_ticker: str, now: dt.datetime) -> dict[str, tuple]:
    """label -> (bid, ask, last) from the most recent priced candle. {} when unavailable."""
    ts = int(now.timestamp())
    out: dict[str, tuple] = {}
    for suf, (label, _, _) in BUCKETS.items():
        d = _get(f"{BASE}/series/KXHIGHNY/markets/KXHIGHNY-{day_ticker}-{suf}"
                 f"/candlesticks?start_ts={ts - 7200}&end_ts={ts}&period_interval=60")
        cs = [c for c in d.get("candlesticks", [])
              if (c.get("price") or {}).get("close_dollars") not in (None, "")]
        if not cs:
            continue
        c = cs[-1]
        out[label] = (
            float((c.get("yes_bid") or {}).get("close_dollars") or 0) * 100,
            float((c.get("yes_ask") or {}).get("close_dollars") or 0) * 100,
            float((c.get("price") or {}).get("close_dollars") or 0) * 100)
    return out


_SUMMARY_FOR = re.compile(r"CLIMATE SUMMARY FOR\s+([A-Z]+\s+\d{1,2}\s+\d{4})")


def preliminary_cli(target: dt.date) -> str | None:
    """Today's preliminary CLI max line, if the ~4:35 PM EDT product is out yet.

    Matches the explicit ``...THE CENTRAL PARK NY CLIMATE SUMMARY FOR <DATE>...`` header
    rather than searching the body for a date string. A loose substring match silently
    returned YESTERDAY's report here (the 06:19Z product summarising Jul 30 while today's
    prelim did not exist yet) — reporting a previous day's max as today's is exactly the
    kind of error that gets a position sized wrong.
    """
    d = _get("https://api.weather.gov/products/types/CLI/locations/NYC")
    want = f"{target:%B %d %Y}".upper().replace(" 0", " ")
    for p in d.get("@graph", []):
        txt = _get(f"https://api.weather.gov/products/{p['id']}").get("productText", "")
        m = _SUMMARY_FOR.search(txt.upper())
        if not m:
            continue
        if " ".join(m.group(1).split()) != want:
            continue
        for line in txt.splitlines():
            if "MAXIMUM" in line:
                return f"{line.strip()}   [summary for {m.group(1)}]"
    return None


def _latest_issue(raw: str, now: dt.datetime) -> dt.datetime | None:
    obs = parse_metar_block(raw, now)
    return obs[0].issued_utc if obs else None


def fetch_waiting_for_new_ob(now: dt.datetime, wait_secs: int, poll_secs: int = 15) -> str:
    """Fetch METARs, polling until an observation NEWER than the last one appears.

    KNYC reports at :51 but transmission lands a minute or three later, and the delay is
    not fixed. A fixed offset either fires early on stale data (which was reported as an
    "update" on 2026-07-31 when nothing had changed) or pads needlessly. Polling reports as
    soon as the data actually exists, which is both faster and safer than guessing.

    Returns the freshest raw block available; on timeout returns what we have rather than
    failing, and main() prints the observation age so staleness is always visible.
    """
    url = "https://aviationweather.gov/api/data/metar?ids=KNYC&format=raw&hours=16"
    raw = _text(url)
    if wait_secs <= 0:
        return raw
    baseline = _latest_issue(raw, now)
    deadline = time.monotonic() + wait_secs
    while time.monotonic() < deadline:
        time.sleep(poll_secs)
        fresh = _text(url)
        latest = _latest_issue(fresh, dt.datetime.now(dt.timezone.utc))
        if latest is not None and (baseline is None or latest > baseline):
            waited = wait_secs - int(deadline - time.monotonic())
            print(f"  (new observation arrived after ~{waited}s of polling)")
            return fresh
        raw = fresh
    print(f"  (no new observation within {wait_secs}s — reporting the latest available)")
    return raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=0, metavar="SECS",
                    help="poll up to SECS for an observation newer than the current one")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    local = to_local(now)
    day = local.date()
    print(f"=== KNYC {local:%Y-%m-%d %H:%M} {tzname_at(now)} ===")

    raw_metar = fetch_waiting_for_new_ob(now, args.wait)
    now = dt.datetime.now(dt.timezone.utc)
    local = to_local(now)
    obs = parse_metar_block(raw_metar, now)
    sm = settlement_max_so_far(obs, day, offset_at(now))
    if sm.best_max_f is None:
        print("  observations UNAVAILABLE")
        return 1
    latest_ob = max((o.issued_utc for o in obs if o.temp_f is not None), default=None)
    if latest_ob is not None:
        age = (now - latest_ob).total_seconds() / 60
        print(f"  latest ob  : {to_local(latest_ob):%H:%M} {tzname_at(latest_ob)} "
              f"({age:.0f} min old)")
    print(f"  max so far : {sm.best_max_f:.2f} F  via {sm.source}"
          f"  (hourly {sm.hourly_max_f}, in-day 6h group {sm.six_hour_max_f})")
    print(f"  trace      : {[round(t, 1) for t in sm.recent_temps_f[-8:]]}")

    o = settlement_distribution("KNYC", sm.best_max_f, local.hour,
                                recent_temps_f=sm.recent_temps_f,
                                observed_max_source=sm.source)
    print(f"  determined={o.determined}  still_rising={o.still_rising}  "
          f"P(max already in)={o.p_max_already_in:.0%}  "
          f"to .5 boundary={o.distance_to_boundary_f} F")

    cli = preliminary_cli(day)
    print(f"  prelim CLI : {cli if cli else 'not issued yet (~4:35 PM EDT)'}")

    bd = board(f"{day:%y%b%d}".upper(), now)
    raw = {}
    for _, (label, lo, hi) in BUCKETS.items():
        if lo is None:
            raw[label] = sum(v for k, v in o.integer_probabilities.items() if k <= hi)
        elif hi is None:
            raw[label] = sum(v for k, v in o.integer_probabilities.items() if k >= lo)
        else:
            raw[label] = bucket_probability(o, lo, hi)

    if not bd:
        print("\n  KALSHI BOARD UNAVAILABLE (no priced candles) — not the same as no volume")
    else:
        rep = calibration_report("KNYC", raw)
        print(f"\n  {'contract':10} {'bid/ask':>12} {'last':>7} {'model raw':>10} {'calibrated':>11}")
        for label in ["<=81", "82-83", "84-85", "86-87", "88-89", ">=90"]:
            b, a, last = bd.get(label, (None, None, None))
            quote = f"{b:.0f}/{a:.0f}c" if b is not None else "n/a"
            lastc = f"{last:.0f}c" if last is not None else "-"
            print(f"  {label:10} {quote:>12} {lastc:>7} {raw[label]*100:9.1f}% "
                  f"{rep['calibrated'][label]*100:10.1f}%")
        w = resolution_warning(rep)
        if w:
            print(f"  NOTE: {w}")
        print("  REMINDER: calibrated tails are not trustworthy on this board; the market "
              "outscored our model (Brier 0.147 vs 0.182) — see REAL_PRICE_BACKTEST.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
