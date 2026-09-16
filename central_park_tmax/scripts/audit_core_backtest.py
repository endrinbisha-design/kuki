#!/usr/bin/env python3
"""Reproduce a fixed-backend smoke benchmark of the core MOS pipeline.

Uses committed datasets unchanged: their GHCN-vintage/feature-availability issues
mean this is a regression diagnostic, NOT a clean settlement or alpha experiment.
--source-root can point at a baseline checkout for a before/after comparison.
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import pandas as pd
import sklearn

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-root", type=Path, default=ROOT)
    p.add_argument("--output", type=Path, default=ROOT / "reports/model_audit/core_after.json")
    args = p.parse_args()
    sys.path.insert(0, str(args.source_root / "src"))
    from central_park_tmax.config import load_config
    from central_park_tmax.evaluation.backtest import run_backtest
    cfg = load_config(config_dir=args.source_root / "configs", project_root=ROOT)
    cfg.models.boosting.backend = "sklearn"
    cfg.models.boosting.n_estimators = 100
    cfg.models.hyperparameter_search.enabled = False
    out = {"python": platform.python_version(), "sklearn": sklearn.__version__,
           "protocol": "sklearn, 100 iterations, no hyperparameter search; default auto folds",
           "limitation": "unchanged historical features and final GHCN research labels; not point-in-time settlement evidence",
           "datasets": {}}
    for city in ("nyc", "phoenix", "vegas"):
        path = ROOT / f"backtest_datasets/{city}_dataset.csv"
        result = run_backtest(cfg, pd.read_csv(path))
        out["datasets"][city] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                  "results": result.to_dict()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({city: r["results"]["summary"] for city, r in out["datasets"].items()}, indent=2))


if __name__ == "__main__":
    main()
