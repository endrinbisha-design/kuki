from datetime import datetime,timedelta,timezone
from dataclasses import replace
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor
from central_park_tmax.paper import PaperConfig,PaperLedger,choose_signal
from central_park_tmax.forward import live_features,board_probabilities
from central_park_tmax.models.conditional_report import REPORT_SUPPORT
from central_park_tmax.evaluation.crossfit import chronological_residuals

T=datetime(2026,7,29,20,tzinfo=timezone.utc)


def book():return {"orderbook_fp":{"yes_dollars":[["0.40","10"]],"no_dollars":[["0.58","10"]]}}


def record(ticker="TEST",seconds=3):
    return {"ticker":ticker,"request_started_utc":(T+timedelta(seconds=seconds-1)).isoformat(),
            "received_utc":(T+timedelta(seconds=seconds)).isoformat(),"payload":book()}


def test_live_mode_rejected():
    with pytest.raises(ValueError,match="paper"):PaperConfig(mode="live")


def test_restart_and_duplicate_signal_do_not_double_spend(tmp_path):
    p=tmp_path/"paper.sqlite";cfg=PaperConfig()
    ledger=PaperLedger(p,cfg)
    assert ledger.submit("a","TEST","EVENT","yes",".5",T,{})=="pending"
    ledger.db.close();ledger=PaperLedger(p,cfg)
    assert ledger.submit("a","TEST","EVENT","yes",".5",T,{})=="duplicate_signal"
    assert ledger.submit("b","TEST","EVENT","no",".5",T,{})=="ticker_already_entered"
    ledger.advance([record(seconds=1)],T+timedelta(seconds=1))
    assert ledger.summary()["states"]["pending"]==1
    ledger.advance([record()],T+timedelta(seconds=3))
    assert ledger.summary()["cash"]==pytest.approx(999.55)
    ledger.advance([record()],T+timedelta(seconds=3))
    assert ledger.summary()["cash"]==pytest.approx(999.55)
    ledger.settle("TEST","yes",T+timedelta(days=1),"recorded exchange result")
    ledger.settle("TEST","yes",T+timedelta(days=1),"recorded exchange result")
    assert ledger.summary()["cash"]==pytest.approx(1000.55)
    with pytest.raises(ValueError,match="Conflicting"):
        ledger.settle("TEST","no",T+timedelta(days=1),"conflicting result")
    ledger.db.close()
    with pytest.raises(ValueError,match="Configuration changed"):
        PaperLedger(p,replace(cfg,quantity=2))


@pytest.mark.parametrize("config,reason",[
    (PaperConfig(initial_cash=".1"),"cash_limit"),
    (PaperConfig(max_event_risk=".1"),"event_risk_limit"),
    (PaperConfig(max_open_risk=".1"),"open_risk_limit"),
    (PaperConfig(max_daily_spend=".1"),"daily_spend_limit"),
])
def test_risk_limits_reserve_before_fill(config,reason):
    ledger=PaperLedger(":memory:",config)
    assert ledger.submit("a","TEST","EVENT","yes",".5",T,{})==reason
    assert ledger.summary()["orders"]==0


def test_pending_risk_and_order_limits():
    ledger=PaperLedger(":memory:",PaperConfig(max_event_risk=".8"))
    assert ledger.submit("a","A","EVENT","yes",".5",T,{})=="pending"
    assert ledger.submit("b","B","EVENT","yes",".5",T,{})=="event_risk_limit"
    ledger.advance([],T+timedelta(seconds=181))
    assert ledger.summary()["reserved_cash"]==0
    assert ledger.submit("b","B","EVENT","yes",".5",T+timedelta(seconds=182),{})=="pending"


def test_halt_cancels_pending_without_spending():
    ledger=PaperLedger(":memory:",PaperConfig())
    ledger.submit("a","TEST","EVENT","yes",".5",T,{})
    ledger.advance([record()],T+timedelta(seconds=3),halted=True)
    assert ledger.summary()["states"]["cancelled"]==1
    assert ledger.summary()["cash"]==1000


def test_future_stale_and_limit_quotes_do_not_fill():
    ledger=PaperLedger(":memory:",PaperConfig())
    ledger.submit("a","TEST","EVENT","yes",".41",T,{})
    ledger.advance([record()],T)
    ledger.advance([record()],T+timedelta(seconds=30))
    ledger.advance([record()],T+timedelta(seconds=3))
    assert ledger.summary()["states"]["pending"]==1


def test_daily_loss_limit_cancels_pending_and_rejects_new():
    ledger=PaperLedger(":memory:",PaperConfig(max_daily_realized_loss=".4"))
    ledger.submit("a","TEST","EVENT","yes",".5",T,{})
    ledger.advance([record()],T+timedelta(seconds=3))
    ledger.submit("b","B","EVENT","yes",".5",T+timedelta(seconds=4),{})
    ledger.settle("TEST","no",T+timedelta(seconds=5),"test outcome")
    ledger.advance([],T+timedelta(seconds=6))
    assert ledger.summary()["states"]["cancelled"]==1
    assert ledger.submit("c","C","EVENT","yes",".5",T+timedelta(seconds=7),{})=="daily_loss_limit"


def test_quality_and_costs_prevent_forced_signals():
    cfg=PaperConfig(strategy="blend_robust")
    assert choose_signal(cfg,.95,.41,book(),quality_ok=False)[1]=="quality_gate"
    assert choose_signal(cfg,.6,.41,book(),quality_ok=True)[1]=="no_net_edge"
    assert choose_signal(PaperConfig(strategy="report_flat"),.9,.41,book(),quality_ok=True)[0]["side"]=="yes"


def test_forward_features_use_standard_day_and_exact_cutoff():
    times=pd.date_range("2026-07-29 04:51Z",periods=17,freq="h")
    payload=[{"icaoId":"KNYC","obsTime":int(t.timestamp()),"rawOb":f"KNYC RMK T{('0380' if i in (0,16) else '0250')}0200"} for i,t in enumerate(times)]
    frame,meta=live_features(payload,T+timedelta(seconds=5))
    assert frame.observed_max.iloc[0]==77 # Excludes prior-day 00:51 and future 16:51 EDT.
    assert meta["quality_ok"]
    assert meta["last_observation_utc"]=="2026-07-29T19:51:00+00:00"
    with pytest.raises(ValueError,match="window"):
        live_features(payload,T+timedelta(minutes=6))


def test_incomplete_board_never_normalized_into_fake_complete_board():
    p=np.zeros(len(REPORT_SUPPORT));p[REPORT_SUPPORT==80]=1
    market={"ticker":"TEST","event_ticker":"EVENT","strike_type":"between","floor_strike":80,"cap_strike":81,
            "status":"active","close_time":(T+timedelta(days=1)).isoformat()}
    with pytest.raises(ValueError,match="Incomplete"):
        board_probabilities([market],{"TEST":record()},p,T+timedelta(seconds=4))


def test_complete_board_is_coherent_and_rejects_duplicate_tickers():
    p=np.zeros(len(REPORT_SUPPORT));p[REPORT_SUPPORT==80]=1
    common={"event_ticker":"EVENT","status":"active","close_time":(T+timedelta(days=1)).isoformat()}
    markets=[dict(common,ticker="A",strike_type="less",cap_strike=80),dict(common,ticker="B",strike_type="greater",floor_strike=79)]
    rows,_=board_probabilities(markets,{t:record(t) for t in ("A","B")},p,T+timedelta(seconds=4))
    assert sum(r["weather_p"] for r in rows)==1
    assert sum(r["market_p"] for r in rows)==pytest.approx(1)
    with pytest.raises(ValueError,match="Duplicate"):
        board_probabilities(markets+markets,{},p,T)


def test_crossfit_errors_are_not_in_sample_or_future_dependent():
    X=pd.DataFrame({"x":np.arange(40)});y=np.arange(40,dtype=float);dates=pd.date_range("2020-01-01",periods=40)
    a=chronological_residuals(DummyRegressor(),X,y,dates,min_train_dates=5,block_dates=5)
    y2=y.copy();y2[-10:]+=1000
    b=chronological_residuals(DummyRegressor(),X,y2,dates,min_train_dates=5,block_dates=5)
    np.testing.assert_allclose(a.prediction[:30],b.prediction[:30],equal_nan=True)
    assert a.prediction.iloc[:10].isna().all()
    assert a.prediction.iloc[10]==pytest.approx(y[:9].mean())
    assert (a.residual.dropna()>0).all()


def test_full_paper_cycle_delays_fills_then_settles_with_mock_feeds(tmp_path,monkeypatch):
    import hashlib,json,io
    root=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root/"scripts"))
    spec=importlib.util.spec_from_file_location("paper_cycle_test",root/"scripts/run_paper_cycle.py")
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    model_path=tmp_path/"report_model.joblib";model_path.write_bytes(b"trusted-test-stub")
    relative="src/central_park_tmax/forward.py"
    card={"model_id":"test","station":"KNYC","source_hashes":{relative:hashlib.sha256((root/relative).read_bytes()).hexdigest()},
          "artifact_sha256":hashlib.sha256(model_path.read_bytes()).hexdigest()}
    model_path.with_name("model_card.json").write_text(json.dumps(card))
    class Model:
        def predict_pmf(self,frame):
            p=np.zeros((len(frame),len(REPORT_SUPPORT)));p[:,REPORT_SUPPORT==80]=1
            return p
    monkeypatch.setattr(runner.joblib,"load",lambda path:{"model":Model(),"card":card})
    times=pd.date_range("2026-07-29 05:51Z",periods=15,freq="h")
    weather=[{"icaoId":"KNYC","obsTime":int(t.timestamp()),"rawOb":"KNYC RMK T02500200"} for t in times]
    monkeypatch.setattr(runner.urllib.request,"urlopen",lambda *a,**kw:io.BytesIO(json.dumps(weather).encode()))
    clock=[T]
    monkeypatch.setattr(runner,"now",lambda:clock[0])
    common={"event_ticker":"KXHIGHNY-26JUL29","status":"active","close_time":(T+timedelta(hours=12)).isoformat()}
    markets=[dict(common,ticker="A",strike_type="less",cap_strike=80),dict(common,ticker="B",strike_type="greater",floor_strike=79)]
    def collect(series):
        books=[{"ticker":t,"request_started_utc":(clock[0]-timedelta(seconds=1)).isoformat(),
                "received_utc":clock[0].isoformat(),"payload":book()} for t in ("A","B")]
        return books,[{"payload":{"markets":markets}}]
    monkeypatch.setattr(runner,"collect",collect)
    def fetch(path):
        ticker=path.split("/")[-1]
        market={"status":"settled" if clock[0]>T+timedelta(hours=12) else "active","result":"yes" if ticker=="B" else "no"}
        return {"payload":{"market":market},"received_utc":clock[0].isoformat(),"url":"mock:"+path}
    monkeypatch.setattr(runner,"fetch",fetch)
    cfg=PaperConfig(strategy="report_flat")
    first=runner.cycle(tmp_path,cfg,model_path)
    assert first["status"]=="ok"
    assert first["portfolio"]["states"]["pending"]==2
    clock[0]=T+timedelta(seconds=3)
    second=runner.cycle(tmp_path,cfg,model_path)
    assert second["portfolio"]["states"]["open"]==2
    assert second["portfolio"]["orders"]==2
    clock[0]=T+timedelta(days=1)
    third=runner.cycle(tmp_path,cfg,model_path)
    assert third["portfolio"]["states"]["settled"]==2
    assert third["portfolio"]["realized_pnl"]==pytest.approx(.92)
    assert json.loads((tmp_path/"heartbeat.json").read_text())["status"]=="ok"
    def failed(series):raise RuntimeError("403 Forbidden")
    monkeypatch.setattr(runner,"collect",failed)
    fourth=runner.cycle(tmp_path,cfg,model_path)
    assert fourth["status"]=="degraded"
    assert fourth["portfolio"]["orders"]==2
