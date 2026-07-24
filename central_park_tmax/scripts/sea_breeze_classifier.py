#!/usr/bin/env python3
"""Sea-breeze / marine-cap day classifier for Central Park (KNYC).

Trains on 2015-2025 warm seasons (May-Sep) using ONLY night-before-known inputs:

  * KNYC GFS-MOS 00Z max forecast (from the committed multi-year series)
  * KJFK GFS-MOS 00Z max forecast -> forecast land/coastal gradient
  * KNYC MOS afternoon wind (18Z/21Z wdr/wsp from the same 00Z run):
      onshore sector for CP is ~[90, 200] deg (SE through S; see features/wind.py)
  * NY-Harbor-entrance buoy 44065 sea-surface temperature (daily mean, prior day)
      -> land-sea thermal contrast = forecast_max - SST
  * seasonality (day-of-year harmonics)

Label ("marine-cap / cool-bust day"): actual CP max underperformed the night-before
MOS forecast by >= 2.5 F. In the warm season at KNYC this bust mode is dominated by
marine-air intrusion; the classifier learns WHICH forecast days carry that risk.

Validation: expanding yearly folds (test 2018-2025). Outputs AUC/Brier, top-decile
lift, a demonstration MAE fix (conditional shift on flagged days), a distilled
logistic model for live use, and the full daily frame for reuse.
"""
from __future__ import annotations

import gzip
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backtest_datasets"
CACHE = OUT / "mos_raw"
UA = {"User-Agent": "central_park_tmax/0.1 (research; endrinsberisha@gmail.com)"}

ONSHORE_LO, ONSHORE_HI = 90, 200      # deg; SE-S marine sector for KNYC
BUST_THRESHOLD_F = -2.5


def _get(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def buoy_sst_daily() -> pd.Series:
    """Daily-mean water temp (F) at NDBC 44065 (NY Harbor entrance), 2015-present."""
    cache = CACHE / "ndbc_44065_sst_daily.csv"
    if cache.exists():
        s = pd.read_csv(cache, index_col=0, parse_dates=True)["sst_f"]
        return s
    frames = []
    for year in range(2015, 2026):
        try:
            raw = _get("https://www.ndbc.noaa.gov/view_text_file.php"
                       f"?filename=44065h{year}.txt.gz&dir=data/historical/stdmet/")
            if raw.lstrip().startswith("<"):
                raise RuntimeError("html error page")
        except Exception:
            # current / partial year lives under realtime or monthly files; skip quietly
            continue
        df = pd.read_csv(io.StringIO(raw), sep=r"\s+", skiprows=[1], na_values=["MM", 999, 99.0, 999.0])
        df = df.rename(columns={"#YY": "YY"})
        ts = pd.to_datetime(dict(year=df["YY"], month=df["MM"], day=df["DD"]), errors="coerce")
        wt = pd.to_numeric(df["WTMP"], errors="coerce")
        wt = wt.where(wt.between(-5, 40))
        frames.append(pd.DataFrame({"date": ts, "wtmp_c": wt}))
        time.sleep(0.5)
    allb = pd.concat(frames).dropna()
    daily = allb.groupby(allb["date"].dt.normalize())["wtmp_c"].mean()
    sst_f = daily * 9 / 5 + 32
    sst_f.name = "sst_f"
    sst_f.to_frame().to_csv(cache)
    return sst_f


def mos_nightly_max(icao: str) -> pd.Series:
    parts = []
    for year in range(2015, 2026):
        f = CACHE / f"{icao}_{year}.csv"
        parts.append(pd.read_csv(f, low_memory=False))
    df = pd.concat(parts, ignore_index=True)
    df["runtime"] = pd.to_datetime(df["runtime"], errors="coerce")
    df["ftime"] = pd.to_datetime(df["ftime"], errors="coerce")
    df["n_x"] = pd.to_numeric(df["n_x"], errors="coerce")
    df = df[(df["runtime"].dt.hour == 0) & df["n_x"].notna()]
    sel = df[(df["ftime"] - df["runtime"]).eq(pd.Timedelta(hours=24)) & (df["ftime"].dt.hour == 0)]
    out = sel.set_index(sel["runtime"].dt.normalize())["n_x"]
    return out[~out.index.duplicated(keep="last")].sort_index()


def mos_afternoon_wind() -> pd.DataFrame:
    """KNYC 00Z-run wdr/wsp at 18Z and 21Z of the run day (forecast afternoon wind)."""
    parts = []
    for year in range(2015, 2026):
        parts.append(pd.read_csv(CACHE / f"KNYC_{year}.csv", low_memory=False))
    df = pd.concat(parts, ignore_index=True)
    df["runtime"] = pd.to_datetime(df["runtime"], errors="coerce")
    df["ftime"] = pd.to_datetime(df["ftime"], errors="coerce")
    df = df[df["runtime"].dt.hour == 0]
    df = df[df["ftime"].dt.hour.isin([18, 21]) &
            (df["ftime"].dt.normalize() == df["runtime"].dt.normalize())]
    df["wdr"] = pd.to_numeric(df["wdr"], errors="coerce")
    df["wsp"] = pd.to_numeric(df["wsp"], errors="coerce")
    g = df.groupby(df["runtime"].dt.normalize())
    out = pd.DataFrame({
        "wdr_pm": g["wdr"].mean(),          # crude circular-mean shortcut; sector test below
        "wsp_pm": g["wsp"].mean(),
        "onshore_pm": g.apply(lambda x: float(((x["wdr"] >= ONSHORE_LO) & (x["wdr"] <= ONSHORE_HI)).mean()),
                              include_groups=False),
    })
    return out


def ghcn_tmax(path: Path) -> pd.Series:
    df = pd.read_csv(path, low_memory=False)
    dcol = "DATE" if "DATE" in df.columns else "date"
    tcol = "TMAX" if "TMAX" in df.columns else "tmax_f"
    s = pd.to_numeric(df[tcol], errors="coerce")
    if s.dropna().abs().median() > 200:       # NCEI wide CSV stores tenths of deg C
        s = s / 10 * 9 / 5 + 32
    elif s.dropna().abs().median() < 60:      # deg C
        s = s * 9 / 5 + 32
    out = pd.Series(s.values, index=pd.to_datetime(df[dcol]).dt.normalize())
    return out[out.notna() & out.between(-30, 120)].sort_index()


def build_frame() -> pd.DataFrame:
    nyc = pd.read_csv(OUT / "nyc_mos_multiyear.csv", index_col=0, parse_dates=True)
    nyc.index = nyc.index.normalize()
    jfk_mos = mos_nightly_max("KJFK")
    wind = mos_afternoon_wind()
    sst = buoy_sst_daily()
    jfk_obs = ghcn_tmax(CACHE / "USW00094789.csv")

    df = nyc.rename(columns={"mos_tmax_f": "mos_cp", "actual_tmax_f": "actual_cp"}).copy()
    df["mos_jfk"] = jfk_mos
    df["grad_fc"] = df["mos_cp"] - df["mos_jfk"]
    df = df.join(wind)
    df["sst_f"] = sst.reindex(df.index).ffill(limit=3).shift(1)   # last known water temp
    df["contrast"] = df["mos_cp"] - df["sst_f"]
    df["actual_jfk"] = jfk_obs
    doy = df.index.dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["bust_cp"] = df["actual_cp"] - df["mos_cp"]
    df["bust_jfk"] = df["actual_jfk"] - df["mos_jfk"]
    df["label"] = (df["bust_cp"] <= BUST_THRESHOLD_F).astype(int)
    warm = df[df.index.month.isin([5, 6, 7, 8, 9])].dropna(
        subset=["mos_cp", "actual_cp", "grad_fc", "wsp_pm", "onshore_pm", "contrast"])
    return warm


FEATS = ["mos_cp", "grad_fc", "wdr_pm", "wsp_pm", "onshore_pm", "contrast",
         "doy_sin", "doy_cos"]


def main() -> int:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score, brier_score_loss
    from sklearn.preprocessing import StandardScaler

    df = build_frame()
    df.to_csv(OUT / "nyc_seabreeze_frame.csv")
    print(f"frame: {len(df)} warm-season days {df.index.min().date()}..{df.index.max().date()}; "
          f"base bust rate {df['label'].mean()*100:.1f}%")

    res = {"n_days": int(len(df)), "base_rate": round(float(df["label"].mean()), 4), "folds": {}}
    probs, labels, busts, fold_of = [], [], [], []
    for year in range(2018, 2026):
        tr = df[df.index.year < year]
        te = df[df.index.year == year]
        if len(te) < 60:
            continue
        sc = StandardScaler().fit(tr[FEATS])
        lo = LogisticRegression(max_iter=1000, C=1.0).fit(sc.transform(tr[FEATS]), tr["label"])
        gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=250,
                                            random_state=42).fit(tr[FEATS], tr["label"])
        p = 0.5 * lo.predict_proba(sc.transform(te[FEATS]))[:, 1] + 0.5 * gb.predict_proba(te[FEATS])[:, 1]
        auc = roc_auc_score(te["label"], p) if te["label"].nunique() > 1 else float("nan")
        res["folds"][str(year)] = {"n": int(len(te)), "auc": round(float(auc), 3),
                                   "brier": round(float(brier_score_loss(te['label'], p)), 4)}
        print(f"  {year}: n={len(te):3d} AUC={auc:.3f}")
        probs.extend(p); labels.extend(te["label"]); busts.extend(te["bust_cp"]); fold_of.extend([year]*len(te))

    probs = np.array(probs); labels = np.array(labels); busts = np.array(busts)
    res["pooled_auc"] = round(float(roc_auc_score(labels, probs)), 3)
    res["pooled_brier"] = round(float(brier_score_loss(labels, probs)), 4)

    # Lift & a demonstration correction: shift flagged days down by the flagged-day mean bust.
    q = np.quantile(probs, 0.85)
    flag = probs >= q
    res["top15pct"] = {
        "threshold": round(float(q), 3),
        "bust_rate_flagged": round(float(labels[flag].mean()), 3),
        "bust_rate_unflagged": round(float(labels[~flag].mean()), 3),
        "mean_bust_f_flagged": round(float(busts[flag].mean()), 2),
        "mean_bust_f_unflagged": round(float(busts[~flag].mean()), 2),
    }
    mae_raw = float(np.abs(busts).mean())
    shift = busts[flag].mean()          # in-sample of pooled OOS; demonstration only
    adj = busts.copy(); adj[flag] -= shift
    res["warm_season_mae"] = {"raw_mos": round(mae_raw, 3),
                              "with_flag_shift_demo": round(float(np.abs(adj).mean()), 3)}

    # Distilled live model: logistic on ALL years (for the live advisory).
    sc = StandardScaler().fit(df[FEATS])
    lo = LogisticRegression(max_iter=1000, C=1.0).fit(sc.transform(df[FEATS]), df["label"])
    res["live_logistic"] = {
        "features": FEATS,
        "means": [round(float(v), 4) for v in sc.mean_],
        "scales": [round(float(v), 4) for v in sc.scale_],
        "coef": [round(float(v), 4) for v in lo.coef_[0]],
        "intercept": round(float(lo.intercept_[0]), 4),
        "flag_threshold": round(float(q), 3),
        "flagged_mean_shift_f": round(float(shift), 2),
    }
    (OUT / "sea_breeze_classifier.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "live_logistic"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
