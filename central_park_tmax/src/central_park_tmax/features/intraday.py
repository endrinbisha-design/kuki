"""Intraday / forecast-vintage features for same-day forecasts.

For forecasts issued during the target day we incorporate the maximum observed so far, hours
remaining, expected remaining warming, and observed-vs-forecast error so far. These features
only use observations available at (<=) the forecast issue time.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from ..time_utils import hours_remaining_in_local_day, is_in_local_day, to_local, to_utc


def intraday_features(
    obs: Optional[pd.DataFrame],
    target_date: date,
    issue_utc: datetime,
    forecast_remaining_max_f: Optional[float] = None,
    same_hour_forecast_temp_f: Optional[float] = None,
    intraday_report_max_f: Optional[float] = None,
) -> dict:
    """Build intraday features from observations available up to ``issue_utc``.

    ``obs`` must have 'timestamp_utc' and 'temp_f'. Only obs within the local target day and
    at/before issue time are used (leakage-safe by construction).

    ``observed_max_so_far_f`` uses the best-available reconstruction — hourly snapshots,
    METAR 6-hour max groups, and an intraday CLI max when supplied — so it matches the NWS
    report peak rather than under-sampling it (see hourly_observations.max_so_far_with_provenance).
    """
    out: dict[str, float] = {
        "hours_remaining_in_day": float(hours_remaining_in_local_day(issue_utc, target_date)),
    }
    if obs is None or obs.empty or "temp_f" not in obs.columns:
        out["is_intraday"] = 0.0
        return out

    ts = pd.to_datetime(obs["timestamp_utc"], utc=True, errors="coerce")
    temps, times = [], []
    for t, temp in zip(ts, obs["temp_f"]):
        if pd.isna(t) or pd.isna(temp):
            continue
        tt = to_utc(t.to_pydatetime())
        if tt <= issue_utc and is_in_local_day(tt, target_date):
            temps.append(float(temp))
            times.append(tt)
    if not temps:
        out["is_intraday"] = 0.0
        return out

    out["is_intraday"] = 1.0
    from ..data.hourly_observations import max_so_far_with_provenance
    best_max, best_src = max_so_far_with_provenance(
        obs, target_date, issue_utc, intraday_report_max_f=intraday_report_max_f)
    obs_max = best_max if best_max is not None else max(temps)
    out["observed_max_so_far_f"] = obs_max
    out["observed_max_snapshot_f"] = max(temps)          # the coarse hourly max (for reference)
    out["observed_max_source_cli"] = 1.0 if best_src == "nws_cli_intraday" else 0.0
    out["observed_max_so_far_source"] = best_src         # str; excluded from design matrix
    out["current_temp_f"] = temps[-1]
    # Observed warming rate over the whole observed span (F/hour).
    if len(temps) >= 3:
        span_h = max(1e-6, (times[-1] - times[0]).total_seconds() / 3600.0)
        out["observed_warming_rate_f_per_h"] = float((temps[-1] - temps[0]) / span_h)
    if same_hour_forecast_temp_f is not None:
        out["obs_minus_forecast_so_far_f"] = float(temps[-1] - same_hour_forecast_temp_f)
    if forecast_remaining_max_f is not None:
        out["expected_remaining_max_f"] = float(forecast_remaining_max_f)
        out["prob_exceed_current_proxy_f"] = float(forecast_remaining_max_f - obs_max)

    # --- real-time temperature-trend / nowcasting features ---
    # These capture whether the temperature is still climbing or has stalled/fallen, the
    # signal the model was blind to on storm days (it runs off NBM forecast cycles, not the
    # live obs trajectory). All use only observations at/before issue time (leakage-safe).
    out.update(_trend_features(times, temps, obs_max, target_date, issue_utc,
                               forecast_remaining_max_f))
    return out


def _trend_features(times, temps, obs_max, target_date, issue_utc, forecast_remaining_max_f):
    """Recent warming rate, time-since-peak, drop-from-peak, and a stall indicator."""
    out: dict[str, float] = {}
    pairs = sorted(zip(times, temps))  # (utc_datetime, temp_f)

    def rate_over(hours: float):
        cutoff = issue_utc - timedelta(hours=hours)
        recent = [(t, v) for t, v in pairs if t >= cutoff]
        if len(recent) >= 2:
            dt_h = (recent[-1][0] - recent[0][0]).total_seconds() / 3600.0
            if dt_h >= 0.25:
                return float((recent[-1][1] - recent[0][1]) / dt_h)
        return None

    r1 = rate_over(1.0)
    r2 = rate_over(2.0)
    r3 = rate_over(3.0)
    if r1 is not None:
        out["warming_rate_recent_1h_f_per_h"] = r1
    if r2 is not None:
        out["warming_rate_recent_2h_f_per_h"] = r2
    if r3 is not None:
        out["warming_rate_recent_3h_f_per_h"] = r3

    # Time since (and drop from) the observed peak.
    peak_time = max(pairs, key=lambda tv: tv[1])[0]
    out["hours_since_observed_max"] = float((issue_utc - peak_time).total_seconds() / 3600.0)
    out["temp_drop_from_max_f"] = float(obs_max - temps[-1])

    # Stall indicator. Use the LONGEST available window as the trend (a sustained flat
    # trend, robust to short dip-and-recover bounces), and combine with time-since-peak:
    # the temperature has stalled if it is barely warming over the last few hours OR it
    # has failed to make a new high for a while, while it is still before the typical
    # afternoon peak (14:00 local).
    local_hour = to_local(issue_utc).hour
    trend_rate = r3 if r3 is not None else (r2 if r2 is not None else r1)
    if trend_rate is not None:
        hours_since_peak = out["hours_since_observed_max"]
        before_peak = local_hour < 14
        stalled = 1.0 if before_peak and (trend_rate <= 0.5 or hours_since_peak >= 1.5) else 0.0
        out["stalled_before_peak_flag"] = stalled
        # Cooling-before-peak: actively falling before the typical peak (stronger signal).
        out["cooling_before_peak_flag"] = 1.0 if (trend_rate < -0.25 and local_hour < 15) else 0.0

    # How much of the forecast's remaining headroom is plausible given the trend: if the
    # temp has stalled, the forecast-remaining-max is less trustworthy. Expose the gap
    # between forecast headroom and recent realized warming so the model can discount it.
    if forecast_remaining_max_f is not None and trend_rate is not None:
        headroom = forecast_remaining_max_f - temps[-1]
        out["forecast_headroom_f"] = float(headroom)
        # headroom the current warming trend would 'support' over the hours to peak (~14 local)
        hours_to_peak = max(0.0, 14 - local_hour)
        out["trend_supported_headroom_f"] = float(max(0.0, trend_rate) * hours_to_peak)
        out["headroom_minus_trend_support_f"] = float(headroom - out["trend_supported_headroom_f"])
    return out


def apply_observed_max_constraint(predicted_max_f: float, observed_max_so_far_f: Optional[float]) -> float:
    """Enforce final_daily_max = max(observed_max_so_far, predicted). Never below observed."""
    if observed_max_so_far_f is None or (isinstance(observed_max_so_far_f, float)
                                         and np.isnan(observed_max_so_far_f)):
        return predicted_max_f
    return float(max(observed_max_so_far_f, predicted_max_f))
