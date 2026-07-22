"""Core inter-agent payload schemas (design §11.3).

Every payload that crosses a module boundary is a pydantic model — free text
never flows from data sources into agents (RT-5) and every row is
parquet-serializable for the audit trail.

All timestamps are timezone-aware UTC. SCHEMA_VERSION is stamped on every
row so stored parquet can be migrated when these models evolve.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(UTC)


class _Row(BaseModel):
    """Base for stored rows: strict, UTC-stamped, versioned."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    ts: datetime = Field(default_factory=utcnow)

    @field_validator("ts")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v.astimezone(UTC)


class SourceType(enum.StrEnum):
    gdelt = "gdelt"
    edgar = "edgar"
    nhc = "nhc"
    news_api = "news_api"


class EventType(enum.StrEnum):
    rate_decision = "rate_decision"
    geopolitical_conflict = "geopolitical_conflict"
    nat_disaster = "nat_disaster"
    filing_8k = "filing_8k"
    earnings = "earnings"
    other = "other"


class TypedEvent(_Row):
    """Output of the extraction firewall — the ONLY thing agents see from news.

    ``raw_ref`` points at archived raw text for human audit; the raw text
    itself never enters agent context (RT-5).
    """

    event_id: str
    source_type: SourceType
    event_type: EventType
    actors: list[str] = Field(default_factory=list)
    direction: str | None = None
    severity: int = Field(ge=1, le=10)
    tickers_affected: list[str] = Field(default_factory=list)
    source_url: str
    raw_ref: str


class ScenarioTrigger(enum.StrEnum):
    manual = "manual"
    shock_detector = "shock_detector"


class PriorSource(enum.StrEnum):
    fedwatch = "fedwatch"
    polymarket = "polymarket"
    kalshi = "kalshi"
    none = "none"


class Scenario(_Row):
    """A counterfactual to reason under, with its market-implied prior.

    Scenarios with no tradeable prior carry ``prior_source=none`` and must be
    surfaced downstream as "prior: none, user-assumed" (design §3).
    """

    scenario_id: str
    description: str
    trigger: ScenarioTrigger
    prior_prob: float | None = Field(default=None, ge=0.0, le=1.0)
    prior_source: PriorSource = PriorSource.none
    horizon_days: int = Field(gt=0)
    affected_buckets: list[int] = Field(default_factory=list)


class Direction(enum.StrEnum):
    up = "up"
    down = "down"
    flat = "flat"


class Prediction(_Row):
    """One row per directional claim any agent makes (RT-4/RT-7).

    This is the evaluation methodology, not optional polish: the LLM layer is
    scored forward on calibration, because backtests of LLM reasoning are
    contaminated by training data.
    """

    prediction_id: str
    scenario_id: str
    agent: str
    ticker: str
    direction: Direction
    magnitude_pct: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    horizon_days: int = Field(gt=0)
    resolved: bool = False
    outcome: Direction | None = None
    brier_contribution: float | None = None


class Action(enum.StrEnum):
    buy = "buy"
    sell = "sell"
    hold = "hold"


class GuardResult(enum.StrEnum):
    passed = "passed"
    clipped = "clipped"
    rejected = "rejected"


class Decision(_Row):
    """Portfolio Manager output — what the system wants to do and why.

    Written to the decision log BEFORE any order is sent (write-ahead), so a
    crash can never lose the audit trail for a live order.
    """

    decision_id: str
    scenario_id: str
    ticker: str
    action: Action
    size_pct: float = Field(ge=0.0)
    reasoning_summary: str
    agent_votes: dict[str, str] = Field(default_factory=dict)
    guard_result: GuardResult | None = None
    guard_reasons: list[str] = Field(default_factory=list)
    executed: bool = False
    order_id: str | None = None
    token_cost_usd: float = 0.0
