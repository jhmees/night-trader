"""Schema bounds + the extraction firewall's output gate (RT-5)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from nighttrader.agents.scenario import manual_scenario
from nighttrader.extraction.events import validate_event
from nighttrader.schemas import (
    Direction,
    Prediction,
    PriorSource,
    Scenario,
    ScenarioTrigger,
    TypedEvent,
)

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def test_typed_event_valid():
    e = TypedEvent(
        event_id="evt-1", ts=NOW, source_type="gdelt", event_type="rate_decision",
        actors=["Fed"], severity=7, tickers_affected=["XLF"],
        source_url="https://example.com", raw_ref="raw/a.txt",
    )
    assert e.severity == 7


def test_severity_bounds_enforced():
    with pytest.raises(ValidationError):
        TypedEvent(
            event_id="evt-2", ts=NOW, source_type="gdelt", event_type="other",
            severity=11, source_url="u", raw_ref="r",
        )


def test_naive_timestamp_rejected():
    with pytest.raises(ValidationError):
        Scenario(
            scenario_id="s", ts=datetime(2026, 7, 1, 12, 0), description="d",
            trigger=ScenarioTrigger.manual, horizon_days=5,
        )


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        Prediction(
            prediction_id="p", scenario_id="s", ts=NOW, agent="a", ticker="XLF",
            direction=Direction.up, confidence=1.2, horizon_days=5,
        )


def test_scenario_prior_consistency():
    with pytest.raises(ValueError):
        manual_scenario("Fed +25bp", horizon_days=10, affected_buckets=[1], prior_prob=0.34)
    s = manual_scenario(
        "Fed +25bp", horizon_days=10, affected_buckets=[1],
        prior_prob=0.34, prior_source=PriorSource.fedwatch,
    )
    assert s.prior_prob == 0.34


# --- firewall output gate on adversarial extractor outputs ---------------------

def _extractor_cases():
    cases = json.loads((FIXTURES / "injection_news.json").read_text())
    return [c for c in cases if "extractor_output" in c]


@pytest.mark.parametrize("case", _extractor_cases(), ids=lambda c: c["name"])
def test_firewall_gate_on_adversarial_extractor_output(case):
    out = case["extractor_output"]
    if case["name"] == "instruction_injection_in_headline":
        # structurally valid event: it validates, but the smuggled ticker is
        # off-universe — the guard is what stops it (tested in test_guard).
        e = validate_event(out)
        assert "MEMECO" in e.tickers_affected
    else:
        with pytest.raises(ValidationError):
            validate_event(out)
