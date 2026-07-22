"""Typed configuration loaded from YAML in configs/. Secrets come only from env.

Loading is layered: default.yaml + locations.yaml + data_sources.yaml + contracts.yaml
are merged into one AppConfig. A saved copy of the resolved config is written alongside
every trained model for reproducibility.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

# Repository layout: this file lives at src/central_park_tmax/config.py; the project
# root (containing configs/ and data/) is three levels up.
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
CONFIGS_DIR = PROJECT_ROOT / "configs"


class StationCfg(BaseModel):
    name: str
    shorthand: str
    noaa_station_id: str
    wban: str
    icao: str
    latitude: float
    longitude: float
    elevation_m: float
    timezone: str


class PathsCfg(BaseModel):
    data_dir: str = "data"
    raw_dir: str = "data/raw"
    observations_dir: str = "data/raw/observations"
    forecasts_dir: str = "data/raw/forecasts"
    nws_reports_dir: str = "data/raw/nws_reports"
    interim_dir: str = "data/interim"
    processed_dir: str = "data/processed"
    predictions_dir: str = "data/predictions"
    settlement_dir: str = "data/settlement"
    models_dir: str = "models"
    reports_dir: str = "reports"
    figures_dir: str = "reports/figures"
    metrics_dir: str = "reports/metrics"

    def resolve(self, root: Path) -> "PathsCfg":
        data = {k: str((root / v)) for k, v in self.model_dump().items()}
        return PathsCfg(**data)


class VintageSpec(BaseModel):
    name: str
    day: str  # prev_day | target_day
    hour: int
    minute: int = 0


class BoostingCfg(BaseModel):
    backend: str = "auto"
    n_estimators: int = 600
    learning_rate: float = 0.03
    max_depth: int = 4
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_lambda: float = 1.0
    min_child_weight: float = 5.0
    early_stopping_rounds: int = 50


class HpSearchCfg(BaseModel):
    enabled: bool = True
    max_candidates: int = 8


class ModelsCfg(BaseModel):
    random_seed: int = 20240101
    residual_target: bool = True
    boosting: BoostingCfg = Field(default_factory=BoostingCfg)
    quantiles: list[float] = Field(default_factory=lambda: [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    hyperparameter_search: HpSearchCfg = Field(default_factory=HpSearchCfg)


class UncertaintyCfg(BaseModel):
    methods: list[str] = Field(default_factory=lambda: ["quantile_gbm", "empirical_residual"])
    n_simulation_draws: int = 20000


class FoldCfg(BaseModel):
    train_end: str
    test_start: str
    test_end: str


class ValidationCfg(BaseModel):
    scheme: str = "rolling_origin"
    folds: list[FoldCfg] = Field(default_factory=list)
    min_train_days: int = 365


class LoggingCfg(BaseModel):
    model_config = {"populate_by_name": True}
    level: str = "INFO"
    json_output: bool = Field(default=False, alias="json")


class HttpCfg(BaseModel):
    timeout_seconds: int = 30
    max_retries: int = 4
    backoff_seconds: float = 2.0
    cache_enabled: bool = True
    user_agent: str = "central_park_tmax/0.1 (research)"


class ArchiveCfg(BaseModel):
    start_date: str = "2019-01-01"
    end_date: Optional[str] = None


class ReportingConventionCfg(BaseModel):
    version: str = "nws_cli_v1"
    method: str = "round_half_up"


class ContractRulesCfg(BaseModel):
    version: str = "nhigh_v1"


class RegimeWeightingCfg(BaseModel):
    """Opt-in, advisory regime-weighting add-on (see models/regime_weighting.py).

    ``enabled=False`` => advisory only: the regime label + regime-weighted estimate are
    REPORTED alongside the model output but do not change the point forecast. Set enabled
    plus a ``blend_strength`` in (0,1] to nudge the point toward the regime estimate.
    """
    enabled: bool = False
    blend_strength: float = 0.5
    pop_storm_threshold: float = 50.0
    pop_clean_threshold: float = 25.0
    nbm_cool_threshold_f: float = 2.0
    weights: dict = Field(default_factory=dict)   # empty => module DEFAULT_WEIGHTS


class LocationPoint(BaseModel):
    key: str
    name: str
    icao: Optional[str] = None
    latitude: float
    longitude: float
    role: str


class GradientPair(BaseModel):
    name: str
    a: str
    b: str


class SpatialExtractionCfg(BaseModel):
    default_method: str = "bilinear"
    neighborhood_radius_km: float = 25.0
    idw_power: float = 2.0


class LocationsCfg(BaseModel):
    primary: LocationPoint
    neighbors: list[LocationPoint] = Field(default_factory=list)
    gradient_pairs: list[GradientPair] = Field(default_factory=list)
    spatial_extraction: SpatialExtractionCfg = Field(default_factory=SpatialExtractionCfg)

    def all_points(self) -> list[LocationPoint]:
        return [self.primary, *self.neighbors]


class ContractTimingCfg(BaseModel):
    timezone: str = "America/New_York"
    last_trading_local: dict[str, int] = Field(default_factory=lambda: {"hour": 23, "minute": 59})
    normal_expiration_candidate_hours: list[int] = Field(default_factory=lambda: [7, 8])
    delayed_determination_local: dict[str, int] = Field(default_factory=lambda: {"hour": 11, "minute": 0})


class ContractsCfg(BaseModel):
    version: str = "nhigh_v1"
    underlying: dict[str, Any] = Field(default_factory=dict)
    timing: ContractTimingCfg = Field(default_factory=ContractTimingCfg)
    review_triggers: list[str] = Field(default_factory=list)
    metar_consistency_tolerance_f: float = 1.0
    example_thresholds: dict[str, Any] = Field(default_factory=dict)
    polling: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    station: StationCfg
    paths: PathsCfg = Field(default_factory=PathsCfg)
    forecast_vintages: list[VintageSpec] = Field(default_factory=list)
    trajectory_hours_local: list[int] = Field(default_factory=lambda: [0, 3, 6, 9, 12, 15, 18, 21])
    active_forecast_sources: list[str] = Field(default_factory=list)
    baseline_source_preference: list[str] = Field(default_factory=list)
    archive: ArchiveCfg = Field(default_factory=ArchiveCfg)
    models: ModelsCfg = Field(default_factory=ModelsCfg)
    uncertainty: UncertaintyCfg = Field(default_factory=UncertaintyCfg)
    validation: ValidationCfg = Field(default_factory=ValidationCfg)
    logging: LoggingCfg = Field(default_factory=LoggingCfg)
    http: HttpCfg = Field(default_factory=HttpCfg)
    reporting_convention: ReportingConventionCfg = Field(default_factory=ReportingConventionCfg)
    contract_rules: ContractRulesCfg = Field(default_factory=ContractRulesCfg)
    regime_weighting: RegimeWeightingCfg = Field(default_factory=RegimeWeightingCfg)

    # Loaded from separate files:
    locations: Optional[LocationsCfg] = None
    contracts: Optional[ContractsCfg] = None
    data_sources: dict[str, Any] = Field(default_factory=dict)

    # Non-serialized runtime helpers:
    project_root: Optional[str] = None

    @property
    def archive_start(self) -> date:
        return date.fromisoformat(self.archive.start_date)

    @property
    def archive_end(self) -> Optional[date]:
        return date.fromisoformat(self.archive.end_date) if self.archive.end_date else None


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(
    config_dir: Optional[Path | str] = None,
    project_root: Optional[Path | str] = None,
) -> AppConfig:
    """Load and merge all config files into a typed AppConfig.

    Paths inside PathsCfg are resolved against ``project_root`` (default: repo root).
    """
    cfg_dir = Path(config_dir) if config_dir else CONFIGS_DIR
    root = Path(project_root) if project_root else PROJECT_ROOT

    default_data = _read_yaml(cfg_dir / "default.yaml")
    locations_data = _read_yaml(cfg_dir / "locations.yaml")
    data_sources_data = _read_yaml(cfg_dir / "data_sources.yaml")
    contracts_data = _read_yaml(cfg_dir / "contracts.yaml")

    cfg = AppConfig(**default_data)
    cfg.paths = cfg.paths.resolve(root)
    cfg.project_root = str(root)
    if locations_data:
        cfg.locations = LocationsCfg(**locations_data)
    if contracts_data:
        cfg.contracts = ContractsCfg(**contracts_data)
    cfg.data_sources = data_sources_data

    # Allow env override of NWS user agent email (secret-ish contact info).
    email = os.environ.get("NWS_API_USER_AGENT_EMAIL")
    if email:
        cfg.http.user_agent = f"central_park_tmax/0.1 (research; {email})"

    _ensure_dirs(cfg)
    return cfg


def _ensure_dirs(cfg: AppConfig) -> None:
    for field in cfg.paths.model_dump().values():
        Path(field).mkdir(parents=True, exist_ok=True)


def save_resolved_config(cfg: AppConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg.model_dump(mode="json"), fh, sort_keys=False)
