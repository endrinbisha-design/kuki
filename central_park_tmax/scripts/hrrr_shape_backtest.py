#!/usr/bin/env python3
"""Case-control backtest of the HRRR afternoon-shape sea-breeze signal (piece 4).

Design (SEA_BREEZE.md): all marine-cap bust days (label=1) 2018-2025 plus an equal
number of month-matched control days. For each day, fetch the HRRR morning-run hourly
afternoon trace (issued_before = 15Z => the 12Z run, an honest intraday vintage) and
distill afternoon_shape_features. Appends one CSV row per day (checkpoint: resumes by
skipping days already present). Verdict analysis runs at the end (or standalone with
--analyze) once enough rows exist.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "backtest_datasets" / "hrrr_shape_backtest.csv"


def pick_days() -> pd.DataFrame:
    frame = pd.read_csv(ROOT / "backtest_datasets" / "nyc_seabreeze_frame.csv",
                        index_col=0, parse_dates=True)
    frame = frame[frame.index.year >= 2018]          # HRRRv3+ only
    busts = frame[frame["label"] == 1]
    rng = np.random.default_rng(42)
    controls = []
    for (year, month), grp in busts.groupby([busts.index.year, busts.index.month]):
        pool = frame[(frame.index.year == year) & (frame.index.month == month)
                     & (frame["label"] == 0)]
        take = min(len(grp), len(pool))
        if take:
            controls.append(pool.iloc[sorted(rng.choice(len(pool), take, replace=False))])
    sel = pd.concat([busts, *controls]).sort_index()
    return sel[["mos_cp", "actual_cp", "bust_cp", "label"]]


def run_fetch() -> None:
    import logging, warnings
    logging.disable(logging.WARNING); warnings.filterwarnings("ignore")
    from central_park_tmax.config import load_config
    from central_park_tmax.data.hrrr_hourly import fetch_afternoon_trace, afternoon_shape_features

    cfg = load_config(ROOT / "configs")
    days = pick_days()
    done = set()
    if OUT.exists():
        done = set(pd.read_csv(OUT)["date"].astype(str))
    print(f"{len(days)} selected days ({int(days['label'].sum())} busts); {len(done)} already fetched",
          flush=True)
    for ts, row in days.iterrows():
        d = ts.date()
        if str(d) in done:
            continue
        issued = datetime(d.year, d.month, d.day, 15, 0, tzinfo=timezone.utc)  # 12Z run
        try:
            trace = fetch_afternoon_trace(cfg, d, issued_before_utc=issued)
            feats = afternoon_shape_features(trace) if trace is not None else {}
        except Exception as exc:  # noqa: BLE001
            print(f"  {d}: FAIL {str(exc)[:80]}", flush=True)
            feats = {}
        rec = {"date": str(d), "label": int(row["label"]), "bust_cp": row["bust_cp"],
               "mos_cp": row["mos_cp"], "actual_cp": row["actual_cp"], **feats}
        pd.DataFrame([rec]).to_csv(OUT, mode="a", header=not OUT.exists(), index=False)
        print(f"  {d}: label={rec['label']} {feats if feats else '(no trace)'}", flush=True)


def analyze() -> None:
    df = pd.read_csv(OUT)
    ok = df.dropna(subset=["hrrr_peak_hour_local"])
    print(f"rows {len(df)}, with trace {len(ok)}, busts {int(ok['label'].sum())}")
    if len(ok) < 40:
        print("not enough rows yet"); return
    cap = ok[ok["hrrr_sees_cap"] == True]           # noqa: E712
    nocap = ok[ok["hrrr_sees_cap"] != True]         # noqa: E712
    print(f"hrrr_sees_cap days : {len(cap):3d}  bust rate {cap['label'].mean()*100:.0f}%  mean bust {cap['bust_cp'].mean():+.2f}F")
    print(f"no-cap days        : {len(nocap):3d}  bust rate {nocap['label'].mean()*100:.0f}%  mean bust {nocap['bust_cp'].mean():+.2f}F")
    try:
        from sklearn.metrics import roc_auc_score
        for col in ("hrrr_onshore_hours", "hrrr_cp_jfk_gap_pm_f", "hrrr_afternoon_range_f"):
            s = ok.dropna(subset=[col])
            sign = -1 if col == "hrrr_afternoon_range_f" else 1
            print(f"AUC({col:24s}) = {roc_auc_score(s['label'], sign*s[col]):.3f}")
    except Exception:
        pass


if __name__ == "__main__":
    if "--analyze" in sys.argv:
        analyze()
    else:
        run_fetch()
        analyze()
