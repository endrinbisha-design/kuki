import numpy as np

from central_park_tmax.models.blend import ConvexBlend


def test_blend_weights_nonnegative_sum_to_one():
    rng = np.random.default_rng(0)
    y = rng.normal(80, 5, 200)
    preds = {
        "good": y + rng.normal(0, 0.5, 200),
        "bad": y + rng.normal(3, 3.0, 200),
    }
    blend = ConvexBlend(model_names=["good", "bad"]).fit(preds, y)
    w = blend.weight_map()
    assert all(v >= 0 for v in w.values())
    assert abs(sum(w.values()) - 1.0) < 1e-6
    # The much-better model should dominate.
    assert w["good"] > 0.8


def test_blend_falls_back_to_single_best():
    rng = np.random.default_rng(1)
    y = rng.normal(80, 5, 100)
    preds = {
        "only": y + rng.normal(0, 1, 100),
    }
    blend = ConvexBlend(model_names=["only"]).fit(preds, y)
    assert blend.weight_map() == {"only": 1.0}
    out = blend.predict({"only": np.array([80.0, 85.0])})
    assert out.shape == (2,)


def test_blend_never_uses_missing_model():
    rng = np.random.default_rng(2)
    y = rng.normal(80, 5, 100)
    preds = {"a": y + rng.normal(0, 1, 100)}
    blend = ConvexBlend(model_names=["a", "not_supplied"]).fit(preds, y)
    assert "not_supplied" not in blend.weight_map()
