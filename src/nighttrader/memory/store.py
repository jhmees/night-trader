"""Parquet + DuckDB storage (design §5, RT-10: no vector DB until it hurts).

Layout: ``data/<category>/date=YYYY-MM-DD/<run_id>.parquet`` — append-only,
one file per run, so a crashed run never corrupts prior data and re-runs are
idempotent per run_id. DuckDB queries the whole category via glob.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd
from pydantic import BaseModel

from nighttrader.schemas import SCHEMA_VERSION

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"

# Category names become DuckDB view identifiers and glob paths; anything
# outside this alphabet is refused on write and skipped on read, so no
# on-disk name can smuggle SQL into query().
_CATEGORY_RE = re.compile(r"[A-Za-z0-9_]+")


def _partition_dir(root: Path, category: str, day: date) -> Path:
    return root / category / f"date={day.isoformat()}"


def write_rows(
    rows: Sequence[BaseModel] | pd.DataFrame,
    category: str,
    run_id: str,
    *,
    root: Path | None = None,
    day: date | None = None,
) -> Path:
    """Write one run's rows for a category. Overwrites only its own run file
    (idempotent re-runs), never other runs' files."""
    root = root or DATA_ROOT
    day = day or datetime.now(UTC).date()
    if not _CATEGORY_RE.fullmatch(category):
        raise ValueError(f"invalid category name {category!r} (allowed: [A-Za-z0-9_])")
    if isinstance(rows, pd.DataFrame):
        if rows.empty:
            raise ValueError("refusing to write empty row set")
        df = rows.copy()
        # Every stored row carries the audit stamps, whichever path wrote it.
        if "schema_version" not in df.columns:
            df["schema_version"] = SCHEMA_VERSION
        if "ts" not in df.columns:
            df["ts"] = datetime.now(UTC).isoformat()
    else:
        if not rows:
            raise ValueError("refusing to write empty row set")
        df = pd.DataFrame([r.model_dump(mode="json") for r in rows])
    target = _partition_dir(root, category, day)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{run_id}.parquet"
    df.to_parquet(path, index=False)
    return path


def read_category(category: str, *, root: Path | None = None) -> pd.DataFrame:
    """All rows ever written for a category, as one DataFrame."""
    root = root or DATA_ROOT
    pattern = str(root / category / "date=*" / "*.parquet")
    con = duckdb.connect()
    try:
        return con.execute(
            "SELECT * FROM read_parquet(?, union_by_name=true)", [pattern]
        ).df()
    finally:
        con.close()


def query(sql: str, *, root: Path | None = None) -> pd.DataFrame:
    """Ad-hoc SQL over the lake. Each category is exposed as a view named
    after its directory (e.g. ``features``, ``decisions``, ``predictions``)."""
    root = root or DATA_ROOT
    con = duckdb.connect()
    try:
        if root.exists():
            for cat_dir in sorted(p for p in root.iterdir() if p.is_dir()):
                if not _CATEGORY_RE.fullmatch(cat_dir.name):
                    continue  # hostile/garbage dir name — never reaches SQL
                pattern = str(cat_dir / "date=*" / "*.parquet").replace("'", "''")
                try:
                    con.execute(
                        f'CREATE VIEW "{cat_dir.name}" AS '
                        f"SELECT * FROM read_parquet('{pattern}', union_by_name=true)"
                    )
                except duckdb.Error:
                    continue  # empty category dir — no view
        return con.execute(sql).df()
    finally:
        con.close()
