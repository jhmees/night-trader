"""Config loading fails loudly, and the no-leverage invariants cannot be
switched on via YAML edits alone."""

import pytest
from pydantic import ValidationError

from nighttrader.config import Limits, load_limits, load_models, load_universe


def test_universe_loads_and_bucket1_nonempty(universe):
    assert universe.tickers_for(1), "bucket 1 is the Phase 0 proving ground"
    assert "XLF" in universe.all_tickers


def test_limits_load(limits):
    assert 0 < limits.max_position_pct <= 100
    assert limits.allow_short is False and limits.allow_margin is False


def test_models_load():
    m = load_models()
    assert m.for_node("portfolio_manager")
    assert m.for_node("nonexistent_node") == m.default
    assert m.max_tokens_usd_per_run > 0


def test_short_margin_cannot_be_enabled():
    base = load_limits().model_dump()
    for flag in ("allow_short", "allow_margin"):
        cfg = dict(base)
        cfg[flag] = True
        with pytest.raises(ValidationError):
            Limits.model_validate(cfg)


def test_unknown_config_keys_rejected():
    cfg = load_limits().model_dump()
    cfg["surprise_knob"] = 1
    with pytest.raises(ValidationError):
        Limits.model_validate(cfg)


def test_missing_file_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_universe(tmp_path / "nope.yaml")
