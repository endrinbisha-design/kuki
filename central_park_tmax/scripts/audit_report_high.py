#!/usr/bin/env python3
"""Annual chronological validation against archived CLI highs, NOT verified payouts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from central_park_tmax.models.conditional_report import ConditionalReportHigh, REPORT_SUPPORT, rounded
from audit_conditional_rise import build_snapshots
from audit_probability_models import validate_archive


def build_frame(raw, labels):
    labels = labels.copy()
    labels["date"] = pd.to_datetime(labels.date)
    labels["product_issued_utc"] = pd.to_datetime(labels.product_issued_utc, utc=True)
    if labels.date.isna().any() or labels.duplicated("date").any():
        raise ValueError("Unique CLI report dates required.")
    if not labels.station.eq("KNYC").all():
        raise ValueError("This experiment is NYC-only.")
    f = build_snapshots(raw, standard_day=True).merge(labels, on="date", validate="many_to_one")
    # Preserve signed gaps: deleting low/revised reports would bias the target.
    f["sampled_final"] = f.observed_max + f.remaining_rise
    f["report_minus_sampled"] = f.cli_high - f.sampled_final
    return f


def summary(frame):
    cols = [c for c in frame if c.endswith(("_rps", "_mae", "_log_loss"))]
    return frame.groupby("date")[cols].mean().mean().to_dict()


def compare_archived_outcomes(labels, archive):
    a = validate_archive(archive)
    a = a[a.series.eq("KXHIGHNY")].drop_duplicates(["date", "bucket"])
    labels = labels.copy()
    labels["date"] = pd.to_datetime(labels.date)
    matched = a.merge(labels, on="date", validate="many_to_one")
    bounds = matched.bucket.str.extract(r"^(-?\d+)-(-?\d+)$").astype(float)
    if bounds.isna().any().any():
        raise ValueError("This check supports only archived inclusive between buckets.")
    implied = matched.cli_high.between(bounds[0], bounds[1]).astype(int)
    return {"dates": matched.date.nunique(), "binary_contracts": len(matched),
            "unmatched_contracts": len(a)-len(matched), "mismatches": int((implied != matched.won).sum()),
            "scope": "Archived partial between-contract outcomes; not fresh exchange verification or full boards."}


def evaluate(frame):
    outputs, folds = [], []
    for year in sorted(frame.date.dt.year.unique()):
        cutoff = pd.Timestamp(f"{year}-01-01", tz="UTC")
        train = frame[(frame.date.dt.year < year) & (frame.product_issued_utc < cutoff)]
        test = frame[frame.date.dt.year == year].copy()
        if train.date.nunique() < 200 or test.date.nunique() < 30:
            continue
        model = ConditionalReportHigh().fit(train)
        # Snapshot-only baseline isolates the cost of ignoring the report gap.
        snapshot_model = ConditionalReportHigh().fit(train.assign(cli_high=rounded(train.sampled_final)))
        outcomes = (test.cli_high.to_numpy()[:, None] <= REPORT_SUPPORT)
        for name, fitted, cond in (("snapshot_only", snapshot_model, True),
                                   ("report_hour_only", model, False), ("report_conditional", model, True)):
            pmf = fitted.predict_pmf(test, conditional=cond)
            cdf = pmf.cumsum(axis=1)
            test[name + "_rps"] = ((cdf - outcomes)**2).sum(axis=1)
            median = REPORT_SUPPORT[(cdf >= .5).argmax(axis=1)]
            test[name + "_mae"] = abs(median - test.cli_high.to_numpy())
            ix = test.cli_high.to_numpy(dtype=int) - REPORT_SUPPORT[0]
            if ((ix < 0) | (ix >= len(REPORT_SUPPORT))).any():
                raise ValueError("Target outside report support.")
            test[name + "_log_loss"] = -np.log(np.maximum(pmf[np.arange(len(test)), ix], 1e-6))
        test["train_end"] = train.date.max()
        test["latest_training_product_utc"] = train.product_issued_utc.max()
        outputs.append(test)
        folds.append({"year": int(year), "train_days": train.date.nunique(),
                      "test_days": test.date.nunique(), "scores": summary(test)})
    if not outputs:
        raise ValueError("Insufficient data for annual evaluation.")
    return pd.concat(outputs, ignore_index=True), folds


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hourly", type=Path, default=ROOT / "backtest_datasets/knyc_hourly_2019_2026.csv")
    p.add_argument("--labels", type=Path, default=ROOT / "backtest_datasets/cli_research/knyc_cli_highs.csv")
    p.add_argument("--output-dir", type=Path, default=ROOT / "reports/model_followup")
    args = p.parse_args()
    labels = pd.read_csv(args.labels)
    frame = build_frame(pd.read_csv(args.hourly), labels)
    pred, folds = evaluate(frame)
    daily = pred.assign(delta=pred.report_conditional_rps - pred.report_hour_only_rps).groupby("date").delta.mean()
    rng = np.random.default_rng(20260916)
    draws = []
    for _ in range(2000):
        sampled = []
        for _, g in daily.groupby(daily.index.year):
            v = g.to_numpy()
            ix = ((rng.integers(0, len(v), int(np.ceil(len(v)/7)))[:, None] + np.arange(7)) % len(v)).ravel()[:len(v)]
            sampled.extend(v[ix])
        draws.append(np.mean(sampled))
    day_rows = pred.drop_duplicates("date")
    report = {"target": "current-revision archived NWS CLI high; not verified Kalshi settlement",
              "day_basis": "fixed EST (UTC-5), decisions at 13:00-18:00 America/New_York",
              "n_days": pred.date.nunique(), "n_snapshots": len(pred), "scores": summary(pred), "folds": folds,
              "rounded_snapshot_disagreement_rate": float((rounded(day_rows.sampled_final) != day_rows.cli_high).mean()),
              "archived_outcome_check": compare_archived_outcomes(labels, pd.read_csv(ROOT / "backtest_datasets/real_price_backtest_trades.csv")),
              "report_minus_sampled_mean_f": float(day_rows.report_minus_sampled.mean()),
              "paired_conditional_minus_hour_rps": {"mean": float(daily.mean()), "ci95": np.quantile(draws,[.025,.975]).tolist(),
                                                     "bootstrap": "7 observed days within each year; descriptive"},
              "inputs": {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (args.hourly,args.labels)},
              "limitations": ["IEM current revisions, not exact reports used by Kalshi; product issue time is not receipt time.",
                              "Observation timestamps assumed available; missing coverage filter may bias sample.",
                              "Research data previously inspected; no prospective untouched holdout.",
                              "PMF log loss clips zero mass at 1e-6 for scoring; distribution tails need further validation.",
                              "No orderbook/fill/P&L evaluation or automatic live promotion."]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Report provenance is joined by date from the separately committed label table.
    pred.drop(columns=["source_url", "retrieved_utc", "station"]).to_csv(
        args.output_dir / "report_high_predictions.csv", index=False, float_format="%.10g")
    (args.output_dir / "report_high_audit.json").write_text(json.dumps(report,indent=2) + "\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
