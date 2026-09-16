"""NYC report model forward features and coherent contract-board diagnostics."""
import math
import numpy as np
import pandas as pd
from .data.fast_metar import _TEMP_RE
from .models.conditional_report import REPORT_SUPPORT
from .evaluation.execution_research import depth_quote, levels, utc


def live_features(payload, received):
    now=pd.Timestamp(utc(received))
    civil=now.tz_convert("America/New_York")
    cutoff=civil.floor("h")
    if civil.month not in (5,6,7,8,9) or civil.hour not in range(13,19) or (civil-cutoff).total_seconds()>300:
        raise ValueError("Outside validated season/hour or five-minute decision window.")
    day=now.tz_convert("Etc/GMT+5").date()
    start=pd.Timestamp(day,tz="Etc/GMT+5")
    rows=[]
    for r in payload:
        if r.get("icaoId")!="KNYC":continue
        observed=pd.to_datetime(r["obsTime"],unit="s",utc=True)
        if not start<=observed<=cutoff:continue
        match=_TEMP_RE.search(r.get("rawOb", ""))
        if match:
            c=int(match.group("t"))/10 * (-1 if match.group("sign")=="1" else 1)
            rows.append((observed,c*9/5+32))
    f=pd.DataFrame(rows,columns=["observed","temp"]).drop_duplicates("observed",keep="last").sort_values("observed")
    if len(f)<2:raise ValueError("Insufficient precise station observations.")
    if not f.temp.between(-40,130).all():raise ValueError("Implausible temperature.")
    last,previous=f.iloc[-1],f.iloc[-2]
    age=(cutoff-last.observed).total_seconds()/3600
    step=(last.observed-previous.observed).total_seconds()/3600
    if age>1.5 or not .1<=step<=2:raise ValueError("Stale observations or unsupported sampling cadence.")
    gaps=f.observed.diff().dt.total_seconds().dropna()/3600
    quality=(len(f)>=10 and (f.observed.iloc[0]-start).total_seconds()<=7200 and gaps.max()<=1.5 and age<=1.25)
    features=pd.DataFrame([{"date":pd.Timestamp(day),"hour":civil.hour,"observed_max":f.temp.max(),
        "drop_from_max":f.temp.max()-last.temp,"slope":(last.temp-previous.temp)/step}])
    return features,{"quality_ok":bool(quality),"observation_count":len(f),"age_hours":age,
        "max_gap_hours":float(gaps.max()),"cutoff_utc":cutoff.tz_convert("UTC").isoformat(),
        "weather_received_utc":now.isoformat(),"last_observation_utc":last.observed.isoformat()}


def contract_mask(market):
    kind=market.get("strike_type")
    def strike(name):
        x=float(market[name])
        if not math.isfinite(x) or x!=int(x):raise ValueError("Integer temperature strikes required.")
        return int(x)
    if kind=="between":
        lo,hi=strike("floor_strike"),strike("cap_strike")
        if lo>hi:raise ValueError("Reversed strikes.")
        return (REPORT_SUPPORT>=lo)&(REPORT_SUPPORT<=hi)
    if kind=="less":return REPORT_SUPPORT<strike("cap_strike")
    if kind=="greater":return REPORT_SUPPORT>strike("floor_strike")
    raise ValueError("Unsupported strike semantics.")


def board_probabilities(markets,books,pmf,now,*,max_age=15):
    """Require a complete non-overlapping board and fresh two-sided books.

    Normalized midpoints are market PROXIES. REST boards are not atomic.
    """
    p=np.asarray(pmf,dtype=float)
    if p.shape!=REPORT_SUPPORT.shape or not np.isfinite(p).all() or (p<0).any() or not np.isclose(p.sum(),1):
        raise ValueError("Invalid report PMF.")
    if not markets or len({m["event_ticker"] for m in markets})!=1:raise ValueError("Single event board required.")
    if len({m["ticker"] for m in markets})!=len(markets):raise ValueError("Duplicate market.")
    masks=np.array([contract_mask(m) for m in markets])
    if not (masks.sum(axis=0)==1).all():raise ValueError("Incomplete or overlapping bucket board.")
    rows=[]
    for m,mask in zip(markets,masks):
        if m.get("status") not in ("open","active"):raise ValueError("Market not active.")
        if utc(m["close_time"])<=utc(now):raise ValueError("Market closed.")
        b=books[m["ticker"]]
        age=(utc(now)-utc(b["received_utc"])).total_seconds()
        if not 0<=age<=max_age:raise ValueError("Stale or future book.")
        if not 0<=(utc(b["received_utc"])-utc(b["request_started_utc"])).total_seconds()<=2:
            raise ValueError("Slow or invalid book request.")
        yes,no=levels(b["payload"],"yes"),levels(b["payload"],"no")
        if not yes or not no:raise ValueError("Missing book side.")
        ask=depth_quote(b["payload"],"yes",1)
        if not ask["fully_fillable"]:raise ValueError("Insufficient board depth.")
        rows.append({"ticker":m["ticker"],"weather_p":float(p[mask].sum()),
                     "mid":float((yes[0][0]+1-no[0][0])/2),"ask":float(ask["gross_dollars"])})
    total=sum(r["mid"] for r in rows)
    if total<=0:raise ValueError("Zero midpoint mass.")
    for r in rows:r["market_p"]=r["mid"]/total
    return rows,{"midpoint_sum":total,"one_each_gross_ask_cost":sum(r["ask"] for r in rows),
                 "interpretation":"diagnostic only; fees and non-atomic snapshots can eliminate apparent arbitrage"}
