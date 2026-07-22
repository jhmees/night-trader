# Nighttrader

Scenario-driven macro research & decision-support pipeline. Turns cheap public
information (macro data, filings, weather, event streams) into structured
scenario reasoning with a full audit trail — a reasoning tool, not a buy button.

**Read first:** [`NIGHTTRADER_DESIGN.md`](NIGHTTRADER_DESIGN.md) — thesis,
architecture, red-team findings, and phase gates. It is the source of truth.
The expert review of the design and this scaffold lives in
[`docs/DESIGN_REVIEW.md`](docs/DESIGN_REVIEW.md).

## Safety posture (short version)

- The LLM **proposes**; deterministic code (`src/nighttrader/execution/guard.py`)
  **disposes**: ticker whitelist, position/turnover caps, no shorts, no margin,
  daily-loss halt, human confirm for live orders. Import purity is enforced by test.
- Raw news/event text never enters agent context — only typed, validated
  events pass the extraction firewall (`src/nighttrader/extraction/`).
- Paper mode is the default. Live mode needs `NIGHTTRADER_LIVE=1` **and**
  `--live` **and** (above a threshold) `--confirm`.
- Every directional claim is logged and scored for calibration
  (`src/nighttrader/evaluation/`) — returns alone can't validate this system
  on any reasonable timescale.

## Quickstart (Phase 0)

```bash
uv venv && uv pip install -e ".[dev]"
cp .env.example .env            # add your FRED_API_KEY
uv run pytest                   # offline test suite
uv run python scripts/daily_run.py --dry          # features + macro snapshot
uv run python scripts/daily_run.py --dry --no-fred  # without a FRED key
uv run python scripts/backfill.py                 # full price history -> data/
```

Data lands in `data/` (gitignored parquet, queryable via DuckDB):

```python
from nighttrader.memory import store
store.query("SELECT ticker, close, dist_ma200_pct FROM features ORDER BY ticker")
```

## Repo map

```
config/          universe whitelist, hard limits, model tiering (the knobs)
src/nighttrader/ schemas · data clients · extraction firewall · guard/broker
                 parquet store · prediction log & calibration
scripts/         daily_run.py (cron entrypoint) · backfill.py
tests/           every guard rule, adversarial injection fixtures, purity check
index.html       legacy macro dashboard (GitHub Pages) — operator view
                 (FRED key is entered in-browser and kept in localStorage)
```

## Live dashboard

👉 [Open dashboard](https://jhmees.github.io/night-trader/) — Faber 10-month MA
signals, FRED macro indicators, crypto ripple monitor. It prompts once for a
FRED API key ([free here](https://fred.stlouisfed.org/docs/api/api_key.html))
and stores it only in your browser.
