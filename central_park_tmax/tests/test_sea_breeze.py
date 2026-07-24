"""Sea-breeze advisory add-on (features/sea_breeze.py)."""
from central_park_tmax.features.sea_breeze import (coastal_divergence, night_before_risk,
                                                   parse_ndbc_realtime_sst_f, FLAG_THRESHOLD)


def test_gradient_raises_risk_monotonically():
    # Forecast CP >> JFK is the strongest marine-erosion signature (coef +0.65).
    lo = night_before_risk(forecast_cp_max_f=82, forecast_jfk_max_f=82, day_of_year=200)
    hi = night_before_risk(forecast_cp_max_f=82, forecast_jfk_max_f=76, day_of_year=200)
    assert hi.probability > lo.probability


def test_missing_inputs_impute_and_stay_valid():
    r = night_before_risk(forecast_cp_max_f=None)
    assert 0.0 < r.probability < 1.0
    assert r.inputs_used == {}


def test_flag_threshold_consistency():
    r = night_before_risk(forecast_cp_max_f=85, forecast_jfk_max_f=77,
                          afternoon_wind_dir_deg=150, afternoon_wind_speed_kt=12,
                          day_of_year=170)
    assert r.flagged == (r.probability >= FLAG_THRESHOLD)


def test_divergence_flags_marine_intrusion():
    # Jul 23 2026 pattern: JFK cool + onshore at JFK, CP wind already easterly-onshore.
    d = coastal_divergence(cp_temp_f=78, jfk_temp_f=73, jfk_wind_dir_deg=160,
                           cp_wind_dir_deg=120)
    assert d.underway and d.score >= 0.5
    quiet = coastal_divergence(cp_temp_f=80, jfk_temp_f=79, jfk_wind_dir_deg=300,
                               cp_wind_dir_deg=310)
    assert not quiet.underway


def test_ndbc_parser():
    text = ("#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE\n"
            "#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft\n"
            "2026 07 24 02 30 180  3.0  4.0    MM    MM    MM  MM 1022.8  22.4  23.3  15.1   MM   MM    MM\n")
    sst = parse_ndbc_realtime_sst_f(text)
    assert sst is not None and abs(sst - 73.94) < 0.1
