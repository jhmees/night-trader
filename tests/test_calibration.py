"""Brier math and reliability binning (RT-7)."""

import uuid
from datetime import UTC, datetime

import pandas as pd
import pytest

from nighttrader.evaluation import calibration, prediction_log
from nighttrader.schemas import Direction, Prediction

NOW = datetime(2026, 7, 1, tzinfo=UTC)


def make_pred(direction=Direction.up, confidence=0.7) -> Prediction:
    return Prediction(
        prediction_id=f"p-{uuid.uuid4().hex[:8]}", scenario_id="s", ts=NOW,
        agent="tech", ticker="XLF", direction=direction, confidence=confidence,
        horizon_days=5,
    )


def test_resolution_direction_bands():
    assert prediction_log.realized_direction(2.0) is Direction.up
    assert prediction_log.realized_direction(-2.0) is Direction.down
    assert prediction_log.realized_direction(0.3) is Direction.flat


def test_brier_hit_and_miss():
    hit = prediction_log.resolve(make_pred(Direction.up, 0.7), realized_move_pct=3.0)
    assert hit.brier_contribution == pytest.approx((0.7 - 1.0) ** 2)
    miss = prediction_log.resolve(make_pred(Direction.up, 0.7), realized_move_pct=-3.0)
    assert miss.brier_contribution == pytest.approx((0.7 - 0.0) ** 2)
    assert hit.resolved and miss.resolved


def _frame(preds):
    return pd.DataFrame([p.model_dump(mode="json") for p in preds])


def test_brier_score_and_report():
    preds = [
        prediction_log.resolve(make_pred(Direction.up, 0.8), 3.0),   # hit
        prediction_log.resolve(make_pred(Direction.up, 0.8), -3.0),  # miss
    ]
    df = _frame(preds)
    bs = calibration.brier_score(df)
    assert bs == pytest.approx(((0.8 - 1) ** 2 + (0.8 - 0) ** 2) / 2)
    text = calibration.report(df)
    assert "statistically meaningless" in text  # small-N honesty (RT-7)


def test_reliability_table_perfect_calibration():
    # 10 preds at 100% confidence, all hits -> hit_rate 1.0 in top bin
    preds = [prediction_log.resolve(make_pred(Direction.up, 1.0), 5.0) for _ in range(10)]
    tbl = calibration.reliability_table(_frame(preds))
    assert tbl["hit_rate"].iloc[-1] == pytest.approx(1.0)


def test_brier_none_when_nothing_resolved():
    df = _frame([make_pred()])
    assert calibration.brier_score(df) is None
