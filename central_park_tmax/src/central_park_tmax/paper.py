"""Persistent, fully funded PAPER orders. This module has no exchange order client.

One pending/open/settled entry per ticker in each independent paper portfolio.
Signals are frozen before later snapshots can fill them. Fees/slippage are explicit
scenario charges, not verified exchange fees or evidence of real fillability.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from .evaluation.execution_research import utc, depth_quote, levels, first_snapshot_after


def units(value):
    d=Decimal(str(value))
    if not d.is_finite() or d<0:raise ValueError("Nonnegative finite money required.")
    return int((d*1_000_000).to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True)
class PaperConfig:
    mode: str="paper"
    strategy: str="blend_robust"
    initial_cash: str="1000"
    max_open_risk: str="50"
    max_event_risk: str="10"
    max_daily_spend: str="20"
    max_daily_realized_loss: str="10"
    max_orders_per_day: int=20
    quantity: int=1
    fee_per_contract: str="0.02"
    slippage_per_contract: str="0.01"
    min_edge: float=.03
    uncertainty_haircut: float=.03
    weather_weight: float=.10
    max_spread: float=.08
    max_book_age_seconds: int=15
    latency_seconds: int=2
    intent_ttl_seconds: int=180

    def __post_init__(self):
        if self.mode!="paper":raise ValueError("Only paper mode is implemented.")
        if self.strategy not in ("report_flat","blend_flat","blend_guarded","blend_robust"):
            raise ValueError("Unknown strategy.")
        for name in ("initial_cash","max_open_risk","max_event_risk","max_daily_spend","max_daily_realized_loss",
                     "fee_per_contract","slippage_per_contract"):
            units(getattr(self,name))
        for name in ("quantity","max_orders_per_day","max_book_age_seconds","latency_seconds","intent_ttl_seconds"):
            value=getattr(self,name)
            if not isinstance(value,int) or isinstance(value,bool) or value<1:raise ValueError("Positive integer limits required.")
        for name in ("min_edge","uncertainty_haircut","weather_weight","max_spread"):
            v=getattr(self,name)
            if not math.isfinite(v) or not 0<=v<=1:raise ValueError("Invalid probability/edge limit.")
        if self.intent_ttl_seconds<=self.latency_seconds:raise ValueError("TTL must exceed latency.")


def choose_signal(config, weather_p, market_p, payload, *, quality_ok, disagreement=0.):
    if not all(math.isfinite(v) and 0<=v<=1 for v in (weather_p,market_p,disagreement)):
        raise ValueError("Invalid probabilities.")
    if config.strategy in ("blend_guarded","blend_robust") and not quality_ok:
        return None,"quality_gate"
    yes,no=levels(payload,"yes"),levels(payload,"no")
    if not yes or not no:return None,"missing_side"
    spread=float(1-no[0][0]-yes[0][0])
    if spread<0 or spread>config.max_spread:return None,"spread_gate"
    p=weather_p if config.strategy=="report_flat" else market_p+config.weather_weight*(weather_p-market_p)
    haircut=max(config.uncertainty_haircut,disagreement*config.weather_weight) if config.strategy=="blend_robust" else 0.
    fee=float(config.fee_per_contract)+float(config.slippage_per_contract)
    choices=[]
    for side,prob in (("yes",p),("no",1-p)):
        quote=depth_quote(payload,side,config.quantity)
        if not quote["fully_fillable"]:continue
        limit=prob-haircut-config.min_edge-fee
        worst=max(float(level["price"]) for level in quote["levels"])
        if limit>=worst and limit>0:
            choices.append((prob-float(quote["vwap"])-fee-haircut,side,limit))
    if not choices:return None,"no_net_edge"
    edge,side,limit=max(choices)
    return {"side":side,"limit_price":str(min(limit,1)),"probability_yes":p,"net_edge":edge},"candidate"


class PaperLedger:
    def __init__(self,path,config):
        self.config=config
        if str(path)!=":memory:":Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(path),timeout=20,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders (
          id TEXT PRIMARY KEY, ticker TEXT NOT NULL, event TEXT NOT NULL, side TEXT NOT NULL,
          quantity INTEGER NOT NULL, limit_price TEXT NOT NULL, reserve INTEGER NOT NULL,
          state TEXT NOT NULL, created TEXT NOT NULL, expires TEXT NOT NULL,
          cost INTEGER DEFAULT 0, payout INTEGER DEFAULT 0, filled TEXT, settled TEXT,
          result TEXT, metadata TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS journal (seq INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
        """)
        encoded=json.dumps(asdict(config),sort_keys=True)
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO settings VALUES ('config',?)",(encoded,))
            if self.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0]!=encoded:
                raise ValueError("Configuration changed: use a new independent paper database.")

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:yield;self.db.execute("COMMIT")
        except BaseException:self.db.execute("ROLLBACK");raise

    def log(self,now,kind,payload):
        self.db.execute("INSERT INTO journal(timestamp,kind,payload) VALUES (?,?,?)",
                        (utc(now).isoformat(),kind,json.dumps(payload,sort_keys=True)))

    def _risk_reason(self,reserve,event,now):
        rows=[dict(r) for r in self.db.execute("SELECT * FROM orders")]
        day=utc(now).date().isoformat()
        cash=units(self.config.initial_cash)+sum(r["payout"]-r["cost"] for r in rows)
        pending=sum(r["reserve"] for r in rows if r["state"]=="pending")
        open_risk=sum(r["cost"] for r in rows if r["state"]=="open")
        event_risk=sum(r["reserve"] if r["state"]=="pending" else r["cost"] for r in rows if r["event"]==event and r["state"] in ("pending","open"))
        spent=sum(r["cost"] for r in rows if (r["filled"] or "").startswith(day))
        realized=sum(r["payout"]-r["cost"] for r in rows if (r["settled"] or "").startswith(day))
        count=sum(r["created"].startswith(day) for r in rows)
        if cash-pending<reserve:return "cash_limit"
        if open_risk+pending+reserve>units(self.config.max_open_risk):return "open_risk_limit"
        if event_risk+reserve>units(self.config.max_event_risk):return "event_risk_limit"
        if spent+pending+reserve>units(self.config.max_daily_spend):return "daily_spend_limit"
        if realized<=-units(self.config.max_daily_realized_loss):return "daily_loss_limit"
        if count>=self.config.max_orders_per_day:return "order_count_limit"
        return None

    def submit(self,signal_id,ticker,event,side,limit_price,now,metadata):
        now=utc(now)
        if side not in ("yes","no") or not ticker or not event:raise ValueError("Invalid order identity.")
        if not 0<Decimal(str(limit_price))<=1:raise ValueError("Invalid price limit.")
        q=self.config.quantity
        reserve=units(q*(Decimal(str(limit_price))+Decimal(self.config.fee_per_contract)+Decimal(self.config.slippage_per_contract)))
        with self.transaction():
            if self.db.execute("SELECT 1 FROM orders WHERE id=?",(signal_id,)).fetchone():return "duplicate_signal"
            if self.db.execute("SELECT 1 FROM orders WHERE ticker=? AND state IN ('pending','open','settled')",(ticker,)).fetchone():return "ticker_already_entered"
            reason=self._risk_reason(reserve,event,now)
            if reason:self.log(now,"rejected",{"id":signal_id,"reason":reason});return reason
            self.db.execute("INSERT INTO orders(id,ticker,event,side,quantity,limit_price,reserve,state,created,expires,metadata) VALUES (?,?,?,?,?,?,?,'pending',?,?,?)",
                (signal_id,ticker,event,side,q,str(limit_price),reserve,now.isoformat(),
                 (now+timedelta(seconds=self.config.intent_ttl_seconds)).isoformat(),json.dumps(metadata,sort_keys=True)))
            self.log(now,"paper_intent",{"id":signal_id,"ticker":ticker})
            return "pending"

    def advance(self,records,now,*,halted=False):
        now=utc(now)
        with self.transaction():
            pending=list(self.db.execute("SELECT * FROM orders WHERE state='pending' ORDER BY created,id"))
            used=set()
            for row in pending:
                loss=self.db.execute("SELECT COALESCE(SUM(payout-cost),0) FROM orders WHERE substr(settled,1,10)=?",(now.date().isoformat(),)).fetchone()[0]
                if halted or loss<=-units(self.config.max_daily_realized_loss):state="cancelled"
                elif now>utc(row["expires"]):state="expired"
                else:state=None
                if state:
                    self.db.execute("UPDATE orders SET state=? WHERE id=?",(state,row["id"]))
                    self.log(now,state,{"id":row["id"]});continue
                eligible=utc(row["created"])+timedelta(seconds=self.config.latency_seconds)
                usable=[r for r in records if utc(r["received_utc"])<=now and
                        0<=(now-utc(r["received_utc"])).total_seconds()<=self.config.max_book_age_seconds]
                record=first_snapshot_after(usable,row["ticker"],eligible,max_wait_seconds=self.config.intent_ttl_seconds-self.config.latency_seconds)
                if record is None or row["ticker"] in used:continue
                quote=depth_quote(record["payload"],row["side"],row["quantity"])
                if not quote["fully_fillable"]:continue
                if max(Decimal(v["price"]) for v in quote["levels"])>Decimal(row["limit_price"]):continue
                cost=units(Decimal(quote["gross_dollars"])+row["quantity"]*(Decimal(self.config.fee_per_contract)+Decimal(self.config.slippage_per_contract)))
                if cost>row["reserve"]:raise RuntimeError("Fill exceeded reserved cash.")
                # Re-check fill-day spend when a pending order crosses UTC midnight.
                spent=self.db.execute("SELECT COALESCE(SUM(cost),0) FROM orders WHERE substr(filled,1,10)=?",(now.date().isoformat(),)).fetchone()[0]
                if spent+cost>units(self.config.max_daily_spend):continue
                self.db.execute("UPDATE orders SET state='open',cost=?,filled=? WHERE id=?",(cost,now.isoformat(),row["id"]))
                self.log(now,"hypothetical_fill",{"id":row["id"],"book_received":record["received_utc"],"quote":quote})
                used.add(row["ticker"])

    def settle(self,ticker,result,now,source):
        if result not in ("yes","no") or not source:raise ValueError("Verified binary result and source required.")
        now=utc(now)
        with self.transaction():
            rows=list(self.db.execute("SELECT * FROM orders WHERE ticker=? AND state IN ('open','settled')",(ticker,)))
            for r in rows:
                if r["state"]=="settled":
                    if r["result"]!=result:raise ValueError("Conflicting settlement: reconcile explicitly.")
                    continue
                if now<utc(r["filled"]):raise ValueError("Settlement precedes fill.")
                payout=1_000_000*r["quantity"] if r["side"]==result else 0
                self.db.execute("UPDATE orders SET state='settled',payout=?,settled=?,result=? WHERE id=?",(payout,now.isoformat(),result,r["id"]))
                self.log(now,"paper_settlement",{"id":r["id"],"source":source,"result":result})

    def summary(self):
        rows=[dict(r) for r in self.db.execute("SELECT * FROM orders")]
        return {"mode":"paper","strategy":self.config.strategy,"orders":len(rows),
            "states":{s:sum(r["state"]==s for r in rows) for s in ("pending","open","settled","expired","cancelled")},
            "cash":(units(self.config.initial_cash)+sum(r["payout"]-r["cost"] for r in rows))/1e6,
            "reserved_cash":sum(r["reserve"] for r in rows if r["state"]=="pending")/1e6,
            "open_cost":sum(r["cost"] for r in rows if r["state"]=="open")/1e6,
            "realized_pnl":sum(r["payout"]-r["cost"] for r in rows if r["state"]=="settled")/1e6}


def signal_id(model_id,cutoff,ticker,strategy):
    return hashlib.sha256(f"{model_id}|{cutoff}|{ticker}|{strategy}".encode()).hexdigest()
