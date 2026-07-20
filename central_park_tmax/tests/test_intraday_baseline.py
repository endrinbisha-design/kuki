"""Observation-constrained baseline for intraday vintages.

For a same-day forecast the NBM run can only forecast the remaining hours, so the correct
baseline is max(observed-so-far, forecast-remaining). A previous-evening vintage (no obs)
keeps the plain full-day forecast max.
"""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from central_park_tmax.data.forecast_base import ForecastRun
from central_park_tmax.features.build_features import build_feature_row
from central_park_tmax.time_utils import NY, local_datetime, local_day_bounds_utc, to_utc


class _Loc:
    def __init__(self, key, lat, lon, role="target"):
        self.key, self.latitude, self.longitude, self.role = key, lat, lon, role


class _Locations:
    def __init__(self):
        self.primary = _Loc("central_park", 40.78, -73.97)
        self.neighbors = []
        self.gradient_pairs = []

    def all_points(self):
        return [self.primary]


def _run_for(target, temps_by_hour_utc):
    start, end = local_day_bounds_utc(target)
    rows = []
    for h, t in temps_by_hour_utc:
        rows.append({"valid_time_utc": start + timedelta(hours=h), "temp_f": t,
                     "wind_dir_deg": 200.0, "wind_speed_mph": 5.0, "cloud_frac": 0.2})
    df = pd.DataFrame(rows)
    return ForecastRun(source="nbm", init_utc=start - timedelta(hours=3), cycle="c",
                       per_location_hourly={"central_park": df}, model_version="nbm")


def _normals():
    return pd.DataFrame({"doy": range(1, 367), "normal_tmax_f": [80.0] * 366})


def test_intraday_baseline_is_obs_constrained():
    target = date(2024, 8, 5)
    # Forecast over the day peaks at 85; issue at 4pm local. Observations to 4pm peaked at 88.
    run = _run_for(target, [(h, 70 + h) for h in range(0, 24)])  # rises through the day
    issue = local_datetime(target, 16)
    obs = pd.DataFrame({
        "timestamp_utc": [to_utc(local_datetime(target, hh)) for hh in (10, 13, 15)],
        "temp_f": [80.0, 88.0, 86.0], "raw_metar": ["", "", ""],
    })
    row = build_feature_row(target, "target_16", issue, run, _Locations(), _normals(), obs=obs)
    assert row["observed_max_so_far_f"] == 88.0
    # baseline must be >= observed max so far (the floor), never below it.
    assert row["baseline_tmax_f"] >= 88.0


def test_prev_evening_baseline_unchanged_without_obs():
    target = date(2024, 8, 5)
    run = _run_for(target, [(h, 70 + h) for h in range(0, 24)])  # max 93 at h=23
    issue = local_datetime(target - timedelta(days=1), 19)
    row = build_feature_row(target, "prev_evening_19", issue, run, _Locations(), _normals(), obs=None)
    # No obs -> baseline equals the full-day forecast max.
    assert row["baseline_tmax_f"] == row["forecast_daily_max_f"]
    assert "observed_max_so_far_f" not in row
