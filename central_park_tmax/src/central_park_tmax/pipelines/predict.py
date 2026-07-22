"""Produce a full probabilistic forecast + contract probabilities for one (date, vintage).

Output is a machine-readable record with the continuous distribution, integer-report PMF,
exact NHIGH contract probabilities, provenance, fallback level, and model attributions. The
intraday observed-max constraint is enforced on the entire predictive distribution.

The weather model produces forecasts ONLY. It never declares a settlement result; settlement
is a separate process (see contracts/settlement_state.py, pipelines/ingest_settlement.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..config import AppConfig
from ..constants import FallbackLevel, c_to_f, f_to_c
from ..contracts.probabilities import (contract_probability_report, probability_between_inclusive,
                                        probability_exactly, probability_greater_than,
                                        probability_greater_than_or_equal, probability_less_than,
                                        probability_less_than_or_equal)
from ..data.forecast_base import ForecastSource
from ..data.storage import write_json
from ..data.synthetic import synthetic_observation_frame
from ..evaluation.diagnostics import (check_integer_pmf_sums_to_one, check_quantiles_ordered,
                                      check_prediction_not_below_observed)
from ..features.build_features import build_feature_row
from ..features.intraday import apply_observed_max_constraint
from ..logging_config import get_logger
from ..models.discrete_outcomes import integer_report_distribution, simulate_from_residuals
from ..models.features_frame import FeatureMatrix
from ..models.reporting_convention import convention_version
from ..time_utils import isoformat_local, isoformat_utc, resolve_vintage, to_local, to_utc
from .train import TrainedBundle, VintageModel

log = get_logger(__name__)


def _nearest_vintage_model(bundle: TrainedBundle, vintage: str) -> Optional[VintageModel]:
    if vintage in bundle.models:
        return bundle.models[vintage]
    if bundle.models:
        # fall back to any trained vintage (documented) if exact one is missing
        return next(iter(bundle.models.values()))
    return None


def predict_one(
    cfg: AppConfig,
    bundle: Optional[TrainedBundle],
    source: ForecastSource,
    target_date: date,
    vintage_name: str,
    issue_local: datetime,
    normals: pd.DataFrame,
    daily_tmax_f: Optional[pd.Series] = None,
    daily_prcp_mm: Optional[pd.Series] = None,
    obs: Optional[pd.DataFrame] = None,
    synthetic: bool = False,
    sources_available: Optional[list[str]] = None,
    sources_missing: Optional[list[str]] = None,
    n_draws: int = 20000,
    secondary_tmax_f: Optional[dict[str, float]] = None,
) -> dict:
    issue_utc = to_utc(issue_local)
    fallback_level = FallbackLevel.FULL_MODEL

    # Newest usable cycle available at the issue time; falls back to earlier cycles on
    # archive gaps (still leakage-safe). None => no source => climate-normal fallback.
    run = source.select_and_fetch(target_date, issue_utc, cfg.locations)
    if run is None:
        return _climate_normal_fallback(cfg, target_date, vintage_name, issue_local, normals,
                                        sources_available, sources_missing)

    if synthetic and obs is None:
        obs = synthetic_observation_frame(target_date, up_to_utc=issue_utc)

    # Same-day forecast: try the intraday CLI (authoritative max-so-far / settlement
    # source) issued at/before the issue time. Only used for a target date that is 'today'
    # locally, and only if the report's target matches (no lookahead).
    intraday_cli_max = None
    if not synthetic and target_date == to_local(issue_utc).date():
        intraday_cli_max = _try_intraday_cli_max(cfg, target_date, issue_utc)

    row = build_feature_row(
        target_date=target_date, vintage_name=vintage_name, issue_local=issue_local,
        primary_run=run, locations=cfg.locations, normals=normals,
        daily_tmax_f=daily_tmax_f, daily_prcp_mm=daily_prcp_mm, obs=obs,
        trajectory_hours=cfg.trajectory_hours_local,
        reporting_method=cfg.reporting_convention.method,
        intraday_report_max_f=intraday_cli_max,
    )
    baseline = row.get("baseline_tmax_f")
    observed_max = row.get("observed_max_so_far_f")

    # --- point prediction & residual std via fallback hierarchy ---
    model = _nearest_vintage_model(bundle, vintage_name) if bundle else None
    attributions: list[dict] = []
    ood_info: dict = {}
    if model is not None and baseline is not None:
        # At predict time there is no label column; build the matrix from the feature row
        # with the baseline supplied for residual reconstruction.
        fm = _feature_matrix_for_predict(row, model.feature_names, baseline)
        point = float(model.boosting.predict(fm)[0])
        # Out-of-distribution guard: attenuate the learned correction when the row's key
        # features sit outside the training envelope (e.g. season the model never saw).
        stats = getattr(model, "feature_stats", None)
        if stats is not None:
            from ..models.ood_guard import apply_shrink, assess_ood
            ood = assess_ood(row, stats, model.boosting.feature_importance())
            if ood.shrink < 1.0:
                log.warning("OOD guard: score=%.2f shrink=%.2f (offending: %s); "
                            "correction %+.2fF -> %+.2fF",
                            ood.score, ood.shrink, ood.offending[:4],
                            point - baseline, (point - baseline) * ood.shrink)
                point = apply_shrink(float(baseline), point, ood.shrink)
            ood_info = ood.to_dict()
        # Consensus guard: bound the correction by live inter-model disagreement when
        # secondary model maxima (e.g. HRRR/GFS) are supplied by the caller.
        if secondary_tmax_f:
            from ..models.ood_guard import consensus_cap
            point, cons = consensus_cap(float(baseline), point, secondary_tmax_f)
            if cons.applied:
                log.warning("Consensus cap: spread=%.2fF cap=%.2fF correction %+.2fF -> %+.2fF",
                            cons.spread_f, cons.cap_f,
                            cons.correction_before_f, cons.correction_after_f)
            ood_info.update(cons.to_dict())
        # Regime-weighting add-on (advisory by default; opt-in blend). Uses NBM baseline +
        # any supplied HRRR/GFS maxima + PoP from the feature row. See models/regime_weighting.
        regime_info = {}
        rw = getattr(cfg, "regime_weighting", None)
        if rw is not None:
            from ..models.regime_weighting import blend_with_model, classify_regime
            # PoP is the reliable regime direction-setter; prefer the row's value, else
            # fetch the NWS gridpoint PoP (advisory; best-effort, non-synthetic only).
            pop = row.get("pop_day_max_pct")
            if pop is None and not synthetic:
                pop = _try_forecast_pop(cfg, target_date)
            assess = classify_regime(
                nbm_f=float(baseline),
                hrrr_f=(secondary_tmax_f or {}).get("hrrr"),
                gfs_f=(secondary_tmax_f or {}).get("gfs"),
                pop_pct=pop,
                pop_storm_threshold=rw.pop_storm_threshold,
                pop_clean_threshold=rw.pop_clean_threshold,
                nbm_cool_threshold_f=rw.nbm_cool_threshold_f,
                weights=(rw.weights or None),
            )
            regime_info = assess.to_dict()
            regime_info["regime_weighting_enabled"] = bool(rw.enabled)
            if rw.enabled and assess.weighted_tmax_f is not None:
                before = point
                point = blend_with_model(point, assess, strength=rw.blend_strength)
                log.info("Regime blend (%s): %.2fF -> %.2fF (strength %.2f)",
                         assess.regime, before, point, rw.blend_strength)
        ood_info.update(regime_info)
        residuals = model.oos_residuals
        attributions = _local_attributions(model, fm)
        model_name = f"{model.boosting.name}"
        reporting_method = model.reporting_method
        # Full model when the configured preferred baseline source is the one in use;
        # otherwise a residual model on a fallback baseline source.
        preferred = cfg.baseline_source_preference[0] if cfg.baseline_source_preference else None
        fallback_level = (FallbackLevel.FULL_MODEL if source.name == preferred
                          else FallbackLevel.RESIDUAL_PRIMARY)
    elif baseline is not None:
        point = float(baseline)
        residuals = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
        model_name = "raw_primary_baseline"
        reporting_method = cfg.reporting_convention.method
        fallback_level = FallbackLevel.RAW_PRIMARY
    else:
        return _climate_normal_fallback(cfg, target_date, vintage_name, issue_local, normals,
                                        sources_available, sources_missing)

    # --- intraday observed-max constraint on the point AND the distribution ---
    point = apply_observed_max_constraint(point, observed_max)
    rng = np.random.default_rng(cfg.models.random_seed)

    # Uncertainty: prefer quantile-GBM inverse-CDF sampling when trained and configured;
    # otherwise (or additionally, as a 50/50 mixture) empirical residual bootstrap.
    methods = list(cfg.uncertainty.methods)
    uncertainty_used = []
    sample_sets = []
    if (model is not None and "quantile_gbm" in methods
            and getattr(model, "quantile_model", None) is not None):
        try:
            from ..models.discrete_outcomes import simulate_from_quantiles
            qdf = model.quantile_model.predict_quantiles(fm)
            levels = model.quantile_model.quantiles
            values = [float(qdf.iloc[0][f"q{int(q*100):02d}"]) for q in levels]
            # Re-center quantile curve on the (possibly obs-constrained) point via the median.
            shift = point - values[len(values) // 2]
            values = [v + shift for v in values]
            sample_sets.append(simulate_from_quantiles(levels, values, n_draws, rng))
            uncertainty_used.append("quantile_gbm")
        except Exception as exc:  # noqa: BLE001
            log.warning("quantile_gbm sampling failed (%s); using empirical residuals.", exc)
    if "empirical_residual" in methods or not sample_sets:
        sample_sets.append(simulate_from_residuals(point, residuals, n_draws, rng))
        uncertainty_used.append("empirical_residual")
    if len(sample_sets) > 1:
        # Equal-weight mixture of the two calibrated sample sets.
        k = n_draws // len(sample_sets)
        samples = np.concatenate([s[:k] for s in sample_sets])
    else:
        samples = sample_sets[0]

    if observed_max is not None and not (isinstance(observed_max, float) and np.isnan(observed_max)):
        samples = np.maximum(samples, observed_max)
    check_prediction_not_below_observed(point, observed_max)

    # --- continuous quantiles ---
    q_levels = [0.10, 0.25, 0.50, 0.75, 0.90]
    q_vals = np.quantile(samples, q_levels)
    check_quantiles_ordered(q_vals)
    p10, p25, p50, p75, p90 = [float(x) for x in q_vals]

    # --- integer report distribution ---
    dist = integer_report_distribution(samples, convention=reporting_method)
    check_integer_pmf_sums_to_one(dist.pmf)

    # --- contract probabilities ---
    thresholds = cfg.contracts.example_thresholds if cfg.contracts else {}
    contract_probs = contract_probability_report(dist.pmf, thresholds)
    # Always include the canonical illustrative set from the spec template.
    contract_probs.update({
        "greater_than_90": probability_greater_than(dist.pmf, 90),
        "greater_than_or_equal_90": probability_greater_than_or_equal(dist.pmf, 90),
        "less_than_90": probability_less_than(dist.pmf, 90),
        "less_than_or_equal_90": probability_less_than_or_equal(dist.pmf, 90),
        "between_88_and_90_inclusive": probability_between_inclusive(dist.pmf, 88, 90),
        "exactly_90": probability_exactly(dist.pmf, 90),
    })

    record = {
        "station": cfg.station.shorthand,
        "station_id": cfg.station.noaa_station_id,
        "target_date_local": target_date.isoformat(),
        "vintage": vintage_name,
        "forecast_issued_at_local": isoformat_local(issue_local),
        "forecast_issued_at_utc": isoformat_utc(issue_utc),
        "last_observation_at_local": _last_obs_local(obs),
        "observed_max_so_far_f": None if observed_max is None or (isinstance(observed_max, float) and np.isnan(observed_max)) else round(float(observed_max), 1),
        "observed_max_so_far_source": row.get("observed_max_so_far_source"),
        # Human-facing nowcasting diagnostics (NOT model inputs; see features_frame
        # DIAGNOSTIC_ONLY_COLUMNS). On a stalled-temperature day these flag that the live
        # trajectory is running below the forecast, even though the model does not weight them.
        "trend_diagnostics": {
            k: (round(float(row[k]), 2) if isinstance(row.get(k), (int, float)) and not
                (isinstance(row.get(k), float) and np.isnan(row[k])) else row.get(k))
            for k in ("stalled_before_peak_flag", "cooling_before_peak_flag",
                      "warming_rate_recent_3h_f_per_h", "hours_since_observed_max",
                      "headroom_minus_trend_support_f")
            if k in row
        },
        "predicted_continuous_tmax_f": round(point, 2),
        "predicted_continuous_tmax_c": round(f_to_c(point), 2),
        "median_tmax_f": round(p50, 2),
        "p10_tmax_f": round(p10, 2),
        "p25_tmax_f": round(p25, 2),
        "p75_tmax_f": round(p75, 2),
        "p90_tmax_f": round(p90, 2),
        "interval_50_f": [round(p25, 2), round(p75, 2)],
        "interval_80_f": [round(p10, 2), round(p90, 2)],
        "predictive_std_f": round(float(np.std(samples)), 3),
        "integer_report_probabilities": dist.as_str_keys(),
        "contract_probabilities": {k: round(float(v), 4) for k, v in contract_probs.items()},
        "baseline_model": source.name,
        "baseline_tmax_f": round(float(baseline), 2),
        "predicted_bias_correction_f": round(point - float(baseline), 2),
        "model_name": model_name,
        "fallback_level": int(fallback_level),
        "data_sources_used": sources_available or [source.name],
        "missing_sources": sources_missing or [],
        "top_model_attributions": attributions,
        "model_trained_through": (model.train_end if model else None),
        "reporting_convention_version": convention_version(reporting_method),
        "contract_rule_version": cfg.contract_rules.version,
        "uncertainty_method": "+".join(uncertainty_used) + "+simulation",
        **ood_info,
        "is_synthetic": synthetic,
        "note": "Forecast only. Not an official NWS report or contract settlement.",
    }
    return record


def _feature_matrix_for_predict(row: dict, feature_names: list[str], baseline: float) -> FeatureMatrix:
    df = pd.DataFrame([row])
    X = df.reindex(columns=feature_names)
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return FeatureMatrix(X=X.reset_index(drop=True),
                         y=pd.Series([np.nan]),
                         baseline=pd.Series([float(baseline)]),
                         dates=pd.Series([row.get("date")]),
                         feature_names=feature_names)


def _local_attributions(model: VintageModel, fm: FeatureMatrix, top_k: int = 6) -> list[dict]:
    """Model-attribution results (NOT causal): feature importance x standardized value sign."""
    imp = model.boosting.feature_importance()
    if not imp:
        return []
    x = fm.X.iloc[0]
    out = []
    for name, weight in list(imp.items())[:top_k]:
        val = float(x.get(name, 0.0))
        out.append({"feature": name, "importance": round(float(weight), 4),
                    "value": round(val, 3),
                    "note": "model attribution, not causal"})
    return out


def _last_obs_local(obs: Optional[pd.DataFrame]) -> Optional[str]:
    if obs is None or obs.empty or "timestamp_utc" not in obs.columns:
        return None
    ts = pd.to_datetime(obs["timestamp_utc"], utc=True, errors="coerce").dropna()
    if ts.empty:
        return None
    return isoformat_local(ts.max().to_pydatetime())


def _try_forecast_pop(cfg, target_date) -> Optional[float]:
    """Best-effort max probability-of-precipitation over the target local day from the NWS
    gridpoint forecast. Used only by the advisory regime classifier; None on any failure."""
    try:
        from ..data.nws_api import NwsApiClient
        from ..data.storage import http_client_from_config
        from ..time_utils import is_in_local_day, to_utc
        import pandas as pd
        client = NwsApiClient(http_client_from_config(cfg))
        gj = client.gridpoint_forecast_hourly(cfg.station.latitude, cfg.station.longitude)
        pops = []
        for p in gj.get("properties", {}).get("periods", []):
            t = p.get("startTime")
            pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
            if t and pop is not None:
                tt = to_utc(pd.to_datetime(t).to_pydatetime())
                if is_in_local_day(tt, target_date):
                    pops.append(float(pop))
        return max(pops) if pops else None
    except Exception as exc:  # noqa: BLE001
        log.debug("No forecast PoP for %s: %s", target_date, exc)
        return None


def _try_intraday_cli_max(cfg, target_date, issue_utc) -> Optional[float]:
    """Fetch today's intraday CLI max if issued at/before ``issue_utc`` (no lookahead).

    Returns the reported max only when a report for ``target_date`` was released at/before
    the prediction time. Any failure (network, no report yet, parse) returns None quietly —
    the observed-max reconstruction then falls back to the METAR sources.
    """
    try:
        from ..data.nws_api import NwsApiClient
        from ..data.nws_climate_report import parse_climate_report
        from ..data.storage import http_client_from_config
        client = NwsApiClient(http_client_from_config(cfg))
        text, _ = client.latest_central_park_cli()
        report = parse_climate_report(text, source="intraday_predict")
        if report.target_date != target_date:
            return None
        if report.issuance_utc is not None and report.issuance_utc > issue_utc:
            return None  # report issued after the prediction time -> leakage; ignore
        log.info("Intraday CLI available for %s: max-so-far %sF (status=%s)",
                 target_date, report.reported_max_f, report.status)
        return float(report.reported_max_f)
    except Exception as exc:  # noqa: BLE001
        log.debug("No usable intraday CLI for %s: %s", target_date, exc)
        return None


def _climate_normal_fallback(cfg, target_date, vintage_name, issue_local, normals,
                             sources_available, sources_missing) -> dict:
    from ..features.climatology import normal_max_f
    point = normal_max_f(normals, target_date)
    samples = np.random.default_rng(0).normal(point, 6.0, 5000)
    dist = integer_report_distribution(samples, convention=cfg.reporting_convention.method)
    log.warning("Climate-normal fallback used for %s (%s): no forecast source available.",
                target_date, vintage_name)
    return {
        "station": cfg.station.shorthand,
        "station_id": cfg.station.noaa_station_id,
        "target_date_local": target_date.isoformat(),
        "vintage": vintage_name,
        "forecast_issued_at_local": isoformat_local(issue_local),
        "forecast_issued_at_utc": isoformat_utc(to_utc(issue_local)),
        "predicted_continuous_tmax_f": round(float(point), 2),
        "predicted_continuous_tmax_c": round(f_to_c(point), 2),
        "integer_report_probabilities": dist.as_str_keys(),
        "contract_probabilities": {
            "greater_than_90": probability_greater_than(dist.pmf, 90),
            "less_than_90": probability_less_than(dist.pmf, 90),
        },
        "baseline_model": "climate_normal",
        "model_name": "climate_normal_fallback",
        "fallback_level": int(FallbackLevel.CLIMATE_NORMAL),
        "data_sources_used": sources_available or [],
        "missing_sources": sources_missing or cfg.active_forecast_sources,
        "reporting_convention_version": convention_version(cfg.reporting_convention.method),
        "contract_rule_version": cfg.contract_rules.version,
        "note": "Climate-normal fallback (last resort). Forecast only, not a settlement.",
    }


def save_prediction(cfg: AppConfig, record: dict) -> Path:
    d = record["target_date_local"]
    v = record.get("vintage", "default")
    out = Path(cfg.paths.predictions_dir) / f"prediction_{d}_{v}.json"
    write_json(out, record)
    return out
