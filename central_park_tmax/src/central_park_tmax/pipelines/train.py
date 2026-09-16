"""Train residual models per forecast vintage and save reproducible artifacts.

Saved with each model bundle (for reproducibility / model-card):
  * fitted boosting residual model (+ quantile model),
  * feature names, training date range, reporting-convention + contract-rule versions,
  * out-of-sample residuals for empirical uncertainty, random seed, git commit hash,
  * a copy of the resolved config.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from ..config import AppConfig, save_resolved_config
from ..logging_config import get_logger
from ..models.boosting import BoostingResidualModel
from ..models.calibration import ResidualCalibrator
from ..models.features_frame import FeatureMatrix
from ..models.quantiles import QuantileBoosting
from ..data.storage import sha256_file, write_json
from ..evaluation.splits import train_tune_calibration_split
from .. import __version__

log = get_logger(__name__)


def _select_hyperparameters(cfg: AppConfig, fm_tr, fm_val) -> dict:
    """Small, time-series-aware hyperparameter search.

    Candidates are scored by MAE on the chronological validation tail (never the test
    period). Falls back to the configured defaults when search is disabled or the
    validation tail is too small to rank candidates meaningfully.
    """
    b = cfg.models.boosting
    defaults = dict(n_estimators=b.n_estimators, learning_rate=b.learning_rate,
                    max_depth=b.max_depth, reg_lambda=b.reg_lambda,
                    min_child_weight=b.min_child_weight)
    hp = cfg.models.hyperparameter_search
    if not hp.enabled or fm_val is None or len(fm_val) < 20:
        return defaults

    grid = [
        defaults,
        {**defaults, "max_depth": 3},
        {**defaults, "max_depth": 6},
        {**defaults, "learning_rate": 0.06, "n_estimators": max(200, b.n_estimators // 2)},
        {**defaults, "learning_rate": 0.015, "n_estimators": b.n_estimators * 2},
        {**defaults, "reg_lambda": 5.0},
        {**defaults, "min_child_weight": 10.0},
        {**defaults, "max_depth": 3, "reg_lambda": 5.0},
    ][: max(1, hp.max_candidates)]

    best_params, best_mae = defaults, float("inf")
    for cand in grid:
        try:
            m = BoostingResidualModel(
                backend=b.backend, early_stopping_rounds=b.early_stopping_rounds,
                random_state=cfg.models.random_seed, **cand,
            ).fit(fm_tr, valid=fm_val)
            mae = float(np.mean(np.abs(m.predict(fm_val) - fm_val.y.to_numpy())))
            if mae < best_mae:
                best_mae, best_params = mae, cand
        except Exception as exc:  # noqa: BLE001
            log.warning("hyperparameter candidate %s failed: %s", cand, exc)
    log.info("hyperparameter search: best val MAE=%.3f params=%s", best_mae, best_params)
    return best_params


def _git_hash() -> Optional[str]:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return None


@dataclass
class VintageModel:
    vintage: str
    boosting: BoostingResidualModel
    quantile_model: Optional[QuantileBoosting]
    feature_names: list[str]
    oos_residuals: np.ndarray
    reporting_method: str
    contract_rule_version: str
    train_start: str
    train_end: str
    n_train: int
    feature_stats: Optional[object] = None   # ood_guard.FeatureStats (None in old bundles)
    tune_start: Optional[str] = None
    tune_end: Optional[str] = None
    calibration_start: Optional[str] = None
    calibration_end: Optional[str] = None
    n_calibration: int = 0


@dataclass
class TrainedBundle:
    package_version: str
    trained_at_utc: str
    git_hash: Optional[str]
    random_seed: int
    reporting_method: str
    contract_rule_version: str
    quantiles: list[float]
    models: dict[str, VintageModel] = field(default_factory=dict)


def train_models(cfg: AppConfig, dataset: pd.DataFrame,
                 target_col: str = "target_report_max_f",
                 save_path: Optional[Path] = None) -> TrainedBundle:
    bundle = TrainedBundle(
        package_version=__version__,
        trained_at_utc=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        git_hash=_git_hash(),
        random_seed=cfg.models.random_seed,
        reporting_method=cfg.reporting_convention.method,
        contract_rule_version=cfg.contract_rules.version,
        quantiles=cfg.models.quantiles,
    )
    vintages = sorted(dataset["vintage"].unique()) if "vintage" in dataset else ["default"]
    for vintage in vintages:
        vdf = (dataset[dataset["vintage"] == vintage] if "vintage" in dataset else dataset)
        vdf = vdf.dropna(subset=[target_col, "baseline_tmax_f"]).sort_values("date").reset_index(drop=True)
        if pd.to_datetime(vdf["date"]).dt.normalize().nunique() < 30:
            log.warning("Vintage %s: fewer than 30 distinct labeled dates; skipping training.", vintage)
            continue
        tr_core, tr_val, tr_cal = train_tune_calibration_split(vdf)
        fm_tr = FeatureMatrix.from_frame(tr_core, target_col=target_col)
        fm_val = (FeatureMatrix.from_frame(tr_val, target_col=target_col,
                                           feature_names=fm_tr.feature_names)
                  if len(tr_val) else None)

        params = _select_hyperparameters(cfg, fm_tr, fm_val)
        boost = BoostingResidualModel(
            backend=cfg.models.boosting.backend,
            early_stopping_rounds=cfg.models.boosting.early_stopping_rounds,
            random_state=cfg.models.random_seed,
            **params,
        ).fit(fm_tr, valid=fm_val)

        qmodel = None
        try:
            qmodel = QuantileBoosting(quantiles=cfg.models.quantiles,
                                      random_state=cfg.models.random_seed).fit(fm_tr)
        except Exception as exc:  # noqa: BLE001
            log.warning("Quantile model training failed for %s: %s", vintage, exc)

        calib = ResidualCalibrator()
        fm_cal = FeatureMatrix.from_frame(tr_cal, target_col=target_col,
                                           feature_names=fm_tr.feature_names)
        calib.add(fm_cal.y.to_numpy(), boost.predict(fm_cal))

        from ..models.ood_guard import FeatureStats
        bundle.models[vintage] = VintageModel(
            vintage=vintage, boosting=boost, quantile_model=qmodel,
            feature_names=fm_tr.feature_names, oos_residuals=calib.array(),
            reporting_method=cfg.reporting_convention.method,
            contract_rule_version=cfg.contract_rules.version,
            train_start=str(tr_core["date"].min()), train_end=str(tr_core["date"].max()),
            n_train=len(tr_core),
            feature_stats=FeatureStats.from_frame(fm_tr.X),
            tune_start=str(tr_val["date"].min()), tune_end=str(tr_val["date"].max()),
            calibration_start=str(tr_cal["date"].min()),
            calibration_end=str(tr_cal["date"].max()), n_calibration=len(tr_cal),
        )
        log.info("Trained vintage=%s backend=%s n=%d resid_std=%.2f",
                 vintage, boost.name, len(tr_core), float(np.std(calib.array())))

    if save_path is None:
        save_path = Path(cfg.paths.models_dir) / "model_bundle.joblib"
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, save_path)
    save_resolved_config(cfg, save_path.with_suffix(".config.yaml"))
    _write_model_card(cfg, bundle, save_path)
    log.info("Saved model bundle: %s (sha256=%s)", save_path, sha256_file(save_path)[:12])
    return bundle


def load_bundle(path: Path | str) -> TrainedBundle:
    return joblib.load(path)


def _write_model_card(cfg: AppConfig, bundle: TrainedBundle, path: Path) -> None:
    card = {
        "model_name": "xgboost_residual (or backend fallback)",
        "package_version": bundle.package_version,
        "trained_at_utc": bundle.trained_at_utc,
        "git_hash": bundle.git_hash,
        "random_seed": bundle.random_seed,
        "reporting_convention": bundle.reporting_method,
        "contract_rule_version": bundle.contract_rule_version,
        "station": cfg.station.model_dump(),
        "vintages": {
            v: {"n_train": m.n_train, "train_start": m.train_start, "train_end": m.train_end,
                "tune_start": m.tune_start, "tune_end": m.tune_end,
                "calibration_start": m.calibration_start, "calibration_end": m.calibration_end,
                "n_calibration": m.n_calibration,
                "n_features": len(m.feature_names), "backend": m.boosting.name,
                "residual_std_f": float(np.std(m.oos_residuals))}
            for v, m in bundle.models.items()
        },
        "limitations": (
            "Residual model corrects a numerical baseline; quality depends on baseline "
            "availability. In synthetic mode the data are simulated and NOT real weather."),
    }
    write_json(path.with_suffix(".model_card.json"), card)
