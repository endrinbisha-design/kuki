from datetime import date, timedelta

from central_park_tmax.config import load_config
from central_park_tmax.constants import FallbackLevel
from central_park_tmax.data.sources import build_source
from central_park_tmax.pipelines.context import synthetic_daily_history
from central_park_tmax.pipelines.predict import predict_one
from central_park_tmax.time_utils import next_local_date, now_local, resolve_vintage


REQUIRED_FIELDS = [
    "station", "station_id", "target_date_local", "forecast_issued_at_local",
    "forecast_issued_at_utc", "predicted_continuous_tmax_f", "predicted_continuous_tmax_c",
    "integer_report_probabilities", "contract_probabilities", "baseline_model",
    "model_name", "fallback_level", "data_sources_used", "missing_sources",
    "reporting_convention_version", "contract_rule_version",
]


def _predict(tmp_path, bundle=None):
    cfg = load_config(project_root=tmp_path)
    src = build_source("synthetic", cfg)
    target = next_local_date(now_local())
    hist = synthetic_daily_history(target - timedelta(days=40), target)
    vt = resolve_vintage(target, "target_day", 12, 0, "target_12")
    return predict_one(cfg, bundle, src, target, "target_12", vt.issue_local,
                       normals=hist["normals"], daily_tmax_f=hist["tmax_f"],
                       daily_prcp_mm=hist["prcp_mm"], synthetic=True,
                       sources_available=["synthetic"], n_draws=4000)


def test_prediction_without_model_uses_raw_primary_fallback(tmp_path):
    rec = _predict(tmp_path, bundle=None)
    # No trained model -> raw-primary fallback (level 4).
    assert rec["fallback_level"] == int(FallbackLevel.RAW_PRIMARY)
    assert rec["model_name"] == "raw_primary_baseline"


def test_prediction_output_has_all_required_fields(tmp_path):
    rec = _predict(tmp_path, bundle=None)
    for field in REQUIRED_FIELDS:
        assert field in rec, f"missing output field {field}"
    # integer probabilities sum to ~1
    assert abs(sum(rec["integer_report_probabilities"].values()) - 1.0) < 1e-6
    # provenance / issue-time bookkeeping present
    assert rec["forecast_issued_at_utc"].endswith("Z")
    assert rec["note"]


def test_missing_all_sources_falls_back_to_climate_normal(tmp_path):
    cfg = load_config(project_root=tmp_path)
    from central_park_tmax.data.nws_gridpoint import NwsGridpointForecastSource
    from central_park_tmax.data.nws_api import NwsApiClient
    from central_park_tmax.data.storage import http_client_from_config
    # NWS gridpoint source with a target far in the past -> no runs available -> climate normal.
    src = NwsGridpointForecastSource(NwsApiClient(http_client_from_config(cfg)))
    target = date(2000, 1, 1)
    hist = synthetic_daily_history(target - timedelta(days=10), target)
    from central_park_tmax.time_utils import local_datetime
    rec = predict_one(cfg, None, src, target, "custom", local_datetime(target, 12),
                      normals=hist["normals"], daily_tmax_f=hist["tmax_f"],
                      synthetic=False, sources_available=[], sources_missing=cfg.active_forecast_sources)
    assert rec["fallback_level"] == int(FallbackLevel.CLIMATE_NORMAL)
    assert rec["model_name"] == "climate_normal_fallback"
