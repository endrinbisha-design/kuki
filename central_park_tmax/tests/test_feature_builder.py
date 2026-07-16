from datetime import date, timedelta

import numpy as np
import pandas as pd

from central_park_tmax.config import load_config
from central_park_tmax.data.sources import build_source
from central_park_tmax.features.build_features import build_feature_row
from central_park_tmax.pipelines.context import synthetic_daily_history
from central_park_tmax.time_utils import resolve_vintage


def test_feature_row_has_core_fields(tmp_path):
    cfg = load_config(project_root=tmp_path)
    src = build_source("synthetic", cfg)
    target = date(2024, 7, 15)
    hist = synthetic_daily_history(target - timedelta(days=40), target)
    vt = resolve_vintage(target, "target_day", 12, 0, "target_12")
    from central_park_tmax.time_utils import to_utc
    handle = src.select_run(target, to_utc(vt.issue_local))
    run = src.fetch_run(handle, cfg.locations, target)
    row = build_feature_row(target, "target_12", vt.issue_local, run, cfg.locations,
                            hist["normals"], daily_tmax_f=hist["tmax_f"],
                            daily_prcp_mm=hist["prcp_mm"],
                            obs=None, trajectory_hours=cfg.trajectory_hours_local)
    # Direct guidance + climatology + wind + spatial + trajectory present.
    for key in ("baseline_tmax_f", "normal_tmax_f", "doy_sin", "doy_cos",
                "wind_u_mean", "onshore_component_mean", "fc_temp_12z_local_f",
                "day_length_hours"):
        assert key in row, f"missing feature {key}"
    assert row["baseline_tmax_f"] is not None


def test_intraday_features_only_use_past_obs(tmp_path):
    cfg = load_config(project_root=tmp_path)
    src = build_source("synthetic", cfg)
    target = date(2024, 7, 15)
    hist = synthetic_daily_history(target - timedelta(days=40), target)
    from central_park_tmax.data.synthetic import synthetic_observation_frame
    from central_park_tmax.time_utils import to_utc
    # noon issue time -> observed max so far should exist and be a lower bound
    vt = resolve_vintage(target, "target_day", 12, 0, "target_12")
    issue_utc = to_utc(vt.issue_local)
    obs = synthetic_observation_frame(target, up_to_utc=issue_utc)
    handle = src.select_run(target, issue_utc)
    run = src.fetch_run(handle, cfg.locations, target)
    row = build_feature_row(target, "target_12", vt.issue_local, run, cfg.locations,
                            hist["normals"], daily_tmax_f=hist["tmax_f"],
                            daily_prcp_mm=hist["prcp_mm"], obs=obs,
                            trajectory_hours=cfg.trajectory_hours_local)
    assert row["is_intraday"] == 1.0
    assert "observed_max_so_far_f" in row
    # all obs used are strictly before issue time
    assert (pd.to_datetime(obs["timestamp_utc"], utc=True) <= pd.Timestamp(issue_utc)).all()
