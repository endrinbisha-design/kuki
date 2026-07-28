"""Low-latency METAR feed + settlement-max reconstruction (data/fast_metar.py)."""
from datetime import date, datetime, timezone

from central_park_tmax.data.fast_metar import (parse_metar_block, settlement_max_so_far)

# Real KNYC block from 2026-07-28 — the day the hourly snapshots (78.08F) disagreed
# with the market (79-80 @93c). The 6-hour group 10261 = 26.1C = 79.0F resolves it.
BLOCK = """METAR KNYC 281751Z AUTO VRB03KT 10SM CLR 25/22 A2970 RMK AO2 SLP047 T02500217 10261 20228 58014 $
METAR KNYC 281651Z AUTO 00000KT 10SM SCT020 25/22 A2972 RMK AO2 SLP054 T02500222 $
SPECI KNYC 281627Z AUTO VRB03KT 9SM BKN021 24/22 A2973 RMK AO2 T02440217 $
METAR KNYC 281551Z AUTO 00000KT 9SM FEW025 25/22 A2974 RMK AO2 SLP060 T02500217 $"""

REF = datetime(2026, 7, 28, 18, 0, tzinfo=timezone.utc)


def test_parses_metar_and_speci():
    obs = parse_metar_block(BLOCK, REF)
    assert len(obs) == 4
    assert obs[0].issued_utc == datetime(2026, 7, 28, 17, 51, tzinfo=timezone.utc)
    assert any(o.is_speci for o in obs)


def test_instantaneous_temperature_decoded():
    obs = parse_metar_block(BLOCK, REF)
    assert abs(obs[0].temp_f - 77.0) < 0.05          # T02500217 -> 25.0C


def test_six_hour_max_group_decoded():
    obs = parse_metar_block(BLOCK, REF)
    assert abs(obs[0].six_hour_max_f - 78.98) < 0.05  # 10261 -> 26.1C = 79.0F


def test_settlement_max_prefers_six_hour_group():
    obs = parse_metar_block(BLOCK, REF)
    s = settlement_max_so_far(obs, date(2026, 7, 28), utc_offset_hours=0)
    assert s.source == "metar_6h_group"
    assert abs(s.best_max_f - 78.98) < 0.05
    assert s.gap_f > 1.5            # the spike the hourly snapshots missed
    assert int(s.best_max_f + 0.5) == 79     # settles 79 -> the bucket the market held


def test_empty_input_is_safe():
    s = settlement_max_so_far([], date(2026, 7, 28), utc_offset_hours=-4)
    assert s.best_max_f is None and s.source == "none"
