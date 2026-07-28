"""Publish a static dashboard payload (data.json) from the parquet lake.

The GitHub Pages dashboard (index.html) renders this file instead of fetching
market data client-side: no API keys in the browser, no CORS proxies, no
vendor rate limits — and what the dashboard shows is exactly what the
pipeline saw. Publish is just "commit data.json and push" from the daily cron.

Only non-sensitive data belongs here: the Pages site is public. Features and
macro are fine; decisions/P&L stay in the local lake.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from nighttrader.memory import store

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data.json"


def _latest(category: str, root: Path | None) -> pd.DataFrame:
    try:
        df = store.read_category(category, root=root)
    except duckdb.Error:
        return pd.DataFrame()
    return df


def _jsonable(df: pd.DataFrame) -> list[dict]:
    """Records with NaN/NaT -> null and timestamps -> ISO strings — data.json
    must be strict JSON (JSON.parse rejects NaN literals)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def build_payload(*, root: Path | None = None) -> dict:
    """Latest feature row per ticker + the latest macro snapshot."""
    feats = _latest("features", root)
    if not feats.empty:
        feats = feats.sort_values("ts").groupby("ticker", as_index=False).tail(1)
        feats = feats.sort_values("ticker")
    macro_df = _latest("macro", root)
    macro = None
    if not macro_df.empty:
        macro = _jsonable(macro_df.sort_values("ts").tail(1))[0]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "features": _jsonable(feats) if not feats.empty else [],
        "macro": macro,
    }


def write_dashboard_json(path: Path | None = None, *, root: Path | None = None) -> Path:
    path = path or DEFAULT_OUT
    payload = build_payload(root=root)
    # allow_nan=False: fail loudly rather than emit JSON the browser rejects
    path.write_text(json.dumps(payload, indent=1, allow_nan=False) + "\n")
    return path
