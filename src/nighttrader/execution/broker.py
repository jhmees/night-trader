"""Broker layer. Paper mode is the default and live mode is double-gated:
``NIGHTTRADER_LIVE=1`` in the environment AND an explicit ``--live`` CLI flag,
enforced at broker construction — a live client cannot even be built without
both keys.

Submission requires a GuardVerdict that (a) passed/clipped, (b) is bound to
the exact Decision being submitted (decision_id/ticker/action), and (c) was
evaluated under the execution context this broker runs in (a live broker
refuses verdicts judged with live=False). A verdict earned by one decision can
never authorize another, and a paper-context verdict can never gate real
money (RT-5 hard boundary).

Alpaca connectivity (``alpaca-py``, install extra ``broker``) is wrapped so
Phase 0/1 code and tests run without the SDK installed.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from nighttrader.execution.guard import GuardVerdict
from nighttrader.schemas import Decision, GuardResult


class GuardBypassError(RuntimeError):
    """Raised when submission is attempted without a matching, passing,
    context-consistent guard verdict — or when live mode is requested
    without both human keys."""


@dataclass(frozen=True)
class OrderReceipt:
    order_id: str
    ticker: str
    side: str
    notional_usd: float
    paper: bool


def live_mode_enabled(cli_live_flag: bool) -> bool:
    """Live trading requires BOTH the env var and the CLI flag (two-key rule)."""
    return cli_live_flag and os.environ.get("NIGHTTRADER_LIVE", "0") == "1"


class PaperBroker:
    """Records intended orders without touching any external API. Used for
    Phase 0/1 dry runs and as the safe default everywhere."""

    def __init__(self) -> None:
        self.submitted: list[OrderReceipt] = []

    def submit(self, decision: Decision, verdict: GuardVerdict, equity_usd: float) -> OrderReceipt:
        _require_guard_approval(decision, verdict, broker_is_live=False)
        receipt = OrderReceipt(
            order_id=f"paper-{uuid.uuid4().hex[:12]}",
            ticker=decision.ticker,
            side=decision.action.value,
            notional_usd=verdict.approved_size_pct / 100.0 * equity_usd,
            paper=True,
        )
        self.submitted.append(receipt)
        return receipt


class AlpacaBroker:
    """Thin wrapper around alpaca-py. Constructed lazily so the dependency is
    only needed when broker connectivity is actually used (Phase 1+).

    ``paper=False`` refuses to construct unless the two-key rule holds — the
    check runs BEFORE any SDK import, so it is testable and unskippable.
    """

    def __init__(self, *, paper: bool = True, cli_live_flag: bool = False) -> None:
        if not paper and not live_mode_enabled(cli_live_flag):
            raise GuardBypassError(
                "live broker requires NIGHTTRADER_LIVE=1 AND the --live flag "
                "(two-key rule); refusing to construct"
            )
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as e:  # pragma: no cover - depends on extra
            raise ImportError(
                "alpaca-py not installed; run `uv sync --extra broker`"
            ) from e
        self._paper = paper
        self._client = TradingClient(
            os.environ["ALPACA_API_KEY"],
            os.environ["ALPACA_SECRET_KEY"],
            paper=paper,
        )

    def submit(  # pragma: no cover - network
        self, decision: Decision, verdict: GuardVerdict, equity_usd: float
    ) -> OrderReceipt:
        _require_guard_approval(decision, verdict, broker_is_live=not self._paper)
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        notional = round(verdict.approved_size_pct / 100.0 * equity_usd, 2)
        order = self._client.submit_order(
            MarketOrderRequest(
                symbol=decision.ticker,
                notional=notional,
                side=OrderSide.BUY if decision.action.value == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        )
        return OrderReceipt(str(order.id), decision.ticker, decision.action.value,
                            notional, self._paper)


def _require_guard_approval(
    decision: Decision, verdict: GuardVerdict, *, broker_is_live: bool
) -> None:
    if verdict.result not in (GuardResult.passed, GuardResult.clipped):
        raise GuardBypassError(f"decision was not approved by guard: {verdict.reasons}")
    if (
        verdict.decision_id != decision.decision_id
        or verdict.ticker != decision.ticker
        or verdict.action != decision.action
    ):
        raise GuardBypassError(
            f"verdict/decision mismatch: verdict is for "
            f"{verdict.decision_id}/{verdict.ticker}/{verdict.action.value}, "
            f"submission is {decision.decision_id}/{decision.ticker}/{decision.action.value}"
        )
    if broker_is_live and not verdict.live:
        raise GuardBypassError(
            "verdict was evaluated in paper context (live=False) but the broker "
            "is live; re-run the guard with live=True"
        )
    if verdict.approved_size_pct <= 0:
        raise GuardBypassError("guard approved zero size; nothing to submit")
