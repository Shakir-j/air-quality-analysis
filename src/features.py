"""
src/features.py
───────────────
Feature engineering for the air-quality prediction model.

Target:  PM2.5 (ug/m3) — 1-hour-ahead value at the same station.

Leakage prevention strategy:
  - All features are based on PAST observations only.
  - Lag features use shift(n) within each station group: lag-1 is the
    previous hour's PM2.5, which would be known at prediction time.
  - Rolling statistics are computed on the past window (shift before rolling
    is NOT needed because pandas rolling excludes the current row with
    min_periods alignment; we use closed='left' to be explicit).
  - The target column is the RAW PM2.5 at the current timestamp (t).
  - At prediction time: input = features at t-1 (all lags/rollies already 
    computed), output = PM2.5 at t.

Feature groups created:
  A. Temporal        — year, month, hour, day_of_week, season_num, is_weekend
  B. Pollutant lags  — PM2.5_lag_1h, 2h, 3h, 6h, 12h, 24h (per station)
  C. Rolling stats   — PM2.5 rolling mean/std over 3h, 6h, 24h (per station)
  D. Co-pollutants   — NO2, CO, SO2, Ozone (lagged 1h to avoid leakage)
  E. Met variables   — RH, WS, AT, SR (current — met data at t is observable)

What goes in:  clean DataFrame from preprocessor.load_processed()
What comes out: (X, y, metadata_df) ready for model training
"""

from __future__ import annotations

import warnings
import numpy as np
import pandas as pd

from src.config import TARGET_COL, RANDOM_STATE

# Suppress FutureWarning for observed= in pandas groupby
warnings.filterwarnings("ignore", category=FutureWarning)

# ── Feature definitions ───────────────────────────────────────────────────────
LAG_HOURS    = [1, 2, 3, 6, 12, 24]
ROLLING_WINS = [3, 6, 24]

# Co-pollutants to include (1-hour lagged to avoid leakage)
CO_POLL_COLS = [
    "NO2 (ug/m3)",
    "CO (mg/m3)",
    "SO2 (ug/m3)",
    "Ozone (ug/m3)",
    "NOx (ppb)",
]

# Meteorological columns (current-hour values — observable at prediction time)
MET_FEATURE_COLS = [
    "RH (%)",
    "WS (m/s)",
    "AT (degree C)",
    "SR (W/mt2)",
    "BP (mmHg)",
]

# Base temporal columns
TEMPORAL_COLS = [
    "year", "month", "hour", "day_of_week", "season_num", "is_weekend"
]


def _add_lag_features(group: pd.DataFrame) -> pd.DataFrame:
    """Add PM2.5 lag features for a single station group (sorted by time)."""
    for lag in LAG_HOURS:
        group[f"pm25_lag_{lag}h"] = group[TARGET_COL].shift(lag)
    return group


def _add_rolling_features(group: pd.DataFrame) -> pd.DataFrame:
    """Add rolling mean/std of PM2.5 for a single station group."""
    for win in ROLLING_WINS:
        # shift(1) before rolling to exclude current row (leakage prevention)
        shifted = group[TARGET_COL].shift(1)
        group[f"pm25_roll_mean_{win}h"] = (
            shifted.rolling(window=win, min_periods=1).mean()
        )
        group[f"pm25_roll_std_{win}h"] = (
            shifted.rolling(window=win, min_periods=1).std()
        )
    return group


def _add_copollutant_lags(group: pd.DataFrame) -> pd.DataFrame:
    """Add 1-hour lagged co-pollutant values (leakage-safe)."""
    for col in CO_POLL_COLS:
        if col in group.columns:
            short = col.split(" ")[0].lower()
            group[f"{short}_lag_1h"] = group[col].shift(1)
    return group


def build_features(
    df: pd.DataFrame,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Build the ML feature matrix from the clean processed DataFrame.

    Parameters
    ----------
    df      : clean DataFrame from preprocessor.load_processed()
    verbose : print progress

    Returns
    -------
    X        : pd.DataFrame — feature matrix
    y        : pd.Series   — target (PM2.5 at time t)
    meta     : pd.DataFrame — [timestamp, station_id, city] for analysis
    """
    if verbose:
        print(f"Building features from {len(df):,} rows...")

    # Sort within each station by time — critical for lag correctness
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    # Per-station operations
    groups = []
    for sid, group in df.groupby("station_id", observed=True, sort=False):
        group = group.copy()
        group = _add_lag_features(group)
        group = _add_rolling_features(group)
        group = _add_copollutant_lags(group)
        groups.append(group)

    df_feat = pd.concat(groups, ignore_index=True)

    # ── Assemble feature list ─────────────────────────────────────────────────
    lag_cols     = [f"pm25_lag_{l}h" for l in LAG_HOURS]
    roll_cols    = [f"pm25_roll_mean_{w}h" for w in ROLLING_WINS] + \
                   [f"pm25_roll_std_{w}h" for w in ROLLING_WINS]
    copoll_cols  = [c for c in df_feat.columns if c.endswith("_lag_1h") and "pm25" not in c]
    met_cols     = [c for c in MET_FEATURE_COLS if c in df_feat.columns]
    temporal_cols = [c for c in TEMPORAL_COLS if c in df_feat.columns]

    feature_cols = temporal_cols + lag_cols + roll_cols + copoll_cols + met_cols

    if verbose:
        print(f"  Feature groups:")
        print(f"    Temporal:      {len(temporal_cols)} — {temporal_cols}")
        print(f"    PM2.5 lags:    {len(lag_cols)}")
        print(f"    Rolling stats: {len(roll_cols)}")
        print(f"    Co-pollutants: {len(copoll_cols)}")
        print(f"    Meteorology:   {len(met_cols)}")
        print(f"  Total features:  {len(feature_cols)}")

    # Target
    y = df_feat[TARGET_COL].copy()

    # Metadata (for error analysis, not for model)
    meta = df_feat[["timestamp", "station_id", "city"]].copy()

    # Feature matrix
    X = df_feat[feature_cols].copy()

    # Drop rows where target is NaN (shouldn't be any after preprocessing,
    # but lag ops can reintroduce them at group boundaries)
    valid_mask = y.notna() & X[lag_cols].notna().all(axis=1)
    X = X[valid_mask].reset_index(drop=True)
    y = y[valid_mask].reset_index(drop=True)
    meta = meta[valid_mask].reset_index(drop=True)

    if verbose:
        print(f"  Rows after dropping lag-NaN boundary rows: {len(X):,}")

    return X, y, meta


def time_aware_split(
    X: pd.DataFrame,
    y: pd.Series,
    meta: pd.DataFrame,
    train_end: str,
    val_end: str,
) -> tuple:
    """
    Chronological train / validation / test split.

    Parameters
    ----------
    X, y, meta     : feature matrix, target, metadata (all same index)
    train_end      : inclusive end date for training set (e.g. "2021-12-31")
    val_end        : inclusive end date for validation set (e.g. "2022-06-30")

    Returns
    -------
    (X_train, X_val, X_test, y_train, y_val, y_test, meta_train, meta_val, meta_test)
    """
    ts = pd.to_datetime(meta["timestamp"])

    train_mask = ts <= pd.Timestamp(train_end)
    val_mask   = (ts > pd.Timestamp(train_end)) & (ts <= pd.Timestamp(val_end))
    test_mask  = ts > pd.Timestamp(val_end)

    return (
        X[train_mask].reset_index(drop=True),
        X[val_mask].reset_index(drop=True),
        X[test_mask].reset_index(drop=True),
        y[train_mask].reset_index(drop=True),
        y[val_mask].reset_index(drop=True),
        y[test_mask].reset_index(drop=True),
        meta[train_mask].reset_index(drop=True),
        meta[val_mask].reset_index(drop=True),
        meta[test_mask].reset_index(drop=True),
    )
