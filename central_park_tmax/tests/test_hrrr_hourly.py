"""HRRR afternoon-shape features (data/hrrr_hourly.py) — pure-function tests."""
import pandas as pd

from central_park_tmax.data.hrrr_hourly import afternoon_shape_features, _wind_dir_speed


def _trace(cp, jfk=None, wdir=None):
    idx = list(range(10, 19))
    d = {"cp_temp_f": cp}
    if jfk: d["jfk_temp_f"] = jfk
    if wdir: d["cp_wdir"] = wdir
    return pd.DataFrame(d, index=pd.Index(idx, name="hour_local"))


def test_capped_day_shape_detected():
    # Jul 23-like: peak at 12-13 local then flat/declining, onshore afternoon winds.
    f = afternoon_shape_features(_trace(
        cp=[72, 75, 78, 78, 77, 77, 76, 75, 74],
        jfk=[70, 72, 73, 73, 72, 72, 72, 71, 71],
        wdir=[60, 70, 100, 130, 150, 160, 150, 140, 130]))
    assert f["hrrr_sees_cap"] is True
    assert f["hrrr_peak_hour_local"] <= 13
    assert f["hrrr_onshore_hours"] >= 5
    assert f["hrrr_cp_jfk_gap_pm_f"] > 3


def test_clean_warming_day_not_capped():
    f = afternoon_shape_features(_trace(
        cp=[74, 77, 80, 82, 84, 85, 85, 84, 82],
        wdir=[300, 310, 300, 290, 280, 290, 300, 310, 300]))
    assert f["hrrr_sees_cap"] is False
    assert f["hrrr_peak_hour_local"] >= 14
    assert f["hrrr_onshore_hours"] == 0


def test_wind_conversion():
    d, s = _wind_dir_speed(0.0, -5.0)   # wind FROM north blowing southward
    assert abs(d - 0.0) < 1e-6 and abs(s - 9.72) < 0.1
    d, _ = _wind_dir_speed(-5.0, 0.0)   # FROM east
    assert abs(d - 90.0) < 1e-6
