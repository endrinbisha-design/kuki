"""Download and process GHCN-Daily observations for Central Park."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import AppConfig
from ..data.ghcn_daily import GhcnDailyLoader, climate_normals_1991_2020
from ..data.storage import atomic_write_text, http_client_from_config, write_manifest
from ..logging_config import get_logger

log = get_logger(__name__)


def build_observations(cfg: AppConfig, save: bool = True) -> pd.DataFrame:
    http = http_client_from_config(cfg)
    loader = GhcnDailyLoader(http=http, station_id=cfg.station.noaa_station_id)
    raw_text = loader.download_csv_text()
    if save:
        atomic_write_text(Path(cfg.paths.observations_dir) / f"{cfg.station.noaa_station_id}.csv", raw_text)
    df = loader.parse_csv(raw_text)
    if save and not df.empty:
        proc = Path(cfg.paths.processed_dir) / "observations_daily.csv"
        df.to_csv(proc, index=False)
        normals = climate_normals_1991_2020(df)
        normals.to_csv(Path(cfg.paths.processed_dir) / "climate_normals.csv", index=False)
        write_manifest(Path(cfg.paths.processed_dir) / "observations_manifest.json", [proc],
                       extra={"n_rows": len(df), "station": cfg.station.noaa_station_id})
        log.info("Processed %d daily observations.", len(df))
    return df
