"""
src/generate_cache.py
─────────────────────
Pre-computes and caches aggregated analytics from the 4.34M rows processed
dataset so the FastAPI backend can respond in <10ms for all web requests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd

from src.config import PROCESSED_FILE
CACHE_DIR = ROOT_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "air_quality_cache.json"

# Coordinates for monitored metropolitan centers
CITY_COORDINATES = {
    "Delhi": {"lat": 28.6139, "lon": 77.2090, "state": "Delhi"},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946, "state": "Karnataka"},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777, "state": "Maharashtra"},
    "Chennai": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu"},
    "Kolkata": {"lat": 22.5726, "lon": 88.3639, "state": "West Bengal"},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "state": "Telangana"},
    "Lucknow": {"lat": 26.8467, "lon": 80.9462, "state": "Uttar Pradesh"},
    "Ahmedabad": {"lat": 23.0225, "lon": 72.5714, "state": "Gujarat"},
    "Patna": {"lat": 25.5941, "lon": 85.1376, "state": "Bihar"},
    "Pune": {"lat": 18.5204, "lon": 73.8567, "state": "Maharashtra"},
}

POLLUTANTS_MAP = {
    "PM2.5": "PM2.5 (ug/m3)",
    "PM10": "PM10 (ug/m3)",
    "NO2": "NO2 (ug/m3)",
    "SO2": "SO2 (ug/m3)",
    "CO": "CO (mg/m3)",
    "Ozone": "Ozone (ug/m3)",
}

from src.aqi import calculate_composite_aqi, calculate_pollutant_subindex

def get_aqi_category(pm25: float) -> tuple[float, str, str]:
    """Return the central PM2.5 sub-index and display metadata."""
    result = calculate_pollutant_subindex("PM2.5", pm25)
    if result is None:
        return 0.0, "Insufficient data", "#94a3b8"
    return result

def compute_cache():
    print("Loading processed dataset...")
    df = pd.read_parquet(PROCESSED_FILE)
    # Filter to only the 10 major metropolitan centers
    df = df[df["city"].isin(CITY_COORDINATES.keys())]
    print(f"Dataset loaded: {len(df):,} rows, {len(df.columns)} columns.")

    cache = {
        "metadata": {
            "total_records": len(df),
            "date_start": str(df["timestamp"].min()),
            "date_end": str(df["timestamp"].max()),
            "total_stations": int(df["station_id"].nunique()),
            "total_cities": int(df["city"].nunique()),
            "cities": sorted(df["city"].unique().tolist()),
            "provenance": "Central Pollution Control Board (CPCB) Ambient Air Quality Network (2010-2023)",
        },
        "cities": {},
        "monthly_trends": {},
        "yearly_trends": {},
        "diurnal_patterns": {},
        "correlations": {},
        "city_pollutant_matrix": {},
        "seasonal_patterns": {},
        "insights": {},
    }

    # ── 1. City & Station Summaries ──────────────────────────────────────────
    print("Computing city & station summaries...")
    for city, c_df in df.groupby("city", observed=True):
        coords = CITY_COORDINATES.get(city, {"lat": 20.5937, "lon": 78.9629, "state": ""})
        station_groups = c_df.groupby(
            ["station_id", "station_location"], observed=True
        )
        stations = []
        station_data = {}

        station_pollutant_columns = {
            "PM2.5": "PM2.5 (ug/m3)",
            "PM10": "PM10 (ug/m3)",
            "NO2": "NO2 (ug/m3)",
            "SO2": "SO2 (ug/m3)",
            "CO": "CO (mg/m3)",
            "O3": "Ozone (ug/m3)",
        }

        for (sid, sloc), s_df in station_groups:
            station_frame = s_df.copy()
            station_frame["timestamp"] = (
                pd.to_datetime(station_frame["timestamp"]).dt.floor("h")
            )
            station_frame["hour"] = station_frame["timestamp"].dt.hour

            station_hourly = (
                station_frame.groupby("timestamp", observed=True)[
                    list(station_pollutant_columns.values())
                ]
                .mean()
                .sort_index()
            )

            valid_pm25 = station_hourly["PM2.5 (ug/m3)"].dropna()
            if valid_pm25.empty:
                continue

            station_latest_time = valid_pm25.index[-1]
            station_latest_row = station_hourly.loc[station_latest_time]

            def station_value(row, column, digits=1):
                value = row[column]
                if pd.isna(value):
                    return None
                return round(float(value), digits)

            # Use real hourly values only; gaps remain missing.
            station_aqi_index = pd.date_range(
                end=station_latest_time, periods=24, freq="h"
            )
            station_aqi_window = station_hourly.reindex(station_aqi_index)

            station_aqi_inputs = {
                pollutant: [
                    None if pd.isna(value) else float(value)
                    for value in station_aqi_window[column].tolist()
                ]
                for pollutant, column in station_pollutant_columns.items()
            }

            station_composite = calculate_composite_aqi(station_aqi_inputs)

            (
                station_pm25_subindex,
                station_pm25_category,
                station_pm25_color,
            ) = get_aqi_category(
                float(station_latest_row["PM2.5 (ug/m3)"])
            )

            # Last 48 clock hours, not simply the last 48 available records.
            trend_index = pd.date_range(
                end=station_latest_time, periods=48, freq="h"
            )
            trend_frame = station_hourly.reindex(trend_index)
            station_trend = []

            for trend_time, row in trend_frame.iterrows():
                station_trend.append({
                    "time": str(trend_time),
                    "pm25": station_value(row, "PM2.5 (ug/m3)"),
                    "pm10": station_value(row, "PM10 (ug/m3)"),
                    "no2": station_value(row, "NO2 (ug/m3)"),
                    "so2": station_value(row, "SO2 (ug/m3)"),
                    "co": station_value(row, "CO (mg/m3)", 2),
                    "ozone": station_value(row, "Ozone (ug/m3)"),
                })

            station_averages = {}
            for pollutant, column in station_pollutant_columns.items():
                values = station_hourly[column].dropna()
                station_averages[pollutant] = (
                    round(float(values.mean()), 1) if not values.empty else None
                )

            hourly_pattern = (
                station_frame.groupby("hour", observed=True)["PM2.5 (ug/m3)"]
                .mean()
                .reindex(range(24))
            )
            station_diurnal = [
                None if pd.isna(value) else round(float(value), 1)
                for value in hourly_pattern.tolist()
            ]

            station_id = str(sid)
            location = str(sloc).strip()

            station_latest = {
                "timestamp": str(station_latest_time),
                "pm25": station_value(station_latest_row, "PM2.5 (ug/m3)"),
                "pm10": station_value(station_latest_row, "PM10 (ug/m3)"),
                "no2": station_value(station_latest_row, "NO2 (ug/m3)"),
                "so2": station_value(station_latest_row, "SO2 (ug/m3)"),
                "co": station_value(station_latest_row, "CO (mg/m3)", 2),
                "ozone": station_value(station_latest_row, "Ozone (ug/m3)"),
                "aqi": station_composite["aqi"],
                "category": station_composite["category"],
                "color": station_composite["color"],
                "composite_aqi": station_composite["aqi"],
                "composite_category": station_composite["category"],
                "composite_color": station_composite["color"],
                "aqi_status": station_composite["status"],
                "pm25_subindex": station_pm25_subindex,
                "pm25_category": station_pm25_category,
                "pm25_color": station_pm25_color,
                "aqi_pollutant_averages": station_composite["pollutant_averages"],
                "aqi_sub_indices": station_composite["sub_indices"],
                "main_pollutant": (
                    station_composite["dominant_pollutant"] or "Unavailable"
                ),
                "station_location": location,
                "observation_type": "station_hourly_observation",
                "station_count_at_timestamp": 1,
                "aqi_basis": station_composite["basis"],
                "pm25_aqi_basis": (
                    "Station-specific hourly PM2.5 sub-index; not composite AQI"
                ),
            }

            stations.append({
                "station_id": station_id,
                "station_location": location,
                "readings": int(len(s_df)),
                "date_min": str(s_df["timestamp"].min()),
                "date_max": str(s_df["timestamp"].max()),
                "mean_pm25": round(
                    float(s_df["PM2.5 (ug/m3)"].mean()), 1
                ),
            })

            station_data[station_id] = {
                "latest_recorded": station_latest,
                "pollutant_averages": station_averages,
                "recent_trend": station_trend,
                "diurnal_pattern": station_diurnal,
            }

        # Build hourly city averages across stations. Each timestamp now
        # represents one city-hour, not an arbitrary station row.
        pollutant_cols = [
            "PM2.5 (ug/m3)", "PM10 (ug/m3)", "NO2 (ug/m3)",
            "SO2 (ug/m3)", "CO (mg/m3)", "Ozone (ug/m3)"
        ]
        city_hour = c_df.copy()
        city_hour["timestamp"] = pd.to_datetime(city_hour["timestamp"]).dt.floor("h")
        city_hourly = (
            city_hour.groupby("timestamp", observed=True)[pollutant_cols]
            .mean()
            .sort_index()
        )
        station_counts = (
            city_hour.groupby("timestamp", observed=True)["station_id"].nunique()
        )

        valid_pm25 = city_hourly["PM2.5 (ug/m3)"].dropna()
        if valid_pm25.empty:
            raise ValueError(f"No valid PM2.5 observations for {city}")

        latest_time = valid_pm25.index[-1]
        latest_row = city_hourly.loc[latest_time]
        latest_station_count = int(station_counts.get(latest_time, 0))

        # Equal-weight stations for long-term city summaries so stations
        # with more records do not automatically dominate the city mean.
        station_means = (
            c_df.groupby("station_id", observed=True)[pollutant_cols].mean()
        )
        pm25_mean = float(station_means["PM2.5 (ug/m3)"].mean())
        pm25_median = float(station_means["PM2.5 (ug/m3)"].median())
        aqi_window_index = pd.date_range(
            end=latest_time, periods=24, freq="h"
        )
        aqi_window_df = city_hourly.reindex(aqi_window_index)
        aqi_column_map = {
            "PM2.5": "PM2.5 (ug/m3)",
            "PM10": "PM10 (ug/m3)",
            "NO2": "NO2 (ug/m3)",
            "SO2": "SO2 (ug/m3)",
            "CO": "CO (mg/m3)",
            "O3": "Ozone (ug/m3)",
        }
        aqi_hourly_values = {}
        for pollutant, column in aqi_column_map.items():
            if column not in aqi_window_df.columns:
                aqi_hourly_values[pollutant] = [None] * 24
            else:
                aqi_hourly_values[pollutant] = [
                    None if pd.isna(value) else float(value)
                    for value in aqi_window_df[column].tolist()
                ]

        composite_aqi = calculate_composite_aqi(aqi_hourly_values)
        aqi_val = composite_aqi["aqi"]
        aqi_cat = composite_aqi["category"]
        aqi_col = composite_aqi["color"]

        latest_pm25 = float(latest_row["PM2.5 (ug/m3)"])
        lat_aqi, lat_cat, lat_col = get_aqi_category(latest_pm25)

        # Use the latest 48 clock hours, inserting nulls for missing hours.
        # Do not fill gaps with made-up measurements.
        recent_index = pd.date_range(end=latest_time, periods=48, freq="h")
        recent_df = city_hourly.reindex(recent_index)
        recent_trend = []
        for ts, r in recent_df.iterrows():
            recent_trend.append({
                "time": str(ts),
                "pm25": round(float(r["PM2.5 (ug/m3)"]), 1) if pd.notna(r["PM2.5 (ug/m3)"]) else None,
                "pm10": round(float(r["PM10 (ug/m3)"]), 1) if pd.notna(r["PM10 (ug/m3)"]) else None,
                "no2": round(float(r["NO2 (ug/m3)"]), 1) if pd.notna(r["NO2 (ug/m3)"]) else None,
                "so2": round(float(r["SO2 (ug/m3)"]), 1) if pd.notna(r["SO2 (ug/m3)"]) else None,
                "co": round(float(r["CO (mg/m3)"]), 2) if pd.notna(r["CO (mg/m3)"]) else None,
                "ozone": round(float(r["Ozone (ug/m3)"]), 1) if pd.notna(r["Ozone (ug/m3)"]) else None,
            })
        cache["cities"][city] = {
            "city": city,
            "state": coords["state"],
            "lat": coords["lat"],
            "lon": coords["lon"],
            "station_count": len(stations),
            "stations": stations,
            "station_data": station_data,
            "total_records": int(len(c_df)),
            "date_start": str(c_df["timestamp"].min()),
            "date_end": str(c_df["timestamp"].max()),
            "overall_pm25_mean": round(pm25_mean, 1),
            "overall_pm25_median": round(pm25_median, 1),
            "overall_aqi": aqi_val,
            "overall_category": aqi_cat,
            "overall_color": aqi_col,
            "overall_aqi_status": composite_aqi["status"],
            "overall_aqi_basis": composite_aqi["basis"],
            "overall_aqi_timestamp": str(latest_time),
            "latest_recorded": {
                "timestamp": str(latest_time),
                "pm25": round(latest_pm25, 1),
                "pm10": round(float(latest_row["PM10 (ug/m3)"]), 1) if pd.notna(latest_row["PM10 (ug/m3)"]) else None,
                "no2": round(float(latest_row["NO2 (ug/m3)"]), 1) if pd.notna(latest_row["NO2 (ug/m3)"]) else None,
                "so2": round(float(latest_row["SO2 (ug/m3)"]), 1) if pd.notna(latest_row["SO2 (ug/m3)"]) else None,
                "co": round(float(latest_row["CO (mg/m3)"]), 2) if pd.notna(latest_row["CO (mg/m3)"]) else None,
                "ozone": round(float(latest_row["Ozone (ug/m3)"]), 1) if pd.notna(latest_row["Ozone (ug/m3)"]) else None,
                "aqi": composite_aqi["aqi"],
                "category": composite_aqi["category"],
                "color": composite_aqi["color"],
                "composite_aqi": composite_aqi["aqi"],
                "composite_category": composite_aqi["category"],
                "composite_color": composite_aqi["color"],
                "aqi_status": composite_aqi["status"],
                "pm25_subindex": lat_aqi,
                "pm25_category": lat_cat,
                "pm25_color": lat_col,
                "aqi_pollutant_averages": composite_aqi["pollutant_averages"],
                "aqi_sub_indices": composite_aqi["sub_indices"],
                "main_pollutant": composite_aqi["dominant_pollutant"] or "Unavailable",
                "station_location": f"City-wide hourly mean ({latest_station_count} stations reporting)",
                "observation_type": "city_hourly_mean",
                "station_count_at_timestamp": latest_station_count,
                "aqi_basis": composite_aqi["basis"],
                "pm25_aqi_basis": "Hourly PM2.5-only sub-index; not a composite AQI",
            },
            "pollutant_averages": {
                "PM2.5": round(float(station_means["PM2.5 (ug/m3)"].mean()), 1) if station_means["PM2.5 (ug/m3)"].notna().any() else None,
                "PM10": round(float(station_means["PM10 (ug/m3)"].mean()), 1) if station_means["PM10 (ug/m3)"].notna().any() else None,
                "NO2": round(float(station_means["NO2 (ug/m3)"].mean()), 1) if station_means["NO2 (ug/m3)"].notna().any() else None,
                "SO2": round(float(station_means["SO2 (ug/m3)"].mean()), 1) if station_means["SO2 (ug/m3)"].notna().any() else None,
                "CO": round(float(station_means["CO (mg/m3)"].mean()), 2) if station_means["CO (mg/m3)"].notna().any() else None,
                "Ozone": round(float(station_means["Ozone (ug/m3)"].mean()), 1) if station_means["Ozone (ug/m3)"].notna().any() else None,
            },
            "recent_trend": recent_trend,
        }

    # ── 2. Historical Monthly & Yearly Trends ─────────────────────────────────
    print("Computing historical monthly & yearly trends...")
    df["year_month"] = df["timestamp"].dt.to_period("M").astype(str)
    
    for city, c_df in df.groupby("city", observed=True):
        cm = c_df.groupby("year_month", observed=True)
        m_stats = cm.agg({
            "PM2.5 (ug/m3)": ["mean", "median"],
            "PM10 (ug/m3)": "mean",
            "NO2 (ug/m3)": "mean",
            "SO2 (ug/m3)": "mean",
            "CO (mg/m3)": "mean",
            "Ozone (ug/m3)": "mean",
        }).reset_index()
        
        m_series = []
        for _, r in m_stats.iterrows():
            m_series.append({
                "period": str(r["year_month"].iloc[0] if isinstance(r["year_month"], pd.Series) else r["year_month"]),
                "pm25_mean": round(float(r[("PM2.5 (ug/m3)", "mean")]), 1) if pd.notna(r[("PM2.5 (ug/m3)", "mean")]) else None,
                "pm25_median": round(float(r[("PM2.5 (ug/m3)", "median")]), 1) if pd.notna(r[("PM2.5 (ug/m3)", "median")]) else None,
                "pm10": round(float(r[("PM10 (ug/m3)", "mean")]), 1) if pd.notna(r[("PM10 (ug/m3)", "mean")]) else None,
                "no2": round(float(r[("NO2 (ug/m3)", "mean")]), 1) if pd.notna(r[("NO2 (ug/m3)", "mean")]) else None,
                "so2": round(float(r[("SO2 (ug/m3)", "mean")]), 1) if pd.notna(r[("SO2 (ug/m3)", "mean")]) else None,
                "co": round(float(r[("CO (mg/m3)", "mean")]), 2) if pd.notna(r[("CO (mg/m3)", "mean")]) else None,
                "ozone": round(float(r[("Ozone (ug/m3)", "mean")]), 1) if pd.notna(r[("Ozone (ug/m3)", "mean")]) else None,
            })
        cache["monthly_trends"][city] = m_series

        # Yearly means and valid-record counts for all six pollutants.
        cy = c_df.groupby("year", observed=True)
        y_stats = cy.agg({
            "PM2.5 (ug/m3)": ["mean", "median", "count"],
            "PM10 (ug/m3)": ["mean", "count"],
            "NO2 (ug/m3)": ["mean", "count"],
            "SO2 (ug/m3)": ["mean", "count"],
            "CO (mg/m3)": ["mean", "count"],
            "Ozone (ug/m3)": ["mean", "count"],
        }).reset_index()

        year_bounds = c_df.groupby("year", observed=True)["timestamp"].agg(["min", "max"])
        stations_by_year = cy["station_id"].nunique()
        city_archive_end = pd.to_datetime(c_df["timestamp"].max())

        y_series = []
        for _, r in y_stats.iterrows():
            yr_val = int(
                r["year"].iloc[0] if isinstance(r["year"], pd.Series) else r["year"]
            )

            def rounded_value(column, stat="mean", digits=1):
                value = r[(column, stat)]
                return round(float(value), digits) if pd.notna(value) else None

            pm25_count = int(r[("PM2.5 (ug/m3)", "count")])
            pm10_count = int(r[("PM10 (ug/m3)", "count")])
            no2_count = int(r[("NO2 (ug/m3)", "count")])
            so2_count = int(r[("SO2 (ug/m3)", "count")])
            co_count = int(r[("CO (mg/m3)", "count")])
            ozone_count = int(r[("Ozone (ug/m3)", "count")])

            is_partial = (
                yr_val == int(city_archive_end.year)
                and city_archive_end < pd.Timestamp(
                    year=yr_val, month=12, day=31, hour=23
                )
            )

            y_series.append({
                "year": yr_val,
                "pm25_mean": rounded_value("PM2.5 (ug/m3)"),
                "pm25_median": rounded_value("PM2.5 (ug/m3)", "median"),
                "readings": pm25_count,
                "pm25_readings": pm25_count,
                "pm10_mean": rounded_value("PM10 (ug/m3)"),
                "pm10_readings": pm10_count,
                "no2": rounded_value("NO2 (ug/m3)"),
                "no2_mean": rounded_value("NO2 (ug/m3)"),
                "no2_readings": no2_count,
                "so2": rounded_value("SO2 (ug/m3)"),
                "so2_mean": rounded_value("SO2 (ug/m3)"),
                "so2_readings": so2_count,
                "co_mean": rounded_value("CO (mg/m3)", digits=2),
                "co_readings": co_count,
                "ozone_mean": rounded_value("Ozone (ug/m3)"),
                "ozone_readings": ozone_count,
                "stations": int(stations_by_year.loc[yr_val]),
                "period_start": str(year_bounds.loc[yr_val, "min"]),
                "period_end": str(year_bounds.loc[yr_val, "max"]),
                "is_partial_year": bool(is_partial),
            })

        cache["yearly_trends"][city] = y_series

    # ── 3. Diurnal (24-Hour) Patterns ─────────────────────────────────────────
    print("Computing diurnal patterns...")
    for city, c_df in df.groupby("city", observed=True):
        h_stats = c_df.groupby("hour", observed=True)["PM2.5 (ug/m3)"].mean()
        cache["diurnal_patterns"][city] = [round(float(v), 1) for v in h_stats.values]
    
    # National diurnal average
    nat_h = df.groupby("hour", observed=True)["PM2.5 (ug/m3)"].mean()
    cache["diurnal_patterns"]["National"] = [round(float(v), 1) for v in nat_h.values]

    # ── 4. Correlation Matrix ─────────────────────────────────────────────────
    print("Computing correlation matrix...")
    corr_cols = [
        "PM2.5 (ug/m3)", "PM10 (ug/m3)", "NO2 (ug/m3)", "SO2 (ug/m3)", 
        "CO (mg/m3)", "Ozone (ug/m3)", "AT (degree C)", "RH (%)", "WS (m/s)"
    ]
    sub_df = df[corr_cols].dropna(how="all")
    corr_matrix = sub_df.corr().round(2)
    display_names = ["PM2.5", "PM10", "NO2", "SO2", "CO", "Ozone", "Temp", "Humidity", "Wind"]
    cache["correlations"] = {
        "labels": display_names,
        "matrix": [
            [
                float(corr_matrix.iloc[i, j])
                if pd.notna(corr_matrix.iloc[i, j])
                else None
                for j in range(len(display_names))
            ]
            for i in range(len(display_names))
        ],
    }

    # ── 5. City x Pollutant Matrix ───────────────────────────────────────────
    print("Computing city x pollutant matrix...")
    poll_cols = ["PM2.5 (ug/m3)", "PM10 (ug/m3)", "NO2 (ug/m3)", "SO2 (ug/m3)", "CO (mg/m3)", "Ozone (ug/m3)"]
    city_poll = df.groupby("city", observed=True)[poll_cols].mean().round(1)
    cache["city_pollutant_matrix"] = {
        "cities": city_poll.index.tolist(),
        "pollutants": ["PM2.5", "PM10", "NO2", "SO2", "CO", "Ozone"],
        "values": [[float(city_poll.loc[c, p]) if pd.notna(city_poll.loc[c, p]) else 0.0 for p in poll_cols] for c in city_poll.index],
    }

    # ── 6. Seasonal Patterns ─────────────────────────────────────────────────
    print("Computing seasonal patterns...")
    season_names = {0: "Winter", 1: "Pre-Monsoon", 2: "Monsoon", 3: "Post-Monsoon"}
    seas_grp = df.groupby(["season_num", "city"], observed=True)["PM2.5 (ug/m3)"].mean().unstack().round(1)
    cache["seasonal_patterns"] = {
        "seasons": [season_names.get(int(i), str(i)) for i in sorted(seas_grp.index.tolist())],
        "cities": seas_grp.columns.tolist(),
        "matrix": [[float(seas_grp.loc[s, c]) if pd.notna(seas_grp.loc[s, c]) else 0.0 for c in seas_grp.columns] for s in sorted(seas_grp.index.tolist())],
    }

    # ── 7. Programmatic Data-Backed Insights ─────────────────────────────────
    print("Computing data-backed insights...")
    city_rank = df.groupby("city", observed=True)["PM2.5 (ug/m3)"].mean().sort_values()
    cleanest_city = city_rank.index[0]
    cleanest_val = round(float(city_rank.iloc[0]), 1)
    highest_city = city_rank.index[-1]
    highest_val = round(float(city_rank.iloc[-1]), 1)

    nat_seasonal = df.groupby("season_num", observed=True)["PM2.5 (ug/m3)"].mean()
    winter_val = round(float(nat_seasonal.get(0, 0)), 1)
    monsoon_val = round(float(nat_seasonal.get(2, 0)), 1)
    season_ratio = round(winter_val / monsoon_val, 2) if monsoon_val > 0 else 1.0

    daily_city = df.groupby(["city", df["timestamp"].dt.date], observed=True)["PM2.5 (ug/m3)"].agg(["mean", "count"])
    daily_city = daily_city[daily_city["count"] >= 12]
    top_episodes = daily_city.sort_values("mean", ascending=False).head(5).reset_index()
    episodes_list = []
    for _, row in top_episodes.iterrows():
        episodes_list.append({
            "city": str(row["city"]),
            "date": str(row["timestamp"]),
            "pm25": round(float(row["mean"]), 1),
            "readings": int(row["count"]),
        })

    diurnal_max_hour = int(nat_h.idxmax())
    diurnal_max_val = round(float(nat_h.max()), 1)
    diurnal_min_hour = int(nat_h.idxmin())
    diurnal_min_val = round(float(nat_h.min()), 1)

    corr_raw = corr_matrix.loc["PM2.5 (ug/m3)", "PM10 (ug/m3)"]
    corr_val = round(float(corr_raw), 2) if pd.notna(corr_raw) else None

    cache["insights"] = {
        "hotspots": {
            "title": "Highest and Lowest City PM2.5 Averages",
            "highest_city": highest_city,
            "highest_pm25": highest_val,
            "lowest_city": cleanest_city,
            "lowest_pm25": cleanest_val,
            "ratio": round(highest_val / cleanest_val, 1) if cleanest_val > 0 else 1.0,
            "summary": (
                f"In the processed historical records, {highest_city} has the highest "
                f"city-average PM2.5 ({highest_val} µg/m³), while {cleanest_city} has "
                f"the lowest ({cleanest_val} µg/m³). These averages describe the available "
                "records; station coverage may differ between cities, and this comparison "
                "does not establish why the cities differ."
            ),
        },
        "seasonal": {
            "title": "Winter–Monsoon PM2.5 Comparison",
            "winter_pm25": winter_val,
            "monsoon_pm25": monsoon_val,
            "ratio": season_ratio,
            "summary": (
                f"The processed records show a winter (December–February) mean of "
                f"{winter_val} µg/m³ and a monsoon (June–September) mean of "
                f"{monsoon_val} µg/m³ (winter-to-monsoon ratio: {season_ratio}x). "
                "This is a descriptive comparison; this calculation does not isolate "
                "the effects of weather, emissions, or other contributing factors."
            ),
        },
        "diurnal": {
            "title": "National Daily PM2.5 Pattern",
            "peak_hour": diurnal_max_hour,
            "peak_pm25": diurnal_max_val,
            "trough_hour": diurnal_min_hour,
            "trough_pm25": diurnal_min_val,
            "summary": (
                f"In the processed historical data, the national hourly mean is highest "
                f"at {diurnal_max_hour}:00 ({diurnal_max_val} µg/m³) and lowest at "
                f"{diurnal_min_hour}:00 ({diurnal_min_val} µg/m³). This describes the "
                "observed time-of-day pattern; it does not establish traffic or other causes."
            ),
        },
        "relationships": {
            "title": "Pollutant Correlations in Historical Data",
            "pm25_pm10_corr": corr_val,
            "summary": (
                (
                    f"Across available pooled historical observations, the Pearson "
                    f"correlation between PM2.5 and PM10 is r = {corr_val:.2f}. "
                    if corr_val is not None
                    else "A PM2.5–PM10 correlation could not be calculated from the available records. "
                )
                + "Correlation describes association, not cause and effect; these "
                "statistics alone do not identify emission sources or prove a traffic effect."
            ),
        },
        "extreme_episodes": {
            "title": "Highest Historical City-Day PM2.5 Means",
            "episodes": episodes_list,
            "summary": (
                "The table ranks city-day mean PM2.5 across available historical records. "
                "Each city-day includes at least 12 readings pooled across available station "
                "records. These values are not necessarily 24 continuous hourly readings "
                "from one station or official 24-hour station averages."
            ),
        },
    }

    print(f"Saving precomputed cache to {CACHE_FILE}...")
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print("Cache generation complete!")
    return cache

if __name__ == "__main__":
    compute_cache()
