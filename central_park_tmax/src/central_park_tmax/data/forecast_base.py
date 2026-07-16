"""Common interface and data structures for numerical-forecast sources.

Every source exposes the same contract so the feature builder is source-agnostic:

    class ForecastSource:
        def list_available_runs(...)
        def validate_run_availability(...)
        def fetch_run(...)            -> ForecastRun
        def extract_point_features(...)
        def extract_neighborhood_features(...)
        def get_metadata(...)

A ``ForecastRun`` carries, per location key, an hourly forecast frame over (at least) the
target local day, plus initialization time, valid times, an availability estimate, grid
coordinates, variable units, model version (when known), and provenance. Point-in-time
availability is a first-class concept: ``validate_run_availability`` rejects any run whose
initialization is after the prediction issue time.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import pandas as pd

from ..logging_config import get_logger

log = get_logger(__name__)


@dataclass
class RunHandle:
    """Identifies a specific model cycle available from a source."""
    source: str
    init_utc: datetime
    cycle: str                       # e.g. "2024-07-15T12Z"
    availability_estimate_utc: Optional[datetime] = None  # when it became usable
    model_version: Optional[str] = None


@dataclass
class ForecastRun:
    """A fetched model run with per-location hourly forecast frames."""
    source: str
    init_utc: datetime
    cycle: str
    per_location_hourly: dict[str, pd.DataFrame]   # key -> hourly frame (valid_time_utc index)
    availability_estimate_utc: Optional[datetime] = None
    model_version: Optional[str] = None
    variable_units: dict[str, str] = field(default_factory=dict)
    grid_coords: dict[str, tuple[float, float]] = field(default_factory=dict)
    provenance: str = "forecast"
    _dmax_cache: dict = field(default_factory=dict, repr=False, compare=False)

    def daily_max_f(self, location_key: str, target_date: date,
                    tz_filter=True) -> Optional[float]:
        """Max forecast 2 m temperature (F) over the local target day at a location.

        Vectorized (bounds comparison, no per-row apply) and memoized per (key, date).
        """
        from ..time_utils import local_day_bounds_utc
        cache_key = (location_key, target_date, tz_filter)
        if cache_key in self._dmax_cache:
            return self._dmax_cache[cache_key]
        df = self.per_location_hourly.get(location_key)
        if df is None or df.empty or "temp_f" not in df.columns:
            self._dmax_cache[cache_key] = None
            return None
        vt = pd.to_datetime(df["valid_time_utc"], utc=True, errors="coerce")
        temps = pd.to_numeric(df["temp_f"], errors="coerce")
        if tz_filter:
            start, end = local_day_bounds_utc(target_date)
            start = pd.Timestamp(start).tz_convert("UTC")
            end = pd.Timestamp(end).tz_convert("UTC")
            mask = (vt >= start) & (vt < end)
            temps = temps[mask.to_numpy()]
        temps = temps.dropna()
        result = float(temps.max()) if len(temps) else None
        self._dmax_cache[cache_key] = result
        return result

    def lead_time_hours(self, target_date: date) -> float:
        from ..time_utils import local_day_bounds_utc
        start, _ = local_day_bounds_utc(target_date)
        return (start - self.init_utc).total_seconds() / 3600.0


class ForecastSource(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    def list_available_runs(self, target_date: date, issued_before_utc: datetime) -> list[RunHandle]:
        """List runs whose data is usable for ``target_date`` and available by the issue time."""

    def validate_run_availability(self, run: RunHandle, issued_before_utc: datetime) -> bool:
        """Reject runs initialized after (or becoming available after) the prediction time.

        This is the core leakage guard for forecasts. A run initialized at or before the
        prediction issue time AND whose availability estimate is <= issue time is usable.
        """
        if run.init_utc > issued_before_utc:
            return False
        if run.availability_estimate_utc and run.availability_estimate_utc > issued_before_utc:
            return False
        return True

    @abc.abstractmethod
    def fetch_run(self, run: RunHandle, locations, target_date: date) -> ForecastRun:
        """Fetch and extract per-location hourly forecasts for a run."""

    def select_run(self, target_date: date, issued_before_utc: datetime) -> Optional[RunHandle]:
        """Pick the latest usable run available at the prediction time (no leakage)."""
        runs = [r for r in self.list_available_runs(target_date, issued_before_utc)
                if self.validate_run_availability(r, issued_before_utc)]
        if not runs:
            return None
        return max(runs, key=lambda r: r.init_utc)

    def extract_point_features(self, run: ForecastRun, location_key: str, target_date: date) -> dict:
        """Default point-feature extraction (daily max + basic trajectory)."""
        out: dict[str, float] = {}
        dmax = run.daily_max_f(location_key, target_date)
        if dmax is not None:
            out[f"{self.name}_{location_key}_tmax_f"] = dmax
        return out

    def extract_neighborhood_features(self, run: ForecastRun, target_date: date,
                                      keys: list[str]) -> dict:
        vals = [run.daily_max_f(k, target_date) for k in keys]
        vals = [v for v in vals if v is not None]
        if not vals:
            return {}
        import numpy as np
        return {
            f"{self.name}_neigh_tmax_mean_f": float(np.mean(vals)),
            f"{self.name}_neigh_tmax_min_f": float(np.min(vals)),
            f"{self.name}_neigh_tmax_max_f": float(np.max(vals)),
            f"{self.name}_neigh_tmax_std_f": float(np.std(vals)),
        }

    def get_metadata(self, run: ForecastRun) -> dict:
        return {
            "source": run.source,
            "init_utc": run.init_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cycle": run.cycle,
            "availability_estimate_utc": (
                run.availability_estimate_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                if run.availability_estimate_utc else None),
            "model_version": run.model_version,
            "variable_units": run.variable_units,
            "provenance": run.provenance,
        }
