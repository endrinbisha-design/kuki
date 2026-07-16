"""SYNTHETIC forecast / observation / report generator for offline demo and tests ONLY.

This is NOT real weather. It produces physically-plausible, fully-deterministic data so the
entire pipeline (features -> models -> probabilities -> contracts -> backtest -> settlement)
can be exercised end-to-end without network access or GRIB. It is selected only via the
explicit ``--synthetic`` switch and is always tagged with provenance ``synthetic_*`` so it
can never be mistaken for a real forecast or a real NWS report.

The generator embeds a modest, regime-dependent baseline bias so the residual model has a
learnable signal, mirroring the real MOS problem (correct systematic model error).
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from ..constants import c_to_f, f_to_c
from ..time_utils import NY, local_day_bounds_utc, local_datetime, to_utc
from .forecast_base import ForecastRun, ForecastSource, RunHandle


def _seed_for(d: date, salt: str = "") -> int:
    h = hashlib.sha256(f"{d.isoformat()}|{salt}".encode()).hexdigest()
    return int(h[:8], 16)


def _rng(d: date, salt: str = "") -> np.random.Generator:
    return np.random.default_rng(_seed_for(d, salt))


def _climate_normal_max_f(d: date) -> float:
    """Smooth NYC seasonal normal maximum (F). Peak ~85 late July, trough ~39 late Jan."""
    doy = d.timetuple().tm_yday
    # cosine peaking around day 205 (late July)
    return 62.0 + 23.0 * np.cos(2 * np.pi * (doy - 205) / 365.25)


class WeatherState:
    """Latent daily 'truth' for a date: continuous max, regime, and companion fields."""

    def __init__(self, d: date):
        self.date = d
        rng = _rng(d, "truth")
        normal = _climate_normal_max_f(d)
        # Persistent regime anomaly via date-seeded AR-like term.
        anom = float(rng.normal(0, 6.0))
        self.regime = "warm" if anom > 3 else ("cool" if anom < -3 else "neutral")
        self.true_max_f = float(np.clip(normal + anom + rng.normal(0, 2.0), -10, 110))
        self.true_min_f = self.true_max_f - float(abs(rng.normal(16, 4)))
        self.cloud_frac = float(np.clip(rng.beta(2, 3), 0, 1))
        # wind direction: onshore (S/SE ~135) suppresses max in summer
        self.wind_dir_deg = float(rng.uniform(0, 360))
        self.dewpoint_f = self.true_max_f - float(abs(rng.normal(18, 6)))
        self.precip_in = float(max(0.0, rng.normal(-0.1, 0.25)))
        self.hour_of_max = int(np.clip(rng.normal(15, 1.2), 11, 18))

    def _fraction(self, h):
        """Diurnal fraction in [0,1] (min near 05 local, peak at hour_of_max). Vectorized."""
        h = np.asarray(h, dtype=float)
        rising = np.clip(np.sin(np.clip((h - 5.0) / (self.hour_of_max - 5.0), 0, 1) * np.pi / 2), 0, 1)
        decay = np.clip((h - self.hour_of_max) / (29.0 - self.hour_of_max), 0, 1)
        falling = np.cos(decay * np.pi / 2)
        return np.where(h <= self.hour_of_max, rising, falling)

    def hourly_temp_f(self, valid_utc: datetime) -> float:
        """Diurnal curve value at a single UTC timestamp (scalar convenience)."""
        from ..time_utils import to_local
        local = to_local(valid_utc)
        h = local.hour + local.minute / 60.0
        frac = float(self._fraction(h))
        return float(self.true_min_f + (self.true_max_f - self.true_min_f) * frac)

    def hourly_temp_f_from_local_hours(self, local_hours) -> np.ndarray:
        """Vectorized diurnal curve for an array of local decimal hours."""
        frac = self._fraction(local_hours)
        return self.true_min_f + (self.true_max_f - self.true_min_f) * frac


def synthetic_baseline_bias_f(state: WeatherState) -> float:
    """Regime-dependent systematic baseline (NBM-like) bias the residual model learns."""
    base = {"warm": -1.6, "cool": +1.2, "neutral": 0.2}[state.regime]
    # cool-bias amplified on cloudy days, warm-bias on onshore-flow summer days
    cloud_term = -0.8 * (state.cloud_frac - 0.5)
    onshore = np.cos(np.deg2rad(state.wind_dir_deg - 135))  # ~1 when SE
    onshore_term = -1.0 * max(0.0, onshore) if _climate_normal_max_f(state.date) > 70 else 0.0
    return base + cloud_term + onshore_term


class SyntheticForecastSource(ForecastSource):
    """Emits a synthetic 'baseline' model (e.g. stand-in for NBM) with learnable bias."""

    name = "synthetic"

    def __init__(self, label: str = "synthetic", cycle_hours: int = 6, latency_hours: float = 3.0):
        self._label = label
        self.cycle_hours = cycle_hours
        self.latency_hours = latency_hours

    def list_available_runs(self, target_date: date, issued_before_utc: datetime) -> list[RunHandle]:
        start, _ = local_day_bounds_utc(target_date)
        earliest = start - timedelta(days=2)
        out: list[RunHandle] = []
        c = earliest.replace(minute=0, second=0, microsecond=0)
        c = c.replace(hour=(c.hour // self.cycle_hours) * self.cycle_hours)
        while c <= issued_before_utc:
            out.append(RunHandle(
                source=self.name, init_utc=c, cycle=c.strftime("%Y-%m-%dT%HZ"),
                availability_estimate_utc=c + timedelta(hours=self.latency_hours),
                model_version=f"{self._label}-v1",
            ))
            c += timedelta(hours=self.cycle_hours)
        return out

    def fetch_run(self, run: RunHandle, locations, target_date: date) -> ForecastRun:
        state = WeatherState(target_date)
        bias = synthetic_baseline_bias_f(state)
        rng = _rng(target_date, f"fc|{run.cycle}")
        # forecast error shrinks as init approaches the target day
        lead_h = max(0.0, (local_day_bounds_utc(target_date)[0] - run.init_utc).total_seconds() / 3600)
        lead_noise = 0.6 + 0.03 * lead_h

        per_loc: dict[str, pd.DataFrame] = {}
        grid_coords: dict[str, tuple[float, float]] = {}
        start, end = local_day_bounds_utc(target_date)
        hours = pd.date_range(start - timedelta(hours=6), end + timedelta(hours=1),
                              freq="h", tz="UTC")
        # Compute local decimal hours once (vectorized diurnal curve for all locations).
        local_ts = hours.tz_convert(NY)
        local_hours = local_ts.hour + local_ts.minute / 60.0
        base_curve = state.hourly_temp_f_from_local_hours(np.asarray(local_hours))
        for p in locations.all_points():
            # small spatial offset per location (coastal cooler in summer, etc.)
            loc_off = _location_offset_f(p.role, state)
            fc = base_curve - bias + loc_off + rng.normal(0, lead_noise * 0.4, len(hours))
            df = pd.DataFrame({
                "valid_time_utc": hours,
                "temp_f": fc,
                "cloud_frac": np.clip(state.cloud_frac + rng.normal(0, 0.05, len(hours)), 0, 1),
                "wind_dir_deg": (state.wind_dir_deg + rng.normal(0, 8, len(hours))) % 360,
                "wind_speed_mph": np.clip(6 + rng.normal(0, 2, len(hours)), 0, None),
                "dewpoint_f": state.dewpoint_f + loc_off + rng.normal(0, 0.5, len(hours)),
                "prob_precip_pct": float(np.clip(state.precip_in * 200, 0, 100)),
            })
            per_loc[p.key] = df
            grid_coords[p.key] = (p.latitude, p.longitude)

        return ForecastRun(
            source=self.name, init_utc=run.init_utc, cycle=run.cycle,
            per_location_hourly=per_loc,
            availability_estimate_utc=run.availability_estimate_utc,
            model_version=f"{self._label}-v1", variable_units={"temp_f": "degF"},
            grid_coords=grid_coords, provenance="synthetic_forecast",
        )


def _location_offset_f(role: str, state: WeatherState) -> float:
    summer = _climate_normal_max_f(state.date) > 70
    if role in ("marine", "coastal", "coastal_airport"):
        return -3.0 if summer else 1.0
    if role in ("inland", "inland_airport"):
        return 2.0 if summer else -1.0
    return 0.0


# --------------------------------------------------------------------------------------
# Synthetic observations & NWS report (for offline archive building / demo)
# --------------------------------------------------------------------------------------
def synthetic_observation_frame(target_date: date, up_to_utc: Optional[datetime] = None) -> pd.DataFrame:
    """Hourly observation frame for the target local day (optionally truncated at ``up_to_utc``)."""
    state = WeatherState(target_date)
    rng = _rng(target_date, "obs")
    start, end = local_day_bounds_utc(target_date)
    hours = pd.date_range(start, end, freq="h", tz="UTC", inclusive="left")
    if up_to_utc is not None:
        cutoff = pd.Timestamp(to_utc(up_to_utc)).tz_convert("UTC")
        hours = hours[hours <= cutoff]
    if len(hours) == 0:
        return pd.DataFrame(columns=["timestamp_utc", "temp_f", "temp_c", "dewpoint_f",
                                     "wind_dir_deg", "wind_speed_kmh", "raw_metar"])
    local_ts = hours.tz_convert(NY)
    local_hours = np.asarray(local_ts.hour + local_ts.minute / 60.0)
    t = state.hourly_temp_f_from_local_hours(local_hours) + rng.normal(0, 0.4, len(hours))
    return pd.DataFrame({
        "timestamp_utc": hours,
        "temp_f": t,
        "temp_c": [f_to_c(x) for x in t],
        "dewpoint_f": state.dewpoint_f + rng.normal(0, 0.4, len(hours)),
        "wind_dir_deg": (state.wind_dir_deg + rng.normal(0, 6, len(hours))) % 360,
        "wind_speed_kmh": np.clip(9 + rng.normal(0, 3, len(hours)), 0, None),
        "raw_metar": "",
    })


def synthetic_report_max_f(target_date: date) -> int:
    """Integer NWS-report max derived from the synthetic latent max (round-half-up)."""
    state = WeatherState(target_date)
    from ..models.reporting_convention import apply_reporting_convention
    return apply_reporting_convention(state.true_max_f, method="round_half_up")
