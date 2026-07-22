"""Calibration scoring (RT-2c, RT-7a): do 70%-confidence claims come true
~70% of the time? Measurable within months — unlike returns, which are
statistically underpowered for years at this cadence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Below this many resolved predictions, any calibration read is noise; the
# report says so instead of printing a misleading number.
MIN_RESOLVED_FOR_SIGNAL = 30


def brier_score(df: pd.DataFrame) -> float | None:
    """Mean Brier contribution over resolved predictions. None if empty."""
    resolved = df[df["resolved"] == True]  # noqa: E712 - parquet bools
    if resolved.empty:
        return None
    return float(resolved["brier_contribution"].mean())


def reliability_table(df: pd.DataFrame, n_bins: int = 5) -> pd.DataFrame:
    """Hit rate per confidence bin. Perfect calibration: hit_rate ≈ mean
    confidence of the bin.

    Bins are fixed over [0, 1] — not fitted to the observed range — so tables
    from different months are directly comparable.
    """
    resolved = df[df["resolved"] == True].copy()  # noqa: E712
    if resolved.empty:
        return pd.DataFrame(columns=["bin", "n", "mean_confidence", "hit_rate"])
    resolved["hit"] = (resolved["direction"] == resolved["outcome"]).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    resolved["bin"] = pd.cut(
        resolved["confidence"], bins=edges, labels=False, include_lowest=True
    )
    grouped = (
        resolved.groupby("bin")
        .agg(n=("hit", "size"), mean_confidence=("confidence", "mean"), hit_rate=("hit", "mean"))
        .reset_index()
    )
    return grouped


def report(df: pd.DataFrame) -> str:
    """Human-readable monthly calibration report (RT-2 guardrail c)."""
    n_total = len(df)
    resolved = df[df["resolved"] == True]  # noqa: E712
    n_res = len(resolved)
    lines = [f"predictions: {n_total} logged, {n_res} resolved"]
    if n_res < MIN_RESOLVED_FOR_SIGNAL:
        # Refuse, don't caveat: sub-threshold numbers get quoted anyway.
        lines.append(
            f"only {n_res} resolved (<{MIN_RESOLVED_FOR_SIGNAL}) — calibration numbers "
            "are statistically meaningless at this sample size and are withheld"
        )
        return "\n".join(lines)
    bs = brier_score(df)
    if bs is not None:
        lines.append(f"brier score: {bs:.4f} (0=oracle, 0.25=coin-flip-at-50%)")
    tbl = reliability_table(df)
    if not tbl.empty:
        lines.append(tbl.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    return "\n".join(lines)
