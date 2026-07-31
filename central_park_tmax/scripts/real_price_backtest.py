#!/usr/bin/env python3
"""Post-peak strategy backtest at REAL Kalshi prices — closing the simulated-market gap.

Every ROI figure in this repo except EDGE_DECAY.md has been against a simulated market:
we priced our own probability, assumed we could trade against it, and reported the edge.
That is circular. This script replaces the simulated market with the actual order book,
using the public candlesticks endpoint on settled markets (no credentials, no lookahead).

Only the OBSERVATION-ANCHORED strategy is backtested here, because it is the only one we
can reconstruct honestly for this window: our MOS feature archive stops at 2026-01-01,
while the Kalshi settled history is 2026-05-24 onward. A forecast-driven backtest over
these days would require refitting guidance we do not have, so it is deliberately omitted
rather than faked.

LEAKAGE DISCIPLINE is the whole game here, and it is stricter than it looks:

  * Hourly/SPECI snapshots are usable at their observation time.
  * A 6-hour maximum group is usable only from its TRANSMISSION time (:51 of the synoptic
    hour), and only if its period lies inside the local day (LESSONS.md #10). This is what
    makes the afternoon genuinely blind: at 15h local the 23:51Z group does not exist yet.
  * Prices come from the candle covering that same local hour.

For each city-day and each decision hour we ask the post-peak tool for the settled-integer
distribution given ONLY what was knowable then, compare it to the real mid price of each
2-degree bucket, and take the position when the edge clears a threshold. P&L is settled
against the market's actual result, net of the Kalshi taker fee.

Output: backtest_datasets/real_price_backtest.json (+ printed summary).
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
from collections import defaultdict
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

# Kalshi series -> (IEM station, station shorthand, local UTC offset in the warm season)
CITIES = {
    "KXHIGHNY": ("NYC", "KNYC", -4),
    "KXHIGHTPHX": ("PHX", "KPHX", -7),
    "KXHIGHTLV": ("LAS", "KLAS", -7),
}
DECISION_HOURS = [13, 14, 15, 16, 17, 18]
EDGE_THRESHOLDS = [0.05, 0.10, 0.15]
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


def fee_cents(price: float) -> float:
    """Kalshi taker fee, ceil(0.07 * C * P * (1-P)) cents per contract (C=1)."""
    return math.ceil(0.07 * price * (1 - price) * 100) / 100.0


def settled_markets(series: str) -> dict[dt.date, list[dict]]:
    rows, cursor, pages = [], None, 0
    while pages < 40:
        url = f"{BASE}/markets?series_ticker={series}&status=settled&limit=1000"
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
    by_day: dict[dt.date, list[dict]] = defaultdict(list)
    for m in rows:
        mm = _TICKER_DATE.search(m["ticker"])
        if mm and m.get("strike_type") == "between":
            by_day[dt.datetime.strptime(mm.group(1), "%y%b%d").date()].append(m)
    return by_day


def hourly_prices(series: str, ticker: str, close_iso: str, offset: int) -> dict[int, float]:
    """local hour -> mid price, from the candle covering that hour."""
    try:
        end = int(dt.datetime.fromisoformat(close_iso.replace("Z", "+00:00")).timestamp())
    except Exception:
        return {}
    d = _get(f"{BASE}/series/{series}/markets/{ticker}/candlesticks"
             f"?start_ts={end - 36*3600}&end_ts={end}&period_interval=60")
    out: dict[int, float] = {}
    for c in d.get("candlesticks", []):
        ts = c.get("end_period_ts")
        if ts is None:
            continue
        p = None
        try:
            b = c.get("yes_bid", {}).get("close_dollars")
            a = c.get("yes_ask", {}).get("close_dollars")
            if b not in (None, "") and a not in (None, ""):
                b, a = float(b), float(a)
                if 0 <= b <= 1 and 0 <= a <= 1 and a >= b:
                    p = (a + b) / 2
            if p is None:
                v = c.get("price", {}).get("close_dollars")
                if v not in (None, ""):
                    p = float(v)
        except Exception:
            p = None
        if p is None:
            continue
        out[(dt.datetime.fromtimestamp(ts, dt.timezone.utc)
             + dt.timedelta(hours=offset)).hour] = p
    return out


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


def observations(station: str, offset: int, start: dt.date, end: dt.date) -> pd.DataFrame:
    url = (f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={station}"
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
            print(f"  retry {station}: {str(exc)[:60]}", flush=True)
            time.sleep(4 * (attempt + 1))
    else:
        return pd.DataFrame()
    raw["valid"] = pd.to_datetime(raw["valid"], errors="coerce", utc=True)
    raw["tmpf"] = pd.to_numeric(raw["tmpf"], errors="coerce")
    raw = raw.dropna(subset=["valid"]).sort_values("valid")
    raw["six"] = raw["metar"].map(six_from_metar)
    raw["local"] = raw["valid"] + pd.Timedelta(hours=offset)
    raw["day"] = raw["local"].dt.date
    # Period bounds for any 6-hour group, used for both the day-attribution rule and the
    # transmission-time (leakage) rule.
    end_utc = raw["valid"].dt.ceil("h")
    raw["grp_ok"] = (raw["six"].notna() & (end_utc.dt.hour % 6 == 0)
                     & ((end_utc - pd.Timedelta(hours=6) + pd.Timedelta(hours=offset)).dt.date
                        == (end_utc + pd.Timedelta(hours=offset)).dt.date))
    raw["grp_day"] = (end_utc + pd.Timedelta(hours=offset)).dt.date
    return raw


def knowable_state(obs: pd.DataFrame, day: dt.date, hour: int, offset: int):
    """(observed_max_f, source, recent trace) using ONLY data transmitted by `hour` local."""
    cutoff = pd.Timestamp(dt.datetime.combine(day, dt.time(hour, 0)), tz="UTC") \
        - pd.Timedelta(hours=offset)
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
    trades: list[dict] = []
    for series, (station, shorthand, offset) in CITIES.items():
        by_day = settled_markets(series)
        if not by_day:
            continue
        days = sorted(by_day)
        obs = observations(station, offset, days[0] - dt.timedelta(days=1),
                           days[-1] + dt.timedelta(days=2))
        if obs.empty:
            print(f"{series}: no observations")
            continue
        print(f"{series}: {len(days)} days, {sum(len(v) for v in by_day.values())} markets",
              flush=True)

        for day in days:
            markets = by_day[day]
            prices = {}
            for m in markets:
                prices[m["ticker"]] = hourly_prices(series, m["ticker"],
                                                    m.get("close_time", ""), offset)
                time.sleep(0.12)
            for hour in DECISION_HOURS:
                omax, source, trace = knowable_state(obs, day, hour, offset)
                if omax is None:
                    continue
                outlook = settlement_distribution(shorthand, omax, hour,
                                                  recent_temps_f=trace,
                                                  observed_max_source=source)
                if not outlook.integer_probabilities:
                    continue
                for m in markets:
                    lo, hi = m.get("floor_strike"), m.get("cap_strike")
                    if lo is None or hi is None:
                        continue
                    price = prices.get(m["ticker"], {}).get(hour)
                    if price is None or not (0.03 <= price <= 0.97):
                        continue
                    p = bucket_probability(outlook, int(lo), int(hi))
                    won = (m.get("result") or "").lower() == "yes"
                    trades.append({
                        "series": series, "date": str(day), "hour": hour,
                        "bucket": f"{int(lo)}-{int(hi)}", "price": price,
                        "model_p": p, "edge": p - price, "won": won,
                        "determined": outlook.determined, "source": source})

    if not trades:
        print("no trades reconstructed")
        return 1
    df = pd.DataFrame(trades)

    def roi(sub: pd.DataFrame) -> dict:
        if sub.empty:
            return {"n": 0}
        cost = sub["price"] + sub["price"].map(fee_cents)
        payout = sub["won"].astype(float)
        pnl = payout - cost
        return {"n": int(len(sub)), "hit_rate": round(float(sub["won"].mean()), 4),
                "mean_price": round(float(sub["price"].mean()), 4),
                "roi_pct": round(float(pnl.sum() / cost.sum() * 100), 2),
                "pnl_per_contract_c": round(float(pnl.mean() * 100), 2)}

    # Trades are NOT independent: the same city-day supplies up to 4 buckets x 6 hours of
    # near-identical information. Significance must be assessed by resampling city-days,
    # not rows, or n=380 will masquerade as 380 independent bets.
    df["cluster"] = df["series"] + "_" + df["date"]

    def cluster_bootstrap(sub: pd.DataFrame, iters: int = 4000) -> dict:
        if sub.empty:
            return {}
        cost = sub["price"] + sub["price"].map(fee_cents)
        pnl = sub["won"].astype(float) - cost
        w = sub.assign(_c=cost, _p=pnl).set_index("cluster")
        clusters = sub["cluster"].unique()
        rng = np.random.default_rng(0)
        boots = []
        for _ in range(iters):
            s = w.loc[rng.choice(clusters, size=len(clusters), replace=True)]
            boots.append(s["_p"].sum() / s["_c"].sum() * 100)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        return {"roi_ci95": [round(float(lo), 2), round(float(hi), 2)],
                "p_roi_le_0": round(float((np.array(boots) <= 0).mean()), 3),
                "n_city_days": int(len(clusters))}

    results: dict = {"n_candidate_quotes": int(len(df)), "by_threshold": {}}
    print(f"\n{len(df)} price/probability observations reconstructed\n")
    print("=== BUY when model edge exceeds threshold (real prices, net of fees) ===")
    for thr in EDGE_THRESHOLDS:
        sel = df[df["edge"] >= thr]
        r = roi(sel)
        r.update(cluster_bootstrap(sel))
        results["by_threshold"][str(thr)] = r
        print(f"  edge >= {thr:.0%}: ROI {r['roi_pct']:+.2f}% "
              f"CI95 {r.get('roi_ci95')} P(ROI<=0)={r.get('p_roi_le_0')} "
              f"n={r['n']} over {r.get('n_city_days')} city-days")

    print("\n=== BY DECISION HOUR (edge >= 10%) ===")
    results["by_hour"] = {}
    for h in DECISION_HOURS:
        r = roi(df[(df["edge"] >= 0.10) & (df["hour"] == h)])
        results["by_hour"][str(h)] = r
        print(f"  {h:02d}h local: {r}")

    print("\n=== DETERMINED vs NOT (edge >= 10%) ===")
    results["by_determined"] = {}
    for flag in (True, False):
        r = roi(df[(df["edge"] >= 0.10) & (df["determined"] == flag)])
        results["by_determined"][str(flag)] = r
        print(f"  determined={flag}: {r}")

    print("\n=== BY CITY (edge >= 10%) ===")
    results["by_city"] = {}
    for s in CITIES:
        r = roi(df[(df["edge"] >= 0.10) & (df["series"] == s)])
        results["by_city"][s] = r
        print(f"  {s}: {r}")

    print("\n=== CALIBRATION: model probability vs realised frequency ===")
    results["calibration"] = []
    for lo in np.arange(0.0, 1.0, 0.2):
        sub = df[(df["model_p"] >= lo) & (df["model_p"] < lo + 0.2)]
        if len(sub) < 20:
            continue
        row = {"bin": f"{lo:.1f}-{lo+0.2:.1f}", "n": int(len(sub)),
               "mean_model_p": round(float(sub["model_p"].mean()), 3),
               "realised": round(float(sub["won"].mean()), 3),
               "mean_market_price": round(float(sub["price"].mean()), 3)}
        results["calibration"].append(row)
        print(f"  model {row['bin']}: n={row['n']:5d}  model {row['mean_model_p']:.3f}  "
              f"actual {row['realised']:.3f}  market {row['mean_market_price']:.3f}")

    df.to_csv(OUT / "real_price_backtest_trades.csv", index=False)
    (OUT / "real_price_backtest.json").write_text(json.dumps(results, indent=1))
    print(f"\nwrote {OUT/'real_price_backtest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
