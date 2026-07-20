"""Tests for the improved observed-max-so-far reconstruction.

Motivated by real data: on 2026-07-20 the KNYC peak was 81F at 1:25 PM, but hourly
METAR snapshots topped out at 80.1F (2:51 PM) because the peak fell between hourly obs.
The floor/feature must use the best available source, not just the hourly snapshot.
"""
from datetime import datetime, timezone

import pandas as pd

from central_park_tmax.data.hourly_observations import max_so_far_with_provenance
from central_park_tmax.time_utils import NY, local_datetime, to_utc


def _obs(rows):
    return pd.DataFrame(rows)


def test_six_hour_group_beats_hourly_snapshot():
    # Hourly snapshots peak at 80; a 6-hour max group encodes the true 81F peak.
    # "10272" = 1(6-hr max group) 0(positive) 272 tenths C = 27.2C = 81.0F.
    day = local_datetime(__import__("datetime").date(2026, 7, 20), 12).date()
    now = to_utc(local_datetime(day, 15))
    obs = _obs([
        {"timestamp_utc": to_utc(local_datetime(day, 12)), "temp_f": 79.0, "raw_metar": ""},
        {"timestamp_utc": to_utc(local_datetime(day, 14)), "temp_f": 80.0,
         "raw_metar": "KNYC 201800Z AUTO 26/11 RMK AO2 T02610100 10272 20200"},
    ])
    val, src = max_so_far_with_provenance(obs, day, now)
    assert src == "metar_6h_group"
    assert abs(val - 81.0) < 0.2


def test_intraday_cli_max_wins_when_highest():
    from datetime import date
    day = date(2026, 7, 20)
    now = to_utc(local_datetime(day, 17))
    obs = _obs([
        {"timestamp_utc": to_utc(local_datetime(day, 14)), "temp_f": 80.1, "raw_metar": ""},
    ])
    val, src = max_so_far_with_provenance(obs, day, now, intraday_report_max_f=81.0)
    assert src == "nws_cli_intraday"
    assert val == 81.0


def test_falls_back_to_hourly_when_only_snapshots():
    from datetime import date
    day = date(2026, 7, 20)
    now = to_utc(local_datetime(day, 15))
    obs = _obs([
        {"timestamp_utc": to_utc(local_datetime(day, 12)), "temp_f": 79.0, "raw_metar": ""},
        {"timestamp_utc": to_utc(local_datetime(day, 14)), "temp_f": 80.1, "raw_metar": ""},
    ])
    val, src = max_so_far_with_provenance(obs, day, now)
    assert src == "metar_hourly" and abs(val - 80.1) < 1e-6


def test_no_lookahead_on_cli_time_handled_by_caller():
    # The function trusts the caller's supplied CLI max; predict._try_intraday_cli_max
    # enforces the issuance<=issue_utc no-lookahead rule. Here just confirm None obs works.
    from datetime import date
    day = date(2026, 7, 20)
    now = to_utc(local_datetime(day, 17))
    val, src = max_so_far_with_provenance(None, day, now, intraday_report_max_f=81.0)
    assert val == 81.0 and src == "nws_cli_intraday"


def test_intraday_feature_uses_best_max():
    from datetime import date
    from central_park_tmax.features.intraday import intraday_features
    day = date(2026, 7, 20)
    issue = to_utc(local_datetime(day, 15))
    obs = _obs([
        {"timestamp_utc": to_utc(local_datetime(day, 12)), "temp_f": 79.0, "raw_metar": ""},
        {"timestamp_utc": to_utc(local_datetime(day, 14)), "temp_f": 80.1, "raw_metar": ""},
    ])
    feats = intraday_features(obs, day, issue, intraday_report_max_f=81.0)
    assert feats["observed_max_so_far_f"] == 81.0
    assert feats["observed_max_snapshot_f"] == 80.1     # coarse hourly kept for reference
    assert feats["observed_max_so_far_source"] == "nws_cli_intraday"
