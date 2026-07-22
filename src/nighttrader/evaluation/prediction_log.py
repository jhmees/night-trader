"""Prediction log — the forward evaluation methodology (RT-4/RT-7).

Every directional claim any agent makes becomes a Prediction row, written in
the same run that produced it (write-ahead: log before any order). Resolution
happens later, mechanically, from realized prices — never by asking an LLM
whether it was right.
"""

from __future__ import annotations

import uuid

import pandas as pd

from nighttrader.memory import store
from nighttrader.schemas import Direction, Prediction

CATEGORY = "predictions"

# A move smaller than this (abs %) over the horizon resolves as "flat".
FLAT_BAND_PCT = 0.75


def new_prediction_id() -> str:
    return f"pred-{uuid.uuid4().hex[:12]}"


def log_predictions(predictions: list[Prediction], run_id: str, **store_kw) -> None:
    store.write_rows(predictions, CATEGORY, run_id, **store_kw)


def realized_direction(move_pct: float, flat_band_pct: float = FLAT_BAND_PCT) -> Direction:
    if move_pct > flat_band_pct:
        return Direction.up
    if move_pct < -flat_band_pct:
        return Direction.down
    return Direction.flat


def resolve(prediction: Prediction, realized_move_pct: float) -> Prediction:
    """Resolve one prediction against the realized move over its horizon.

    Brier contribution treats the claim as a binary event "my direction
    happens" at the stated confidence: (confidence - hit)^2. Lower is better;
    always-50% scores 0.25.
    """
    outcome = realized_direction(realized_move_pct)
    hit = 1.0 if outcome == prediction.direction else 0.0
    return prediction.model_copy(
        update={
            "resolved": True,
            "outcome": outcome,
            "brier_contribution": (prediction.confidence - hit) ** 2,
        }
    )


def load_all(**store_kw) -> pd.DataFrame:
    return store.read_category(CATEGORY, **store_kw)
