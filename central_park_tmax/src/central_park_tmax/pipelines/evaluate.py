"""Run the rolling-origin backtest, save metrics JSON, and produce plots."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import AppConfig
from ..data.storage import write_json
from ..evaluation.backtest import run_backtest
from ..evaluation.diagnostics import check_dataset
from ..logging_config import get_logger
from ..reporting.plots import plot_backtest_mae

log = get_logger(__name__)


def evaluate(cfg: AppConfig, dataset: pd.DataFrame, save: bool = True) -> dict:
    check_dataset(dataset, raise_on_critical=False)
    result = run_backtest(cfg, dataset)
    out = result.to_dict()
    if save:
        metrics_path = Path(cfg.paths.metrics_dir) / "backtest_metrics.json"
        write_json(metrics_path, out)
        try:
            plot_backtest_mae(result.per_vintage, Path(cfg.paths.figures_dir) / "backtest_mae.png")
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not render backtest plot: %s", exc)
        log.info("Saved backtest metrics: %s", metrics_path)
    return out
