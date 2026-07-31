"""Post-peak settlement probabilities (models/post_peak.py)."""
from central_park_tmax.models.post_peak import (bucket_probability, edge_vs_price,
                                                is_still_rising, remaining_rise_cdf,
                                                resolve_city_key, settlement_distribution)

# A trace that has clearly turned over: required before any max counts as banked.
FALLING = [79.0, 80.1, 79.3, 78.4]


def test_city_resolution_and_table_loads():
    assert resolve_city_key("KNYC") == "nyc"
    assert resolve_city_key("KDEN") is None
    cdf = remaining_rise_cdf("nyc", 16)
    assert cdf and 0.9 < cdf[0] <= 1.0        # NYC 4pm: max is almost always already in


def test_late_afternoon_is_determined():
    # Jul 25 live NYC: 80.1F banked at 4pm -> settles 80 with high confidence.
    o = settlement_distribution("KNYC", 80.1, 16, recent_temps_f=FALLING)
    assert o.determined and o.top_bucket == 80
    assert o.top_probability > 0.9
    assert bucket_probability(o, 80, 81) > 0.95


def test_midday_is_not_determined():
    # Same temperature at noon leaves plenty of heating: not a safe bet.
    o = settlement_distribution("KNYC", 80.1, 12)
    assert not o.determined
    assert o.top_probability < 0.9


def test_rounding_boundary_is_flagged():
    o = settlement_distribution("KPHX", 116.5, 17, recent_temps_f=FALLING)
    assert "rounding boundary" in o.rationale


def test_round_half_up_settlement():
    # 116.6F with the day over settles to 117, not 116.
    o = settlement_distribution("KPHX", 116.6, 17, recent_temps_f=FALLING)
    assert o.top_bucket == 117


def test_desert_hours_differ_from_coast():
    # Phoenix peaks later than NYC, so 2pm is far less settled there.
    nyc = settlement_distribution("KNYC", 90.0, 14)
    phx = settlement_distribution("KPHX", 110.0, 14)
    assert nyc.p_max_already_in > phx.p_max_already_in


def test_edge_vs_price_math():
    o = settlement_distribution("KNYC", 80.1, 16, recent_temps_f=FALLING)
    e = edge_vs_price(o, 80, 81, yes_price_cents=89)
    assert e["model_probability"] > 0.95
    assert e["edge_cents"] > 0
    assert e["net_edge_cents"] < e["edge_cents"]      # fee subtracted


def test_unknown_station_degrades_gracefully():
    o = settlement_distribution("KDEN", 95.0, 16)
    assert not o.determined and o.integer_probabilities == {}


def test_still_rising_blocks_determined():
    """2026-07-29: hourly climatology called all three cities determined while every one
    of them was still climbing. The live trace has to veto the unconditional table."""
    rising = settlement_distribution("KNYC", 80.1, 16, recent_temps_f=[77.0, 79.0, 80.1])
    assert rising.still_rising and not rising.determined
    assert rising.top_probability > 0.9        # climatology alone would have said "yes"
    assert "NOT DETERMINED" in rising.rationale
    assert settlement_distribution("KNYC", 80.1, 16, recent_temps_f=FALLING).determined


def test_no_trace_is_treated_as_still_rising():
    # Absent evidence of a turnover, refuse to call the max banked.
    assert not settlement_distribution("KNYC", 80.1, 16).determined
    assert is_still_rising(None) and is_still_rising([80.0])


def test_noise_sized_dip_is_not_a_peak():
    # ASOS resolves to 0.1C (~0.18F); a dip that small is not evidence of a turnover.
    assert is_still_rising([80.0, 79.95])
    assert not is_still_rising([80.0, 79.5])


def test_distance_is_to_the_half_degree_boundary():
    """2026-07-30 Vegas: 111.02F was 0.48F from settling 112, not 0.98F."""
    o = settlement_distribution("KLAS", 111.02, 17, recent_temps_f=FALLING)
    assert o.distance_to_boundary_f == 0.48
    assert o.top_bucket == 111
    # Just past the boundary, the next tick is a full degree away again.
    assert settlement_distribution("KLAS", 111.6, 17,
                                   recent_temps_f=FALLING).distance_to_boundary_f == 0.9
