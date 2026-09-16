"""Depth-aware quote diagnostics. No orders, fill guarantees, or portfolio simulation.

Requires modern fixed-point books; never guess whether integer prices mean cents.
Fees are an explicit scenario budget, NOT an implementation of exchange fee rules.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal


def utc(value):
    value = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamps required.")
    return value.astimezone(timezone.utc)


def nonnegative(value):
    d = Decimal(str(value))
    if not d.is_finite() or d < 0:
        raise ValueError("Finite nonnegative decimal required.")
    return d


def levels(payload, side):
    if side not in ("yes", "no"):
        raise ValueError("side must be yes or no.")
    book = payload["orderbook_fp"]
    result = []
    seen = set()
    for price, size in book[side + "_dollars"] or []:
        p, q = nonnegative(price), nonnegative(size)
        if p > 1 or p in seen:
            raise ValueError("Out-of-range or duplicate price level.")
        seen.add(p)
        if q:
            result.append((p, q))
    return sorted(result, reverse=True)


def validate_book(payload):
    yes, no = levels(payload,"yes"), levels(payload,"no")
    if yes and no and yes[0][0] + no[0][0] > 1:
        raise ValueError("Crossed binary book; reject inconsistent snapshot.")


def depth_quote(payload, side, quantity, *, action="buy"):
    validate_book(payload)
    if side not in ("yes", "no") or action not in ("buy", "sell"):
        raise ValueError("Invalid side/action.")
    requested = nonnegative(quantity)
    if not requested:
        raise ValueError("Positive quantity required.")
    opposite = "no" if side == "yes" else "yes"
    ladder = [(1-p,q) for p,q in levels(payload,opposite)] if action == "buy" else levels(payload,side)
    remaining, total = requested, Decimal(0)
    fills = []
    for price, available in ladder:
        size = min(remaining, available)
        if not size:
            break
        total += price * size
        remaining -= size
        fills.append({"price": str(price), "quantity": str(size)})
    filled = requested - remaining
    return {"requested": str(requested), "available_fill": str(filled),
            "fully_fillable": remaining == 0, "gross_dollars": str(total),
            "vwap": str(total/filled) if filled else None, "levels": fills}


def first_snapshot_after(records, ticker, when, *, max_wait_seconds=5, max_request_seconds=2):
    # The REQUEST must start after the desired event/latency boundary. A response
    # received afterwards can otherwise contain a pre-boundary server snapshot.
    when = utc(when)
    if max_wait_seconds < 0 or max_request_seconds < 0:
        raise ValueError("Nonnegative timing limits required.")
    candidates = []
    for row in records:
        if row.get("ticker") != ticker or row.get("error"):
            continue
        start, receipt = utc(row["request_started_utc"]), utc(row["received_utc"])
        if receipt < start:
            raise ValueError("Receipt precedes request.")
        if start < when or receipt > when + timedelta(seconds=max_wait_seconds):
            continue
        if (receipt-start).total_seconds() > max_request_seconds:
            continue
        validate_book(row["payload"])
        candidates.append(row)
    return min(candidates,key=lambda r: utc(r["received_utc"])) if candidates else None


def event_markout(signal, records, *, latency_seconds, horizon_seconds, fee_budget_per_contract,
                  max_wait_seconds=5):
    """Frozen signal -> first eligible entry book -> future exit book.

    Fee budget covers the ROUND TRIP. Positive output remains a hypothetical
    quote markout; cancellation, fills, repeated depth use and cash are unmodeled.
    """
    if latency_seconds < 0 or horizon_seconds <= 0:
        raise ValueError("Invalid latency or holding horizon.")
    fee = nonnegative(fee_budget_per_contract)
    quantity = nonnegative(signal["quantity"])
    if quantity == 0 or signal["side"] not in ("yes", "no"):
        raise ValueError("Positive quantity and yes/no side required.")
    boundary = utc(signal["signal_received_utc"]) + timedelta(seconds=latency_seconds)
    entry = first_snapshot_after(records, signal["ticker"], boundary, max_wait_seconds=max_wait_seconds)
    if entry is None:
        return {"status": "missing_entry_book"}
    buy = depth_quote(entry["payload"], signal["side"], quantity)
    if not buy["fully_fillable"]:
        return {"status": "insufficient_entry_depth", "entry": buy}
    # Anchor horizon to actual entry receipt, not the earlier signal timestamp.
    exit_boundary = utc(entry["received_utc"]) + timedelta(seconds=horizon_seconds)
    later = first_snapshot_after(records, signal["ticker"], exit_boundary, max_wait_seconds=max_wait_seconds)
    if later is None:
        return {"status": "missing_exit_book", "entry": buy}
    sell = depth_quote(later["payload"], signal["side"], quantity, action="sell")
    if not sell["fully_fillable"]:
        return {"status": "insufficient_exit_depth", "entry": buy, "exit": sell}
    gross = Decimal(sell["gross_dollars"]) - Decimal(buy["gross_dollars"])
    return {"status": "quote_markout_only", "entry": buy, "exit": sell,
            "entry_received_utc": entry["received_utc"], "exit_received_utc": later["received_utc"],
            "gross_markout_dollars": str(gross), "round_trip_fee_budget_dollars": str(quantity*fee),
            "markout_after_fee_budget_dollars": str(gross-quantity*fee)}
