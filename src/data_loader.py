"""
src/data_loader.py
──────────────────
Responsible for reading raw station CSVs and combining them into a
single cleaned DataFrame with station metadata attached.

Key design decisions:
  - Processes files one at a time to avoid OOM on 14M-row dataset.
  - Applies a schema union: all files share a common superset of columns;
    missing columns for a given station are filled with NaN.
  - Station metadata (state, city, station_location) is merged in here,
    not downstream — so every row carries location context.
  - Optionally filters to a subset of cities to keep RAM manageable.

Inputs:  data/raw/*.csv  +  data/raw/stations_info.csv
Outputs: pd.DataFrame (in memory, passed to preprocessor)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from src.config import DATA_RAW, STATIONS_FILE, POLLUTANT_COLS, MET_COLS

logger = logging.getLogger(__name__)

# ── Core columns every file must have ────────────────────────────────────────
DATE_COLS = ["From Date", "To Date"]

# All possible data columns across the whole dataset
ALL_DATA_COLS = POLLUTANT_COLS + MET_COLS

# Additional met cols that appear under variant names in some files
VARIANT_MET_COLS = {
    "Temp (degree C)": "AT (degree C)",   # Temp is the same as AT; map to AT
    "WD (degree)":     "WD (deg)",         # variant header for wind direction
}


def load_stations_info() -> pd.DataFrame:
    """Load and return station metadata as a clean DataFrame."""
    df = pd.read_csv(STATIONS_FILE)
    df.columns = df.columns.str.strip()
    df["file_name"] = df["file_name"].str.strip()
    df["state"]     = df["state"].str.strip()
    df["city"]      = df["city"].str.strip()
    df["station_location"] = df["station_location"].str.strip()
    return df


def _read_single_station(filepath: Path, station_id: str) -> pd.DataFrame:
    """
    Read one station CSV and return a standardised DataFrame.

    Standardisation steps:
      1. Parse date columns.
      2. Rename variant column names to canonical names.
      3. Coerce all numeric columns to float32 (memory efficient).
      4. Add station_id column.
    """
    try:
        df = pd.read_csv(filepath, low_memory=False)
    except Exception as e:
        logger.warning(f"Could not read {filepath.name}: {e}")
        return pd.DataFrame()

    # Rename variant column names
    df.rename(columns=VARIANT_MET_COLS, inplace=True)

    # Parse dates — use From Date as the observation timestamp
    df["timestamp"] = pd.to_datetime(df["From Date"], errors="coerce")
    df.drop(columns=["From Date", "To Date"], inplace=True, errors="ignore")

    # Drop rows with unparseable timestamps
    df = df[df["timestamp"].notna()].copy()

    # Keep only known data columns (ignore station-specific extras like CH4, THC)
    keep_cols = ["timestamp"] + [c for c in ALL_DATA_COLS if c in df.columns]
    df = df[keep_cols].copy()

    # Coerce numeric columns to float32 — handle possible duplicate col names
    # by working on the dataframe after deduplicating columns first
    df = df.loc[:, ~df.columns.duplicated()].copy()
    numeric_cols = [c for c in keep_cols if c != "timestamp" and c in df.columns]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col].squeeze(), errors="coerce").astype("float32")

    df["station_id"] = station_id
    return df


def load_all_stations(
    city_filter: Optional[list[str]] = None,
    state_filter: Optional[list[str]] = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Load all (or filtered) station CSVs and return a combined DataFrame.

    Parameters
    ----------
    city_filter  : list of city names to include. None = include all.
    state_filter : list of state names to include. None = include all.
    verbose      : print progress to stdout.

    Returns
    -------
    pd.DataFrame with columns:
        timestamp, <pollutant cols>, <met cols>, station_id,
        state, city, station_location
    """
    stations_meta = load_stations_info()

    # Apply geographic filter
    meta = stations_meta.copy()
    if city_filter:
        meta = meta[meta["city"].isin(city_filter)]
    if state_filter:
        meta = meta[meta["state"].isin(state_filter)]

    if meta.empty:
        raise ValueError("No stations match the provided filter criteria.")

    station_ids = meta["file_name"].tolist()
    total = len(station_ids)
    if verbose:
        print(f"Loading {total} stations...")

    frames = []
    for i, sid in enumerate(station_ids, 1):
        fp = DATA_RAW / f"{sid}.csv"
        if not fp.exists():
            logger.warning(f"File not found: {fp}")
            continue
        df = _read_single_station(fp, sid)
        if df.empty:
            continue
        frames.append(df)
        if verbose and (i % 50 == 0 or i == total):
            print(f"  [{i}/{total}] loaded {sid} ({len(df):,} rows)")

    if not frames:
        raise RuntimeError("No data loaded.")

    combined = pd.concat(frames, ignore_index=True, sort=False)

    # Merge station metadata
    meta_slim = meta[["file_name", "state", "city", "station_location"]].copy()
    combined = combined.merge(
        meta_slim,
        left_on="station_id",
        right_on="file_name",
        how="left",
    ).drop(columns=["file_name"])

    if verbose:
        print(f"Combined dataset: {len(combined):,} rows, {len(combined.columns)} columns")

    return combined
