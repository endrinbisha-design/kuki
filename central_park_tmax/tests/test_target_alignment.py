from datetime import date, datetime, timedelta

import pandas as pd

from central_park_tmax.time_utils import NY, is_in_local_day, local_day_bounds_utc, to_utc


def test_utc_day_differs_from_local_day():
    # A UTC-day window is NOT the same as the local day; a 04:00Z timestamp on 2024-07-16
    # belongs to local 2024-07-16 midnight EDT (00:00), still local day 16, but 23:00Z on
    # 2024-07-15 is local 19:00 EDT on the 15th -> must map to local day 15, not 16.
    ts_2300z_15 = datetime(2024, 7, 15, 23, 0, tzinfo=to_utc(datetime(2024, 1, 1, tzinfo=NY)).tzinfo)
    assert is_in_local_day(ts_2300z_15, date(2024, 7, 15))
    assert not is_in_local_day(ts_2300z_15, date(2024, 7, 16))


def test_valid_times_outside_local_day_detected():
    from central_park_tmax.evaluation.diagnostics import check_valid_times_in_local_day
    start, end = local_day_bounds_utc(date(2024, 7, 15))
    times = [start, start + timedelta(hours=12), end + timedelta(hours=1)]
    outside = check_valid_times_in_local_day(times, date(2024, 7, 15))
    assert outside == 1
