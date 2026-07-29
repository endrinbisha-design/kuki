#!/usr/bin/env python3
"""Conditional distribution post-processing: the bucket-probability upgrade.

Motivation: live bucket bets went 5/16 while the point forecast stayed accurate. Kalshi
pays on the INTEGER DISTRIBUTION, not the point. The literature answer is distributional
post-processing (EMOS, Gneiting et al. 2005; quantile-regression forests, Taillardat
2016; neural CRPS post-processing, Rasp & Lerch 2018): predict the full conditional
error distribution from forecast-time features instead of wrapping a fixed-width spread
around a point.

Our measured regime tables (wet/dry, hot-day) are crude two-bin versions of this. Here we
train, per city, gradient-boosting QUANTILE models of ``err = actual - MOS`` on
night-before-known features from the same 00Z MOS run (leakage-safe):

    mos_tmax, forecast PoP (max p12 across the target day), afternoon wind dir/speed,
    day-of-year harmonics, rolling 30d bias, rolling 30d error std

and convert the predicted quantiles into a round-half-up INTEGER PMF. Scored against the
status quo (rolling-bias point + Gaussian sigma fitted on training residuals) on integer
log-loss and 2-degree-bucket accuracy, expanding yearly folds 2019-2025.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backtest_datasets"
CACHE = OUT / "mos_raw"
CITIES = {"nyc": "KNYC", "phoenix": "KPHX", "vegas": "KLAS"}
QS = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
FEATS = ["mos", "pop", "wdr", "wsp", "doy_sin", "doy_cos", "bias_30d", "estd_30d"]


def load_mos_features(icao: str) -> pd.DataFrame:
    parts = [pd.read_csv(CACHE / f"{icao}_{y}.csv", low_memory=False) for y in range(2015, 2026)]
    df = pd.concat(parts, ignore_index=True)
    df["runtime"] = pd.to_datetime(df["runtime"], errors="coerce")
    df["ftime"] = pd.to_datetime(df["ftime"], errors="coerce")
    df = df[df["runtime"].dt.hour == 0]
    for c in ("n_x", "p12", "wdr", "wsp"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    day = df["runtime"].dt.normalize()
    # p12 periods END at 12Z same-day and 00Z next-day; include ftimes through +24h so the
    # afternoon PoP (ending next-day 00Z) is captured.
    window = df[(df["ftime"] > df["runtime"]) & (df["ftime"] <= df["runtime"] + pd.Timedelta(hours=24))]
    g = window.groupby(day[window.index])
    feats = pd.DataFrame({
        "pop": g["p12"].max(),
        "wdr": g.apply(lambda x: x.loc[x["ftime"].dt.hour.isin([18, 21]), "wdr"].mean(),
                       include_groups=False),
        "wsp": g.apply(lambda x: x.loc[x["ftime"].dt.hour.isin([18, 21]), "wsp"].mean(),
                       include_groups=False),
    })
    nx = df[(df["ftime"] - df["runtime"]).eq(pd.Timedelta(hours=24))
            & (df["ftime"].dt.hour == 0) & df["n_x"].notna()]
    s = nx.set_index(nx["runtime"].dt.normalize())["n_x"]
    feats["mos"] = s[~s.index.duplicated(keep="last")]
    return feats


def build(city: str, icao: str) -> pd.DataFrame:
    actual = pd.read_csv(OUT / f"{city}_mos_multiyear.csv", index_col=0, parse_dates=True)
    actual.index = actual.index.normalize()
    df = load_mos_features(icao).join(actual[["actual_tmax_f"]], how="inner").dropna(
        subset=["mos", "actual_tmax_f"])
    df["err"] = df["actual_tmax_f"] - df["mos"]
    doy = df.index.dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    hist = df["err"].shift(1)
    df["bias_30d"] = hist.rolling(30, min_periods=10).mean()
    df["estd_30d"] = hist.rolling(30, min_periods=10).std()
    return df.dropna(subset=FEATS)


def integer_logloss_from_quantiles(qpred: np.ndarray, mos: np.ndarray,
                                   actual: np.ndarray) -> tuple[float, float]:
    """CDF-interpolate quantiles -> integer PMF (round-half-up) -> log-loss & top2 hit."""
    losses, hits = [], []
    grid = np.arange(-15, 15.1, 0.1)
    for i in range(len(actual)):
        q = np.maximum.accumulate(qpred[i])           # enforce monotone quantiles
        cdf = np.interp(grid, q, QS, left=0.0, right=1.0)
        final = mos[i] + grid
        ints = np.round(final + 1e-9).astype(int)     # round-half-up on the grid
        pmf: dict[int, float] = {}
        dens = np.diff(np.concatenate([[0.0], cdf]))
        for k, p in zip(ints, dens):
            pmf[k] = pmf.get(k, 0.0) + p
        tot = sum(pmf.values()) or 1.0
        pmf = {k: v / tot for k, v in pmf.items()}
        a = int(np.round(actual[i] + 1e-9))
        losses.append(-np.log(max(pmf.get(a, 0.0), 1e-6)))
        top2 = sorted(pmf, key=pmf.get, reverse=True)[:2]
        hits.append(a in top2)
    return float(np.mean(losses)), float(np.mean(hits))


def gaussian_baseline(train: pd.DataFrame, test: pd.DataFrame) -> tuple[float, float]:
    from scipy.stats import norm
    sigma = float((train["err"] - train["bias_30d"]).std())
    losses, hits = [], []
    for _, r in test.iterrows():
        mu = r["mos"] + r["bias_30d"]
        ints = np.arange(int(mu) - 12, int(mu) + 13)
        p = norm.cdf(ints + 0.5, mu, sigma) - norm.cdf(ints - 0.5, mu, sigma)
        p = p / p.sum()
        a = int(np.round(r["actual_tmax_f"] + 1e-9))
        idx = np.where(ints == a)[0]
        losses.append(-np.log(max(float(p[idx][0]) if len(idx) else 0.0, 1e-6)))
        top2 = ints[np.argsort(p)[-2:]]
        hits.append(a in top2)
    return float(np.mean(losses)), float(np.mean(hits))


def emos_conditional(train: pd.DataFrame, test: pd.DataFrame) -> tuple[float, float]:
    """EMOS-style: Gaussian with GBM-regressed conditional mean AND sigma (Gneiting 2005)."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    from scipy.stats import norm
    m = HistGradientBoostingRegressor(max_depth=3, max_iter=200, learning_rate=0.06,
                                      random_state=42).fit(train[FEATS], train["err"])
    resid = train["err"] - m.predict(train[FEATS])
    s = HistGradientBoostingRegressor(max_depth=3, max_iter=150, learning_rate=0.06,
                                      random_state=42).fit(train[FEATS], resid.abs())
    mu_err = m.predict(test[FEATS])
    sig = np.maximum(s.predict(test[FEATS]) * np.sqrt(np.pi / 2), 0.8)
    losses, hits = [], []
    for i, (_, r) in enumerate(test.iterrows()):
        mu = r["mos"] + mu_err[i]
        ints = np.arange(int(mu) - 12, int(mu) + 13)
        p = norm.cdf(ints + 0.5, mu, sig[i]) - norm.cdf(ints - 0.5, mu, sig[i])
        p = p / p.sum()
        a = int(np.round(r["actual_tmax_f"] + 1e-9))
        idx = np.where(ints == a)[0]
        losses.append(-np.log(max(float(p[idx][0]) if len(idx) else 0.0, 1e-6)))
        hits.append(a in ints[np.argsort(p)[-2:]])
    return float(np.mean(losses)), float(np.mean(hits))


def main() -> int:
    from sklearn.ensemble import HistGradientBoostingRegressor
    results = {}
    for city, icao in CITIES.items():
        df = build(city, icao)
        gl, ql, gh, qh, n = [], [], [], [], 0
        el, eh = [], []
        for year in range(2019, 2026):
            tr, te = df[df.index.year < year], df[df.index.year == year]
            if len(tr) < 700 or len(te) < 100:
                continue
            qpred = np.column_stack([
                HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=3,
                                              max_iter=200, learning_rate=0.06,
                                              random_state=42)
                .fit(tr[FEATS], tr["err"]).predict(te[FEATS]) for q in QS])
            l_q, h_q = integer_logloss_from_quantiles(qpred, te["mos"].values,
                                                      te["actual_tmax_f"].values)
            l_g, h_g = gaussian_baseline(tr, te)
            l_e, h_e = emos_conditional(tr, te)
            ql.append(l_q * len(te)); gl.append(l_g * len(te))
            qh.append(h_q * len(te)); gh.append(h_g * len(te)); n += len(te)
            el.append(l_e * len(te)); eh.append(h_e * len(te))
            print(f"{city} {year}: n={len(te):4d}  logloss gauss {l_g:.3f} | quant {l_q:.3f} | "
                  f"EMOS {l_e:.3f}   top2 {h_g:.2f}|{h_q:.2f}|{h_e:.2f}", flush=True)
        results[city] = {
            "n": n,
            "logloss_gaussian_baseline": round(sum(gl) / n, 4),
            "logloss_conditional": round(sum(ql) / n, 4),
            "top2_gaussian": round(sum(gh) / n, 4),
            "top2_conditional": round(sum(qh) / n, 4),
            "logloss_emos": round(sum(el) / n, 4),
            "top2_emos": round(sum(eh) / n, 4),
        }
    (OUT / "conditional_distribution_backtest.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
