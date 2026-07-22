"""Deterministic pre-trade guard (design §11.4 — non-negotiable contract).

This module is pure Python: no LLM imports, no network calls. It receives a
Decision the agent graph proposed and enforces, in order:

  1. ticker must be in the universe whitelist (config/universe.yaml)
  2. position size <= limits.max_position_pct           (clip)
  3. today's turnover budget                            (clip, reject if spent)
  4. no shorts, no margin / gross exposure cap          (reject / clip)
  5. daily loss circuit-breaker: halt new buys          (reject)
  6. live orders above threshold require human confirm  (reject without flag)

Anything failing is returned with machine-readable reasons and NOT sent.
The LLM proposes; this file disposes. ``tests/test_guard.py`` covers every
rule, adversarial injection fixtures, and enforces import purity via AST.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nighttrader.config import Limits, Universe
from nighttrader.schemas import Action, Decision, GuardResult


@dataclass(frozen=True)
class PortfolioState:
    """Snapshot the guard judges against. Built from broker data by the
    caller — the guard itself never talks to the network."""

    equity_usd: float
    # current position sizes as % of equity, by ticker (long-only => >= 0)
    positions_pct: dict[str, float] = field(default_factory=dict)
    # sum of |trade notional| already executed today, % of equity
    turnover_today_pct: float = 0.0
    # realized P&L today, % of equity (negative = loss)
    realized_pnl_today_pct: float = 0.0


@dataclass(frozen=True)
class GuardVerdict:
    """A verdict is bound to the exact decision and execution context it
    judged (decision_id/ticker/action/live/human_confirmed). The broker
    refuses any verdict whose binding doesn't match the order being submitted,
    so a verdict earned by one (safe) decision can never authorize another."""

    result: GuardResult
    # size actually allowed to trade, % of equity (0 when rejected)
    approved_size_pct: float
    reasons: list[str]
    # binding to the judged decision + context
    decision_id: str
    ticker: str
    action: Action
    live: bool
    human_confirmed: bool
    # the equity snapshot the % (and the confirm-threshold check) was judged
    # against — the broker refuses a different basis, so the dollar amount
    # the human-confirm gate saw is the dollar amount that trades
    equity_usd: float

    @property
    def approved_notional_usd(self) -> float:
        return self.approved_size_pct / 100.0 * self.equity_usd


def check(
    decision: Decision,
    portfolio: PortfolioState,
    universe: Universe,
    limits: Limits,
    *,
    live: bool = False,
    human_confirmed: bool = False,
) -> GuardVerdict:
    """Evaluate a proposed Decision against the hard limits.

    Returns a verdict; never raises on bad proposals (a hostile or confused
    proposal is data, not an exception). Rules apply in the documented order;
    the first rejecting rule wins, clips accumulate.
    """
    reasons: list[str] = []

    def _verdict(result: GuardResult, size_pct: float, why: list[str]) -> GuardVerdict:
        return GuardVerdict(
            result=result,
            approved_size_pct=size_pct,
            reasons=why,
            decision_id=decision.decision_id,
            ticker=decision.ticker,
            action=decision.action,
            live=live,
            human_confirmed=human_confirmed,
            equity_usd=portfolio.equity_usd,
        )

    def _reject(reason: str) -> GuardVerdict:
        return _verdict(GuardResult.rejected, 0.0, [reason])

    if decision.action is Action.hold:
        return _verdict(GuardResult.passed, 0.0, ["hold: nothing to execute"])

    # -- 1. universe whitelist ------------------------------------------------
    if decision.ticker not in universe.all_tickers:
        return _reject(f"ticker {decision.ticker!r} not in universe whitelist")

    size = float(decision.size_pct)
    if size <= 0:
        return _reject("non-positive size")
    held = portfolio.positions_pct.get(decision.ticker, 0.0)

    # -- 2. per-position cap --------------------------------------------------
    if decision.action is Action.buy:
        max_add = limits.max_position_pct - held
        if max_add <= 0:
            return _reject(
                f"position {decision.ticker} already at cap "
                f"({held:.1f}% >= {limits.max_position_pct:.1f}%)"
            )
        if size > max_add:
            reasons.append(f"clipped {size:.1f}% -> {max_add:.1f}% (per-position cap)")
            size = max_add

    # -- 4a. no shorts (checked before turnover so a naked sell dies early) ---
    if decision.action is Action.sell:
        if held <= 0:
            return _reject(f"no position in {decision.ticker} to sell (shorting disabled)")
        if size > held:
            reasons.append(f"clipped sell {size:.1f}% -> {held:.1f}% (no shorting)")
            size = held

    # -- 3. daily turnover budget --------------------------------------------
    remaining = limits.max_daily_turnover_pct - portfolio.turnover_today_pct
    if remaining <= 0:
        return _reject(
            f"daily turnover budget spent "
            f"({portfolio.turnover_today_pct:.1f}%/{limits.max_daily_turnover_pct:.1f}%)"
        )
    if size > remaining:
        reasons.append(f"clipped {size:.1f}% -> {remaining:.1f}% (turnover budget)")
        size = remaining

    # -- 4b. no margin: gross exposure must stay under cap on buys ------------
    if decision.action is Action.buy:
        gross = sum(portfolio.positions_pct.values())
        room = limits.max_gross_exposure_pct - gross
        if room <= 0:
            return _reject(
                f"gross exposure at cap ({gross:.1f}% >= {limits.max_gross_exposure_pct:.1f}%)"
            )
        if size > room:
            reasons.append(f"clipped {size:.1f}% -> {room:.1f}% (gross exposure cap)")
            size = room

    # -- 5. daily loss circuit-breaker ----------------------------------------
    if (
        decision.action is Action.buy
        and portfolio.realized_pnl_today_pct <= -limits.daily_loss_halt_pct
    ):
        return _reject(
            f"daily loss halt: realized {portfolio.realized_pnl_today_pct:.2f}% "
            f"<= -{limits.daily_loss_halt_pct:.2f}%, no new buys today"
        )

    # -- 6. live human-confirmation threshold ---------------------------------
    if live:
        notional_usd = size / 100.0 * portfolio.equity_usd
        if notional_usd > limits.live_confirm_threshold_usd and not human_confirmed:
            return _reject(
                f"live order ${notional_usd:.0f} exceeds confirm threshold "
                f"${limits.live_confirm_threshold_usd:.0f} and no --confirm given"
            )

    if reasons:
        return _verdict(GuardResult.clipped, round(size, 6), reasons)
    return _verdict(GuardResult.passed, round(size, 6), ["all checks passed"])
