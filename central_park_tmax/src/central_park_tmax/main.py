"""Command-line interface for central_park_tmax.

Commands (see README):
  build-observations, build-report-archive, build-forecast-archive, build-dataset,
  backtest, train, predict-tomorrow, predict-at-time, ingest-nws-report,
  determine-expiration-value, generate-report, run-daily, monitor-settlement, demo

Most commands accept --synthetic to run fully offline against the synthetic generator (no
network / no GRIB). This is intended for demos, CI, and development; synthetic outputs are
always tagged and must not be mistaken for real forecasts.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import AppConfig, load_config
from .data.nws_api import NwsApiClient
from .data.sources import build_active_sources, build_source, choose_baseline_source
from .data.storage import http_client_from_config
from .logging_config import configure_logging, get_logger
from .time_utils import NY, next_local_date, now_local, resolve_vintage, to_local

log = get_logger(__name__)


def _load(args) -> AppConfig:
    cfg = load_config(config_dir=args.config_dir)
    configure_logging(cfg.logging.level, cfg.logging.json_output)
    return cfg


def _history(cfg: AppConfig, synthetic: bool):
    """Return (normals, daily_tmax_f, daily_prcp_mm) for features/climatology."""
    from .pipelines.context import daily_history_from_ghcn, synthetic_daily_history
    if synthetic:
        from datetime import timedelta
        h = synthetic_daily_history(cfg.archive_start - timedelta(days=40),
                                    cfg.archive_end or date.today())
        return h["normals"], h["tmax_f"], h["prcp_mm"]
    from .pipelines.build_observations import build_observations
    ghcn = build_observations(cfg, save=True)
    h = daily_history_from_ghcn(ghcn)
    return h["normals"], h["tmax_f"], h["prcp_mm"]


# --------------------------------------------------------------------------------------
# Command implementations
# --------------------------------------------------------------------------------------
def cmd_build_observations(cfg, args):
    from .pipelines.build_observations import build_observations
    df = build_observations(cfg)
    print(f"Downloaded & processed {len(df)} daily GHCN observations for {cfg.station.shorthand}.")


def cmd_build_report_archive(cfg, args):
    from .pipelines.build_report_archive import archive_report_text, fetch_and_archive_latest
    if args.from_file:
        text = Path(args.from_file).read_text(encoding="utf-8")
        rec = archive_report_text(cfg, text, source=f"file:{Path(args.from_file).name}")
    else:
        rec = fetch_and_archive_latest(cfg)
    print(f"Archived CLI: target={rec['target_date']} max={rec['reported_max_f']}F "
          f"status={rec['status']} newly={rec.get('newly_archived')}")


def cmd_build_forecast_archive(cfg, args):
    from .pipelines.build_forecast_archive import build_forecast_archive
    source = _pick_source(cfg, args)
    start = _parse_date(args.start) or cfg.archive_start
    end = _parse_date(args.end) or (cfg.archive_end or date.today())
    out = build_forecast_archive(cfg, source, start, end)
    print(f"Forecast archive written: {out}")


def cmd_build_dataset(cfg, args):
    from .pipelines.build_dataset import build_dataset
    source = _pick_source(cfg, args)
    normals, tmax, prcp = _history(cfg, args.synthetic)
    start = _parse_date(args.start) or cfg.archive_start
    end = _parse_date(args.end) or (cfg.archive_end or date.today())
    df = build_dataset(cfg, source, start, end, synthetic=args.synthetic, normals=normals,
                       daily_tmax_f=tmax, daily_prcp_mm=prcp)
    print(f"Built dataset: {len(df)} rows, {df['vintage'].nunique() if len(df) else 0} vintages.")


def cmd_backtest(cfg, args):
    from .pipelines.evaluate import evaluate
    df = _load_dataset(cfg, args)
    out = evaluate(cfg, df)
    print("Backtest summary (best model / MAE by vintage):")
    for vintage, s in out.get("summary", {}).items():
        print(f"  {vintage}: best={s['best_model']} MAE={s['best_mae']:.3f} "
              f"(raw primary MAE={s.get('raw_primary_mae')})")


def cmd_train(cfg, args):
    from .pipelines.train import train_models
    df = _load_dataset(cfg, args)
    bundle = train_models(cfg, df)
    print(f"Trained {len(bundle.models)} vintage model(s). Saved to {cfg.paths.models_dir}/model_bundle.joblib")


def cmd_predict_tomorrow(cfg, args):
    target = next_local_date()
    _predict_all_vintages(cfg, args, target)


def cmd_predict_at_time(cfg, args):
    target = _parse_date(args.target_date) or next_local_date()
    issue_local = datetime.fromisoformat(args.issue_time).replace(tzinfo=NY) \
        if args.issue_time else now_local()
    _predict_single(cfg, args, target, issue_local, vintage_name=args.vintage or "custom")


def cmd_run_daily(cfg, args):
    target = next_local_date()
    print(f"=== run-daily for target {target} ({'SYNTHETIC' if args.synthetic else 'live'}) ===")
    _predict_all_vintages(cfg, args, target, only_current=True)


def cmd_ingest_nws_report(cfg, args):
    cmd_build_report_archive(cfg, args)


def cmd_determine_expiration_value(cfg, args):
    from .pipelines.ingest_settlement import monitor_settlement
    target = _parse_date(args.target_date)
    if target is None:
        raise SystemExit("--target-date is required (YYYY-MM-DD)")
    obs = _synth_obs(target) if args.synthetic else None
    monitor_settlement(cfg, target, obs=obs, fetch_live=not args.synthetic)


def cmd_monitor_settlement(cfg, args):
    cmd_determine_expiration_value(cfg, args)


def cmd_generate_report(cfg, args):
    from .reporting.forecast_report import render_forecast_text
    from .data.storage import read_json
    p = Path(args.prediction) if args.prediction else _latest_prediction(cfg)
    if p is None or not p.exists():
        raise SystemExit("No prediction JSON found; run predict-tomorrow first.")
    print(render_forecast_text(read_json(p)))


def cmd_demo(cfg, args):
    """Full offline synthetic end-to-end smoke test."""
    from .config import FoldCfg
    args.synthetic = True
    # Compact but multi-period window so the smoke test runs in ~1-2 minutes on a laptop.
    args.start = getattr(args, "start", None) or "2024-01-01"
    args.end = getattr(args, "end", None) or "2024-06-30"
    args.source = getattr(args, "source", None)
    # Override validation folds to lie inside the demo window (rolling-origin, non-overlapping).
    cfg.validation.folds = [
        FoldCfg(train_end="2024-03-31", test_start="2024-04-01", test_end="2024-05-15"),
        FoldCfg(train_end="2024-05-15", test_start="2024-05-16", test_end="2024-06-30"),
    ]
    cfg.validation.min_train_days = 30
    print(f"== [1/5] Build synthetic dataset ({args.start}..{args.end}) ==")
    cmd_build_dataset(cfg, args)
    print("== [2/5] Backtest ==")
    cmd_backtest(cfg, args)
    print("== [3/5] Train ==")
    cmd_train(cfg, args)
    print("== [4/5] Predict tomorrow (all vintages) ==")
    cmd_predict_tomorrow(cfg, args)
    print("== [5/5] Settlement demo ==")
    target = next_local_date()
    from .pipelines.ingest_settlement import monitor_settlement
    from .pipelines.build_report_archive import archive_report_text
    monitor_settlement(cfg, target, obs=_synth_obs(target), fetch_live=False)
    print("\nDemo complete. Artifacts under data/ and reports/.")


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def _pick_source(cfg, args):
    nws = NwsApiClient(http_client_from_config(cfg))
    if args.synthetic:
        return build_source("synthetic", cfg, nws)
    if getattr(args, "source", None):
        return build_source(args.source, cfg, nws)
    available = build_active_sources(cfg, nws)
    name = choose_baseline_source(cfg, available)
    return available[name]


def _load_dataset(cfg, args) -> pd.DataFrame:
    from .pipelines.build_dataset import build_dataset
    name = "dataset_synthetic.csv" if args.synthetic else "dataset.csv"
    p = Path(cfg.paths.processed_dir) / name
    if p.exists():
        return pd.read_csv(p)
    log.info("Dataset %s not found; building it now.", p)
    source = _pick_source(cfg, args)
    normals, tmax, prcp = _history(cfg, args.synthetic)
    return build_dataset(cfg, source, cfg.archive_start, cfg.archive_end or date.today(),
                         synthetic=args.synthetic, normals=normals, daily_tmax_f=tmax,
                         daily_prcp_mm=prcp)


def _load_bundle_or_none(cfg):
    from .pipelines.train import load_bundle
    p = Path(cfg.paths.models_dir) / "model_bundle.joblib"
    return load_bundle(p) if p.exists() else None


def _predict_all_vintages(cfg, args, target, only_current=False):
    from .pipelines.predict import predict_one, save_prediction
    from .reporting.forecast_report import render_forecast_text
    source = _pick_source(cfg, args)
    bundle = _load_bundle_or_none(cfg)
    normals, tmax, prcp = _history(cfg, args.synthetic)
    now = now_local()
    for vintage in cfg.forecast_vintages:
        vt = resolve_vintage(target, vintage.day, vintage.hour, vintage.minute, vintage.name)
        if only_current and vt.issue_local > now:
            continue
        try:
            rec = predict_one(cfg, bundle, source, target, vintage.name, vt.issue_local,
                              normals=normals, daily_tmax_f=tmax, daily_prcp_mm=prcp,
                              synthetic=args.synthetic,
                              sources_available=[source.name],
                              sources_missing=_missing_sources(cfg, source.name, args.synthetic),
                              n_draws=cfg.uncertainty.n_simulation_draws)
        except Exception as exc:  # noqa: BLE001
            log.warning("Prediction failed for vintage %s: %s", vintage.name, exc)
            continue
        save_prediction(cfg, rec)
        print(render_forecast_text(rec))
        print("-" * 60)


def _predict_single(cfg, args, target, issue_local, vintage_name):
    from .pipelines.predict import predict_one, save_prediction
    from .reporting.forecast_report import render_forecast_text
    source = _pick_source(cfg, args)
    bundle = _load_bundle_or_none(cfg)
    normals, tmax, prcp = _history(cfg, args.synthetic)
    rec = predict_one(cfg, bundle, source, target, vintage_name, issue_local,
                      normals=normals, daily_tmax_f=tmax, daily_prcp_mm=prcp,
                      synthetic=args.synthetic, sources_available=[source.name],
                      sources_missing=_missing_sources(cfg, source.name, args.synthetic),
                      n_draws=cfg.uncertainty.n_simulation_draws)
    save_prediction(cfg, rec)
    print(render_forecast_text(rec))


def _missing_sources(cfg, used: str, synthetic: bool) -> list[str]:
    if synthetic:
        return []
    return [s for s in cfg.active_forecast_sources if s != used]


def _synth_obs(target: date):
    from .data.synthetic import synthetic_observation_frame
    return synthetic_observation_frame(target)


def _latest_prediction(cfg) -> Optional[Path]:
    files = sorted(Path(cfg.paths.predictions_dir).glob("prediction_*.json"))
    return files[-1] if files else None


def _parse_date(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


# --------------------------------------------------------------------------------------
# argument parser
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="central_park_tmax",
                                description="KNYC max-temperature MOS + NHIGH contract probabilities")
    p.add_argument("--config-dir", default=None, help="Directory of YAML configs (default: ./configs)")
    p.add_argument("--synthetic", action="store_true", help="Run fully offline against synthetic data")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, func, **kw):
        sp = sub.add_parser(name, help=func.__doc__)
        # Accept --synthetic both before and after the subcommand. SUPPRESS default so that
        # omitting it here does not clobber a --synthetic passed before the subcommand.
        sp.add_argument("--synthetic", action="store_true", default=argparse.SUPPRESS,
                        help="Run fully offline against synthetic data")
        sp.set_defaults(func=func)
        return sp

    add("build-observations", cmd_build_observations)
    rp = add("build-report-archive", cmd_build_report_archive)
    rp.add_argument("--from-file", default=None, help="Archive a CLI report from a text file")
    fa = add("build-forecast-archive", cmd_build_forecast_archive)
    fa.add_argument("--source", default=None); fa.add_argument("--start", default=None); fa.add_argument("--end", default=None)
    bd = add("build-dataset", cmd_build_dataset)
    bd.add_argument("--source", default=None); bd.add_argument("--start", default=None); bd.add_argument("--end", default=None)
    add("backtest", cmd_backtest)
    add("train", cmd_train)
    add("predict-tomorrow", cmd_predict_tomorrow).add_argument("--source", default=None)
    pa = add("predict-at-time", cmd_predict_at_time)
    pa.add_argument("--target-date", default=None); pa.add_argument("--issue-time", default=None)
    pa.add_argument("--vintage", default=None); pa.add_argument("--source", default=None)
    ir = add("ingest-nws-report", cmd_ingest_nws_report)
    ir.add_argument("--from-file", default=None)
    dev = add("determine-expiration-value", cmd_determine_expiration_value)
    dev.add_argument("--target-date", default=None)
    add("run-daily", cmd_run_daily).add_argument("--source", default=None)
    ms = add("monitor-settlement", cmd_monitor_settlement)
    ms.add_argument("--target-date", default=None)
    gr = add("generate-report", cmd_generate_report)
    gr.add_argument("--prediction", default=None)
    add("demo", cmd_demo)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = _load(args)
    args.func(cfg, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
