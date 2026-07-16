from datetime import date, datetime

from central_park_tmax.time_utils import (NY, hours_remaining_in_local_day, is_in_local_day,
                                          local_day_bounds, local_day_bounds_utc,
                                          local_day_length_hours, next_local_date, to_local,
                                          to_utc)


def test_local_calendar_day_uses_new_york():
    d = date(2024, 7, 15)
    start, end = local_day_bounds(d)
    assert start.tzinfo.key == "America/New_York"
    assert start.hour == 0 and end.hour == 0
    assert (end - start).days == 1


def test_normal_day_is_24_hours():
    assert local_day_length_hours(date(2024, 7, 15)) == 24.0


def test_spring_forward_is_23_hours():
    # DST begins 2024-03-10 in the US (spring forward) -> 23-hour local day.
    assert local_day_length_hours(date(2024, 3, 10)) == 23.0


def test_fall_back_is_25_hours():
    # DST ends 2024-11-03 (fall back) -> 25-hour local day.
    assert local_day_length_hours(date(2024, 11, 3)) == 25.0


def test_utc_conversion_roundtrip():
    dt = datetime(2024, 7, 15, 18, 30, tzinfo=NY)
    assert to_local(to_utc(dt)) == dt


def test_is_in_local_day_boundaries():
    d = date(2024, 7, 15)
    start, end = local_day_bounds_utc(d)
    assert is_in_local_day(start, d)
    assert not is_in_local_day(end, d)  # end is exclusive (next local midnight)


def test_hours_remaining_monotonic():
    d = date(2024, 7, 15)
    noon_local = datetime(2024, 7, 15, 12, 0, tzinfo=NY)
    six_pm_local = datetime(2024, 7, 15, 18, 0, tzinfo=NY)
    assert hours_remaining_in_local_day(to_utc(noon_local), d) > \
        hours_remaining_in_local_day(to_utc(six_pm_local), d)


def test_next_local_date():
    ref = datetime(2024, 7, 15, 20, 0, tzinfo=NY)
    assert next_local_date(ref) == date(2024, 7, 16)
