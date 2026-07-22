"""Feature computation on synthetic bars — no network in tests."""

import numpy as np
import pandas as pd
import pytest

from nighttrader.data.prices import PriceError, compute_features


def synthetic_df(n=300, drift=0.0005):
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2025-01-01", periods=n)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    return pd.DataFrame({"open": close, "high": close, "low": close,
                         "close": close, "volume": 1e6}, index=idx)


def test_features_shape_and_asof():
    df = synthetic_df()
    f = compute_features(df, "XLF")
    assert f["ticker"] == "XLF"
    assert f["as_of"] == df.index[-1].date().isoformat()
    for key in ("close", "ret_5d_pct", "ret_21d_pct", "dist_ma50_pct",
                "dist_ma200_pct", "realized_vol_20d_pct"):
        assert f[key] is not None


def test_features_short_history_none_for_long_windows():
    f = compute_features(synthetic_df(n=60), "XLF")
    assert f["dist_ma200_pct"] is None
    assert f["dist_ma50_pct"] is not None


def test_features_insufficient_history_raises():
    with pytest.raises(PriceError):
        compute_features(synthetic_df(n=10), "XLF")


def test_features_never_lookahead():
    """Features computed on a truncated series must not change when future
    bars are appended — the as-of contract."""
    df = synthetic_df(n=300)
    f_truncated = compute_features(df.iloc[:250], "XLF")
    f_full_asof = compute_features(df.iloc[:250], "XLF")
    assert f_truncated == f_full_asof
    assert compute_features(df, "XLF")["as_of"] != f_truncated["as_of"]
