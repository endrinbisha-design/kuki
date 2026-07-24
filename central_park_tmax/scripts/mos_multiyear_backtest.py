#!/usr/bin/env python3
"""Multi-year MOS-based backtest for NYC / Phoenix / Las Vegas.

Motivation (see MULTI_CITY_COMPARISON.md): the NBM/GRIB backtest window is only
184 days, which is too thin to train/evaluate the ML robustly. IEM archives GFS-MOS
text guidance back ~15+ years and serves it in bulk CSV, with the day-max forecast
in the ``n_x`` field — orders of magnitude faster to fetch than GRIB.

Design:
  * Baseline = GFS-MOS 00Z run ("night-before": 00Z = 8 PM EDT / 5 PM MST the prior
    local evening — leakage-safe for next-day max).
  * MOS X/N convention: the ``n_x`` value with ftime at 00Z of day D+1 is the
    daytime-max forecast for local day D (verified against Phoenix Aug 2024 heat).
  * Labels = GHCN-Daily final tmax (already built per city). NOTE: GHCN is the
    research label, not the CLI settlement value; adequate for model comparison.
  * Candidates per city (same trio as the NBM backtest):
      raw_mos           : the MOS number as-is
      rolling_bias_30d  : MOS + mean of last 30 available (label - MOS) errors
      boosting_ml       : GradientBoosting on leakage-safe features
  * Validation: expanding-window yearly folds (train <= year-1, test = year).

Fetches are cached to <city>_mos_raw/ so re-runs are cheap; the derived per-day
forecast series and the results JSON/markdown land in backtest_datasets/.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "backtest_datasets"
CACHE_DIR = OUT_DIR / "mos_raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UA = "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"
BULK_URL = ("https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py"
            "?station={icao}&model=GFS&sts={y1}-01-01T00:00Z&ets={y2}-01-01T00:00Z&format=csv")

CITIES = {
    "nyc":     {"icao": "KNYC", "labels": ROOT / "data/processed/observations_daily.csv",
                "utc_offset_h": -5},   # ET (DST-aware not needed at daily granularity)
    "phoenix": {"icao": "KPHX", "labels": ROOT / "data_phoenix/processed/observations_daily.csv",
                "utc_offset_h": -7},
    "vegas":   {"icao": "KLAS", "labels": ROOT / "data_vegas/processed/observations_daily.csv",
                "utc_offset_h": -8},
}

START_YEAR, END_YEAR = 2015, 2025   # inclusive test coverage 2016..2025


def fetch_year(icao: str, year: int) -> pd.DataFrame:
    """One calendar year of bulk GFS-MOS CSV for a station (cached)."""
    cache = CACHE_DIR / f"{icao}_{year}.csv"
    if cache.exists() and cache.stat().st_size > 1000:
        return pd.read_csv(cache, low_memory=False)
    url = BULK_URL.format(icao=icao, y1=year, y2=year + 1)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                text = resp.read().decode("utf-8", "replace")
            if not text.startswith("runtime"):
                raise RuntimeError(f"unexpected payload head: {text[:80]!r}")
            cache.write_text(text)
            return pd.read_csv(cache, low_memory=False)
        except Exception as exc:  # noqa: BLE001
            wait = 3 * (attempt + 1)
            print(f"    fetch {icao} {year} failed ({exc}); retry in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"could not fetch {icao} {year}")


def nightly_max_series(mos: pd.DataFrame) -> pd.Series:
    """target_date -> night-before MOS max forecast (deg F).

    Use the 00Z run of target_date (issued the prior local evening across CONUS)
    and read n_x at ftime == 00Z of target_date+1 (MOS daytime-max convention).
    """
    df = mos.copy()
    df["runtime"] = pd.to_datetime(df["runtime"], errors="coerce")
    df["ftime"] = pd.to_datetime(df["ftime"], errors="coerce")
    df["n_x"] = pd.to_numeric(df["n_x"], errors="coerce")
    df = df[(df["runtime"].dt.hour == 0) & df["n_x"].notna()]
    # keep rows where ftime is exactly runtime + 24h at 00Z -> daytime max of run day
    sel = df[(df["ftime"] - df["runtime"]).eq(pd.Timedelta(hours=24)) & (df["ftime"].dt.hour == 0)]
    out = sel.set_index(sel["runtime"].dt.date)["n_x"]
    return out[~out.index.duplicated(keep="last")].sort_index()


def load_labels(path: Path) -> pd.Series:
    obs = pd.read_csv(path)
    obs["date"] = pd.to_datetime(obs["date"]).dt.date
    s = obs.set_index("date")["tmax_f"]
    return s[s.notna()]


def build_frame(city: str, cfg: dict) -> pd.DataFrame:
    parts = []
    for year in range(START_YEAR, END_YEAR + 1):
        parts.append(fetch_year(cfg["icao"], year))
        time.sleep(1.0)   # be polite to IEM
    fc = nightly_max_series(pd.concat(parts, ignore_index=True))
    labels = load_labels(cfg["labels"])
    df = pd.DataFrame({"mos_tmax_f": fc}).join(pd.DataFrame({"actual_tmax_f": labels}), how="inner")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df["error"] = df["actual_tmax_f"] - df["mos_tmax_f"]     # label minus forecast
    # QC: drop absurd values (parse glitches)
    df = df[(df["mos_tmax_f"].between(-30, 130)) & (df["actual_tmax_f"].between(-30, 130))]
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Leakage-safe features: everything is shifted so day D uses info through D-1."""
    out = df.copy()
    doy = out.index.dayofyear
    out["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    out["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    err_hist = out["error"].shift(1)                          # last settled day's error
    out["bias_30d"] = err_hist.rolling(30, min_periods=10).mean()
    out["bias_7d"] = err_hist.rolling(7, min_periods=3).mean()
    out["err_std_30d"] = err_hist.rolling(30, min_periods=10).std()
    out["yesterday_actual"] = out["actual_tmax_f"].shift(1)
    out["yesterday_mos"] = out["mos_tmax_f"].shift(1)
    out["mos_change_1d"] = out["mos_tmax_f"] - out["yesterday_mos"]
    return out


FEATURES = ["mos_tmax_f", "doy_sin", "doy_cos", "bias_30d", "bias_7d",
            "err_std_30d", "yesterday_actual", "mos_change_1d"]


def evaluate_city(city: str, cfg: dict) -> dict:
    from sklearn.ensemble import HistGradientBoostingRegressor

    print(f"== {city} ({cfg['icao']}) ==", flush=True)
    df = add_features(build_frame(city, cfg))
    (OUT_DIR / f"{city}_mos_multiyear.csv").write_text(
        df[["mos_tmax_f", "actual_tmax_f"]].to_csv())
    results = {"n_days": int(len(df)),
               "date_range": [str(df.index.min().date()), str(df.index.max().date())],
               "folds": {}, "pooled": {}}

    preds = {"raw_mos": [], "rolling_bias_30d": [], "boosting_ml": []}
    truths = []
    for year in range(START_YEAR + 1, END_YEAR + 1):
        train = df[df.index.year < year].dropna(subset=FEATURES + ["error"])
        test = df[df.index.year == year].dropna(subset=FEATURES + ["error"])
        if len(train) < 365 or len(test) < 60:
            continue
        model = HistGradientBoostingRegressor(
            max_depth=3, learning_rate=0.05, max_iter=300,
            l2_regularization=1.0, random_state=42)
        model.fit(train[FEATURES], train["error"])           # predict the residual
        ml = test["mos_tmax_f"] + np.clip(model.predict(test[FEATURES]), -15, 15)

        fold = {}
        for name, p in (("raw_mos", test["mos_tmax_f"]),
                        ("rolling_bias_30d", test["mos_tmax_f"] + test["bias_30d"]),
                        ("boosting_ml", ml)):
            err = (test["actual_tmax_f"] - p)
            fold[name] = {"mae": round(float(err.abs().mean()), 3),
                          "bias": round(float(err.mean()), 3),
                          "pct_within_2f": round(float((err.abs() <= 2).mean() * 100), 1)}
            preds[name].append(pd.Series(p, index=test.index))
        truths.append(test["actual_tmax_f"])
        fold["n"] = int(len(test))
        results["folds"][str(year)] = fold
        print(f"  {year}: n={len(test):3d}  raw {fold['raw_mos']['mae']:.2f}  "
              f"bias {fold['rolling_bias_30d']['mae']:.2f}  ml {fold['boosting_ml']['mae']:.2f}",
              flush=True)

    truth = pd.concat(truths)
    for name in preds:
        p = pd.concat(preds[name])
        err = truth - p
        results["pooled"][name] = {
            "mae": round(float(err.abs().mean()), 3),
            "rmse": round(float(np.sqrt((err ** 2).mean())), 3),
            "bias": round(float(err.mean()), 3),
            "pct_within_2f": round(float((err.abs() <= 2).mean() * 100), 1),
            "n": int(len(err)),
        }
    return results


def main() -> int:
    all_results = {}
    for city, cfg in CITIES.items():
        all_results[city] = evaluate_city(city, cfg)
    out = OUT_DIR / "mos_multiyear_backtest.json"
    out.write_text(json.dumps(all_results, indent=1))
    print(f"\nwrote {out}")
    for city, r in all_results.items():
        p = r["pooled"]
        print(f"{city:8s} n={p['raw_mos']['n']:5d}  raw {p['raw_mos']['mae']:.2f}  "
              f"bias30 {p['rolling_bias_30d']['mae']:.2f}  ml {p['boosting_ml']['mae']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
