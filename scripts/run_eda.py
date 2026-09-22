"""
scripts/run_eda.py
──────────────────
Generates all EDA figures and saves them to reports/figures/.
Run after preprocessing is complete.

Usage:
    python scripts/run_eda.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set UTF-8 output on Windows
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.preprocessor import load_processed
from src.eda import (
    plot_pm25_distribution,
    plot_pollutant_boxplots,
    plot_city_comparison,
    plot_monthly_trend,
    plot_seasonal_heatmap,
    plot_correlation_heatmap,
    plot_city_pollutant_heatmap,
    plot_yearly_trend,
    plot_hourly_pattern,
    plot_aqi_distribution,
    plot_month_year_heatmap,
)
from src.config import FIGURES_DIR

FIGURES_DIR.mkdir(parents=True, exist_ok=True)

def save_fig(fig, name: str):
    path = FIGURES_DIR / f"{name}.html"
    fig.write_html(str(path))
    print(f"  Saved: {path.name}")


def main():
    print("Loading processed data...")
    df = load_processed()
    print(f"  {len(df):,} rows loaded.")
    print()

    print("Generating EDA figures...")

    save_fig(plot_pm25_distribution(df),          "01_pm25_distribution")
    save_fig(plot_pollutant_boxplots(df),          "02_pollutant_boxplots")
    save_fig(plot_city_comparison(df),             "03_city_comparison")
    save_fig(plot_monthly_trend(df),               "04_monthly_trend")
    save_fig(plot_seasonal_heatmap(df),            "05_seasonal_heatmap")
    save_fig(plot_correlation_heatmap(df),         "06_correlation_heatmap")
    save_fig(plot_city_pollutant_heatmap(df),      "07_city_pollutant_heatmap")
    save_fig(plot_yearly_trend(df),                "08_yearly_trend")
    save_fig(plot_hourly_pattern(df),              "09_hourly_pattern")
    save_fig(plot_aqi_distribution(df),            "10_aqi_distribution")
    save_fig(plot_month_year_heatmap(df, city="Delhi"), "11_month_year_heatmap_delhi")

    print()
    print(f"All figures saved to: {FIGURES_DIR}")
    print("Phase 3 (EDA) complete.")


if __name__ == "__main__":
    main()
