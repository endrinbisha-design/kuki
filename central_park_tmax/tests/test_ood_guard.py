import numpy as np
import pandas as pd

from central_park_tmax.models.ood_guard import (FeatureStats, apply_shrink, assess_ood)


def _stats_and_importance(n=100, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({
        "a": rng.normal(0, 1, n),
        "b": rng.normal(10, 2, n),
        "c": rng.uniform(-1, 1, n),
    })
    stats = FeatureStats.from_frame(X)
    importance = {"a": 0.5, "b": 0.3, "c": 0.2}
    return stats, importance


def test_in_distribution_row_not_shrunk():
    stats, imp = _stats_and_importance()
    row = {"a": 0.1, "b": 10.5, "c": 0.0}
    ood = assess_ood(row, stats, imp)
    assert ood.score == 0.0 and ood.shrink == 1.0


def test_out_of_distribution_row_shrunk():
    stats, imp = _stats_and_importance()
    # All three key features far outside the training envelope.
    row = {"a": 25.0, "b": -40.0, "c": 9.0}
    ood = assess_ood(row, stats, imp)
    assert ood.score == 1.0
    assert ood.shrink == 0.25            # floor
    assert set(ood.offending) == {"a", "b", "c"}


def test_partial_ood_shrinks_partially():
    stats, imp = _stats_and_importance()
    row = {"a": 25.0, "b": 10.0, "c": 0.0}   # 1 of 3 outside
    ood = assess_ood(row, stats, imp)
    assert 0.25 < ood.shrink < 1.0


def test_apply_shrink_moves_toward_baseline_never_past():
    # +4F correction shrunk by 0.25 -> +1F; baseline itself is the fixed point.
    assert apply_shrink(79.0, 83.0, 0.25) == 80.0
    assert apply_shrink(79.0, 83.0, 1.0) == 83.0
    # Negative corrections shrink symmetrically.
    assert apply_shrink(90.0, 86.0, 0.5) == 88.0


def test_missing_stats_features_are_ignored():
    stats, imp = _stats_and_importance()
    imp = {**imp, "not_in_training": 0.9}
    row = {"a": 0.0, "b": 10.0, "c": 0.0, "not_in_training": 1e9}
    ood = assess_ood(row, stats, imp)
    assert ood.shrink == 1.0


def test_consensus_cap_binds_on_tight_agreement():
    from central_park_tmax.models.ood_guard import consensus_cap
    # The observed live failure: NBM 79.25, HRRR 79.0, GFS 80.9 (spread ~0.9F) but
    # a +4.05F learned correction. Cap = 2*spread -> correction bounded near +1.7F.
    point, a = consensus_cap(79.25, 83.3, {"hrrr": 79.0, "gfs": 80.9})
    assert a.applied
    assert point < 81.5                    # pulled well below the raw +4 correction
    assert abs((point - 79.25) - a.cap_f) < 1e-9


def test_consensus_cap_inactive_on_disagreement():
    from central_park_tmax.models.ood_guard import consensus_cap
    # Models 6F apart -> cap 12F -> a +4 correction is untouched.
    point, a = consensus_cap(80.0, 84.0, {"hrrr": 74.0, "gfs": 86.0})
    assert not a.applied and point == 84.0


def test_consensus_cap_needs_two_models():
    from central_park_tmax.models.ood_guard import consensus_cap
    point, a = consensus_cap(80.0, 84.0, {})
    assert not a.applied and point == 84.0
