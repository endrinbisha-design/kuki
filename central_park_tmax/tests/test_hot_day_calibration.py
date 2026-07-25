"""Hot-day tail calibration (models/hot_day_calibration.py)."""
from central_park_tmax.models.hot_day_calibration import (assess_hot_day, reweight_integer_pmf,
                                                          resolve_city_key)


def test_below_threshold_does_not_apply():
    a = assess_hot_day("KPHX", 100.0)          # below the 108.6F PHX hot threshold
    assert not a.applies and a.point_shift_f == 0.0


def test_phoenix_hot_day_shifts_warm():
    a = assess_hot_day("KPHX", 115.0)
    assert a.applies and a.point_shift_f > 0      # guidance runs cool in PHX heat
    assert a.p_warm_2f > a.p_cool_2f              # fat warm tail


def test_vegas_hot_day_shifts_cool_opposite_of_phoenix():
    a = assess_hot_day("KLAS", 112.0)
    assert a.applies and a.point_shift_f < 0      # guidance runs warm in LAS heat
    assert a.p_cool_2f > a.p_warm_2f              # fat cool tail — warm bucket is a trap


def test_nyc_hot_day_is_centred_but_wide():
    a = assess_hot_day("KNYC", 90.0)
    assert a.applies and abs(a.point_shift_f) < 0.5
    assert a.p_warm_2f > 0.15 and a.p_cool_2f > 0.15


def test_reweight_moves_mass_warm_in_phoenix():
    pmf = {113: 0.15, 114: 0.25, 115: 0.30, 116: 0.20, 117: 0.10}
    out = reweight_integer_pmf(pmf, assess_hot_day("KPHX", 115.0))
    assert abs(sum(out.values()) - 1.0) < 1e-9
    ev_in = sum(k * v for k, v in pmf.items())
    ev_out = sum(k * v for k, v in out.items())
    assert ev_out > ev_in                          # expectation moves warmer


def test_reweight_is_noop_when_not_applicable():
    pmf = {80: 0.5, 81: 0.5}
    assert reweight_integer_pmf(pmf, assess_hot_day("KPHX", 90.0)) == pmf


def test_station_resolution():
    assert resolve_city_key("KPHX") == "phoenix"
    assert resolve_city_key("KNYC") == "nyc"
    assert resolve_city_key("KDEN") is None
