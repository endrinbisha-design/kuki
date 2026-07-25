#!/usr/bin/env python3
"""Fit/refresh the per-city hot-day error statistics in models/hot_day_calibration.py.

Reads the committed multi-year MOS series and reports, for each city, the error
distribution on hot days (forecast >= the city's 90th-percentile forecast). Re-run this
after extending the archive; paste the printed table into HOT_DAY_STATS.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "backtest_datasets"


def main() -> int:
    print(f"{'city':8s} {'thresh':>7s} {'n':>4s} {'median':>7s} {'mean':>6s} "
          f"{'P>=+2':>6s} {'P<=-2':>6s}")
    stats = {}
    for city in ("nyc", "phoenix", "vegas"):
        d = pd.read_csv(OUT / f"{city}_mos_multiyear.csv", index_col=0, parse_dates=True)
        d["err"] = d["actual_tmax_f"] - d["mos_tmax_f"]
        thr = float(d["mos_tmax_f"].quantile(0.90))
        s = d[d["mos_tmax_f"] >= thr]
        stats[city] = {
            "hot_threshold_f": round(thr, 1),
            "median_err_f": round(float(s["err"].median()), 1),
            "p_warm_2f": round(float((s["err"] >= 2).mean()), 2),
            "p_cool_2f": round(float((s["err"] <= -2).mean()), 2),
            "n": int(len(s)),
        }
        st = stats[city]
        print(f"{city:8s} {thr:7.1f} {len(s):4d} {st['median_err_f']:+7.1f} "
              f"{s['err'].mean():+6.2f} {st['p_warm_2f']*100:5.0f}% {st['p_cool_2f']*100:5.0f}%")
    print("\nHOT_DAY_STATS =", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
