import numpy as np

from central_park_tmax.features.wind import (angular_difference_deg, onshore_component,
                                             summarize_wind, wind_components)


def test_direction_boundary_359_and_1_are_similar():
    # 359 deg and 1 deg differ by 2 deg, not 358.
    assert abs(angular_difference_deg(1, 359)) == 2
    u1, v1 = wind_components(359, 10)
    u2, v2 = wind_components(1, 10)
    assert np.hypot(u1 - u2, v1 - v2) < 1.0  # vector components nearly identical


def test_opposite_directions_are_far():
    assert abs(angular_difference_deg(0, 180)) == 180


def test_onshore_component_positive_for_marine_sector():
    # Wind from ~150 deg (SSE, the onshore reference) => strongly positive onshore component.
    on = onshore_component(150, 10)
    off = onshore_component(330, 10)  # offshore (NNW)
    assert on > 0 > off
    assert np.isclose(on, 10, atol=1e-6)


def test_summarize_wind_uses_vector_mean_across_boundary():
    import pandas as pd
    # Winds oscillating around north (350..010) should average near north, not near 180.
    dirs = [350, 355, 0, 5, 10]
    df = pd.DataFrame({"wind_dir_deg": dirs, "wind_speed_mph": [10] * 5})
    out = summarize_wind(df)
    # Northerly winds average coherently (no 0/360 cancellation): v strongly negative
    # (wind FROM north blows toward south => v = -s*cos(0) < 0), u near zero.
    assert abs(out["wind_u_mean"]) < 2.0
    assert out["wind_v_mean"] < -5.0


def test_wind_components_westerly():
    # Wind FROM the west (270) blows toward the east => positive u (zonal eastward).
    u, v = wind_components(270, 10)
    assert u > 8 and abs(v) < 1e-6
