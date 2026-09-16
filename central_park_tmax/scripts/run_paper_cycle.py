#!/usr/bin/env python3
"""One unattended PAPER cycle: archive -> forecast -> delayed fills -> signals -> settle.

Public GETs only. No keys, order endpoints, broker connection, or live mode.
Use the supplied systemd timer on a persistent host; overlapping runs are rejected.
"""
from datetime import datetime,timezone
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
import joblib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from central_park_tmax.paper import PaperConfig,PaperLedger,choose_signal,signal_id
from central_park_tmax.forward import live_features,board_probabilities
from central_park_tmax.evaluation.execution_research import utc
from archive_orderbooks import collect,fetch


def now():return datetime.now(timezone.utc)


def save_json(path,value):
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value,indent=2)+"\n")
    temporary.replace(path)


def cycle(state,config,model_path):
    ledger=PaperLedger(state/"paper.sqlite",config)
    run_started=now();stamp=run_started.strftime("%Y%m%dT%H%M%S%fZ")
    archive=state/"archive";archive.mkdir(parents=True,exist_ok=True)
    status={"started_utc":run_started.isoformat(),"mode":"paper","status":"started"}
    try:
        if (state/"STOP").exists():
            ledger.advance([],now(),halted=True)
            status["status"]="halted";return status
        card=json.loads(model_path.with_name("model_card.json").read_text())
        if card.get("station")!="KNYC" or not card.get("source_hashes"):
            raise ValueError("A current NYC model card with source hashes is required.")
        for relative,expected in card["source_hashes"].items():
            if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
                raise ValueError("Model/feature source changed: prepare a new frozen experiment.")
        if hashlib.sha256(model_path.read_bytes()).hexdigest()!=card["artifact_sha256"]:
            raise ValueError("Model artifact hash mismatch.")
        # Only load locally built, trusted artifacts, never downloaded joblib files.
        bundle=joblib.load(model_path)
        if bundle["card"]["model_id"]!=card["model_id"]:raise ValueError("Model card mismatch.")
        ledger.db.execute("INSERT OR IGNORE INTO settings VALUES ('model_id',?)",(card["model_id"],))
        if ledger.db.execute("SELECT value FROM settings WHERE key='model_id'").fetchone()[0]!=card["model_id"]:
            raise ValueError("Model changed: create a new forward experiment database.")
        status["model_id"]=card["model_id"]
        weather_start=now()
        url="https://aviationweather.gov/api/data/metar?ids=KNYC&format=json&hours=24"
        req=urllib.request.Request(url,headers={"User-Agent":"central-park-tmax-paper-research/0.1"})
        with urllib.request.urlopen(req,timeout=20) as response:raw=response.read()
        weather_received=now()
        payload=json.loads(raw)
        save_json(archive/f"{stamp}_weather.json",{"url":url,"request_started_utc":weather_start.isoformat(),
            "received_utc":weather_received.isoformat(),"sha256":hashlib.sha256(raw).hexdigest(),"payload":payload})
        # Still collect/settle outside prediction hours. Failure to forecast means abstain.
        try:
            features,quality=live_features(payload,weather_received)
            pmf=bundle["model"].predict_pmf(features)[0]
            prediction={"features":features.assign(date=features.date.astype(str)).to_dict("records"),
                        "quality":quality,"pmf":pmf.tolist(),"model_id":card["model_id"]}
            save_json(archive/f"{stamp}_prediction.json",prediction)
        except ValueError as exc:
            features=None;status["forecast_abstention"]=str(exc)
        books,metadata=collect("KXHIGHNY")
        for label,data in (("books",books),("metadata",metadata)):
            save_json(archive/f"{stamp}_{label}.json",data)
        if any("error" in b for b in books):raise ValueError("Incomplete orderbook collection.")
        current=now()
        # Losing valid weather coverage also withdraws unfilled paper intents.
        halt_fills=(state/"STOP").exists() or features is None
        if features is not None and config.strategy in ("blend_guarded","blend_robust"):
            halt_fills=halt_fills or not quality["quality_ok"]
        ledger.advance(books,current,halted=halt_fills)
        # Settlement comes from explicit exchange outcomes, not a model estimate.
        open_tickers=[r[0] for r in ledger.db.execute("SELECT DISTINCT ticker FROM orders WHERE state='open'")]
        for ticker in open_tickers:
            try:
                try:result=fetch("/markets/"+ticker)
                except urllib.error.HTTPError as exc:
                    if exc.code!=404:raise
                    result=fetch("/historical/markets/"+ticker)
                save_json(archive/f"{stamp}_{ticker}_settlement.json",result)
                market=result["payload"]["market"]
                if market.get("status")=="settled" and market.get("result") in ("yes","no"):
                    ledger.settle(ticker,market["result"],result["received_utc"],result["url"])
            except Exception as exc:
                ledger.log(now(),"settlement_error",{"ticker":ticker,"error":str(exc)})
        if features is not None and not (state/"STOP").exists():
            # Weather decision must remain close to its trained exact-hour cutoff.
            if (now()-utc(quality["cutoff_utc"])).total_seconds()>300:
                raise ValueError("Collection exceeded forecast decision window.")
            markets=[m for page in metadata for m in page["payload"].get("markets",[])]
            tag=features.date.iloc[0].strftime("%y%b%d").upper()
            markets=[m for m in markets if m.get("event_ticker")==f"KXHIGHNY-{tag}"]
            bookmap={b["ticker"]:b for b in books}
            rows,diagnostic=board_probabilities(markets,bookmap,pmf,now(),max_age=config.max_book_age_seconds)
            ledger.log(now(),"board_diagnostic",diagnostic)
            for row in rows:
                decision,reason=choose_signal(config,row["weather_p"],row["market_p"],bookmap[row["ticker"]]["payload"],
                    quality_ok=quality["quality_ok"],disagreement=abs(row["weather_p"]-row["market_p"]))
                sid=signal_id(card["model_id"],quality["cutoff_utc"],row["ticker"],config.strategy)
                ledger.log(now(),"decision",{"id":sid,"ticker":row["ticker"],"reason":reason,"probabilities":row,"quality":quality})
                if decision:
                    ledger.submit(sid,row["ticker"],markets[0]["event_ticker"],decision["side"],decision["limit_price"],now(),
                                  {"model_id":card["model_id"],"cutoff":quality["cutoff_utc"],"decision":decision})
        status["status"]="ok"
    except Exception as exc:
        # Data/model failure cancels unfilled intents, preserving funded positions.
        ledger.advance([],now(),halted=True)
        status.update(status="degraded",error=f"{type(exc).__name__}: {exc}")
        ledger.log(now(),"cycle_error",status)
    finally:
        status["finished_utc"]=now().isoformat();status["portfolio"]=ledger.summary()
        save_json(state/"heartbeat.json",status)
        save_json(archive/f"{stamp}_cycle.json",status)
        ledger.db.close()
    return status


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-dir",type=Path,default=ROOT/"data/paper/run")
    p.add_argument("--config",type=Path,default=ROOT/"configs/paper.json")
    p.add_argument("--model",type=Path,default=ROOT/"data/paper/model/report_model.joblib")
    args=p.parse_args()
    args.state_dir.mkdir(parents=True,exist_ok=True)
    with (args.state_dir/"run.lock").open("w") as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:print("Another paper cycle is running.");return 1
        config=PaperConfig(**json.loads(args.config.read_text()))
        status=cycle(args.state_dir,config,args.model)
        print(json.dumps(status,indent=2))
    return 0 if status["status"] in ("ok","halted") else 1


if __name__=="__main__":raise SystemExit(main())
