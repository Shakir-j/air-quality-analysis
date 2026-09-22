"""
tests/test_features.py
──────────────────────
Unit tests for feature engineering, leakage prevention, and chronological splitting.
"""

import numpy as np
import pandas as pd
import pytest

from src.features import (
    _add_lag_features,
    _add_rolling_features,
    time_aware_split,
    LAG_HOURS,
    ROLLING_WINS,
)
from src.config import TARGET_COL


def test_lag_features_shift():
    """Verify that lag features represent strictly historical values (shift n)."""
    df = pd.DataFrame({
        TARGET_COL: [10.0, 20.0, 30.0, 40.0, 50.0],
    })
    res = _add_lag_features(df)

    # lag_1h at index 1 should be value at index 0 (10.0)
    assert pd.isna(res["pm25_lag_1h"].iloc[0])
    assert res["pm25_lag_1h"].iloc[1] == 10.0
    assert res["pm25_lag_1h"].iloc[2] == 20.0

    # lag_2h at index 2 should be value at index 0 (10.0)
    assert pd.isna(res["pm25_lag_2h"].iloc[0])
    assert pd.isna(res["pm25_lag_2h"].iloc[1])
    assert res["pm25_lag_2h"].iloc[2] == 10.0


def test_rolling_features_leakage_free():
    """Verify rolling statistics exclude current observation to prevent target leakage."""
    df = pd.DataFrame({
        TARGET_COL: [10.0, 20.0, 30.0, 40.0, 50.0],
    })
    res = _add_rolling_features(df)

    # At index 1, shifted rolling mean of 3h should be based only on index 0
    assert res["pm25_roll_mean_3h"].iloc[1] == 10.0
    # At index 2, mean of index 0 (10) and index 1 (20) = 15.0
    assert res["pm25_roll_mean_3h"].iloc[2] == 15.0


def test_time_aware_chronological_split():
    """Verify zero overlap and strict chronological ordering across train, val, and test."""
    dates = pd.date_range("2021-01-01", "2023-01-01", freq="D")
    n = len(dates)

    X = pd.DataFrame({"feat1": np.arange(n)})
    y = pd.Series(np.arange(n))
    meta = pd.DataFrame({"timestamp": dates, "station_id": ["ST01"] * n, "city": ["Delhi"] * n})

    (X_tr, X_val, X_te,
     y_tr, y_val, y_te,
     m_tr, m_val, m_te) = time_aware_split(X, y, meta, "2021-12-31", "2022-06-30")

    # Verify chronological bounds
    assert pd.to_datetime(m_tr["timestamp"]).max() <= pd.Timestamp("2021-12-31")
    assert pd.to_datetime(m_val["timestamp"]).min() > pd.Timestamp("2021-12-31")
    assert pd.to_datetime(m_val["timestamp"]).max() <= pd.Timestamp("2022-06-30")
    assert pd.to_datetime(m_te["timestamp"]).min() > pd.Timestamp("2022-06-30")

    # Verify partition sum equals total
    assert len(X_tr) + len(X_val) + len(X_te) == n
