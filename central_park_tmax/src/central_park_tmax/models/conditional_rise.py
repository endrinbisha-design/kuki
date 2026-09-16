"""Smoothed conditional distribution of remaining rise in HOURLY snapshots.

This research model replaces an unconditional time-of-day table with a distribution
conditioned on distance below the banked high and recent trend. The target is the
remaining maximum of sampled observations, NOT the official CLI settlement or the
continuous sensor trace. Never substitute this for settlement probabilities without
jointly modeling/reporting that measurement gap and validating the resulting PMF.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

THRESHOLDS = np.array([0.05, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0])


def state_key(hour, drop, slope):
    # Fixed physical bins; no search on the test window.
    return (int(hour), int(np.digitize(drop, [0.5, 2.0, 5.0])),
            int(np.digitize(slope, [-0.2, 0.2])))


@dataclass
class ConditionalRemainingRise:
    prior_strength: float = 30.0

    def fit(self, frame: pd.DataFrame):
        if not np.isfinite(self.prior_strength) or self.prior_strength <= 0:
            raise ValueError("prior_strength must be positive.")
        fields = ["hour", "drop_from_max", "slope", "remaining_rise"]
        if frame.empty or not np.isfinite(frame[fields].to_numpy()).all():
            raise ValueError("Training frame must be nonempty and finite.")
        if (frame.remaining_rise < 0).any():
            raise ValueError("Remaining rise cannot be negative.")
        if frame.duplicated(["date", "hour"]).any():
            raise ValueError("Only one snapshot per date/hour is allowed.")
        self.train_end = pd.to_datetime(frame.date).max()
        self.hour_samples = {int(h): group.remaining_rise.to_numpy()
                             for h, group in frame.groupby("hour")}
        cells = {}
        for r in frame.itertuples():
            key = state_key(r.hour, r.drop_from_max, r.slope)
            cells.setdefault(key, []).append(r.remaining_rise)
        self.cells = {key: np.asarray(values) for key, values in cells.items()}
        return self

    def predict(self, frame: pd.DataFrame, *, conditional=True):
        if not hasattr(self, "train_end"):
            raise RuntimeError("Fit before predicting.")
        if not np.isfinite(frame[["hour", "drop_from_max", "slope"]].to_numpy()).all():
            raise ValueError("Prediction features must be finite.")
        if pd.to_datetime(frame.date).le(self.train_end).any():
            raise ValueError("Prediction dates must follow every training date.")
        cdfs, means = [], []
        for r in frame.itertuples():
            prior = self.hour_samples.get(int(r.hour))
            if prior is None:
                raise ValueError("No training history for this decision hour.")
            pcdf = (prior[:, None] <= THRESHOLDS).mean(axis=0)
            pm = prior.mean()
            cell = self.cells.get(state_key(r.hour, r.drop_from_max, r.slope))
            if conditional and cell is not None:
                w = len(cell) / (len(cell) + self.prior_strength)
                pcdf = (1 - w) * pcdf + w * (cell[:, None] <= THRESHOLDS).mean(axis=0)
                pm = (1 - w) * pm + w * cell.mean()
            cdfs.append(pcdf)
            means.append(pm)
        return np.asarray(cdfs), np.asarray(means)
