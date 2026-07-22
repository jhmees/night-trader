"""Parquet + DuckDB storage (design §5, RT-10: no vector DB until it hurts).

Layout: ``data/<category>/date=YYYY-MM-DD/<run_id>.parquet`` — append-only,
one file per run, so a crashed run never corrupts prior data and re-runs are
idempotent per run_id. DuckDB queries the whole category via glob.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd
from pydantic import BaseModel

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


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
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
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
                pattern = str(cat_dir / "date=*" / "*.parquet")
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
