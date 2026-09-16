#!/usr/bin/env python3
"""Fit a frozen NYC paper-model artifact and reproducible provenance card."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import joblib
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from central_park_tmax.models.conditional_report import ConditionalReportHigh
from audit_report_high import build_frame


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",type=Path,default=ROOT/"data/paper/model")
    args=p.parse_args()
    now=pd.Timestamp.now(tz="UTC")
    paths=[ROOT/"backtest_datasets/knyc_hourly_2019_2026.csv",ROOT/"backtest_datasets/cli_research/knyc_cli_highs.csv"]
    f=build_frame(pd.read_csv(paths[0]),pd.read_csv(paths[1]))
    f=f[(f.product_issued_utc<now-pd.Timedelta(days=2)) & (f.date<now.tz_localize(None).normalize()-pd.Timedelta(days=2))]
    if f.date.nunique()<200:raise ValueError("Insufficient historical dates.")
    card={"station":"KNYC","fit_at_utc":now.isoformat(),"train_end":f.date.max().isoformat(),
          "train_days":f.date.nunique(),"latest_label_issue":f.product_issued_utc.max().isoformat(),
          "prior_strength":30,"day_basis":"fixed UTC-5","supported_civil_hours":[13,14,15,16,17,18],
          "input_hashes":{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
          "git_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
          "purpose":"frozen forward paper research, not approved live orders"}
    sources=[Path(__file__),ROOT/"scripts/audit_report_high.py",ROOT/"scripts/audit_conditional_rise.py",
             ROOT/"src/central_park_tmax/models/conditional_report.py",
             ROOT/"src/central_park_tmax/models/conditional_rise.py",
             ROOT/"src/central_park_tmax/forward.py",ROOT/"src/central_park_tmax/paper.py",
             ROOT/"src/central_park_tmax/evaluation/execution_research.py",
             ROOT/"scripts/run_paper_cycle.py",ROOT/"scripts/archive_orderbooks.py"]
    card["source_hashes"]={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    card["git_worktree_dirty"]=bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip())
    card["model_id"]=hashlib.sha256(json.dumps(card,sort_keys=True).encode()).hexdigest()
    model=ConditionalReportHigh().fit(f)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    artifact=args.output_dir/"report_model.joblib"
    joblib.dump({"model":model,"card":card},artifact)
    card["artifact_sha256"]=hashlib.sha256(artifact.read_bytes()).hexdigest()
    (args.output_dir/"model_card.json").write_text(json.dumps(card,indent=2)+"\n")
    print(json.dumps(card,indent=2))


if __name__=="__main__":main()
