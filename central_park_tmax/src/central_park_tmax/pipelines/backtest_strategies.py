"""Walk-forward strategy backtest: model PMFs vs market quotes on NHIGH bucket ladders.

Pipeline:
  1. Rolling-origin folds over the labeled dataset (same leakage rules as the model
     backtest: each test day is predicted by a model trained only on earlier days, with
     residual calibration from the training tail only).
  2. For each test day, build the market ladder centered on the issue-time NBM baseline
     and obtain quotes — real Kalshi candles where reachable, else the documented
     simulated market maker.
  3. Each strategy decides trades from (quotes, model PMF); trades settle on the real
     recorded integer outcome with Kalshi taker fees.

Everything the strategies see (baseline, PMF, quotes) is information available at the
forecast issue time. Outcomes are used only for settlement. This is research tooling;
it places no orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..config import AppConfig
from ..contracts.strategies import (EdgeThresholdFlat, FractionalKelly, StrategyResult,
                                    TailFade)
from ..data.kalshi import (KalshiMarketDataSource, MarketDataUnavailable,
                           SimulatedMarketDataSource)
from ..data.storage import http_client_from_config, write_json
from ..evaluation.splits import auto_folds_from_span, folds_from_config, train_valid_split
from ..logging_config import get_logger
from ..models.boosting import BoostingResidualModel
from ..models.calibration import ResidualCalibrator
from ..models.discrete_outcomes import integer_report_distribution, simulate_from_residuals
from ..models.features_frame import FeatureMatrix

log = get_logger(__name__)


@dataclass
class DayRecord:
    target_date: date
    pmf: dict[int, float]
    outcome: int
    baseline_tmax_f: float


def walk_forward_pmfs(cfg: AppConfig, dataset: pd.DataFrame,
                      target_col: str = "target_report_max_f",
                      n_draws: int = 8000) -> list[DayRecord]:
    """Out-of-sample integer PMFs for every test day across rolling-origin folds."""
    from ..evaluation.backtest import resolve_folds
    df = dataset.dropna(subset=[target_col, "baseline_tmax_f"]).sort_values("date").reset_index(drop=True)
    folds = resolve_folds(cfg, df)

    records: list[DayRecord] = []
    rng = np.random.default_rng(cfg.models.random_seed)
    for fold in folds:
        tr = df[fold.train_mask(df["date"])].reset_index(drop=True)
        te = df[fold.test_mask(df["date"])].reset_index(drop=True)
        if len(tr) < 30 or len(te) == 0:
            continue
        tr_core, tr_val = train_valid_split(tr, valid_fraction=0.15)
        fm_tr = FeatureMatrix.from_frame(tr_core, target_col=target_col)
        fm_val = (FeatureMatrix.from_frame(tr_val, target_col=target_col,
                                           feature_names=fm_tr.feature_names)
                  if len(tr_val) else None)
        model = BoostingResidualModel(
            backend=cfg.models.boosting.backend,
            n_estimators=cfg.models.boosting.n_estimators,
            learning_rate=cfg.models.boosting.learning_rate,
            max_depth=cfg.models.boosting.max_depth,
            random_state=cfg.models.random_seed,
        ).fit(fm_tr, valid=fm_val)
        calib = ResidualCalibrator()
        if fm_val is not None and len(fm_val):
            calib.add(fm_val.y.to_numpy(), model.predict(fm_val))
        else:
            calib.add(fm_tr.y.to_numpy(), model.predict(fm_tr))
        residuals = calib.array()

        fm_te = FeatureMatrix.from_frame(te, target_col=target_col,
                                         feature_names=fm_tr.feature_names)
        points = model.predict(fm_te)
        for i, row in te.iterrows():
            samples = simulate_from_residuals(float(points[i]), residuals, n_draws, rng)
            dist = integer_report_distribution(
                samples, convention=cfg.reporting_convention.method)
            records.append(DayRecord(
                target_date=date.fromisoformat(str(row["date"])[:10]),
                pmf=dist.pmf,
                outcome=int(row[target_col]),
                baseline_tmax_f=float(row["baseline_tmax_f"]),
            ))
    return records


def default_strategies() -> list:
    return [EdgeThresholdFlat(edge_threshold=0.08),
            FractionalKelly(edge_threshold=0.05, kelly_fraction=0.25),
            TailFade()]


def run_strategy_backtest(cfg: AppConfig, dataset: pd.DataFrame,
                          use_simulated_market: bool = True,
                          save: bool = True) -> dict:
    records = walk_forward_pmfs(cfg, dataset)
    if not records:
        raise ValueError("No out-of-sample days available for the strategy backtest.")
    log.info("Walk-forward produced %d out-of-sample day PMFs.", len(records))

    sim = SimulatedMarketDataSource()
    real: Optional[KalshiMarketDataSource] = None
    if not use_simulated_market:
        real = KalshiMarketDataSource(http_client_from_config(cfg))

    strategies = default_strategies()
    results = {s.name: StrategyResult(name=s.name) for s in strategies}
    market_source_used = "simulated" if use_simulated_market else "kalshi"
    n_days_priced = 0

    for rec in records:
        if real is not None:
            try:
                from ..time_utils import local_datetime, to_utc
                issue = to_utc(local_datetime(rec.target_date, 19))  # prev-evening proxy
                market = real.day_market(rec.target_date, issue)
            except MarketDataUnavailable as exc:
                raise MarketDataUnavailable(
                    f"Real Kalshi data unavailable ({exc}); rerun with simulated market."
                ) from exc
        else:
            market = sim.day_market(rec.target_date, rec.baseline_tmax_f)
        n_days_priced += 1
        bucket_by_label = {q.bucket.label(): q.bucket for q in market.quotes}
        for strat in strategies:
            for trade in strat.decide(market, rec.pmf):
                trade.settle(rec.outcome, bucket_by_label[trade.bucket_label])
                results[strat.name].trades.append(trade)

    summaries = [results[s.name].summary() for s in strategies]
    out = {
        "market_source": market_source_used,
        "market_disclaimer": (
            "SIMULATED market prices (Kalshi API unreachable in this environment): "
            "results measure strategy behavior against a documented pseudo-market maker "
            "anchored on the same public NBM guidance, NOT realized profitability."
            if use_simulated_market else
            "Real Kalshi entry prices from public candlesticks at/before issue time."),
        "n_days": n_days_priced,
        "strategies": summaries,
    }
    if save:
        path = Path(cfg.paths.metrics_dir) / "strategy_backtest.json"
        write_json(path, out)
        log.info("Saved strategy backtest: %s", path)
    return out
