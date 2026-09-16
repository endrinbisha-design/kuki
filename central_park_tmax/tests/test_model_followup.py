"""Guards for report targets, physical-state validation, and quote diagnostics."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from central_park_tmax.models.conditional_report import ConditionalReportHigh, REPORT_SUPPORT
from central_park_tmax.evaluation.execution_research import (
    depth_quote, validate_book, first_snapshot_after, event_markout)

ROOT=Path(__file__).resolve().parents[1]


def script(name,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec=importlib.util.spec_from_file_location(name,ROOT / "scripts" / f"{name}.py")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def training():
    return pd.DataFrame({"date":pd.date_range("2024-05-01",periods=60),"hour":16,
        "drop_from_max":0.,"slope":0.,"observed_max":80.,"cli_high":np.tile([79,81,82],20)})


def test_report_pmf_preserves_negative_gap_and_total_probability():
    model=ConditionalReportHigh().fit(training())
    test=training().iloc[:1].assign(date=pd.Timestamp("2025-05-01"))
    pmf=model.predict_pmf(test)
    assert pmf.shape==(1,len(REPORT_SUPPORT))
    assert pmf.sum()==pytest.approx(1)
    assert pmf[0,REPORT_SUPPORT==79][0]==pytest.approx(1/3)
    assert (np.diff(pmf.cumsum(axis=1),axis=1)>=-1e-12).all()
    # Labels in the prediction frame must have no influence on forecast output.
    np.testing.assert_array_equal(pmf,model.predict_pmf(test.assign(cli_high=120)))


def test_report_rejects_in_sample_dates_and_fractional_labels():
    model=ConditionalReportHigh().fit(training())
    with pytest.raises(ValueError,match="dates"):
        model.predict_pmf(training())
    with pytest.raises(ValueError,match="integers"):
        ConditionalReportHigh().fit(training().assign(cli_high=80.5))
    with pytest.raises(ValueError,match="unique"):
        ConditionalReportHigh().fit(pd.concat([training(),training()]))


def test_standard_day_excludes_prior_civil_midnight_and_includes_next(monkeypatch):
    module=script("audit_conditional_rise",monkeypatch)
    times=pd.date_range("2025-07-01 00:51",periods=49,freq="h",tz="America/New_York")
    temperatures=np.full(len(times),70.)
    temperatures[0]=100.  # Belongs to June 30's CLI day.
    temperatures[24]=80. # July 2 00:51 belongs to July 1's CLI day.
    raw=pd.DataFrame({"valid":times.tz_convert("UTC"),"tmpf":temperatures})
    frame=module.build_snapshots(raw,standard_day=True)
    row=frame[(frame.date==pd.Timestamp("2025-07-01")) & (frame.hour==16)].iloc[0]
    assert row.observed_max==70
    assert row.remaining_rise==10
    assert row.last_observation_utc<=row.cutoff_utc


def test_cli_join_rejects_duplicate_labels(monkeypatch):
    module=script("audit_report_high",monkeypatch)
    labels=pd.DataFrame({"date":["2025-07-01"]*2,"product_issued_utc":["2025-07-02T10:00Z"]*2,"station":"KNYC"})
    with pytest.raises(ValueError,match="Unique"):
        module.build_frame(pd.DataFrame(),labels)


def test_market_states_are_frozen_and_future_labels_do_not_change_earlier_predictions(monkeypatch):
    module=script("audit_market_states",monkeypatch)
    states=module.physical_state(pd.DataFrame({"slope":[1.,-.3,0.],"drop_from_max":[3.,3.,0.]}))
    assert states.tolist()==["rising","below_peak","near_peak_flat_or_cooling"]
    f=pd.DataFrame({"date":pd.date_range("2025-05-01",periods=65),"model_p":.8,"price":.6,
                    "won":np.tile([0,1,1,1,0],13),"state":np.resize(states,65)})
    first=module.evaluate(f)
    changed=f.copy()
    cutoff=f.date.iloc[-5]
    changed.loc[changed.date>=cutoff,"won"]=1-changed.loc[changed.date>=cutoff,"won"]
    second=module.evaluate(changed)
    np.testing.assert_array_equal(first.loc[first.date<cutoff,"state_anchor"],second.loc[second.date<cutoff,"state_anchor"])
    assert (first.train_end<=first.date-pd.Timedelta(days=2)).all()


def test_orderbook_collector_preserves_pagination_and_errors(monkeypatch):
    module=script("archive_orderbooks",monkeypatch)
    def fetch(path):
        if path.startswith("/series/"):
            return {"payload":{"series":{"ticker":"TEST"}}}
        if path.startswith("/markets?"):
            if "cursor=next" in path:
                return {"payload":{"markets":[{"ticker":"B"}],"cursor":""}}
            return {"payload":{"markets":[{"ticker":"A"}],"cursor":"next"}}
        if "/B/" in path:
            raise RuntimeError("temporary failure")
        assert path.endswith("depth=0")
        return record("00:00","00:01")
    monkeypatch.setattr(module,"fetch",fetch)
    records,metadata=module.collect("TEST")
    assert len(metadata)==3
    assert len(records)==2
    assert records[0]["depth_requested"]==0
    assert records[1]["error"]=="temporary failure"


def book(yes=None,no=None):
    return {"orderbook_fp":{"yes_dollars":yes or [["0.4000","5.00"]],
                            "no_dollars":no or [["0.5900","2.50"],["0.5500","3.00"]]}}


def test_buy_consumes_opposite_bids_with_decimal_precision_and_depth():
    q=depth_quote(book(),"yes","4.00")
    assert q["fully_fillable"]
    assert float(q["gross_dollars"])==pytest.approx(.41*2.5+.45*1.5)
    assert q["available_fill"]=="4.00"
    assert not depth_quote(book(),"yes",6)["fully_fillable"]
    assert float(depth_quote(book(),"no",1)["vwap"])==.6
    assert float(depth_quote(book(),"yes",1,action="sell")["vwap"])==.4


@pytest.mark.parametrize("payload",[
    {"orderbook_fp":{"yes_dollars":[["0.8","1"]],"no_dollars":[["0.3","1"]]}},
    {"orderbook_fp":{"yes_dollars":[["NaN","1"]],"no_dollars":[]}},
    {"orderbook_fp":{"yes_dollars":[[".4","1"],[".4","2"]],"no_dollars":[]}},
    {"orderbook_fp":{"yes_dollars":[[".4","-1"]],"no_dollars":[]}},
])
def test_reject_invalid_books(payload):
    with pytest.raises(ValueError):
        validate_book(payload)


def record(start,receipt,payload=None):
    return {"ticker":"TEST","request_started_utc":f"2026-09-16T16:{start}+00:00",
            "received_utc":f"2026-09-16T16:{receipt}+00:00","payload":payload or book()}


def test_receipt_after_event_is_not_enough_if_request_started_before():
    rows=[record("00:00","00:02"),record("00:02","00:03")]
    selected=first_snapshot_after(rows,"TEST","2026-09-16T16:00:01Z")
    assert selected==rows[1]
    assert first_snapshot_after(rows,"TEST","2026-09-16T16:01:00Z") is None
    with pytest.raises(ValueError,match="aware"):
        first_snapshot_after(rows,"TEST","2026-09-16T16:00:00")


def test_event_markout_charges_spread_and_explicit_fee_budget():
    rows=[record("00:02","00:03"),record("01:03","01:04")]
    signal={"ticker":"TEST","side":"yes","quantity":"1","signal_received_utc":"2026-09-16T16:00:00Z"}
    result=event_markout(signal,rows,latency_seconds=1,horizon_seconds=60,fee_budget_per_contract=".02")
    assert result["status"]=="quote_markout_only"
    assert float(result["markout_after_fee_budget_dollars"])==pytest.approx(-.03)
    signal["quantity"]="100"
    assert event_markout(signal,rows,latency_seconds=1,horizon_seconds=60,fee_budget_per_contract=".02")["status"]=="insufficient_entry_depth"
