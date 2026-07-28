#!/usr/bin/env python3
"""Refit the wet/dry regime statistics in models/daily_strategy.py.

Joins the committed multi-year MOS series to GHCN daily precipitation per city and
reports warm-season (May-Sep) error statistics split by wet (prcp>0) vs dry days.
Paste the printed dict into REGIME_STATS.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OBS = {"nyc": "data/processed/observations_daily.csv",
       "phoenix": "data_phoenix/processed/observations_daily.csv",
       "vegas": "data_vegas/processed/observations_daily.csv"}


def main() -> int:
    out = {}
    print(f"{'city':8s} {'regime':6s} {'n':>5s} {'bias':>7s} {'MAE':>6s} {'P>=+2':>7s} {'P<=-2':>7s}")
    for city, op in OBS.items():
        m = pd.read_csv(ROOT / f"backtest_datasets/{city}_mos_multiyear.csv",
                        index_col=0, parse_dates=True)
        o = pd.read_csv(ROOT / op, low_memory=False)
        o["date"] = pd.to_datetime(o["date"])
        d = m.join(o.set_index("date")[["prcp_mm"]], how="inner")
        d["err"] = d["actual_tmax_f"] - d["mos_tmax_f"]
        d = d[d.index.month.isin([5, 6, 7, 8, 9])]
        out[city] = {}
        for lbl, s in (("wet", d[d.prcp_mm > 0]), ("dry", d[d.prcp_mm == 0])):
            out[city][lbl] = {"n": int(len(s)), "bias": round(float(s.err.mean()), 2),
                              "mae": round(float(s.err.abs().mean()), 2),
                              "p_warm2": round(float((s.err >= 2).mean()), 2),
                              "p_cool2": round(float((s.err <= -2).mean()), 2)}
            st = out[city][lbl]
            print(f"{city:8s} {lbl:6s} {st['n']:5d} {st['bias']:+7.2f} {st['mae']:6.2f} "
                  f"{st['p_warm2']*100:6.0f}% {st['p_cool2']*100:6.0f}%")
    print("\nREGIME_STATS =", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
