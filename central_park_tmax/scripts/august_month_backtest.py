#!/usr/bin/env python3
"""Backtest the strategies this month's logging produced, on real Kalshi prices.

Every strategy here is derived from a finding recorded in ``track_record/call_log.jsonl``
during the 30-day August 2026 daily-logging run. The point is to test whether any of them
is tradeable, not to demonstrate that they are.

Strategies
----------
MARKET_FAVOURITE   Buy the market's own highest-priced bucket. A SANITY BENCHMARK, not a
                   candidate: it must hit near 50-60%. If it does not, the price plumbing
                   is broken -- this is the check that caught the $4.2M bug in
                   bet_after_1351_backtest.py.
GROUP_1351         After the 8am-2pm six-hour group transmits (~13:52 local), feed the
                   banked max into models/post_peak and buy its top bucket.
GROUP_1351_EDGE    Same, but only when model probability exceeds the ask by >= 15 points.
PRELIM_ALL         After the preliminary CLI (~16:35 local), buy the bucket containing its
                   reported max. Uses the 17:00 candle.
PRELIM_FALLING     PRELIM_ALL, but only on days where the :51 trace is FALLING into the
                   4 PM cutoff. This is the month's most reliable finding: non-falling ->
                   preliminary reads low, 4/4 (Aug 3, 17, 25, 30); falling -> correct, 4/4.
PRELIM_FALLING_DRY PRELIM_FALLING with WET_DAY_AVOID applied (skip measurable precip).

Leakage discipline: at decision time T only instantaneous obs at or before T, and a
six-hour group only from its transmission time and only if its period lies in the local
day. The preliminary CLI is used only at 17:00, after its ~16:35 issuance plus the
~10-minute product-page propagation lag measured on Aug 20 and Aug 21.

Fills at the ASK from the candle closing at the decision hour, net of the Kalshi taker
fee. Flat $10 stake: the Aug 2 study showed 20%-of-bankroll sizing turned a breakeven
signal into -88% through volatility drag, so flat staking isolates the signal from the
sizing.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import math
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from central_park_tmax.models import post_peak  # noqa: E402

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES, OFFSET = "KXHIGHNY", -4          # EDT; August only, see SEASONAL_TRANSITION.md
UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}
START, STAKE = 100.0, 10.0
EDGE = 0.15
MIN_P, MAX_P = 0.03, 0.90
_TICKER_DATE = re.compile(r"-(\d{2}[A-Z]{3}\d{2})-")
_SIX = re.compile(r"(?:^|\s)1([01])(\d{3})(?:\s|$)")


def _get(url: str) -> dict:
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.5 * (a + 1))
    return {}


def fee(p: float) -> float:
    return math.ceil(0.07 * p * (1 - p) * 100) / 100.0


def settled_by_day() -> dict[dt.date, list[dict]]:
    rows, cursor, pages = [], None, 0
    while pages < 40:
        url = f"{BASE}/markets?series_ticker={SERIES}&status=settled&limit=1000"
        if cursor:
            url += f"&cursor={cursor}"
        d = _get(url)
        ms = d.get("markets", [])
        rows += ms
        cursor = d.get("cursor")
        pages += 1
        if not ms or not cursor:
            break
        time.sleep(0.2)
    out: dict[dt.date, list[dict]] = {}
    for m in rows:
        mm = _TICKER_DATE.search(m["ticker"])
        if mm:
            out.setdefault(dt.datetime.strptime(mm.group(1), "%y%b%d").date(), []).append(m)
    return out


def candle_at(ticker: str, close_iso: str, day: dt.date, local_hour: int):
    """(ask, bid) from the candle closing at ``local_hour``:00 on ``day``, or None.

    Matches the EXACT target timestamp. The lookback window contains more than one candle
    at a given local hour, and taking the first match silently uses the previous day's
    price -- the bug that produced a $100 -> $4.2M result in an earlier study.
    """
    try:
        end = int(dt.datetime.fromisoformat(close_iso.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None
    target = int((dt.datetime.combine(day, dt.time(local_hour, 0), tzinfo=dt.timezone.utc)
                  - dt.timedelta(hours=OFFSET)).timestamp())
    d = _get(f"{BASE}/series/{SERIES}/markets/{ticker}/candlesticks"
             f"?start_ts={end - 36*3600}&end_ts={end}&period_interval=60")
    for c in d.get("candlesticks", []):
        if c.get("end_period_ts") != target:
            continue
        a = (c.get("yes_ask") or {}).get("close_dollars")
        b = (c.get("yes_bid") or {}).get("close_dollars")
        if a in (None, "") or b in (None, ""):
            return None
        try:
            a, b = float(a), float(b)
        except Exception:
            return None
        return (a, b) if 0 < a <= 1 and 0 <= b <= 1 else None
    return None


def bucket_of(sub: str):
    """Parse a market subtitle into an inclusive integer range."""
    s = sub.replace("°", "").strip()
    m = re.match(r"^(-?\d+)\s*(?:to|-)\s*(-?\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^(-?\d+)\s*or below$", s, re.I)
    if m:
        return -999, int(m.group(1))
    m = re.match(r"^(-?\d+)\s*or above$", s, re.I)
    if m:
        return int(m.group(1)), 999
    return None


def load_obs(d1: dt.date, d2: dt.date):
    u = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=NYC&data=metar"
         f"&tz=UTC&format=onlycomma&latlon=no&missing=M&trace=T"
         f"&year1={d1.year}&month1={d1.month}&day1={d1.day}"
         f"&year2={d2.year}&month2={d2.month}&day2={d2.day}")
    df = pd.read_csv(io.StringIO(urllib.request.urlopen(
        urllib.request.Request(u, headers=UA), timeout=300).read().decode()), low_memory=False)
    df["valid"] = pd.to_datetime(df["valid"], utc=True)
    obs, groups = [], []
    for _, r in df.iterrows():
        mm = str(r.get("metar", ""))
        v = r["valid"]
        g = re.search(r"\bT([01])(\d{3})", mm)
        if g:
            f = (1 if g.group(1) == "0" else -1) * int(g.group(2)) / 10 * 9 / 5 + 32
            obs.append((v, f, v.minute == 51))
        if "RMK" in mm and v.minute == 51 and v.hour % 6 == 5:
            gg = _SIX.search(mm.split("RMK", 1)[1])
            if gg:
                c = (1 if gg.group(1) == "0" else -1) * int(gg.group(2)) / 10
                end = v + pd.Timedelta(minutes=9)
                s_loc = end - pd.Timedelta(hours=6) + pd.Timedelta(hours=OFFSET)
                e_loc = end + pd.Timedelta(hours=OFFSET)
                if s_loc.date() == e_loc.date():
                    groups.append((v, s_loc.date(), c * 9 / 5 + 32))
    return obs, groups


def banked(day, local_hour, obs, groups):
    """(max, source, recent :51 trace) knowable at ``local_hour``:00 local on ``day``."""
    cut = pd.Timestamp(dt.datetime.combine(day, dt.time(local_hour, 0)), tz="UTC") \
        - pd.Timedelta(hours=OFFSET)
    inst = [(v, f) for v, f, _ in obs
            if v <= cut and (v + pd.Timedelta(hours=OFFSET)).date() == day]
    gs = [g for tv, gd, g in groups if tv <= cut and gd == day]
    if not inst and not gs:
        return None, None, []
    best_i = max((f for _, f in inst), default=None)
    best_g = max(gs, default=None)
    trace = [f for v, f, is51 in obs
             if is51 and v <= cut and (v + pd.Timedelta(hours=OFFSET)).date() == day][-4:]
    if best_g is not None and (best_i is None or best_g >= best_i):
        return best_g, "metar_6h_group", trace
    return best_i, "hourly_snapshot", trace


def falling_into_cutoff(day, obs):
    """True if the :51 trace is clearly declining through the 4 PM CLI validity cutoff."""
    cut = pd.Timestamp(dt.datetime.combine(day, dt.time(16, 0)), tz="UTC") \
        - pd.Timedelta(hours=OFFSET)
    t = [f for v, f, is51 in obs
         if is51 and v <= cut and (v + pd.Timedelta(hours=OFFSET)).date() == day][-3:]
    return len(t) == 3 and t[-1] < t[0] and t[-1] <= t[1]


def boot(rets):
    if len(rets) < 6:
        return None
    a = np.array(rets)
    rng = np.random.default_rng(0)
    b = np.array([rng.choice(a, len(a), replace=True).mean() for _ in range(4000)])
    return a.mean() * 100, np.percentile(b, 2.5) * 100, np.percentile(b, 97.5) * 100, \
        float((b <= 0).mean())


def main() -> int:
    log = {}
    for line in open(ROOT / "track_record/call_log.jsonl"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("city") in (None, "nyc") and r["target_date"] >= "2026-08-01" \
                and r.get("actual_high_f") is not None:
            log[dt.date.fromisoformat(r["target_date"])] = r

    print(f"loading obs for {len(log)} logged days ...", flush=True)
    obs, groups = load_obs(dt.date(2026, 8, 1), dt.date(2026, 8, 31))
    print(f"  {len(obs)} obs, {len(groups)} day-attributed groups", flush=True)

    print("loading settled Kalshi markets ...", flush=True)
    mkts = settled_by_day()
    print(f"  {sum(len(v) for v in mkts.values())} settled markets across {len(mkts)} days",
          flush=True)

    trades = {k: [] for k in ("MARKET_FAVOURITE", "GROUP_1351", "GROUP_1351_EDGE",
                              "PRELIM_ALL", "PRELIM_FALLING", "PRELIM_FALLING_DRY")}
    skipped = {"no_markets": 0, "no_prices": 0, "no_banked": 0}

    for day in sorted(log):
        settle = log[day]["actual_high_f"]
        wet = (log[day].get("precip_in") or 0) > 0.01
        ms = mkts.get(day, [])
        if not ms:
            skipped["no_markets"] += 1
            continue

        for hour, tag in ((14, "sig"), (17, "cli")):
            board = []
            for m in ms:
                rng_ = bucket_of(m.get("subtitle", "") or m.get("yes_sub_title", ""))
                if not rng_:
                    continue
                pr = candle_at(m["ticker"], m["close_time"], day, hour)
                if not pr:
                    continue
                board.append({"lo": rng_[0], "hi": rng_[1], "ask": pr[0], "bid": pr[1],
                              "won": rng_[0] <= settle <= rng_[1]})
            if not board:
                skipped["no_prices"] += 1
                continue
            # The benchmark must see the WHOLE board. Applying the strategy price cap to
            # it excluded genuine favourites priced above 90c and made "follow the
            # market" hit 39% -- impossible, and the tell that the cap was poisoning
            # every leg. Strategies keep the cap; the benchmark does not.
            ok = [b for b in board if MIN_P <= b["ask"] <= MAX_P]
            if tag == "sig":
                trades["MARKET_FAVOURITE"].append(max(board, key=lambda x: x["ask"]))
            if not ok:
                continue

            if tag == "sig":
                bmax, src, trace = banked(day, hour, obs, groups)
                if bmax is None:
                    skipped["no_banked"] += 1
                    continue
                o = post_peak.settlement_distribution("KNYC", bmax, hour,
                                                      recent_temps_f=trace,
                                                      observed_max_source=src)
                pmf = o.integer_probabilities or {}
                if pmf:
                    for b in ok:
                        b["p"] = sum(v for k, v in pmf.items() if b["lo"] <= k <= b["hi"])
                    top = max(ok, key=lambda x: x["p"])
                    trades["GROUP_1351"].append(top)
                    if top["p"] - top["ask"] >= EDGE:
                        trades["GROUP_1351_EDGE"].append(top)
            else:
                # Preliminary CLI: valid only as of 4 PM. Its reported max is the banked
                # value knowable at 16:00 from a continuous source.
                bmax, src, _ = banked(day, 16, obs, groups)
                if bmax is None:
                    continue
                implied = int(math.floor(bmax + 0.5))
                # Search the FULL board: by 17:00 the implied bucket is usually the
                # market favourite and frequently priced above the 90c strategy cap.
                # Filtering first dropped 25 of 30 days and left an unusable n=5.
                pick = next((b for b in board
                             if b["lo"] <= implied <= b["hi"] and b["ask"] >= MIN_P), None)
                if not pick:
                    continue
                trades["PRELIM_ALL"].append(pick)
                if falling_into_cutoff(day, obs):
                    trades["PRELIM_FALLING"].append(pick)
                    if not wet:
                        trades["PRELIM_FALLING_DRY"].append(pick)

    print(f"\nskipped: {skipped}\n")
    print(f"{'strategy':<20} {'bets':>5} {'hit':>6} {'final':>10} {'mean/bet':>10} "
          f"{'95% CI':>20} {'P(<=0)':>7}")
    print("-" * 82)
    out = {}
    for name, ts in trades.items():
        if not ts:
            print(f"{name:<20} {'0':>5}   never fired")
            out[name] = {"bets": 0}
            continue
        bank, rets, wins = START, [], 0
        for t in ts:
            unit = t["ask"] + fee(t["ask"])
            pnl = STAKE * ((1.0 if t["won"] else 0.0) / unit - 1.0)
            bank += pnl
            rets.append(pnl / STAKE)
            wins += int(t["won"])
        b = boot(rets)
        ci = f"[{b[1]:+.0f}, {b[2]:+.0f}]" if b else "n/a"
        mean = f"{b[0]:+.1f}%" if b else "n/a"
        ple = f"{b[3]:.2f}" if b else "n/a"
        print(f"{name:<20} {len(ts):>5} {wins/len(ts):>5.0%} {bank:>10,.2f} {mean:>10} "
              f"{ci:>20} {ple:>7}")
        out[name] = {"bets": len(ts), "hit_rate": round(wins / len(ts), 3),
                     "final": round(bank, 2),
                     "mean_pct": round(b[0], 2) if b else None,
                     "ci95": [round(b[1], 1), round(b[2], 1)] if b else None,
                     "p_le_0": round(b[3], 3) if b else None}
    (ROOT / "backtest_datasets/august_month_backtest.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote backtest_datasets/august_month_backtest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
