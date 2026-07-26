"""Post-peak settlement probabilities (models/post_peak.py)."""
from central_park_tmax.models.post_peak import (bucket_probability, edge_vs_price,
                                                remaining_rise_cdf, resolve_city_key,
                                                settlement_distribution)


def test_city_resolution_and_table_loads():
    assert resolve_city_key("KNYC") == "nyc"
    assert resolve_city_key("KDEN") is None
    cdf = remaining_rise_cdf("nyc", 16)
    assert cdf and 0.9 < cdf[0] <= 1.0        # NYC 4pm: max is almost always already in


def test_late_afternoon_is_determined():
    # Jul 25 live NYC: 80.1F banked at 4pm -> settles 80 with high confidence.
    o = settlement_distribution("KNYC", 80.1, 16)
    assert o.determined and o.top_bucket == 80
    assert o.top_probability > 0.9
    assert bucket_probability(o, 80, 81) > 0.95


def test_midday_is_not_determined():
    # Same temperature at noon leaves plenty of heating: not a safe bet.
    o = settlement_distribution("KNYC", 80.1, 12)
    assert not o.determined
    assert o.top_probability < 0.9


def test_rounding_boundary_is_flagged():
    o = settlement_distribution("KPHX", 116.5, 17)
    assert "rounding boundary" in o.rationale


def test_round_half_up_settlement():
    # 116.6F with the day over settles to 117, not 116.
    o = settlement_distribution("KPHX", 116.6, 17)
    assert o.top_bucket == 117


def test_desert_hours_differ_from_coast():
    # Phoenix peaks later than NYC, so 2pm is far less settled there.
    nyc = settlement_distribution("KNYC", 90.0, 14)
    phx = settlement_distribution("KPHX", 110.0, 14)
    assert nyc.p_max_already_in > phx.p_max_already_in


def test_edge_vs_price_math():
    o = settlement_distribution("KNYC", 80.1, 16)
    e = edge_vs_price(o, 80, 81, yes_price_cents=89)
    assert e["model_probability"] > 0.95
    assert e["edge_cents"] > 0
    assert e["net_edge_cents"] < e["edge_cents"]      # fee subtracted


def test_unknown_station_degrades_gracefully():
    o = settlement_distribution("KDEN", 95.0, 16)
    assert not o.determined and o.integer_probabilities == {}
