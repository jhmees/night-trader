"""Calibration scoring (RT-2c, RT-7a): do 70%-confidence claims come true
~70% of the time? Measurable within months — unlike returns, which are
statistically underpowered for years at this cadence.
"""

from __future__ import annotations

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
    """Hit rate per confidence bin. Perfect calibration: hit_rate ≈ bin mid."""
    resolved = df[df["resolved"] == True].copy()  # noqa: E712
    if resolved.empty:
        return pd.DataFrame(columns=["bin", "n", "mean_confidence", "hit_rate"])
    resolved["hit"] = (resolved["direction"] == resolved["outcome"]).astype(float)
    resolved["bin"] = pd.cut(resolved["confidence"], bins=n_bins, labels=False)
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
    bs = brier_score(df)
    if bs is not None:
        lines.append(f"brier score: {bs:.4f} (0=oracle, 0.25=coin-flip-at-50%)")
    if n_res < MIN_RESOLVED_FOR_SIGNAL:
        lines.append(
            f"NOTE: only {n_res} resolved (<{MIN_RESOLVED_FOR_SIGNAL}) — "
            "calibration numbers below are statistically meaningless, shown for plumbing only"
        )
    tbl = reliability_table(df)
    if not tbl.empty:
        lines.append(tbl.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    return "\n".join(lines)
