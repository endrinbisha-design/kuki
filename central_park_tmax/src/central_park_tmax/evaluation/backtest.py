"""Rolling-origin backtest across forecast vintages with leakage-safe per-fold fitting.

For each vintage and each fold: fit baselines + residual models on the training window only
(with a chronological validation tail for early stopping and empirical residual calibration),
predict the test window, and score continuous, quantile, integer, and contract targets.

All transforms (imputation medians, scalers, residual quantiles, blend weights) are fit on
train/validation only. The test window's targets are never used for any fitting decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..config import AppConfig
from ..logging_config import get_logger
from ..models.baselines import (ClimateNormalBaseline, PersistenceBaseline,
                                 RawPrimaryBaseline, RollingBiasBaseline)
from ..models.boosting import BoostingResidualModel
from ..models.calibration import ResidualCalibrator
from ..models.discrete_outcomes import (integer_report_distribution, simulate_from_residuals)
from ..models.features_frame import FeatureMatrix
from ..models.linear import LinearResidual
from ..models.quantiles import EmpiricalResidualQuantiles
from ..contracts.probabilities import contract_probability_report
from . import metrics as M
from .splits import Fold, folds_from_config, train_valid_split

log = get_logger(__name__)


@dataclass
class BacktestResult:
    per_vintage: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"per_vintage": self.per_vintage, "summary": self.summary}


def run_backtest(cfg: AppConfig, dataset: pd.DataFrame,
                 target_col: str = "target_report_max_f") -> BacktestResult:
    folds = folds_from_config(cfg.validation.folds)
    result = BacktestResult()
    vintages = sorted(dataset["vintage"].unique()) if "vintage" in dataset else ["default"]
    thresholds = (cfg.contracts.example_thresholds if cfg.contracts else {})
    convention = cfg.reporting_convention.method

    for vintage in vintages:
        vdf = dataset[dataset["vintage"] == vintage] if "vintage" in dataset else dataset
        vdf = vdf.dropna(subset=[target_col, "baseline_tmax_f"]).reset_index(drop=True)
        if len(vdf) < cfg.validation.min_train_days:
            log.warning("Vintage %s has only %d rows; skipping.", vintage, len(vdf))
        model_names = ["raw_primary", "rolling_bias_30d", "linear_residual", "boosting_residual"]
        fold_rows: list[dict] = []
        contract_rows: list[dict] = []

        for fold in folds:
            tr = vdf[fold.train_mask(vdf["date"])].reset_index(drop=True)
            te = vdf[fold.test_mask(vdf["date"])].reset_index(drop=True)
            if len(tr) < 30 or len(te) == 0:
                continue
            tr_core, tr_val = train_valid_split(tr, valid_fraction=0.15)

            fm_tr = FeatureMatrix.from_frame(tr_core, target_col=target_col)
            fm_val = FeatureMatrix.from_frame(tr_val, target_col=target_col,
                                              feature_names=fm_tr.feature_names) if len(tr_val) else None
            fm_te = FeatureMatrix.from_frame(te, target_col=target_col,
                                             feature_names=fm_tr.feature_names)

            preds: dict[str, np.ndarray] = {}
            preds["raw_primary"] = RawPrimaryBaseline().predict(te)
            rb = RollingBiasBaseline(30).fit(tr, pd.to_numeric(tr[target_col]))
            preds["rolling_bias_30d"] = rb.predict(te)
            lin = LinearResidual().fit(fm_tr)
            preds["linear_residual"] = lin.predict(fm_te)
            boost = BoostingResidualModel(
                backend=cfg.models.boosting.backend,
                n_estimators=cfg.models.boosting.n_estimators,
                learning_rate=cfg.models.boosting.learning_rate,
                max_depth=cfg.models.boosting.max_depth,
                random_state=cfg.models.random_seed,
            ).fit(fm_tr, valid=fm_val)
            preds["boosting_residual"] = boost.predict(fm_te)

            actual = pd.to_numeric(te[target_col]).to_numpy(dtype=float)
            for name in model_names:
                cm = M.continuous_metrics(actual, preds[name])
                cm.update({"vintage": vintage, "fold": fold.index, "model": name,
                           "test_year": fold.test_start.year})
                fold_rows.append(cm)

            # Empirical residual uncertainty + integer/contract scoring for the boosting model,
            # calibrated on the validation tail only.
            best = "boosting_residual"
            calib = ResidualCalibrator()
            if fm_val is not None and len(fm_val):
                calib.add(fm_val.y.to_numpy(), boost.predict(fm_val))
            resid = calib.array()
            contract_rows.extend(_score_integers_and_contracts(
                actual, preds[best], resid, convention, thresholds, vintage, fold.index))

        result.per_vintage[vintage] = {
            "continuous": _aggregate(fold_rows, model_names),
            "contract": _aggregate_contract(contract_rows),
            "n_examples": int(len(vdf)),
        }

    result.summary = _summarize(result.per_vintage)
    return result


def _score_integers_and_contracts(actual, point_pred, residuals, convention, thresholds,
                                  vintage, fold) -> list[dict]:
    rng = np.random.default_rng(0)
    rows = []
    for a, p in zip(actual, point_pred):
        samples = simulate_from_residuals(float(p), residuals, 4000, rng)
        dist = integer_report_distribution(samples, convention=convention)
        actual_int = int(round(a))
        ll = M.log_loss_integer(dist.pmf, actual_int)
        rps = M.ranked_probability_score(dist.pmf, actual_int)
        row = {"vintage": vintage, "fold": fold, "log_loss": ll, "rps": rps,
               "exact_hit": 1.0 if dist.mode() == actual_int else 0.0,
               "top2_hit": 1.0 if actual_int in dist.top_two() else 0.0}
        # contract Brier for configured greater_than thresholds
        cprobs = contract_probability_report(dist.pmf, thresholds)
        for k in thresholds.get("greater_than", []):
            prob = cprobs.get(f"greater_than_{k}")
            outcome = 1.0 if actual_int > k else 0.0
            row[f"gt_{k}_prob"] = prob
            row[f"gt_{k}_outcome"] = outcome
        rows.append(row)
    return rows


def _aggregate(rows: list[dict], model_names: list[str]) -> dict:
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    out = {}
    for name in model_names:
        sub = df[df["model"] == name]
        if sub.empty:
            continue
        out[name] = {
            "mae": float(sub["mae"].mean()),
            "rmse": float(sub["rmse"].mean()),
            "mean_error": float(sub["mean_error"].mean()),
            "pct_within_2f": float(sub["pct_within_2f"].mean()),
            "by_year": sub.groupby("test_year")["mae"].mean().round(3).to_dict(),
        }
    return out


def _aggregate_contract(rows: list[dict]) -> dict:
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    out = {
        "integer_log_loss": float(df["log_loss"].mean()),
        "integer_rps": float(df["rps"].mean()),
        "exact_integer_accuracy": float(df["exact_hit"].mean()),
        "top_two_accuracy": float(df["top2_hit"].mean()),
    }
    for col in [c for c in df.columns if c.endswith("_prob")]:
        k = col[:-5]
        oc = f"{k}_outcome"
        if oc in df.columns:
            out[f"brier_{k}"] = M.brier_score(df[col].to_numpy(), df[oc].to_numpy())
    return out


def _summarize(per_vintage: dict) -> dict:
    best = {}
    for vintage, res in per_vintage.items():
        cont = res.get("continuous", {})
        if not cont:
            continue
        ranked = sorted(cont.items(), key=lambda kv: kv[1]["mae"])
        best[vintage] = {"best_model": ranked[0][0], "best_mae": ranked[0][1]["mae"],
                         "raw_primary_mae": cont.get("raw_primary", {}).get("mae")}
    return best
