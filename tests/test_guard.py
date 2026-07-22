"""Every guard rule gets a test (design §11.4), plus adversarial fixtures and
an AST-based purity check that guard.py imports no LLM/network machinery."""

import ast
import json
import uuid
from pathlib import Path

import pytest

from nighttrader.execution import guard
from nighttrader.execution.broker import GuardBypassError, PaperBroker
from nighttrader.execution.guard import PortfolioState
from nighttrader.schemas import Action, Decision, GuardResult

FIXTURES = Path(__file__).parent / "fixtures"


def make_decision(ticker="XLF", action=Action.buy, size_pct=5.0, **kw) -> Decision:
    return Decision(
        decision_id=f"dec-{uuid.uuid4().hex[:8]}",
        scenario_id="scn-test",
        ticker=ticker,
        action=action,
        size_pct=size_pct,
        reasoning_summary="test",
        **kw,
    )


def flat_portfolio(**kw) -> PortfolioState:
    defaults = dict(equity_usd=10_000.0, positions_pct={}, turnover_today_pct=0.0,
                    realized_pnl_today_pct=0.0)
    defaults.update(kw)
    return PortfolioState(**defaults)


# --- rule 1: universe whitelist -------------------------------------------------

def test_unknown_ticker_rejected(universe, limits):
    v = guard.check(make_decision(ticker="TSLA"), flat_portfolio(), universe, limits)
    assert v.result is GuardResult.rejected
    assert v.approved_size_pct == 0.0


def test_universe_ticker_passes(universe, limits):
    v = guard.check(make_decision(ticker="XLF", size_pct=5.0), flat_portfolio(), universe, limits)
    assert v.result is GuardResult.passed
    assert v.approved_size_pct == 5.0


# --- rule 2: per-position cap ---------------------------------------------------

def test_oversize_buy_clipped(universe, limits):
    v = guard.check(make_decision(size_pct=50.0), flat_portfolio(), universe, limits)
    assert v.result is GuardResult.clipped
    assert v.approved_size_pct == limits.max_position_pct


def test_buy_clipped_accounting_for_existing_position(universe, limits):
    p = flat_portfolio(positions_pct={"XLF": 8.0})
    v = guard.check(make_decision(size_pct=5.0), p, universe, limits)
    assert v.result is GuardResult.clipped
    assert v.approved_size_pct == pytest.approx(limits.max_position_pct - 8.0)


def test_buy_rejected_when_position_at_cap(universe, limits):
    p = flat_portfolio(positions_pct={"XLF": limits.max_position_pct})
    v = guard.check(make_decision(size_pct=1.0), p, universe, limits)
    assert v.result is GuardResult.rejected


# --- rule 3: daily turnover budget ----------------------------------------------

def test_turnover_budget_clips(universe, limits):
    p = flat_portfolio(turnover_today_pct=limits.max_daily_turnover_pct - 2.0)
    v = guard.check(make_decision(size_pct=5.0), p, universe, limits)
    assert v.result is GuardResult.clipped
    assert v.approved_size_pct == pytest.approx(2.0)


def test_turnover_budget_exhausted_rejects(universe, limits):
    p = flat_portfolio(turnover_today_pct=limits.max_daily_turnover_pct)
    v = guard.check(make_decision(size_pct=1.0), p, universe, limits)
    assert v.result is GuardResult.rejected


# --- rule 4: no shorts, no margin ----------------------------------------------

def test_sell_without_position_rejected_as_short(universe, limits):
    v = guard.check(make_decision(action=Action.sell, size_pct=5.0),
                    flat_portfolio(), universe, limits)
    assert v.result is GuardResult.rejected


def test_sell_clipped_to_held(universe, limits):
    p = flat_portfolio(positions_pct={"XLF": 3.0})
    v = guard.check(make_decision(action=Action.sell, size_pct=9.0), p, universe, limits)
    assert v.result is GuardResult.clipped
    assert v.approved_size_pct == pytest.approx(3.0)


def test_gross_exposure_cap(universe, limits):
    positions = {"SPY": 96.0}
    p = flat_portfolio(positions_pct=positions)
    v = guard.check(make_decision(ticker="XLF", size_pct=8.0), p, universe, limits)
    assert v.result is GuardResult.clipped
    assert v.approved_size_pct == pytest.approx(limits.max_gross_exposure_pct - 96.0)


# --- rule 5: daily loss circuit breaker -----------------------------------------

def test_daily_loss_halts_new_buys(universe, limits):
    p = flat_portfolio(realized_pnl_today_pct=-limits.daily_loss_halt_pct)
    v = guard.check(make_decision(size_pct=2.0), p, universe, limits)
    assert v.result is GuardResult.rejected
    assert "loss halt" in v.reasons[0]


def test_daily_loss_still_allows_derisking_sells(universe, limits):
    p = flat_portfolio(positions_pct={"XLF": 5.0},
                       realized_pnl_today_pct=-limits.daily_loss_halt_pct - 1)
    v = guard.check(make_decision(action=Action.sell, size_pct=5.0), p, universe, limits)
    assert v.result is GuardResult.passed


# --- rule 6: live confirm threshold ---------------------------------------------

def test_live_above_threshold_requires_confirm(universe, limits):
    p = flat_portfolio(equity_usd=100_000.0)  # 5% = $5000 > threshold
    d = make_decision(size_pct=5.0)
    v = guard.check(d, p, universe, limits, live=True, human_confirmed=False)
    assert v.result is GuardResult.rejected
    v2 = guard.check(d, p, universe, limits, live=True, human_confirmed=True)
    assert v2.result is GuardResult.passed


def test_paper_mode_never_needs_confirm(universe, limits):
    p = flat_portfolio(equity_usd=100_000.0)
    v = guard.check(make_decision(size_pct=5.0), p, universe, limits, live=False)
    assert v.result is GuardResult.passed


# --- misc -----------------------------------------------------------------------

def test_hold_is_noop(universe, limits):
    v = guard.check(make_decision(action=Action.hold, size_pct=0.0),
                    flat_portfolio(), universe, limits)
    assert v.result is GuardResult.passed
    assert v.approved_size_pct == 0.0


def test_zero_size_trade_rejected(universe, limits):
    v = guard.check(make_decision(size_pct=0.0), flat_portfolio(), universe, limits)
    assert v.result is GuardResult.rejected


# --- adversarial fixtures (RT-5): injected news -> hostile decisions ------------

def _hostile_decisions():
    cases = json.loads((FIXTURES / "injection_news.json").read_text())
    return [c for c in cases if "resulting_decision" in c]


@pytest.mark.parametrize("case", _hostile_decisions(), ids=lambda c: c["name"])
def test_injected_decisions_never_pass_unclamped(case, universe, limits):
    """Decisions produced under prompt injection must be rejected or clipped
    to hard limits — never executed as proposed."""
    rd = case["resulting_decision"]
    d = make_decision(ticker=rd["ticker"], action=Action(rd["action"]), size_pct=rd["size_pct"])
    v = guard.check(d, flat_portfolio(), universe, limits)
    if v.result is GuardResult.rejected:
        assert v.approved_size_pct == 0.0
    else:
        # whatever survives must respect the per-position cap
        assert v.approved_size_pct <= limits.max_position_pct


def test_broker_refuses_unguarded_decision(universe, limits):
    """No code path may submit an order without a passing verdict."""
    broker = PaperBroker()
    d = make_decision()
    rejected = guard.check(make_decision(ticker="EVILCO"), flat_portfolio(), universe, limits)
    assert rejected.result is GuardResult.rejected
    with pytest.raises(GuardBypassError):
        broker.submit(d, rejected, equity_usd=10_000.0)


def test_broker_refuses_verdict_for_different_decision(universe, limits):
    """A verdict earned by a safe decision must never authorize another
    decision — verdict/decision binding (review finding C1)."""
    broker = PaperBroker()
    safe = make_decision(ticker="XLF", size_pct=2.0)
    verdict_for_safe = guard.check(safe, flat_portfolio(), universe, limits)
    assert verdict_for_safe.result is GuardResult.passed

    hostile = make_decision(ticker="XLF", size_pct=2.0)  # different decision_id
    with pytest.raises(GuardBypassError, match="mismatch"):
        broker.submit(hostile, verdict_for_safe, equity_usd=10_000.0)

    # ticker swap under a reused decision_id also dies
    swapped = safe.model_copy(update={"ticker": "SPY"})
    with pytest.raises(GuardBypassError, match="mismatch"):
        broker.submit(swapped, verdict_for_safe, equity_usd=10_000.0)

    # the genuine pairing still submits fine
    receipt = broker.submit(safe, verdict_for_safe, equity_usd=10_000.0)
    assert receipt.notional_usd == pytest.approx(200.0)


def test_live_broker_requires_two_keys(monkeypatch):
    """AlpacaBroker(paper=False) must refuse to construct without BOTH the
    env var and the CLI flag — checked before any SDK import (finding I1)."""
    from nighttrader.execution.broker import AlpacaBroker

    monkeypatch.delenv("NIGHTTRADER_LIVE", raising=False)
    with pytest.raises(GuardBypassError, match="two-key"):
        AlpacaBroker(paper=False, cli_live_flag=True)
    monkeypatch.setenv("NIGHTTRADER_LIVE", "1")
    with pytest.raises(GuardBypassError, match="two-key"):
        AlpacaBroker(paper=False, cli_live_flag=False)


def test_live_context_verdict_required(universe, limits):
    """A verdict evaluated in paper context cannot gate a live submission."""
    from nighttrader.execution.broker import _require_guard_approval

    d = make_decision(size_pct=2.0)
    paper_verdict = guard.check(d, flat_portfolio(), universe, limits, live=False)
    assert paper_verdict.result is GuardResult.passed
    with pytest.raises(GuardBypassError, match="paper context"):
        _require_guard_approval(d, paper_verdict, broker_is_live=True)
    live_verdict = guard.check(d, flat_portfolio(), universe, limits,
                               live=True, human_confirmed=True)
    _require_guard_approval(d, live_verdict, broker_is_live=True)  # no raise


# --- purity: guard.py must not import LLM/network machinery ---------------------

ALLOWED_GUARD_IMPORTS = {
    "__future__", "dataclasses", "typing", "math", "enum",
    "nighttrader.config", "nighttrader.schemas",
}


def test_guard_import_purity():
    src = Path(guard.__file__).read_text()
    tree = ast.parse(src)
    seen = set()
    dynamic = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            seen.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            seen.add(node.module or "")
        elif isinstance(node, ast.Call):
            # dynamic-import / code-exec escape hatches count too
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else None)
            if name in {"__import__", "import_module", "eval", "exec", "compile"}:
                dynamic.append(name)
    illegal = seen - ALLOWED_GUARD_IMPORTS
    assert not illegal and not dynamic, (
        f"guard.py imports {illegal or dynamic} — the guard must stay pure "
        "(no LLM, no network, no dynamic imports; design §11.4)"
    )
