from central_park_tmax.data.ghcn_daily import GhcnDailyLoader
from central_park_tmax.data.storage import HttpClient

WIDE_CSV = """\
"STATION","DATE","TMAX","TMAX_ATTRIBUTES","TMIN","TMIN_ATTRIBUTES","PRCP","PRCP_ATTRIBUTES"
"USW00094728","2024-07-15","356",",,W","228",",,W","0",",,W"
"USW00094728","2024-07-16","333",",,W","217",",,W","25",",,W"
"""

LONG_CSV = """\
ID,DATE,ELEMENT,DATA_VALUE,M_FLAG,Q_FLAG,S_FLAG,OBS_TIME
USW00094728,20240715,TMAX,356,,,W,2400
USW00094728,20240715,TMIN,228,,,W,2400
USW00094728,20240715,PRCP,0,,,W,2400
USW00094728,20240716,TMAX,333,,,W,2400
USW00094716,20240716,SNOW,0,,,W,2400
"""


def _loader():
    return GhcnDailyLoader(http=HttpClient(cache_enabled=False))


def test_wide_parser_tenths_conversion():
    df = _loader().load(csv_text=WIDE_CSV, csv_format="wide")
    row = df[df["date"].astype(str) == "2024-07-15"].iloc[0]
    assert abs(row["tmax_c"] - 35.6) < 1e-9
    assert abs(row["tmax_f"] - 96.08) < 1e-6
    assert abs(row["prcp_mm"] - 0.0) < 1e-9
    assert row["provenance"] == "ghcn_daily_final"


def test_long_parser_matches_wide():
    wide = _loader().load(csv_text=WIDE_CSV, csv_format="wide")
    long = _loader().load(csv_text=LONG_CSV, csv_format="long")
    w = wide[wide["date"].astype(str) == "2024-07-15"].iloc[0]
    l = long[long["date"].astype(str) == "2024-07-15"].iloc[0]
    assert abs(w["tmax_f"] - l["tmax_f"]) < 1e-9
    assert abs(w["tmin_c"] - l["tmin_c"]) < 1e-9


def test_format_sniffing():
    df = _loader().load(csv_text=LONG_CSV)  # no format hint -> sniffed as long
    assert len(df) == 2
    assert "tmax_f" in df.columns


def test_long_parser_keeps_flags():
    df = _loader().load(csv_text=LONG_CSV, csv_format="long")
    row = df[df["date"].astype(str) == "2024-07-15"].iloc[0]
    assert row["tmax_sflag"] == "W"
