"""Data-quality checks. Critical issues raise; noncritical issues log warnings.

These guard the leakage-safety and physical-plausibility invariants of the dataset before
training and at prediction time.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

from ..constants import MAX_PLAUSIBLE_TMAX_F, MIN_PLAUSIBLE_TMAX_F
from ..logging_config import get_logger

log = get_logger(__name__)


class DataQualityError(RuntimeError):
    """Raised for critical data-quality violations."""


def check_dataset(df: pd.DataFrame, target_col: str = "target_report_max_f",
                  raise_on_critical: bool = True) -> list[str]:
    issues: list[str] = []
    critical: list[str] = []

    if "date" not in df.columns:
        critical.append("dataset missing 'date' column")
    else:
        dup = df.duplicated(subset=[c for c in ["date", "vintage"] if c in df.columns])
        if dup.any():
            critical.append(f"{int(dup.sum())} duplicate (date,vintage) rows")

    if target_col in df.columns:
        t = pd.to_numeric(df[target_col], errors="coerce")
        n_missing = int(t.isna().sum())
        if n_missing:
            issues.append(f"{n_missing} rows with missing target")
        implausible = ((t < MIN_PLAUSIBLE_TMAX_F) | (t > MAX_PLAUSIBLE_TMAX_F)) & t.notna()
        if implausible.any():
            critical.append(f"{int(implausible.sum())} implausible target temperatures")

    if "baseline_tmax_f" in df.columns:
        b = pd.to_numeric(df["baseline_tmax_f"], errors="coerce")
        impl = ((b < MIN_PLAUSIBLE_TMAX_F) | (b > MAX_PLAUSIBLE_TMAX_F)) & b.notna()
        if impl.any():
            issues.append(f"{int(impl.sum())} implausible baseline temperatures")

    for w in issues:
        log.warning("data-quality: %s", w)
    for c in critical:
        log.error("data-quality CRITICAL: %s", c)
    if critical and raise_on_critical:
        raise DataQualityError("; ".join(critical))
    return issues + critical


def check_forecast_availability(init_utc: datetime, issue_utc: datetime) -> None:
    """Reject a forecast run initialized after the prediction issue time (leakage)."""
    if init_utc > issue_utc:
        raise DataQualityError(
            f"Forecast init {init_utc.isoformat()} is after issue time {issue_utc.isoformat()} "
            f"(future data leakage)."
        )


def check_observation_availability(obs_ts_utc: datetime, issue_utc: datetime) -> None:
    if obs_ts_utc > issue_utc:
        raise DataQualityError(
            f"Observation at {obs_ts_utc.isoformat()} is after issue time {issue_utc.isoformat()}."
        )


def check_integer_pmf_sums_to_one(pmf: dict, tol: float = 1e-6) -> None:
    total = sum(pmf.values())
    if abs(total - 1.0) > tol:
        raise DataQualityError(f"Integer PMF sums to {total:.8f}, not 1 (tol={tol}).")


def check_quantiles_ordered(quantile_row: np.ndarray, tol: float = 1e-9) -> None:
    q = np.asarray(quantile_row, dtype=float)
    if np.any(np.diff(q) < -tol):
        raise DataQualityError(f"Quantiles are not monotone (crossed): {q}")


def check_prediction_not_below_observed(predicted: float, observed_max_so_far: Optional[float],
                                        tol: float = 1e-9) -> None:
    if observed_max_so_far is None:
        return
    if predicted < observed_max_so_far - tol:
        raise DataQualityError(
            f"Prediction {predicted} below observed max so far {observed_max_so_far}."
        )


def check_valid_times_in_local_day(valid_times_utc, target_date: date) -> int:
    """Count (and warn on) forecast valid times that fall outside the local target day."""
    from ..time_utils import is_in_local_day, to_utc
    outside = 0
    for t in valid_times_utc:
        if not is_in_local_day(to_utc(t), target_date):
            outside += 1
    if outside:
        log.debug("%d forecast valid-times fall outside local day %s", outside, target_date)
    return outside
