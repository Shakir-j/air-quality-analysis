"""
src/preprocessor.py
───────────────────
Transforms the raw combined DataFrame into a clean, ML-ready dataset.

Pipeline (in order):
  1. Sort by (station_id, timestamp) — required for lag features later.
  2. Remove duplicate (station_id, timestamp) pairs — keep first.
  3. Set timestamp as index.
  4. Remove impossible negative values for pollutants (replace with NaN).
  5. Cap extreme outliers at scientifically defensible limits.
  6. Forward-fill short gaps (≤ 3 consecutive hours) within each station.
  7. Drop rows where PM2.5 (the target) is still NaN after imputation.
  8. Compute Indian AQI from PM2.5 using CPCB breakpoints.
  9. Add derived temporal columns (year, month, day, hour, season, etc.).
  10. Save to data/processed/air_quality_processed.parquet.

What goes in:  raw combined DataFrame from data_loader.load_all_stations()
What comes out: cleaned DataFrame saved as Parquet (and returned)

Design notes:
  - Forward-fill is capped at 3 hours to avoid fabricating data over
    long sensor outages. Gaps >3h are left as NaN and rows with NaN
    PM2.5 are dropped (they cannot be used as labeled training examples).
  - Outlier caps are based on CPCB monitoring network sensor limits and
    published literature — not chosen to improve model metrics.
  - All operations are per-station group to prevent bleed between stations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.config import (
    DATA_PROC,
    PROCESSED_FILE,
    POLLUTANT_COLS,
    AQI_BREAKPOINTS_PM25,
    TARGET_COL,
)

logger = logging.getLogger(__name__)

# ── Outlier caps (based on CPCB sensor range limits + published extreme events)
OUTLIER_CAPS: dict[str, float] = {
    "PM2.5 (ug/m3)":   500.0,   # Above 500 µg/m³ is beyond CPCB scale
    "PM10 (ug/m3)":    900.0,
    "NO (ug/m3)":      400.0,
    "NO2 (ug/m3)":     400.0,
    "NOx (ppb)":       600.0,
    "NH3 (ug/m3)":     400.0,
    "SO2 (ug/m3)":     800.0,
    "CO (mg/m3)":       50.0,
    "Ozone (ug/m3)":   400.0,
    "Benzene (ug/m3)":  50.0,
    "Toluene (ug/m3)": 200.0,
    "Xylene (ug/m3)":  200.0,
    "RH (%)":          100.0,
    "WS (m/s)":         50.0,
    "AT (degree C)":    55.0,
    "BP (mmHg)":       800.0,
}

# Pollutants that must be >= 0
NON_NEGATIVE_COLS = POLLUTANT_COLS + [
    "RH (%)", "WS (m/s)", "SR (W/mt2)"
]

# Max forward-fill gap (hours)
MAX_FILL_GAP = 3


def _compute_aqi_from_pm25(pm25_series: pd.Series) -> pd.Series:
    """
    Compute Indian AQI sub-index from a PM2.5 series (µg/m³).
    Uses CPCB linear interpolation within breakpoint ranges.
    Values outside the highest breakpoint are capped at 500.

    Returns a float32 Series of AQI values.
    """
    aqi = pd.Series(np.nan, index=pm25_series.index, dtype="float32")

    for c_lo, c_hi, i_lo, i_hi, _ in AQI_BREAKPOINTS_PM25:
        mask = (pm25_series >= c_lo) & (pm25_series <= c_hi)
        aqi[mask] = (
            (pm25_series[mask] - c_lo) / (c_hi - c_lo) * (i_hi - i_lo) + i_lo
        ).astype("float32")

    # Above highest breakpoint → 500
    aqi[pm25_series > 500] = 500.0
    return aqi


def _get_aqi_category(aqi_series: pd.Series) -> pd.Series:
    """Map numeric AQI to CPCB category string."""
    cats = pd.cut(
        aqi_series,
        bins=[0, 50, 100, 200, 300, 400, 500],
        labels=["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"],
        right=True,
    )
    return cats.astype(str)


def _clean_station_group(group: pd.DataFrame) -> pd.DataFrame:
    """
    Apply cleaning steps to a single station's data (sorted by timestamp).
    This is called via groupby.apply() to prevent cross-station bleed.
    """
    g = group.copy().sort_values("timestamp")

    # ── 1. Remove exact duplicates ───────────────────────────────────────────
    g = g.drop_duplicates(subset=["timestamp"]).copy()

    # ── 2. Remove impossible negatives ──────────────────────────────────────
    for col in NON_NEGATIVE_COLS:
        if col in g.columns:
            g.loc[g[col] < 0, col] = np.nan

    # ── 3. Cap outliers ──────────────────────────────────────────────────────
    for col, cap in OUTLIER_CAPS.items():
        if col in g.columns:
            g.loc[g[col] > cap, col] = cap

    # ── 4. Short-gap forward-fill (≤ MAX_FILL_GAP consecutive NaNs) ─────────
    #  We only fill numeric columns — not categorical/metadata.
    numeric_cols = g.select_dtypes(include="number").columns.tolist()
    # Sort by time, ffill limited to MAX_FILL_GAP steps
    g = g.sort_values("timestamp")
    g[numeric_cols] = g[numeric_cols].ffill(limit=MAX_FILL_GAP)

    return g


def preprocess(
    raw_df: pd.DataFrame,
    save: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Full preprocessing pipeline.

    Parameters
    ----------
    raw_df  : Combined raw DataFrame from data_loader.load_all_stations()
    save    : If True, save cleaned data to PROCESSED_FILE (parquet).
    verbose : Print progress.

    Returns
    -------
    Cleaned pd.DataFrame ready for EDA and feature engineering.
    """
    if verbose:
        print(f"Preprocessing {len(raw_df):,} rows...")

    df = raw_df.copy()

    # ── Ensure correct dtypes ────────────────────────────────────────────────
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df[df["timestamp"].notna()].copy()
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    if verbose:
        print(f"  After timestamp validation: {len(df):,} rows")

    # ── Per-station cleaning ─────────────────────────────────────────────────
    if verbose:
        print("  Applying per-station cleaning (negatives, outliers, gap-fill)...")

    cleaned_groups = []
    for sid, group in df.groupby("station_id", sort=False):
        cleaned_groups.append(_clean_station_group(group))

    df = pd.concat(cleaned_groups, ignore_index=True)
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    if verbose:
        print(f"  After per-station cleaning: {len(df):,} rows")

    # ── Drop rows where target (PM2.5) is missing ───────────────────────────
    before = len(df)
    df = df[df[TARGET_COL].notna()].copy()
    after = len(df)
    if verbose:
        print(f"  Dropped {before - after:,} rows with missing PM2.5 -> {after:,} rows remain")

    # ── Add Indian AQI ───────────────────────────────────────────────────────
    df["AQI"] = _compute_aqi_from_pm25(df[TARGET_COL])
    df["AQI_Category"] = _get_aqi_category(df["AQI"])

    # ── Add temporal features ────────────────────────────────────────────────
    df["year"]        = df["timestamp"].dt.year.astype("int16")
    df["month"]       = df["timestamp"].dt.month.astype("int8")
    df["day"]         = df["timestamp"].dt.day.astype("int8")
    df["hour"]        = df["timestamp"].dt.hour.astype("int8")
    df["day_of_week"] = df["timestamp"].dt.dayofweek.astype("int8")   # 0=Mon
    df["is_weekend"]  = (df["day_of_week"] >= 5).astype("int8")

    # Season: meteorological (India-specific)
    # Winter: Dec-Feb, Pre-monsoon: Mar-May, Monsoon: Jun-Sep, Post-monsoon: Oct-Nov
    month_to_season = {
        12: "Winter", 1: "Winter", 2: "Winter",
        3: "Pre-Monsoon", 4: "Pre-Monsoon", 5: "Pre-Monsoon",
        6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon",
        10: "Post-Monsoon", 11: "Post-Monsoon",
    }
    df["season"] = df["month"].map(month_to_season)
    df["season_num"] = df["season"].map(
        {"Winter": 0, "Pre-Monsoon": 1, "Monsoon": 2, "Post-Monsoon": 3}
    ).astype("int8")

    if verbose:
        print("  Added AQI and temporal features.")

    # ── Final dtype optimisation ─────────────────────────────────────────────
    # Keep float32 for all numeric pollutant/met cols (already set in loader)
    # station_id, state, city → categorical
    for cat_col in ["station_id", "state", "city", "station_location", "AQI_Category", "season"]:
        if cat_col in df.columns:
            df[cat_col] = df[cat_col].astype("category")

    # ── Summary stats ────────────────────────────────────────────────────────
    if verbose:
        pm25 = df[TARGET_COL].dropna()
        print(f"\n  === CLEAN DATASET SUMMARY ===")
        print(f"  Rows: {len(df):,}")
        print(f"  Columns: {len(df.columns)}")
        print(f"  Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
        print(f"  Cities: {df['city'].nunique()}")
        print(f"  Stations: {df['station_id'].nunique()}")
        print(f"  PM2.5 — mean: {pm25.mean():.1f}, median: {pm25.median():.1f}, "
              f"min: {pm25.min():.1f}, max: {pm25.max():.1f}")
        aqi_dist = df["AQI_Category"].value_counts()
        print(f"  AQI distribution:\n{aqi_dist.to_string()}")

    # ── Save ─────────────────────────────────────────────────────────────────
    if save:
        DATA_PROC.mkdir(parents=True, exist_ok=True)
        df.to_parquet(PROCESSED_FILE, index=False)
        size_mb = PROCESSED_FILE.stat().st_size / 1_048_576
        if verbose:
            print(f"\n  Saved → {PROCESSED_FILE}  ({size_mb:.1f} MB)")

    return df


def load_processed() -> pd.DataFrame:
    """Load the preprocessed parquet file. Fast alternative to re-running pipeline."""
    if not PROCESSED_FILE.exists():
        raise FileNotFoundError(
            f"Processed file not found: {PROCESSED_FILE}\n"
            "Run scripts/run_preprocessing.py first."
        )
    df = pd.read_parquet(PROCESSED_FILE)
    # Restore categorical dtype for columns that parquet may have serialised as object
    for cat_col in ["station_id", "state", "city", "station_location", "AQI_Category", "season"]:
        if cat_col in df.columns:
            df[cat_col] = df[cat_col].astype("category")
    return df
