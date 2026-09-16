#!/usr/bin/env python3
"""Does the new report-high model improve predictions beyond archived NYC prices?

Weather model fixed at Jan 1 of each test year. Blending/calibration uses only
earlier eligible market dates. All legacy price/receipt limitations still apply.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from central_park_tmax.models.conditional_report import ConditionalReportHigh, REPORT_SUPPORT
from audit_report_high import build_frame
from audit_probability_models import evaluate, score, validate_archive


def paired_interval(pred, name):
    daily=pred.assign(delta=(pred[name]-pred.won)**2-(pred.price-pred.won)**2).groupby("date").delta.mean()
    rng=np.random.default_rng(20260916)
    v=daily.to_numpy();draws=[]
    for _ in range(2000):
        ix=((rng.integers(0,len(v),int(np.ceil(len(v)/7)))[:,None]+np.arange(7))%len(v)).ravel()[:len(v)]
        draws.append(v[ix].mean())
    return {"mean_brier_difference_vs_market":float(daily.mean()),"ci95":np.quantile(draws,[.025,.975]).tolist(),
            "bootstrap":"7 observed-day circular blocks; missing calendar dates compressed; descriptive only",
            "missing_calendar_days":len(pd.date_range(daily.index.min(),daily.index.max()))-len(daily)}


def main():
    paths={"labels":ROOT / "backtest_datasets/cli_research/knyc_cli_highs.csv",
           "hourly":ROOT / "backtest_datasets/knyc_hourly_2019_2026.csv",
           "markets":ROOT / "backtest_datasets/real_price_backtest_trades.csv"}
    frame=build_frame(pd.read_csv(paths["hourly"]),pd.read_csv(paths["labels"]))
    archive=validate_archive(pd.read_csv(paths["markets"]))
    archive=archive[archive.series.eq("KXHIGHNY")]
    snapshots=archive.merge(frame,on=["date","hour"],validate="many_to_one",suffixes=("","_weather"))
    outputs=[]
    for year,g in snapshots.groupby(snapshots.date.dt.year):
        train=frame[(frame.date.dt.year<year) & (frame.product_issued_utc<pd.Timestamp(f"{year}-01-01",tz="UTC"))]
        if train.date.nunique()<200:
            continue
        model=ConditionalReportHigh().fit(train)
        pmf=model.predict_pmf(g)
        bounds=g.bucket.str.extract(r"^(-?\d+)-(-?\d+)$").astype(float)
        if bounds.isna().any().any():
            raise ValueError("Only inclusive between contracts supported here.")
        masks=(REPORT_SUPPORT>=bounds[0].to_numpy()[:,None]) & (REPORT_SUPPORT<=bounds[1].to_numpy()[:,None])
        g=g.copy()
        g["legacy_weather"]=g.model_p
        g["model_p"]=(pmf*masks).sum(axis=1)
        g["weather_train_end"]=train.date.max()
        outputs.append(g)
    if not outputs:
        raise ValueError("No eligible weather folds.")
    candidate=pd.concat(outputs,ignore_index=True)
    pred=evaluate(candidate)
    legacy=pred.assign(model_p=pred.legacy_weather,raw_weather=pred.legacy_weather)
    report={"n_days":pred.date.nunique(),"n_rows":len(pred),"matched_input_rows":len(candidate),
            "scores":score(pred),"legacy_weather_on_identical_rows":score(legacy)["raw_weather"],
            "paired_vs_market":{name:paired_interval(pred,name) for name in ("raw_weather","market_anchor")},
            "mean_weather_weight":float(pred.groupby("date").weather_weight.first().mean()),
            "protocol":"Prior-year CLI weather fit; daily 30-date minimum market blend, 2-day embargo, penalty .01; fixed hyperparameters.",
            "inputs":{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
            "limitations":["Old candle joins unresolved, no executable books or receipt times.",
                            "Current CLI archive revisions, not contemporaneous report vintages.",
                            "Partial NYC contract boards, matched observation days, short previously examined sample.",
                            "No alpha/deployment claim regardless of score; fresh prospective evidence required."]}
    output=ROOT / "reports/model_followup"
    output.mkdir(parents=True,exist_ok=True)
    pred.drop(columns=["source_url","retrieved_utc","station"]).to_csv(output / "report_market_predictions.csv",index=False,float_format="%.10g")
    (output / "report_market_audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
