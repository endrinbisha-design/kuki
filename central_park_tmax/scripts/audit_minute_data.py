#!/usr/bin/env python3
"""Measure value of delayed one-minute observations. NEVER a live input backtest.

IEM/NCEI one-minute data have about a 24-hour availability delay. Temperature is
quantized in this service. Coverage and retrospective revision limitations apply.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]


def download(year, cache):
    start=f"{year}-05-01T05:00Z"
    end=f"{year}-10-01T05:00Z" if year<2026 else "2026-08-02T05:00Z"
    url="https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py?"+urllib.parse.urlencode(
        {"station":"NYC","vars":"tmpf","sts":start,"ets":end,"what":"download","tz":"UTC","sample":"1min"})
    path=cache/f"NYC_{year}_minute.csv"
    meta_path=path.with_suffix(".json")
    if path.exists() and meta_path.exists():
        raw=path.read_bytes(); meta=json.loads(meta_path.read_text())
        if hashlib.sha256(raw).hexdigest()!=meta["sha256"]:
            raise ValueError("Cached source hash mismatch.")
    else:
        started=datetime.now(timezone.utc).isoformat()
        with urllib.request.urlopen(url,timeout=90) as r:raw=r.read()
        meta={"url":url,"started_utc":started,"received_utc":datetime.now(timezone.utc).isoformat(),
              "sha256":hashlib.sha256(raw).hexdigest(),"latency":"~24 hours per provider; not real-time"}
        cache.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw);meta_path.write_text(json.dumps(meta,indent=2)+"\n")
    f=pd.read_csv(io.BytesIO(raw),comment="#").rename(columns={"valid(UTC)":"valid"})
    f["valid"]=pd.to_datetime(f.valid,utc=True)
    f["tmpf"]=pd.to_numeric(f.tmpf,errors="coerce")
    if not f.station.eq("NYC").all():raise ValueError("Wrong station.")
    f=f[f.tmpf.between(-40,130)].drop_duplicates("valid").sort_values("valid")
    f["date"]=f.valid.dt.tz_convert("Etc/GMT+5").dt.date
    rows=[]
    for day,g in f.groupby("date"):
        start=pd.Timestamp(day,tz="Etc/GMT+5").tz_convert("UTC")
        gaps=np.diff(np.r_[start.value,g.valid.astype("int64"), (start+pd.Timedelta(days=1)).value])/60e9
        rows.append({"date":str(day),"minute_max":g.tmpf.max(),"n_minutes":g.valid.nunique(),
                     "largest_gap_minutes":float(gaps.max()),"eligible":g.valid.nunique()>=1000 and gaps.max()<=60})
    return pd.DataFrame(rows),meta


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--years",nargs="+",type=int,default=[2025,2026])
    args=p.parse_args()
    frames=[];sources=[]
    for y in args.years:
        f,meta=download(y,ROOT/"data/research_weather")
        frames.append(f);sources.append(meta)
    f=pd.concat(frames,ignore_index=True)
    hourly=pd.read_csv(ROOT/"backtest_datasets/knyc_hourly_2019_2026.csv")
    hourly["date"]=pd.to_datetime(hourly.valid,utc=True).dt.tz_convert("Etc/GMT+5").dt.strftime("%Y-%m-%d")
    hourly["tmpf"]=pd.to_numeric(hourly.tmpf,errors="coerce")
    highs=hourly.groupby("date").tmpf.max().rename("hourly_max")
    labels=pd.read_csv(ROOT/"backtest_datasets/cli_research/knyc_cli_highs.csv")
    f=f.merge(highs,on="date",validate="one_to_one").merge(labels[["date","cli_high"]],on="date",validate="one_to_one")
    eligible=f[f.eligible].copy()
    if eligible.empty:raise ValueError("No days meet coverage requirements.")
    report={"kind":"retrospective measurement diagnostic, NOT tradable signal",
      "sources":sources,"matched_days":len(f),"eligible_days":len(eligible),
      "coverage_rule":"at least 1000 unique minutes and no gap including day edges over 60 minutes",
      "hourly_rounded_exact_match":float((np.floor(eligible.hourly_max+.5)==eligible.cli_high).mean()),
      "minute_rounded_exact_match":float((np.floor(eligible.minute_max+.5)==eligible.cli_high).mean()),
      "hourly_max_mae_f":float(abs(eligible.hourly_max-eligible.cli_high).mean()),
      "minute_max_mae_f":float(abs(eligible.minute_max-eligible.cli_high).mean()),
      "minute_minus_hourly_mean_f":float((eligible.minute_max-eligible.hourly_max).mean()),
      "limitations":["Archive arrives about 24h late; using it at same-day decision time would leak future availability.",
                      "One-minute service temperature quantization and missingness differ from METAR.",
                      "CLI current revisions, not exact Kalshi settlement versions.",
                      "Only matched covered dates; retrospective diagnostic, not model or P&L improvement."]}
    out=ROOT/"reports/automation_research";out.mkdir(parents=True,exist_ok=True)
    f.to_csv(out/"minute_daily_comparison.csv",index=False)
    (out/"minute_data_audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
