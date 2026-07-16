"""Convex model blending with weights estimated ONLY from validation predictions.

Weights are nonnegative and sum to one. They are found by minimizing validation MAE over
the simplex (SLSQP). If the optimizer fails or offers no improvement, the blend falls back
to the single best validation model (a one-hot weight vector). Test-period targets are never
used to estimate weights.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class ConvexBlend:
    model_names: list[str]
    weights: Optional[np.ndarray] = None
    name: str = "convex_blend"

    def fit(self, val_predictions: dict[str, np.ndarray], val_actual: np.ndarray) -> "ConvexBlend":
        names = [n for n in self.model_names if n in val_predictions]
        self.model_names = names
        P = np.column_stack([val_predictions[n] for n in names])  # (n_obs, n_models)
        y = np.asarray(val_actual, dtype=float)
        mask = ~np.isnan(y)
        P, y = P[mask], y[mask]
        k = P.shape[1]
        if k == 0:
            raise ValueError("No models available to blend.")
        if k == 1:
            self.weights = np.array([1.0])
            return self

        from scipy.optimize import minimize

        def obj(w: np.ndarray) -> float:
            pred = P @ w
            return float(np.mean(np.abs(pred - y)))

        w0 = np.full(k, 1.0 / k)
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, 1.0)] * k
        try:
            res = minimize(obj, w0, method="SLSQP", bounds=bounds, constraints=cons,
                           options={"maxiter": 500, "ftol": 1e-8})
            w = np.clip(res.x, 0, None)
            w = w / w.sum() if w.sum() > 0 else w0
        except Exception:  # noqa: BLE001
            w = w0
        # Fall back to single best if blend does not beat it on validation.
        single_maes = [float(np.mean(np.abs(P[:, i] - y))) for i in range(k)]
        best_i = int(np.argmin(single_maes))
        if obj(w) > single_maes[best_i] - 1e-9:
            w = np.zeros(k)
            w[best_i] = 1.0
        self.weights = w
        return self

    def predict(self, predictions: dict[str, np.ndarray]) -> np.ndarray:
        if self.weights is None:
            raise RuntimeError("Blend not fitted.")
        P = np.column_stack([predictions[n] for n in self.model_names])
        return P @ self.weights

    def weight_map(self) -> dict[str, float]:
        if self.weights is None:
            return {}
        return {n: float(w) for n, w in zip(self.model_names, self.weights)}
