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
    """Appending future bars — even wildly different ones — must not change
    the feature row computed as-of an earlier date."""
    df = synthetic_df(n=300)
    as_of = df.index[249]
    f_truncated = compute_features(df.iloc[:250], "XLF")

    # same as-of, but the function now SEES 50 future bars
    f_with_future = compute_features(df, "XLF", as_of=as_of)
    assert f_with_future == f_truncated

    # corrupt the future violently; the as-of row must be identical
    df_evil = df.copy()
    df_evil.loc[df_evil.index[250]:, "close"] = 1e9
    f_evil_future = compute_features(df_evil, "XLF", as_of=as_of)
    assert f_evil_future == f_truncated

    # sanity: without as_of, the extra bars do change the row
    assert compute_features(df, "XLF")["as_of"] != f_truncated["as_of"]
