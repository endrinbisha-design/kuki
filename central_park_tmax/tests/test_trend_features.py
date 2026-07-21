"""Real-time temperature-trend features (nowcasting signal the model lacked on storm days).

Motivated by 2026-07-21: temp stalled at 75F all morning under pre-storm clouds while the
model (running off NBM forecasts) still expected ~80F. The trend features must flag the
stall so the model can discount the forecast headroom.
"""
from datetime import date, timedelta

import pandas as pd

from central_park_tmax.features.intraday import intraday_features
from central_park_tmax.time_utils import local_datetime, to_utc


def _obs(target, hourly_temps_local):
    """hourly_temps_local: list of (local_hour, temp_f)."""
    return pd.DataFrame({
        "timestamp_utc": [to_utc(local_datetime(target, h)) for h, _ in hourly_temps_local],
        "temp_f": [t for _, t in hourly_temps_local],
        "raw_metar": ["" for _ in hourly_temps_local],
    })


def test_stall_detected_before_peak():
    target = date(2026, 7, 21)
    # Flat at 75 from 8am..11am (the real Jul 21 morning). Issue at 11am.
    obs = _obs(target, [(8, 75.0), (9, 73.9), (10, 75.0), (11, 75.0)])
    issue = to_utc(local_datetime(target, 11))
    f = intraday_features(obs, target, issue, forecast_remaining_max_f=80.0)
    assert f["stalled_before_peak_flag"] == 1.0
    assert abs(f["warming_rate_recent_3h_f_per_h"]) < 0.3
    # Forecast wants ~5F more; trend supports ~0 -> large positive discount signal.
    assert f["headroom_minus_trend_support_f"] > 3.0


def test_healthy_warming_not_flagged():
    target = date(2026, 7, 15)
    # Steady climb 72 -> 84 through the morning. Issue at noon.
    obs = _obs(target, [(8, 72.0), (9, 75.0), (10, 78.0), (11, 81.0), (12, 84.0)])
    issue = to_utc(local_datetime(target, 12))
    f = intraday_features(obs, target, issue, forecast_remaining_max_f=88.0)
    assert f["stalled_before_peak_flag"] == 0.0
    assert f["warming_rate_recent_3h_f_per_h"] > 2.0
    assert f["hours_since_observed_max"] < 0.5      # peak is the latest ob


def test_cooling_before_peak_flagged():
    target = date(2026, 7, 21)
    # Rose to 78 by 10am then FELL to 74 by 1pm (storm-cooled) before the usual peak.
    obs = _obs(target, [(8, 74.0), (9, 76.0), (10, 78.0), (11, 76.0), (12, 75.0), (13, 74.0)])
    issue = to_utc(local_datetime(target, 13))
    f = intraday_features(obs, target, issue, forecast_remaining_max_f=82.0)
    assert f["cooling_before_peak_flag"] == 1.0
    assert f["temp_drop_from_max_f"] == 4.0         # 78 peak - 74 now
    assert f["hours_since_observed_max"] >= 3.0


def test_trend_features_absent_without_obs():
    target = date(2026, 7, 21)
    f = intraday_features(None, target, to_utc(local_datetime(target, 12)))
    assert f["is_intraday"] == 0.0
    assert "stalled_before_peak_flag" not in f
