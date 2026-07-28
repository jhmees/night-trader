"""data.json publisher: strict JSON, latest-row selection, empty-lake grace."""

import json
from datetime import UTC, date, datetime

import pandas as pd

from nighttrader.dashboard import build_payload, write_dashboard_json
from nighttrader.memory import store


def _seed(tmp_path, day, ts, close):
    df = pd.DataFrame(
        [{"ticker": "XLF", "as_of": day.isoformat(), "close": close,
          "ret_5d_pct": 1.2, "ret_21d_pct": None, "dist_ma50_pct": float("nan"),
          "dist_ma200_pct": 3.3, "realized_vol_20d_pct": 14.0, "ts": ts}]
    )
    store.write_rows(df, "features", f"run-{day:%Y%m%d}", root=tmp_path, day=day)


def test_payload_latest_row_and_strict_json(tmp_path):
    _seed(tmp_path, date(2026, 7, 1), datetime(2026, 7, 1, tzinfo=UTC).isoformat(), 50.0)
    _seed(tmp_path, date(2026, 7, 2), datetime(2026, 7, 2, tzinfo=UTC).isoformat(), 51.0)
    macro = pd.DataFrame([{"as_of": "2026-07-02", "DGS10": 4.2, "DGS2": 3.9,
                           "FEDFUNDS": 4.1, "VIXCLS": 15.0, "BAMLH0A0HYM2": 3.0,
                           "curve_2s10s": 0.3,
                           "ts": datetime(2026, 7, 2, tzinfo=UTC).isoformat()}])
    store.write_rows(macro, "macro", "run-20260702", root=tmp_path, day=date(2026, 7, 2))

    payload = build_payload(root=tmp_path)
    assert len(payload["features"]) == 1  # latest row per ticker only
    row = payload["features"][0]
    assert row["close"] == 51.0
    assert row["dist_ma50_pct"] is None  # NaN sanitized
    assert payload["macro"]["VIXCLS"] == 15.0
    json.dumps(payload, allow_nan=False)  # must be strict JSON


def test_empty_lake_graceful(tmp_path):
    payload = build_payload(root=tmp_path)
    assert payload["features"] == []
    assert payload["macro"] is None


def test_write_roundtrip(tmp_path):
    _seed(tmp_path, date(2026, 7, 1), datetime(2026, 7, 1, tzinfo=UTC).isoformat(), 50.0)
    out = write_dashboard_json(tmp_path / "data.json", root=tmp_path)
    loaded = json.loads(out.read_text())
    assert loaded["features"][0]["ticker"] == "XLF"
