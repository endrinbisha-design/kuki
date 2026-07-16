"""Matplotlib plots for backtests and forecasts (headless 'Agg' backend)."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_backtest_mae(per_vintage: dict, out_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 5))
    for vintage, res in per_vintage.items():
        cont = res.get("continuous", {})
        models = list(cont.keys())
        maes = [cont[m]["mae"] for m in models]
        ax.plot(models, maes, marker="o", label=vintage)
    ax.set_ylabel("MAE (°F)")
    ax.set_xlabel("model")
    ax.set_title("Backtest MAE by model and forecast vintage")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


def plot_integer_distribution(pmf: Mapping[str, float], out_path: Path, title: str = "") -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    keys = sorted(int(k) for k in pmf.keys())
    vals = [pmf[str(k)] for k in keys]
    ax.bar(keys, vals, color="#3a7ca5")
    ax.set_xlabel("reported integer max (°F)")
    ax.set_ylabel("probability")
    ax.set_title(title or "Integer report-value distribution")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


def plot_reliability(bins: list[dict], out_path: Path, title: str = "Reliability") -> Path:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="perfect")
    if bins:
        xs = [b["mean_predicted"] for b in bins]
        ys = [b["observed_frequency"] for b in bins]
        ax.plot(xs, ys, marker="o", label="model")
    ax.set_xlabel("predicted probability")
    ax.set_ylabel("observed frequency")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path
