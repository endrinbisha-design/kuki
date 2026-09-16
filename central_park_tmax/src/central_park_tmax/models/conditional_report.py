"""Research PMF for a reported integer high, jointly learning warming/measurement gap.

Learn report_high - rounded_observed_max directly; do not convolve independent gap
and warming distributions. Negative residuals are retained (rounding/revisions).
The caller must establish the report day and source-vintage/availability provenance.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .conditional_rise import state_key

REPORT_SUPPORT = np.arange(-100, 201)


def rounded(values):
    return np.floor(np.asarray(values, dtype=float) + .5).astype(int)


@dataclass
class ConditionalReportHigh:
    prior_strength: float = 30.

    def fit(self, frame):
        cols = ["hour", "drop_from_max", "slope", "observed_max", "cli_high"]
        if frame.empty or not np.isfinite(frame[cols]).all().all():
            raise ValueError("Nonempty finite training data required.")
        if not np.isfinite(self.prior_strength) or self.prior_strength <= 0:
            raise ValueError("Positive prior_strength required.")
        if frame.duplicated(["date", "hour"]).any() or pd.to_datetime(frame.date).isna().any():
            raise ValueError("Require unique dated hourly snapshots.")
        if not np.equal(frame.cli_high, rounded(frame.cli_high)).all():
            raise ValueError("CLI highs must be integers.")
        self.train_end = pd.to_datetime(frame.date).max()
        f = frame.assign(residual=frame.cli_high.to_numpy() - rounded(frame.observed_max))
        self.hours = {int(h): g.residual.to_numpy(dtype=int) for h, g in f.groupby("hour")}
        self.cells = {}
        for r in f.itertuples():
            self.cells.setdefault(state_key(r.hour, r.drop_from_max, r.slope), []).append(r.residual)
        self.cells = {k: np.asarray(v, dtype=int) for k, v in self.cells.items()}
        return self

    def predict_pmf(self, frame, *, conditional=True):
        if not hasattr(self, "train_end"):
            raise RuntimeError("Fit first.")
        if not np.isfinite(frame[["hour", "drop_from_max", "slope", "observed_max"]]).all().all():
            raise ValueError("Finite features required.")
        dates = pd.to_datetime(frame.date)
        if dates.isna().any() or dates.le(self.train_end).any():
            raise ValueError("Forecast dates must follow all training dates.")
        out = []
        for r in frame.itertuples():
            prior = self.hours.get(int(r.hour))
            if prior is None:
                raise ValueError("Unseen decision hour.")
            origin = int(rounded([r.observed_max])[0])
            def histogram(samples):
                ix = origin + samples - REPORT_SUPPORT[0]
                if ((ix < 0) | (ix >= len(REPORT_SUPPORT))).any():
                    raise ValueError("Expand report support rather than clip tail probabilities.")
                return np.bincount(ix, minlength=len(REPORT_SUPPORT)) / len(ix)
            pmf = histogram(prior)
            cell = self.cells.get(state_key(r.hour, r.drop_from_max, r.slope))
            if conditional and cell is not None:
                weight = len(cell) / (len(cell) + self.prior_strength)
                pmf = (1 - weight) * pmf + weight * histogram(cell)
            out.append(pmf)
        return np.asarray(out)
