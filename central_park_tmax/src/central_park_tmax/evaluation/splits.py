"""Rolling-origin / expanding-window splits (never a random split).

Each fold trains on all data with target date <= train_end and tests on [test_start, test_end].
Folds are strictly time-ordered and non-overlapping in their test windows. A small validation
tail is carved from the END of each training window for early stopping / blend weights, so
tuning never touches the test period.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator, Optional

import numpy as np
import pandas as pd


@dataclass
class Fold:
    index: int
    train_end: date
    test_start: date
    test_end: date

    def train_mask(self, dates: pd.Series) -> pd.Series:
        d = pd.to_datetime(dates)
        return d <= pd.Timestamp(self.train_end)

    def test_mask(self, dates: pd.Series) -> pd.Series:
        d = pd.to_datetime(dates)
        return (d >= pd.Timestamp(self.test_start)) & (d <= pd.Timestamp(self.test_end))


def folds_from_config(fold_cfgs) -> list[Fold]:
    folds = []
    for i, fc in enumerate(fold_cfgs):
        folds.append(Fold(
            index=i,
            train_end=date.fromisoformat(fc.train_end),
            test_start=date.fromisoformat(fc.test_start),
            test_end=date.fromisoformat(fc.test_end),
        ))
    _validate_non_overlap(folds)
    return folds


def _validate_non_overlap(folds: list[Fold]) -> None:
    for a, b in zip(folds, folds[1:]):
        if b.test_start <= a.test_end:
            raise ValueError(
                f"Fold test windows overlap: fold {a.index} ends {a.test_end}, "
                f"fold {b.index} starts {b.test_start}."
            )
        if a.train_end >= a.test_start:
            raise ValueError(
                f"Fold {a.index}: train_end {a.train_end} not before test_start {a.test_start}."
            )


def train_valid_split(train_df: pd.DataFrame, valid_fraction: float = 0.15,
                      date_col: str = "date") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carve a chronological validation tail from the training frame (no leakage)."""
    df = train_df.sort_values(date_col).reset_index(drop=True)
    n = len(df)
    if n < 10:
        return df, df.iloc[0:0]
    cut = int(n * (1 - valid_fraction))
    return df.iloc[:cut].reset_index(drop=True), df.iloc[cut:].reset_index(drop=True)


def auto_folds_from_span(dates: pd.Series, n_folds: int = 3,
                         min_train_fraction: float = 0.4) -> list[Fold]:
    """Derive rolling-origin folds from the dataset's own date span.

    Used when the configured folds don't intersect the data (e.g. a short real-data
    window). The first ``min_train_fraction`` of the span is always training; the
    remainder is split into ``n_folds`` consecutive test windows, each trained on
    everything strictly before it. Chronological, non-overlapping, leakage-safe.
    """
    d = pd.to_datetime(dates).sort_values().unique()
    if len(d) < 10:
        raise ValueError(f"Too few distinct dates ({len(d)}) to build folds.")
    start_idx = int(len(d) * min_train_fraction)
    test_dates = d[start_idx:]
    chunks = np.array_split(test_dates, n_folds)
    folds = []
    for i, chunk in enumerate(c for c in chunks if len(c)):
        test_start = pd.Timestamp(chunk[0]).date()
        test_end = pd.Timestamp(chunk[-1]).date()
        train_end = test_start - timedelta(days=1)
        folds.append(Fold(index=i, train_end=train_end,
                          test_start=test_start, test_end=test_end))
    _validate_non_overlap(folds)
    return folds


def rolling_origin_from_dates(dates: pd.Series, first_test_year: int,
                              last_test_year: int) -> list[Fold]:
    """Generate annual expanding-window folds from the data's date span."""
    folds = []
    for i, yr in enumerate(range(first_test_year, last_test_year + 1)):
        folds.append(Fold(
            index=i,
            train_end=date(yr - 1, 12, 31),
            test_start=date(yr, 1, 1),
            test_end=date(yr, 12, 31),
        ))
    _validate_non_overlap(folds)
    return folds
