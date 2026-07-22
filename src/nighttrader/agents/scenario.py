"""Scenario construction + prior attachment (design §3).

Phase 1 scope: manual scenario input with an explicit prior. The
scenario-threading mechanism (injecting the counterfactual into each
analyst's tool calls) is open design work (§8.2) and lands in Phase 2.
"""

from __future__ import annotations

import uuid

from nighttrader.schemas import PriorSource, Scenario, ScenarioTrigger


def manual_scenario(
    description: str,
    *,
    horizon_days: int,
    affected_buckets: list[int],
    prior_prob: float | None = None,
    prior_source: PriorSource = PriorSource.none,
) -> Scenario:
    """Build a manually-injected scenario.

    A prior probability without a source (or vice versa) is a category error —
    "X trades at 34%" only means something if we can say where it trades.
    """
    if (prior_prob is None) != (prior_source is PriorSource.none):
        raise ValueError("prior_prob and prior_source must be set together")
    return Scenario(
        scenario_id=f"scn-{uuid.uuid4().hex[:12]}",
        description=description,
        trigger=ScenarioTrigger.manual,
        prior_prob=prior_prob,
        prior_source=prior_source,
        horizon_days=horizon_days,
        affected_buckets=affected_buckets,
    )
