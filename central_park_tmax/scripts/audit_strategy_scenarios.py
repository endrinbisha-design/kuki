#!/usr/bin/env python3
"""Friction scenarios on legacy MIDPOINT proxies, NOT executable strategy backtests.

No depth/receipt history exists for these inputs. Quotes below are explicitly
synthetic: fixed spreads, one-contract liquidity, unchanged prices after latency.
Results are stress diagnostics only; never combine with forward paper performance.
"""
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from central_park_tmax.paper import PaperConfig,PaperLedger,choose_signal,signal_id


def run(frame,strategy,half_spread,fee):
    config=PaperConfig(strategy=strategy,fee_per_contract=str(fee),slippage_per_contract="0")
    ledger=PaperLedger(":memory:",config)
    settlements=[];reasons={};curve=[0.]
    for r in frame.sort_values(["date","hour","bucket"]).itertuples():
        now=(pd.Timestamp(r.date).tz_localize("America/New_York")+pd.Timedelta(hours=r.hour)).to_pydatetime()
        for at,ticker,outcome in list(settlements):
            if at<=now:
                ledger.settle(ticker,outcome,at,"legacy archived outcome; assumed two-day availability")
                settlements.remove((at,ticker,outcome))
                curve.append(ledger.summary()["realized_pnl"])
        midpoint=float(r.price)
        bid=max(0,midpoint-half_spread);ask=min(1,midpoint+half_spread)
        book={"orderbook_fp":{"yes_dollars":[[f"{bid:.6f}","1"]],"no_dollars":[[f"{1-ask:.6f}","1"]]}}
        age=(pd.Timestamp(r.cutoff_utc)-pd.Timestamp(r.last_observation_utc)).total_seconds()/3600
        quality=age<=1.25 and abs(float(r.model_p)-midpoint)<=.25
        decision,reason=choose_signal(config,float(r.model_p),midpoint,book,quality_ok=quality,
                                      disagreement=abs(float(r.model_p)-midpoint))
        reasons[reason]=reasons.get(reason,0)+1
        if decision:
            ticker=f"{r.date}:{r.bucket}"
            sid=signal_id("historical_scenario",str(now),ticker,strategy)
            ledger.submit(sid,ticker,str(r.date),decision["side"],decision["limit_price"],now,{"synthetic_quote":True})
            record={"ticker":ticker,"request_started_utc":(now+timedelta(seconds=2)).isoformat(),
                    "received_utc":(now+timedelta(seconds=3)).isoformat(),"payload":book}
            ledger.advance([record],now+timedelta(seconds=3))
            outcome="yes" if bool(r.won) else "no"
            event=(pd.Timestamp(r.date).tz_localize("UTC")+pd.Timedelta(days=2,hours=10)).to_pydatetime()
            if not any(t==ticker for _,t,_ in settlements):settlements.append((event,ticker,outcome))
    for at,ticker,outcome in sorted(settlements):
        ledger.settle(ticker,outcome,at,"legacy archived outcome; assumed two-day availability")
        curve.append(ledger.summary()["realized_pnl"])
    result=ledger.summary()
    result["max_realized_drawdown"]=float(np.max(np.maximum.accumulate(curve)-curve))
    result["decision_reasons"]=reasons
    result["assumptions"]={"half_spread":half_spread,"fee_per_contract":fee,"synthetic_depth":1,"price_unchanged_after_latency":True}
    ledger.db.close()
    return result


def main():
    path=ROOT/"reports/model_followup/report_market_predictions.csv"
    frame=pd.read_csv(path)
    strategies=("report_flat","blend_flat","blend_guarded","blend_robust")
    scenarios=((.005,.01),(.015,.02),(.025,.03))
    report={"kind":"hypothetical friction scenarios; NOT historical executable returns",
            "input_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"rows":len(frame),"days":frame.date.nunique(),
            "results":[run(frame,s,h,f) for h,f in scenarios for s in strategies],
            "limitations":["Unresolved legacy price joins; no quote age, true bid/ask, depth or arrival history.",
                           "Fixed 10% weather blend is an exploratory choice on previously examined data.",
                           "Synthetic unchanged quotes after latency can overstate fills.",
                           "Outcomes released on an assumed two-day schedule; incomplete NYC boards.",
                           "No optimized winner or alpha claim; forward experiment needed."]}
    out=ROOT/"reports/automation_research";out.mkdir(parents=True,exist_ok=True)
    (out/"strategy_scenarios.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
