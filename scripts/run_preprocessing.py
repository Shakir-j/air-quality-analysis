"""
scripts/run_preprocessing.py
─────────────────────────────
Entry-point for the preprocessing pipeline.

Usage:
    python scripts/run_preprocessing.py
    python scripts/run_preprocessing.py --all   # process all 453 stations

By default processes the top-city subset (~10 major cities) to stay within
RAM constraints on a typical laptop. Use --all for the full dataset (needs 8+ GB RAM).

Output: data/processed/air_quality_processed.parquet
"""

import sys
import argparse
import logging
from pathlib import Path

# Make src importable when running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_loader import load_all_stations
from src.preprocessor import preprocess
from src.config import DATA_PROC

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ── Default city subset — top cities by data volume ───────────────────────────
# These 10 cities cover all major geographic regions and pollution profiles
DEFAULT_CITIES = [
    "Delhi",
    "Mumbai",
    "Bengaluru",
    "Chennai",
    "Lucknow",
    "Hyderabad",
    "Kolkata",
    "Pune",
    "Ahmedabad",
    "Patna",
]


def main():
    parser = argparse.ArgumentParser(description="Run air-quality preprocessing pipeline.")
    parser.add_argument(
        "--all", action="store_true",
        help="Process ALL 453 stations (requires ~8 GB RAM). Default: top-10 cities only."
    )
    parser.add_argument(
        "--cities", nargs="+", default=None,
        help="Specific city names to process (space-separated)."
    )
    args = parser.parse_args()

    DATA_PROC.mkdir(parents=True, exist_ok=True)

    if args.all:
        city_filter = None
        print("Mode: ALL stations (this may take several minutes and ~6-8 GB RAM)...")
    elif args.cities:
        city_filter = args.cities
        print(f"Mode: Custom cities: {city_filter}")
    else:
        city_filter = DEFAULT_CITIES
        print(f"Mode: Top-10 cities: {DEFAULT_CITIES}")

    # ── Load ──────────────────────────────────────────────────────────────────
    raw_df = load_all_stations(city_filter=city_filter, verbose=True)

    # ── Preprocess ────────────────────────────────────────────────────────────
    clean_df = preprocess(raw_df, save=True, verbose=True)

    print(f"\n✅ Preprocessing complete.")
    print(f"   Output: {clean_df.shape[0]:,} rows × {clean_df.shape[1]} columns")
    print(f"   Columns: {list(clean_df.columns)}")


if __name__ == "__main__":
    main()
