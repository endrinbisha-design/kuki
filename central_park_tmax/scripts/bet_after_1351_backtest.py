#!/usr/bin/env python3
"""Bankroll backtest: bet right after the 13:51 local observation, starting with $100.

The 13:51 EDT METAR is the first genuinely informative moment of a NYC day: it carries the
6-hour maximum group covering 8 AM - 2 PM, the first CONTINUOUS-source reading. Hourly :51
snapshots under-read the true max by a measured median of ~1.0 F at KNYC, so this is the
observation that tells you what is actually banked. On 2026-07-31 it read 84.02 F while
hourly had only reached 82.94 F, and the day's official peak (85 at 1:17 PM) sat inside
that window.

This asks the practical question: **if you traded that signal every day with $100, what
happened?**

Design, with the leakage rules that matter:

  * Signal time is 13:53 local (the ob lands 13:51, transmission takes a minute or two).
    Only snapshots at/before 13:51 and 6-hour groups TRANSMITTED by then are used. The
    afternoon group (18Z-00Z) does not exist until 19:51 local and is excluded.
  * Prices come from the candle CLOSING at 14:00 local — i.e. a fill about seven minutes
    after the signal, at the ask (we are buying), net of the Kalshi taker fee. Using the
    ask rather than the mid is what makes this a tradeable result rather than a paper one.
  * Only ``between`` markets (the 2-degree buckets).

Four rules are compared, because "did the model help?" is the whole question:

  MODEL_TOP       buy the bucket our model likes most
  MODEL_EDGE      buy only when model probability - ask clears a threshold
  MARKET_FAVOURITE buy the cheapest-to-be-favourite bucket the MARKET likes most
                  (the benchmark: following the price, using no model at all)
  MODEL_BEATS_MKT buy our top bucket only when it differs from the market's favourite
                  (isolates the days our model actually disagrees)

NYC only. The 13:51 timing is specific to UTC-4: at KPHX/KLAS (UTC-7) the same synoptic
report lands at 10:51 local, far too early to be the day's signal.
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
OUT = ROOT / "backtest_datasets"
sys.path.insert(0, str(ROOT / "src"))

from central_park_tmax.models.post_peak import (  # noqa: E402
    bucket_probability, settlement_distribution)

UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}
BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES, STATION, ICAO, OFFSET = "KXHIGHNY", "KNYC", "NYC", -4
SIGNAL_LOCAL_HOUR, SIGNAL_LOCAL_MIN = 13, 53
FILL_CANDLE_LOCAL_HOUR = 14          # candle closing at 14:00 local
START_BANKROLL = 100.0
STAKE_FRACTION = 0.20                # fraction of bankroll risked per qualifying day
EDGE_THRESHOLD = 0.10
_SIX = re.compile(r"\b1([01])(\d{3})\b")
_TICKER_DATE = re.compile(r"-(\d{2}[A-Z]{3}\d{2})-")


def _get(url: str) -> dict:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return {}


def fee_dollars(price: float) -> float:
    """Kalshi taker fee per contract: ceil(0.07 * P * (1-P)) cents."""
    return math.ceil(0.07 * price * (1 - price) * 100) / 100.0


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
        if mm and m.get("strike_type") == "between":
            out.setdefault(dt.datetime.strptime(mm.group(1), "%y%b%d").date(), []).append(m)
    return out


def fill_price(ticker: str, close_iso: str, day: dt.date) -> tuple[float, float] | None:
    """(ask, bid) from the candle closing at 14:00 local ON ``day`` — our fill.

    The exact timestamp is required, not merely "a candle whose local hour is 14". The
    36-hour lookback window contains TWO such candles (the market closes at 00:59 local
    the following day), and taking the first match silently used the PREVIOUS day's price:
    buying yesterday's cheap out-of-the-money buckets and settling them against today's
    outcome. That bug produced a $100 -> $4.2M backtest and a +207% mean return per bet,
    with the tell being that following the market's own favourite "won" only 29% of the
    time. Matching the target timestamp removes it.
    """
    try:
        end = int(dt.datetime.fromisoformat(close_iso.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None
    target = int((dt.datetime.combine(day, dt.time(FILL_CANDLE_LOCAL_HOUR, 0),
                                      tzinfo=dt.timezone.utc)
                  - dt.timedelta(hours=OFFSET)).timestamp())
    d = _get(f"{BASE}/series/{SERIES}/markets/{ticker}/candlesticks"
             f"?start_ts={end - 36*3600}&end_ts={end}&period_interval=60")
    for c in d.get("candlesticks", []):
        if c.get("end_period_ts") != target:
            continue
        try:
            a = (c.get("yes_ask") or {}).get("close_dollars")
            b = (c.get("yes_bid") or {}).get("close_dollars")
            if a in (None, "") or b in (None, ""):
                return None
            a, b = float(a), float(b)
            if 0 < a <= 1 and 0 <= b <= 1:
                return a, b
        except Exception:
            return None
    return None


def six_from_metar(metar: str) -> float | None:
    if not isinstance(metar, str):
        return None
    parts = metar.split(" RMK ", 1)
    if len(parts) < 2:
        return None
    m = _SIX.search(parts[1])
    if not m:
        return None
    c = int(m.group(2)) / 10.0
    return (-c if m.group(1) == "1" else c) * 9 / 5 + 32


def observations(start: dt.date, end: dt.date) -> pd.DataFrame:
    url = (f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={ICAO}"
           f"&data=tmpf&data=metar&tz=UTC&format=onlycomma&latlon=no&missing=M&trace=T"
           f"&report_type=3&report_type=4"
           f"&year1={start.year}&month1={start.month}&day1={start.day}"
           f"&year2={end.year}&month2={end.month}&day2={end.day}")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                raw = pd.read_csv(io.StringIO(r.read().decode()), low_memory=False)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  retry obs: {str(exc)[:60]}", flush=True)
            time.sleep(4 * (attempt + 1))
    else:
        return pd.DataFrame()
    raw["valid"] = pd.to_datetime(raw["valid"], errors="coerce", utc=True)
    raw["tmpf"] = pd.to_numeric(raw["tmpf"], errors="coerce")
    raw = raw.dropna(subset=["valid"]).sort_values("valid")
    raw["six"] = raw["metar"].map(six_from_metar)
    raw["day"] = (raw["valid"] + pd.Timedelta(hours=OFFSET)).dt.date
    end_utc = raw["valid"].dt.ceil("h")
    raw["grp_ok"] = (raw["six"].notna() & (end_utc.dt.hour % 6 == 0)
                     & ((end_utc - pd.Timedelta(hours=6) + pd.Timedelta(hours=OFFSET)).dt.date
                        == (end_utc + pd.Timedelta(hours=OFFSET)).dt.date))
    raw["grp_day"] = (end_utc + pd.Timedelta(hours=OFFSET)).dt.date
    return raw


def signal_state(obs: pd.DataFrame, day: dt.date):
    """(observed_max, source, trace) knowable at 13:53 local."""
    cutoff = (pd.Timestamp(dt.datetime.combine(day, dt.time(SIGNAL_LOCAL_HOUR,
                                                            SIGNAL_LOCAL_MIN)), tz="UTC")
              - pd.Timedelta(hours=OFFSET))
    snaps = obs[(obs["day"] == day) & (obs["valid"] <= cutoff) & obs["tmpf"].notna()]
    if snaps.empty:
        return None, None, []
    snap_max = float(snaps["tmpf"].max())
    grp = obs[obs["grp_ok"] & (obs["grp_day"] == day) & (obs["valid"] <= cutoff)]
    grp_max = float(grp["six"].max()) if not grp.empty else float("nan")
    if np.isfinite(grp_max) and grp_max > snap_max:
        return grp_max, "metar_6h_group", list(snaps["tmpf"].tail(4))
    return snap_max, "hourly_snapshot", list(snaps["tmpf"].tail(4))


def main() -> int:
    cache = OUT / "bet_after_1351_rows.json"
    if cache.exists() and "--refresh" not in sys.argv:
        rows = json.loads(cache.read_text())
        print(f"loaded {len(rows)} cached day-rows (use --refresh to refetch)", flush=True)
        return analyse(rows)
    by_day = settled_by_day()
    days = sorted(by_day)
    print(f"{SERIES}: {len(days)} settled days {days[0]} .. {days[-1]}", flush=True)
    obs = observations(days[0] - dt.timedelta(days=1), days[-1] + dt.timedelta(days=2))
    if obs.empty:
        print("no observations")
        return 1

    rows = []
    for day in days:
        omax, source, trace = signal_state(obs, day)
        if omax is None:
            continue
        outlook = settlement_distribution(STATION, omax, SIGNAL_LOCAL_HOUR,
                                          recent_temps_f=trace, observed_max_source=source)
        if not outlook.integer_probabilities:
            continue
        cands = []
        for m in by_day[day]:
            lo, hi = m.get("floor_strike"), m.get("cap_strike")
            if lo is None or hi is None:
                continue
            px = fill_price(m["ticker"], m.get("close_time", ""), day)
            time.sleep(0.10)
            if px is None:
                continue
            ask, bid = px
            if not (0.02 <= ask <= 0.98):
                continue
            cands.append({"bucket": f"{int(lo)}-{int(hi)}", "ask": ask, "bid": bid,
                          "p": bucket_probability(outlook, int(lo), int(hi)),
                          "won": (m.get("result") or "").lower() == "yes"})
        if not cands:
            continue
        rows.append({"date": day, "obs_max": omax, "source": source, "cands": cands})
        print(f"  {day} max={omax:.2f} ({source}) {len(cands)} quoted buckets", flush=True)

    if not rows:
        print("no tradeable days reconstructed")
        return 1
    (OUT / "bet_after_1351_rows.json").write_text(
        json.dumps([{**r, "date": str(r["date"])} for r in rows]))
    return analyse(rows)



# ---------------------------------------------------------------- rule + sizing --------
# "Reasonable" means three things the first version got wrong:
#   1. FLAT or KELLY staking, not 20% of bankroll every day. A -5% per-bet edge compounded
#      at 20% turned into -88% purely through volatility drag; sizing was doing more damage
#      than the signal.
#   2. A PRICE CAP. Buying the favourite at 95c to win 5c is not a bet, it is a fee. Any
#      sane rule declines to pay up for near-certainties.
#   3. PERMISSION TO SKIP. A strategy that must trade every day is not a strategy.
FLAT_STAKE = 10.0          # dollars risked per qualifying day
KELLY_FRACTION = 0.25      # quarter-Kelly; full Kelly on 68 noisy days is reckless
MAX_PRICE = 0.90           # never pay above this
MIN_PRICE = 0.05


def pick(cands, rule):
    """Choose one contract to buy, or None to sit out."""
    ok = [c for c in cands if MIN_PRICE <= c["ask"] <= MAX_PRICE]
    if not ok:
        return None
    if rule == "MARKET_FAVOURITE":
        return max(ok, key=lambda x: x["ask"])
    best = max(ok, key=lambda x: x["p"] - x["ask"])
    edge = best["p"] - best["ask"]
    if rule == "EDGE_05":
        return best if edge >= 0.05 else None
    if rule == "EDGE_15":
        return best if edge >= 0.15 else None
    if rule == "EDGE_25":
        return best if edge >= 0.25 else None
    if rule == "LOCK":
        # only when the banked observation makes a bucket near-certain AND it is not
        # already priced as such: the arithmetic bet, not the forecast bet.
        lock = [c for c in ok if c["p"] >= 0.90 and c["ask"] <= c["p"] - 0.05]
        return max(lock, key=lambda x: x["p"] - x["ask"]) if lock else None
    return None


def stake_for(rule_sizing, bank, sel):
    if rule_sizing == "flat":
        return min(FLAT_STAKE, bank)
    p, cost = sel["p"], sel["ask"] + fee_dollars(sel["ask"])
    b = (1.0 - cost) / cost if cost > 0 else 0.0          # net odds received
    k = (p * (b + 1) - 1) / b if b > 0 else 0.0           # Kelly fraction
    return max(0.0, min(bank * max(k, 0.0) * KELLY_FRACTION, bank))


def analyse(rows) -> int:
    rules = ["EDGE_05", "EDGE_15", "EDGE_25", "LOCK", "MARKET_FAVOURITE"]
    results = {}
    print(f"\n=== ${START_BANKROLL:.0f} start | fill at the ASK, net of fees | "
          f"price capped at {MAX_PRICE:.0%} | {len(rows)} days ===")
    for sizing in ("flat", "kelly"):
        lab = f"flat ${FLAT_STAKE:.0f}" if sizing == "flat" else f"{KELLY_FRACTION:.2f}-Kelly"
        print(f"\n-- staking: {lab} --")
        print(f"  {'rule':17} {'final':>10} {'bets':>5} {'hit':>6} {'maxDD':>7} "
              f"{'mean/bet':>9} {'CI95':>20} {'P(<=0)':>7}")
        for rule in rules:
            bank, peak, mdd, n, wins = START_BANKROLL, START_BANKROLL, 0.0, 0, 0
            rets = []
            for r in rows:
                sel = pick(r["cands"], rule)
                if sel is None:
                    continue
                stake = stake_for(sizing, bank, sel)
                if stake <= 0.01:
                    continue
                unit = sel["ask"] + fee_dollars(sel["ask"])
                payout = (stake / unit) * (1.0 if sel["won"] else 0.0)
                bank = bank - stake + payout
                rets.append((1.0 if sel["won"] else 0.0) / unit - 1.0)
                n += 1
                wins += int(sel["won"])
                peak = max(peak, bank)
                mdd = max(mdd, (peak - bank) / peak)
            if n == 0:
                print(f"  {rule:17} {'no qualifying bets':>10}")
                results[f"{sizing}:{rule}"] = {"n": 0}
                continue
            a = np.array(rets)
            rng = np.random.default_rng(0)
            boots = np.array([rng.choice(a, size=len(a), replace=True).mean()
                              for _ in range(4000)])
            lo, hi = np.percentile(boots, [2.5, 97.5])
            results[f"{sizing}:{rule}"] = {
                "final_bankroll": round(bank, 2), "n_bets": n,
                "hit_rate": round(wins / n, 3), "max_drawdown_pct": round(mdd * 100, 1),
                "mean_bet_return_pct": round(float(a.mean()) * 100, 2),
                "ci95_pct": [round(float(lo) * 100, 2), round(float(hi) * 100, 2)],
                "p_le_0": round(float((boots <= 0).mean()), 3)}
            print(f"  {rule:17} ${bank:>9,.2f} {n:>5} {wins/n:>6.2f} {mdd*100:>6.1f}% "
                  f"{a.mean()*100:>+8.2f}% {f'[{lo*100:+.1f},{hi*100:+.1f}]':>20} "
                  f"{(boots<=0).mean():>7.2f}")
    (OUT / "bet_after_1351_backtest.json").write_text(json.dumps(results, indent=1))
    print(f"\nwrote {OUT/'bet_after_1351_backtest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
