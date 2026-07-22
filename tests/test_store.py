"""Parquet lake roundtrip + DuckDB views + recall search."""

from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest

from nighttrader.memory import store
from nighttrader.memory.recall import cosine_top_k
from nighttrader.schemas import Direction, Prediction

NOW = datetime(2026, 7, 1, tzinfo=UTC)


def _pred(i: int) -> Prediction:
    return Prediction(
        prediction_id=f"p-{i}", scenario_id="s", ts=NOW, agent="a", ticker="XLF",
        direction=Direction.up, confidence=0.6, horizon_days=5,
    )


def test_write_read_roundtrip(tmp_path):
    rows = [_pred(i) for i in range(3)]
    path = store.write_rows(rows, "predictions", "run-1", root=tmp_path,
                            day=date(2026, 7, 1))
    assert path.exists()
    df = store.read_category("predictions", root=tmp_path)
    assert len(df) == 3
    assert set(df["prediction_id"]) == {"p-0", "p-1", "p-2"}


def test_rerun_same_run_id_is_idempotent(tmp_path):
    day = date(2026, 7, 1)
    store.write_rows([_pred(0)], "predictions", "run-1", root=tmp_path, day=day)
    store.write_rows([_pred(0)], "predictions", "run-1", root=tmp_path, day=day)
    assert len(store.read_category("predictions", root=tmp_path)) == 1


def test_separate_runs_append(tmp_path):
    day = date(2026, 7, 1)
    store.write_rows([_pred(0)], "predictions", "run-1", root=tmp_path, day=day)
    store.write_rows([_pred(1)], "predictions", "run-2", root=tmp_path, day=day)
    assert len(store.read_category("predictions", root=tmp_path)) == 2


def test_empty_rows_refused(tmp_path):
    with pytest.raises(ValueError):
        store.write_rows([], "predictions", "run-1", root=tmp_path)
    with pytest.raises(ValueError):
        store.write_rows(pd.DataFrame(), "predictions", "run-1", root=tmp_path)


def test_dataframe_rows_get_audit_stamps(tmp_path):
    """Rows written via the DataFrame path (daily_run features/macro) must
    carry schema_version and a ts like model rows do (finding I3)."""
    df = pd.DataFrame([{"ticker": "XLF", "close": 50.0}])
    store.write_rows(df, "features", "run-1", root=tmp_path, day=date(2026, 7, 1))
    out = store.read_category("features", root=tmp_path)
    assert "schema_version" in out.columns and out["schema_version"].iloc[0] == 1
    assert "ts" in out.columns and out["ts"].iloc[0]


def test_hostile_category_names_never_reach_sql(tmp_path):
    """A directory name crafted to break out of the CREATE VIEW identifier
    must be skipped, and hostile category writes refused (finding I2)."""
    with pytest.raises(ValueError):
        store.write_rows([_pred(0)], 'evil"; CREATE TABLE pwned(y INT); --',
                         "run-1", root=tmp_path)
    # plant a hostile dir on disk directly; query() must ignore it
    evil = tmp_path / 'v" AS SELECT 42 AS x; CREATE TABLE pwned(y INT); --'
    (evil / "date=2026-07-01").mkdir(parents=True)
    store.write_rows([_pred(0)], "predictions", "run-1", root=tmp_path,
                     day=date(2026, 7, 1))
    df = store.query("SELECT count(*) AS n FROM predictions", root=tmp_path)
    assert df["n"].iloc[0] == 1
    tables = store.query("SHOW TABLES", root=tmp_path)
    assert not any("pwned" in str(t) for t in tables.to_numpy().ravel())


def test_sql_view_per_category(tmp_path):
    store.write_rows([_pred(0)], "predictions", "run-1", root=tmp_path,
                     day=date(2026, 7, 1))
    df = store.query("SELECT count(*) AS n FROM predictions", root=tmp_path)
    assert df["n"].iloc[0] == 1


def test_cosine_recall():
    corpus = pd.DataFrame(
        {
            "text": ["rates up", "hurricane", "orthogonal"],
            "embedding": [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]],
        }
    )
    out = cosine_top_k(np.array([1.0, 0.0]), corpus, k=2)
    assert list(out["text"]) == ["rates up", "hurricane"]
    assert out["similarity"].iloc[0] == pytest.approx(1.0)


def test_cosine_recall_empty_corpus():
    out = cosine_top_k(np.array([1.0, 0.0]), pd.DataFrame(columns=["embedding"]), k=3)
    assert out.empty
