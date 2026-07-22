"""Typed loaders for config/*.yaml.

Configs are validated at load time so a malformed limits file fails loudly at
startup, never silently mid-run. ``limits.yaml`` values feed the deterministic
guard (design §11.4) — they are hard constraints, not tunable prompts.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


class Bucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    risk: str
    tickers: list[str]


class Universe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buckets: list[Bucket]

    @property
    def all_tickers(self) -> frozenset[str]:
        return frozenset(t for b in self.buckets for t in b.tickers)

    def tickers_for(self, bucket_id: int) -> list[str]:
        for b in self.buckets:
            if b.id == bucket_id:
                return list(b.tickers)
        raise KeyError(f"unknown bucket {bucket_id}")


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_position_pct: float = Field(gt=0, le=100)
    max_daily_turnover_pct: float = Field(gt=0, le=100)
    max_gross_exposure_pct: float = Field(gt=0, le=100)
    allow_short: bool
    allow_margin: bool
    live_confirm_threshold_usd: float = Field(ge=0)
    daily_loss_halt_pct: float = Field(gt=0)

    @model_validator(mode="after")
    def _no_leverage_invariants(self) -> Limits:
        # The design locks these off (§11.4 rule 4). Refuse to even load a
        # config that tries to switch them on — removing this check is a
        # deliberate human decision, visible in git history.
        if self.allow_short or self.allow_margin:
            raise ValueError("allow_short/allow_margin must be false (design §11.4)")
        return self


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default: str
    nodes: dict[str, str]
    max_tokens_usd_per_run: float = Field(gt=0)

    def for_node(self, node: str) -> str:
        return self.nodes.get(node, self.default)


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_universe(path: Path | None = None) -> Universe:
    return Universe.model_validate(_load_yaml(path or CONFIG_DIR / "universe.yaml"))


def load_limits(path: Path | None = None) -> Limits:
    return Limits.model_validate(_load_yaml(path or CONFIG_DIR / "limits.yaml"))


def load_models(path: Path | None = None) -> Models:
    return Models.model_validate(_load_yaml(path or CONFIG_DIR / "models.yaml"))
