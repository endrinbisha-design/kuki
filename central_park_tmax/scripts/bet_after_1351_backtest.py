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


def fill_price(ticker: str, close_iso: str) -> tuple[float, float] | None:
    """(ask, bid) from the candle closing at 14:00 local — our fill, ~7 min post-signal."""
    try:
        end = int(dt.datetime.fromisoformat(close_iso.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None
    d = _get(f"{BASE}/series/{SERIES}/markets/{ticker}/candlesticks"
             f"?start_ts={end - 36*3600}&end_ts={end}&period_interval=60")
    for c in d.get("candlesticks", []):
        ts = c.get("end_period_ts")
        if ts is None:
            continue
        lt = dt.datetime.fromtimestamp(ts, dt.timezone.utc) + dt.timedelta(hours=OFFSET)
        if lt.hour != FILL_CANDLE_LOCAL_HOUR:
            continue
        try:
            a = (c.get("yes_ask") or {}).get("close_dollars")
            b = (c.get("yes_bid") or {}).get("close_dollars")
            if a in (None, "") or b in (None, ""):
                continue
            a, b = float(a), float(b)
            if 0 < a <= 1 and 0 <= b <= 1:
                return a, b
        except Exception:
            continue
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
            px = fill_price(m["ticker"], m.get("close_time", ""))
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

    def pick(day_row, rule):
        c = day_row["cands"]
        model_top = max(c, key=lambda x: x["p"])
        mkt_fav = max(c, key=lambda x: x["ask"])
        if rule == "MODEL_TOP":
            return model_top
        if rule == "MODEL_EDGE":
            best = max(c, key=lambda x: x["p"] - x["ask"])
            return best if (best["p"] - best["ask"]) >= EDGE_THRESHOLD else None
        if rule == "MARKET_FAVOURITE":
            return mkt_fav
        if rule == "MODEL_BEATS_MKT":
            return model_top if model_top["bucket"] != mkt_fav["bucket"] else None
        return None

    results = {}
    print(f"\n=== $100 bankroll, {STAKE_FRACTION:.0%} of bankroll staked per qualifying day, "
          f"filled at the ASK, net of fees ===")
    for rule in ("MODEL_TOP", "MODEL_EDGE", "MARKET_FAVOURITE", "MODEL_BEATS_MKT"):
        bank, peak, mdd, n, wins, curve = START_BANKROLL, START_BANKROLL, 0.0, 0, 0, []
        daily = []
        for r in rows:
            sel = pick(r, rule)
            if sel is None:
                curve.append(bank)
                continue
            stake = bank * STAKE_FRACTION
            unit = sel["ask"] + fee_dollars(sel["ask"])
            contracts = stake / unit
            payout = contracts * (1.0 if sel["won"] else 0.0)
            before = bank
            bank = bank - stake + payout
            daily.append((bank - before) / before)
            n += 1
            wins += int(sel["won"])
            peak = max(peak, bank)
            mdd = max(mdd, (peak - bank) / peak)
            curve.append(bank)
        results[rule] = {"final_bankroll": round(bank, 2), "n_bets": n,
                         "win_rate": round(wins / n, 3) if n else None,
                         "max_drawdown_pct": round(mdd * 100, 1),
                         "total_return_pct": round((bank / START_BANKROLL - 1) * 100, 1)}
        r = results[rule]
        print(f"  {rule:17} ${r['final_bankroll']:>9,.2f}  ({r['total_return_pct']:+7.1f}%)  "
              f"bets={r['n_bets']:3}  hit={r['win_rate']}  maxDD={r['max_drawdown_pct']}%")

    # Day-clustered bootstrap on the per-bet return, the honest error bar.
    print("\n=== bootstrap over days (per-bet return) ===")
    for rule in results:
        rets = []
        b = START_BANKROLL
        for r in rows:
            sel = pick(r, rule)
            if sel is None:
                continue
            unit = sel["ask"] + fee_dollars(sel["ask"])
            rets.append((1.0 if sel["won"] else 0.0) / unit - 1.0)
        if len(rets) < 10:
            print(f"  {rule:17} too few bets ({len(rets)})")
            results[rule]["mean_bet_return_pct"] = None
            continue
        a = np.array(rets)
        rng = np.random.default_rng(0)
        boots = [rng.choice(a, size=len(a), replace=True).mean() for _ in range(4000)]
        lo, hi = np.percentile(boots, [2.5, 97.5])
        results[rule].update({"mean_bet_return_pct": round(float(a.mean()) * 100, 2),
                              "ci95_pct": [round(float(lo) * 100, 2), round(float(hi) * 100, 2)],
                              "p_le_0": round(float((np.array(boots) <= 0).mean()), 3)})
        print(f"  {rule:17} mean {a.mean()*100:+6.2f}% per bet  "
              f"CI95 [{lo*100:+.1f}%, {hi*100:+.1f}%]  P(<=0)={(np.array(boots)<=0).mean():.2f}  "
              f"n={len(a)}")

    (OUT / "bet_after_1351_backtest.json").write_text(json.dumps(results, indent=1))
    print(f"\nwrote {OUT/'bet_after_1351_backtest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
