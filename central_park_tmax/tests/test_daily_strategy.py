"""Daily strategy selector (models/daily_strategy.py)."""
from central_park_tmax.models.daily_strategy import recommend_strategy


def test_post_peak_lock_wins_priority():
    a = recommend_strategy(station_shorthand="KNYC", local_hour=16, pop_pct=80,
                           observed_max_f=80.1, determined=True)
    assert a.strategy == "POST_PEAK_LOCK" and a.confidence == "high"


def test_wet_day_says_avoid():
    a = recommend_strategy(station_shorthand="KNYC", local_hour=12, pop_pct=78,
                           observed_max_f=78.0, determined=False)
    assert a.strategy == "WET_DAY_AVOID" and a.regime == "wet"
    assert a.expected_mae_f > 2.0


def test_dry_phoenix_leans_warm():
    a = recommend_strategy(station_shorthand="KPHX", local_hour=11, pop_pct=5,
                           forecast_tmax_f=111.0, determined=False)
    assert a.strategy == "DRY_LEAN_WARM" and a.lean == "warm"
    assert a.p_cool_2f < 0.10          # measured 6% cool tail on dry PHX days


def test_wet_phoenix_flips_off_the_warm_lean():
    # The sign flip: a monsoon day must NOT inherit the dry-day warm rule.
    a = recommend_strategy(station_shorthand="KPHX", local_hour=11, pop_pct=60,
                           forecast_tmax_f=108.0, determined=False)
    assert a.strategy == "WET_DAY_AVOID"
    assert a.p_cool_2f > 0.25          # cool tail explodes 6% -> 31%


def test_dry_vegas_leans_cool_opposite_phoenix():
    a = recommend_strategy(station_shorthand="KLAS", local_hour=11, pop_pct=2,
                           forecast_tmax_f=110.0, determined=False)
    assert a.strategy == "DRY_LEAN_COOL" and a.lean == "cool"


def test_nyc_dry_prepeak_waits():
    a = recommend_strategy(station_shorthand="KNYC", local_hour=11, pop_pct=0,
                           forecast_tmax_f=83.0, determined=False)
    assert a.strategy == "WAIT_FOR_PEAK"


def test_wide_model_spread_noted():
    a = recommend_strategy(station_shorthand="KNYC", local_hour=11, pop_pct=0,
                           forecast_tmax_f=83.0, determined=False, model_spread_f=6.4)
    assert "spread" in a.rationale


def test_unknown_station():
    a = recommend_strategy(station_shorthand="KDEN", local_hour=15, pop_pct=0)
    assert a.strategy == "NO_COVERAGE"
