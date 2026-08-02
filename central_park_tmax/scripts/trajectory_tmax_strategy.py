#!/usr/bin/env python3
"""Estimate the day's max from the :51 hourly reports — measured against real history.

The :51 METAR trace is the one input we have proven we read correctly and on time
(kalshi_settlement_validation.py: 204/204). This script asks how much of the day's maximum
is *predictable* from that trace at each decision hour, over warm seasons 2019-2026 —
hundreds of days, not the 68 the Kalshi-era backtests were stuck with.

Estimators, all leakage-safe at decision hour h (only :51 snapshots at/before h and 6-hour
groups TRANSMITTED by then; the 8am-2pm group exists only from 13:51):

  CLIMO   running max + the training years' median remaining rise for hour h.
          This is what models/post_peak.py does today — the incumbent.
  RIDGE   linear model on [T_h, 3h rise, running max, day-of-year harmonics].
  ANALOG  k-nearest historical days by the shape of the :51 trace (z-scored temps at
          7:51..h:51, day-of-year proximity). Prediction = median of the neighbours'
          actual maxima. Regime is handled implicitly: a muggy stalled morning finds
          other muggy stalled mornings, without us hand-labelling wet/dry.
  MOS     the 00Z MOS n_x day-max (cached, backtest_datasets/mos_raw) — knowable from
          ~1am, uses NO intraday data. The control: if trajectory methods cannot beat a
          static overnight forecast, the :51 reports add nothing.
  MOS+TRAJ ridge on the MOS forecast PLUS the trajectory features — the natural blend.

Truth = the day's settlement-grade max: all instantaneous reports plus day-attributed
6-hour groups (the reconstruction validated against 204/204 Kalshi settlements).

Split: fit on 2019-2023, score on 2024-2026. Scores: MAE, bias, P(|err|<=1), and the
2-degree-bucket hit rate (the Kalshi-relevant number).

Output: backtest_datasets/trajectory_tmax.json (+ printed summary).
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backtest_datasets"
CACHE = OUT / "knyc_hourly_2019_2026.csv"
MOS_RAW = OUT / "mos_raw"
UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}

YEARS = range(2019, 2027)
MONTHS = (5, 9)                      # warm season, matching every other study here
TRAIN_MAX_YEAR = 2023                # fit 2019-2023, score 2024-2026
DECISION_HOURS = (9, 11, 13)         # local :51 decision points
TRACE_HOURS = (7, 8, 9, 10, 11, 12, 13)
K_NEIGHBOURS = 25
OFFSET = -4
_SIX = re.compile(r"\b1([01])(\d{3})\b")


def fetch_year(year: int) -> pd.DataFrame:
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=NYC"
           "&data=tmpf&data=metar&tz=UTC&format=onlycomma&latlon=no&missing=M&trace=T"
           "&report_type=3&report_type=4"
           f"&year1={year}&month1={MONTHS[0]}&day1=1&year2={year}&month2={MONTHS[1]}&day2=30")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=240) as r:
                return pd.read_csv(io.StringIO(r.read().decode()), low_memory=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  retry {year}: {str(exc)[:60]}", flush=True)
            time.sleep(4 * (attempt + 1))
    return pd.DataFrame()


def six_from_metar(metar) -> float | None:
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


def load_obs() -> pd.DataFrame:
    if CACHE.exists():
        raw = pd.read_csv(CACHE, low_memory=False)
    else:
        parts = []
        for y in YEARS:
            df = fetch_year(y)
            print(f"  {y}: {len(df)} obs", flush=True)
            if not df.empty:
                parts.append(df)
        raw = pd.concat(parts, ignore_index=True)
        raw.to_csv(CACHE, index=False)
    raw["valid"] = pd.to_datetime(raw["valid"], errors="coerce", utc=True)
    raw["tmpf"] = pd.to_numeric(raw["tmpf"], errors="coerce")
    raw = raw.dropna(subset=["valid"]).sort_values("valid")
    raw["six"] = raw["metar"].map(six_from_metar)
    local = raw["valid"] + pd.Timedelta(hours=OFFSET)
    raw["day"] = local.dt.date
    raw["lhour"] = local.dt.hour
    end_utc = raw["valid"].dt.ceil("h")
    raw["grp_ok"] = (raw["six"].notna() & (end_utc.dt.hour % 6 == 0)
                     & ((end_utc - pd.Timedelta(hours=6) + pd.Timedelta(hours=OFFSET)).dt.date
                        == (end_utc + pd.Timedelta(hours=OFFSET)).dt.date))
    raw["grp_day"] = (end_utc + pd.Timedelta(hours=OFFSET)).dt.date
    return raw


def build_days(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per day: :51 temps, groups (with transmission hour), settlement max."""
    # settlement-grade truth: snapshots + day-attributed groups
    snap_max = raw.groupby("day")["tmpf"].max()
    grp_max = raw[raw["grp_ok"]].groupby("grp_day")["six"].max()
    rows = []
    hourly = raw[raw["valid"].dt.minute == 51]        # the :51 reports specifically
    by_day = {d: g for d, g in hourly.groupby("day")}
    for day, g in by_day.items():
        temps = {}
        for h in TRACE_HOURS:
            v = g.loc[g["lhour"] == h, "tmpf"]
            temps[f"t{h}"] = float(v.iloc[0]) if len(v) else np.nan
        sm = snap_max.get(day, np.nan)
        gm = grp_max.get(day, np.nan)
        truth = np.nanmax([sm, gm])
        if not np.isfinite(truth):
            continue
        # groups transmitted by each decision hour (07:51 carries 2-8am; 13:51 8am-2pm)
        g_morning = raw[(raw["grp_ok"]) & (raw["grp_day"] == day)
                        & (raw["lhour"] <= 8) & (raw["six"].notna())]["six"].max()
        g_midday = raw[(raw["grp_ok"]) & (raw["grp_day"] == day)
                       & (raw["lhour"].between(13, 14)) & (raw["six"].notna())]["six"].max()
        rows.append({"day": day, **temps, "grp_by_9": g_morning,
                     "grp_by_13plus": g_midday, "tmax": float(truth)})
    df = pd.DataFrame(rows)
    df["day"] = pd.to_datetime(df["day"])
    doy = df["day"].dt.dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["year"] = df["day"].dt.year
    return df


def runmax_at(df: pd.DataFrame, h: int) -> pd.Series:
    cols = [f"t{k}" for k in TRACE_HOURS if k <= h]
    rm = df[cols].max(axis=1)
    rm = np.fmax(rm, df["grp_by_9"].fillna(-99))
    if h >= 13:
        rm = np.fmax(rm, df["grp_by_13plus"].fillna(-99))
    return rm


def load_mos() -> pd.Series:
    """00Z-run MOS day-max (n_x at +24h) per day, from the cached IEM files."""
    parts = []
    for f in sorted(MOS_RAW.glob("KNYC_*.csv")):
        parts.append(pd.read_csv(f, low_memory=False))
    if not parts:
        return pd.Series(dtype=float)
    m = pd.concat(parts, ignore_index=True)
    m["runtime"] = pd.to_datetime(m["runtime"], errors="coerce")
    m["ftime"] = pd.to_datetime(m["ftime"], errors="coerce")
    m = m[(m["runtime"].dt.hour == 0)]
    m["n_x"] = pd.to_numeric(m["n_x"], errors="coerce")
    sel = m[(m["ftime"] - m["runtime"]).eq(pd.Timedelta(hours=24))
            & (m["ftime"].dt.hour == 0) & m["n_x"].notna()]
    s = sel.set_index(sel["runtime"].dt.normalize())["n_x"]
    return s[~s.index.duplicated(keep="last")]


def score(pred: np.ndarray, truth: np.ndarray) -> dict:
    err = pred - truth
    ok = np.isfinite(err)
    err = err[ok]
    pi = np.round(pred[ok] + 1e-9)
    ti = np.round(truth[ok] + 1e-9)
    # Kalshi 2-degree buckets are anchored on even integers (80-81, 82-83, ...):
    bucket_hit = (np.floor(pi / 2) == np.floor(ti / 2)).mean()
    return {"n": int(err.size), "mae": round(float(np.abs(err).mean()), 3),
            "bias": round(float(err.mean()), 3),
            "p_within_1f": round(float((np.abs(err) <= 1.0).mean()), 3),
            "bucket_hit": round(float(bucket_hit), 3)}


def main() -> int:
    raw = load_obs()
    df = build_days(raw)
    mos = load_mos()
    df["mos"] = df["day"].dt.normalize().map(mos)
    print(f"{len(df)} days built ({df['year'].min()}-{df['year'].max()}); "
          f"MOS available for {df['mos'].notna().sum()}")

    train = df[df["year"] <= TRAIN_MAX_YEAR].copy()
    test = df[df["year"] > TRAIN_MAX_YEAR].copy()
    print(f"train {len(train)} days (2019-{TRAIN_MAX_YEAR}), test {len(test)} days\n")
    results: dict = {}

    from sklearn.linear_model import Ridge

    for h in DECISION_HOURS:
        need = [f"t{k}" for k in TRACE_HOURS if k <= h]
        tr = train.dropna(subset=need + ["tmax"]).copy()
        te = test.dropna(subset=need + ["tmax"]).copy()
        tr_rm, te_rm = runmax_at(tr, h), runmax_at(te, h)
        truth = te["tmax"].to_numpy()
        res: dict = {}

        # CLIMO — incumbent: runmax + train-median remaining rise
        med_rise = float((tr["tmax"] - tr_rm).clip(lower=0).median())
        res["CLIMO"] = score(te_rm.to_numpy() + med_rise, truth)

        # RIDGE — trajectory features only
        def feats(d, rm):
            f = pd.DataFrame(index=d.index)
            f["rm"] = rm
            f["t_now"] = d[f"t{h}"]
            f["rise3"] = d[f"t{h}"] - d[f"t{max(h-3, TRACE_HOURS[0])}"]
            f["doy_sin"], f["doy_cos"] = d["doy_sin"], d["doy_cos"]
            return f
        Xtr, Xte = feats(tr, tr_rm), feats(te, te_rm)
        r = Ridge(alpha=1.0).fit(Xtr, tr["tmax"])
        res["RIDGE"] = score(r.predict(Xte), truth)

        # ANALOG — k-NN on the z-scored :51 trace + season
        Ztr = tr[need].to_numpy()
        mu, sd = np.nanmean(Ztr, axis=0), np.nanstd(Ztr, axis=0) + 1e-9
        Ztr = (Ztr - mu) / sd
        Zte = (te[need].to_numpy() - mu) / sd
        Str = tr[["doy_sin", "doy_cos"]].to_numpy() * 1.5     # season weight
        Ste = te[["doy_sin", "doy_cos"]].to_numpy() * 1.5
        preds = np.empty(len(te))
        tmax_tr = tr["tmax"].to_numpy()
        for i in range(len(te)):
            d2 = ((Ztr - Zte[i]) ** 2).sum(axis=1) + ((Str - Ste[i]) ** 2).sum(axis=1)
            idx = np.argpartition(d2, K_NEIGHBOURS)[:K_NEIGHBOURS]
            preds[i] = np.median(tmax_tr[idx])
        # an analog prediction can never undercut what is already banked
        preds = np.fmax(preds, te_rm.to_numpy())
        res["ANALOG"] = score(preds, truth)

        # MOS — static overnight forecast, no intraday data (control)
        mos_te = te["mos"].to_numpy()
        res["MOS"] = score(np.where(np.isfinite(mos_te), mos_te, np.nan), truth)

        # MOS + trajectory blend
        both_tr = tr.dropna(subset=["mos"])
        both_te = te.dropna(subset=["mos"])
        if len(both_tr) > 100 and len(both_te) > 30:
            Xtr2 = feats(both_tr, runmax_at(both_tr, h)); Xtr2["mos"] = both_tr["mos"]
            Xte2 = feats(both_te, runmax_at(both_te, h)); Xte2["mos"] = both_te["mos"]
            r2 = Ridge(alpha=1.0).fit(Xtr2, both_tr["tmax"])
            res["MOS+TRAJ"] = score(r2.predict(Xte2), both_te["tmax"].to_numpy())

        results[f"{h}:51"] = res
        print(f"=== decision {h}:51 EDT (test n={len(te)}) ===")
        for k, v in res.items():
            print(f"  {k:9} MAE {v['mae']:5.2f}  bias {v['bias']:+5.2f}  "
                  f"P(|err|<=1) {v['p_within_1f']:.0%}  bucket-hit {v['bucket_hit']:.0%}")
        print()

    (OUT / "trajectory_tmax.json").write_text(json.dumps(results, indent=1))
    print(f"wrote {OUT/'trajectory_tmax.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
