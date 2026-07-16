"""Evaluation metrics for continuous, quantile, integer, and contract forecasts."""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np


# --------------------------------------------------------------------------------------
# Continuous
# --------------------------------------------------------------------------------------
def continuous_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    mask = ~(np.isnan(a) | np.isnan(p))
    a, p = a[mask], p[mask]
    if a.size == 0:
        return {"n": 0}
    err = p - a
    abs_err = np.abs(err)
    out = {
        "n": int(a.size),
        "mae": float(np.mean(abs_err)),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mean_error": float(np.mean(err)),
        "median_abs_error": float(np.median(abs_err)),
        "max_abs_error": float(np.max(abs_err)),
        "pct_within_1f": float(np.mean(abs_err <= 1.0) * 100),
        "pct_within_2f": float(np.mean(abs_err <= 2.0) * 100),
        "pct_within_3f": float(np.mean(abs_err <= 3.0) * 100),
    }
    if a.size >= 2 and np.std(a) > 0 and np.std(p) > 0:
        out["pearson_r"] = float(np.corrcoef(a, p)[0, 1])
        out["spearman_r"] = float(_spearman(a, p))
    return out


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = _rankdata(a)
    rb = _rankdata(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def _rankdata(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(len(x))
    # average ties
    _, inv, counts = np.unique(x, return_inverse=True, return_counts=True)
    cum = np.zeros(len(counts))
    # simple average-rank for ties
    sorted_idx = np.argsort(x, kind="mergesort")
    sx = x[sorted_idx]
    r = np.arange(len(x), dtype=float)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and sx[j + 1] == sx[i]:
            j += 1
        r[i:j + 1] = np.mean(r[i:j + 1])
        i = j + 1
    out = np.empty(len(x))
    out[sorted_idx] = r
    return out


# --------------------------------------------------------------------------------------
# Quantile / probabilistic
# --------------------------------------------------------------------------------------
def pinball_loss(actual: np.ndarray, quantile_pred: np.ndarray, q: float) -> float:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(quantile_pred, dtype=float)
    diff = a - p
    return float(np.mean(np.maximum(q * diff, (q - 1) * diff)))


def interval_coverage(actual: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    a = np.asarray(actual, dtype=float)
    return float(np.mean((a >= np.asarray(lower)) & (a <= np.asarray(upper))))


def interval_width(lower: np.ndarray, upper: np.ndarray) -> float:
    return float(np.mean(np.asarray(upper, dtype=float) - np.asarray(lower, dtype=float)))


def crps_from_samples(actual: float, samples: np.ndarray) -> float:
    """CRPS via the empirical-sample estimator (energy form)."""
    s = np.asarray(samples, dtype=float)
    n = s.size
    if n == 0:
        return float("nan")
    term1 = np.mean(np.abs(s - actual))
    term2 = 0.5 * np.mean(np.abs(s[:, None] - s[None, :])) if n <= 4000 else 0.5 * _crps_term2_fast(s)
    return float(term1 - term2)


def _crps_term2_fast(s: np.ndarray) -> float:
    s = np.sort(s)
    n = s.size
    i = np.arange(1, n + 1)
    return float(2.0 / n ** 2 * np.sum((2 * i - n - 1) * s))


# --------------------------------------------------------------------------------------
# Integer-outcome / classification
# --------------------------------------------------------------------------------------
def log_loss_integer(pmf: Mapping[int, float], actual_int: int, eps: float = 1e-12) -> float:
    return float(-np.log(max(pmf.get(int(actual_int), 0.0), eps)))


def ranked_probability_score(pmf: Mapping[int, float], actual_int: int) -> float:
    """Discrete RPS: sum over thresholds of (CDF_pred - CDF_obs)^2."""
    ks = sorted(pmf.keys())
    lo, hi = min(ks + [actual_int]), max(ks + [actual_int])
    cum_p = 0.0
    rps = 0.0
    for k in range(lo, hi + 1):
        cum_p += pmf.get(k, 0.0)
        cum_o = 1.0 if actual_int <= k else 0.0
        rps += (cum_p - cum_o) ** 2
    return float(rps)


def brier_score(prob: np.ndarray, outcome: np.ndarray) -> float:
    p = np.asarray(prob, dtype=float)
    o = np.asarray(outcome, dtype=float)
    mask = ~(np.isnan(p) | np.isnan(o))
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean((p[mask] - o[mask]) ** 2))


def log_loss_binary(prob: np.ndarray, outcome: np.ndarray, eps: float = 1e-12) -> float:
    p = np.clip(np.asarray(prob, dtype=float), eps, 1 - eps)
    o = np.asarray(outcome, dtype=float)
    mask = ~np.isnan(o)
    p, o = p[mask], o[mask]
    if p.size == 0:
        return float("nan")
    return float(-np.mean(o * np.log(p) + (1 - o) * np.log(1 - p)))


def reliability_bins(prob: np.ndarray, outcome: np.ndarray, n_bins: int = 10) -> list[dict]:
    p = np.asarray(prob, dtype=float)
    o = np.asarray(outcome, dtype=float)
    mask = ~(np.isnan(p) | np.isnan(o))
    p, o = p[mask], o[mask]
    edges = np.linspace(0, 1, n_bins + 1)
    out = []
    for i in range(n_bins):
        sel = (p >= edges[i]) & (p < edges[i + 1] if i < n_bins - 1 else p <= edges[i + 1])
        if sel.sum() == 0:
            continue
        out.append({
            "bin_low": float(edges[i]), "bin_high": float(edges[i + 1]),
            "mean_predicted": float(np.mean(p[sel])),
            "observed_frequency": float(np.mean(o[sel])),
            "count": int(sel.sum()),
        })
    return out


def exact_integer_accuracy(pred_int: Sequence[int], actual_int: Sequence[int]) -> float:
    p = np.asarray(pred_int)
    a = np.asarray(actual_int)
    return float(np.mean(p == a))


def top_two_accuracy(top_two: Sequence[Sequence[int]], actual_int: Sequence[int]) -> float:
    hits = [1.0 if a in tt else 0.0 for tt, a in zip(top_two, actual_int)]
    return float(np.mean(hits)) if hits else float("nan")
