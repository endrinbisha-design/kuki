#!/usr/bin/env python3
"""Does weather add information to NYC market proxies conditional on physical state?

Fixed states and shrinkage, expanding daily fits; legacy price provenance remains
unresolved. State conditioning cannot repair stale/wrong prices. No alpha claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from central_park_tmax.models.market_anchor import MarketAnchoredBlend
from audit_conditional_rise import build_snapshots
from audit_probability_models import validate_archive


def physical_state(frame):
    # A rising observation takes priority even if below an earlier high.
    return np.select([frame.slope > .2, frame.drop_from_max >= 2.],
                     ["rising", "below_peak"], default="near_peak_flat_or_cooling")


def evaluate(frame):
    out = []
    for day in sorted(frame.date.unique()):
        train = frame[frame.date <= day - pd.Timedelta(days=2)]
        test = frame[frame.date == day].copy()
        if train.date.nunique() < 30:
            continue
        def fit(g, minimum):
            return MarketAnchoredBlend(min_dates=minimum).fit(g.model_p,g.price,g.won,g.date)
        global_model = fit(train,30)
        test["global_anchor"] = global_model.predict(test.model_p,test.price,forecast_date=day)
        test["state_anchor"] = test.global_anchor
        test["weather_weight"] = global_model.weather_weight
        for state, group in test.groupby("state"):
            history = train[train.state == state]
            n = history.date.nunique()
            if n >= 10:
                # Shrink local coefficient to global; same weight for every bucket
                # at a given physical state, preserving any coherent input board.
                local_model = fit(history,10)
                w = n/(n+30)
                alpha = w*local_model.weather_weight + (1-w)*global_model.weather_weight
                test.loc[group.index,"state_anchor"] = group.price + alpha*(group.model_p-group.price)
                test.loc[group.index,"weather_weight"] = alpha
        test["train_end"] = train.date.max()
        out.append(test)
    if not out:
        raise ValueError("Insufficient eligible dates.")
    return pd.concat(out,ignore_index=True)


def scores(f):
    result = {}
    for name in ("price","model_p","global_anchor","state_anchor"):
        p=f[name].clip(1e-6,1-1e-6)
        result[name] = {"brier": float(f.assign(loss=(f[name]-f.won)**2).groupby("date").loss.mean().mean()),
                       "log_loss": float(f.assign(loss=-(f.won*np.log(p)+(1-f.won)*np.log(1-p))).groupby("date").loss.mean().mean())}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",type=Path,default=ROOT / "reports/model_followup")
    args=p.parse_args()
    market_path=ROOT / "backtest_datasets/real_price_backtest_trades.csv"
    hourly_path=ROOT / "backtest_datasets/knyc_hourly_2019_2026.csv"
    archive=validate_archive(pd.read_csv(market_path))
    nyc=archive[archive.series.eq("KXHIGHNY")]
    features=build_snapshots(pd.read_csv(hourly_path),standard_day=True)
    features["state"]=physical_state(features)
    # Deliberately don't pass final high/remaining rise to the learner.
    f=nyc.merge(features[["date","hour","state","last_observation_utc","cutoff_utc"]],on=["date","hour"],validate="many_to_one")
    pred=evaluate(f)
    delta=pred.assign(delta=(pred.state_anchor-pred.won)**2-(pred.price-pred.won)**2).groupby("date").delta.mean()
    rng=np.random.default_rng(20260916)
    v=delta.to_numpy();draws=[]
    for _ in range(2000):
        ix=((rng.integers(0,len(v),int(np.ceil(len(v)/7)))[:,None]+np.arange(7))%len(v)).ravel()[:len(v)]
        draws.append(v[ix].mean())
    report={"n_rows":len(pred),"n_days":pred.date.nunique(),"matched_rows":len(f),"unmatched_rows":len(nyc)-len(f),
            "scores":scores(pred),"per_state":{s:{"days":g.date.nunique(),"scores":scores(g),"mean_weather_weight":float(g.groupby("date").weather_weight.mean().mean())} for s,g in pred.groupby("state")},
            "paired_state_minus_market_brier":{"mean":float(delta.mean()),"ci95":np.quantile(draws,[.025,.975]).tolist(),"bootstrap":"7 observed days, paired, descriptive"},
            "inputs":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (market_path,hourly_path)},
            "protocol":{"min_global_dates":30,"min_state_dates":10,"state_prior_dates":30,"penalty":.01,"embargo_calendar_days":2,"parameter_search":False},
            "limitations":["Unresolved legacy price joins, midpoint proxies, no depth or receipt times.","Matched NYC subset only; missing observations may select days.","Two-day label delay is assumed, not actual settlement availability.","No marine-state test: aligned historical cloud/wind data unavailable in this input.","Previously inspected data; exploratory subgroup analysis, not confirmed alpha."]}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    pred.to_csv(args.output_dir / "market_state_predictions.csv",index=False)
    (args.output_dir / "market_state_audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
