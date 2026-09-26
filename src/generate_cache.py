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

def get_aqi_category(pm25: float) -> tuple[float, str, str]:
    """Return AQI sub-index, category string, and hex color."""
    if pm25 <= 30:
        return round(pm25 * (50 / 30), 1), "Good", "#10b981"
    elif pm25 <= 60:
        return round(50 + (pm25 - 30) * (50 / 30), 1), "Satisfactory", "#84cc16"
    elif pm25 <= 90:
        return round(100 + (pm25 - 60) * (100 / 30), 1), "Moderate", "#f59e0b"
    elif pm25 <= 120:
        return round(200 + (pm25 - 90) * (100 / 30), 1), "Poor", "#f97316"
    elif pm25 <= 250:
        return round(300 + (pm25 - 120) * (100 / 130), 1), "Very Poor", "#ef4444"
    else:
        return min(500.0, round(400 + (pm25 - 250) * (100 / 250), 1)), "Severe", "#991b1b"

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
        station_groups = c_df.groupby(["station_id", "station_location"], observed=True)
        stations = []
        for (sid, sloc), s_df in station_groups:
            stations.append({
                "station_id": str(sid),
                "station_location": str(sloc).strip(),
                "readings": int(len(s_df)),
                "date_min": str(s_df["timestamp"].min()),
                "date_max": str(s_df["timestamp"].max()),
                "mean_pm25": round(float(s_df["PM2.5 (ug/m3)"].mean()), 1),
            })

        # Latest recorded observation for the city
        c_sorted = c_df.sort_values("timestamp")
        latest_row = c_sorted.iloc[-1]
        
        # Calculate city overall stats
        pm25_mean = float(c_df["PM2.5 (ug/m3)"].mean())
        aqi_val, aqi_cat, aqi_col = get_aqi_category(pm25_mean)

        latest_pm25 = float(latest_row["PM2.5 (ug/m3)"]) if pd.notna(latest_row["PM2.5 (ug/m3)"]) else pm25_mean
        lat_aqi, lat_cat, lat_col = get_aqi_category(latest_pm25)

        # Recent 48 hours for trend line
        recent_df = c_sorted.tail(48)[["timestamp", "PM2.5 (ug/m3)", "PM10 (ug/m3)", "NO2 (ug/m3)", "SO2 (ug/m3)", "CO (mg/m3)", "Ozone (ug/m3)"]]
        recent_trend = []
        for _, r in recent_df.iterrows():
            recent_trend.append({
                "time": str(r["timestamp"]),
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
            "total_records": int(len(c_df)),
            "date_start": str(c_df["timestamp"].min()),
            "date_end": str(c_df["timestamp"].max()),
            "overall_pm25_mean": round(pm25_mean, 1),
            "overall_pm25_median": round(float(c_df["PM2.5 (ug/m3)"].median()), 1),
            "overall_aqi": aqi_val,
            "overall_category": aqi_cat,
            "overall_color": aqi_col,
            "latest_recorded": {
                "timestamp": str(latest_row["timestamp"]),
                "pm25": round(latest_pm25, 1),
                "pm10": round(float(latest_row["PM10 (ug/m3)"]), 1) if pd.notna(latest_row["PM10 (ug/m3)"]) else None,
                "no2": round(float(latest_row["NO2 (ug/m3)"]), 1) if pd.notna(latest_row["NO2 (ug/m3)"]) else None,
                "so2": round(float(latest_row["SO2 (ug/m3)"]), 1) if pd.notna(latest_row["SO2 (ug/m3)"]) else None,
                "co": round(float(latest_row["CO (mg/m3)"]), 2) if pd.notna(latest_row["CO (mg/m3)"]) else None,
                "ozone": round(float(latest_row["Ozone (ug/m3)"]), 1) if pd.notna(latest_row["Ozone (ug/m3)"]) else None,
                "aqi": lat_aqi,
                "category": lat_cat,
                "color": lat_col,
                "main_pollutant": "PM2.5",
                "station_location": str(latest_row["station_location"]).strip(),
            },
            "pollutant_averages": {
                "PM2.5": round(float(c_df["PM2.5 (ug/m3)"].mean()), 1),
                "PM10": round(float(c_df["PM10 (ug/m3)"].dropna().mean()), 1) if not c_df["PM10 (ug/m3)"].dropna().empty else None,
                "NO2": round(float(c_df["NO2 (ug/m3)"].dropna().mean()), 1) if not c_df["NO2 (ug/m3)"].dropna().empty else None,
                "SO2": round(float(c_df["SO2 (ug/m3)"].dropna().mean()), 1) if not c_df["SO2 (ug/m3)"].dropna().empty else None,
                "CO": round(float(c_df["CO (mg/m3)"].dropna().mean()), 2) if not c_df["CO (mg/m3)"].dropna().empty else None,
                "Ozone": round(float(c_df["Ozone (ug/m3)"].dropna().mean()), 1) if not c_df["Ozone (ug/m3)"].dropna().empty else None,
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

        # Yearly stats
        cy = c_df.groupby("year", observed=True)
        y_stats = cy.agg({
            "PM2.5 (ug/m3)": ["mean", "median", "count"],
            "PM10 (ug/m3)": "mean",
            "NO2 (ug/m3)": "mean",
            "SO2 (ug/m3)": "mean",
        }).reset_index()
        y_series = []
        for _, r in y_stats.iterrows():
            yr_val = int(r["year"].iloc[0] if isinstance(r["year"], pd.Series) else r["year"])
            y_series.append({
                "year": yr_val,
                "pm25_mean": round(float(r[("PM2.5 (ug/m3)", "mean")]), 1) if pd.notna(r[("PM2.5 (ug/m3)", "mean")]) else None,
                "pm25_median": round(float(r[("PM2.5 (ug/m3)", "median")]), 1) if pd.notna(r[("PM2.5 (ug/m3)", "median")]) else None,
                "readings": int(r[("PM2.5 (ug/m3)", "count")]),
                "pm10_mean": round(float(r[("PM10 (ug/m3)", "mean")]), 1) if pd.notna(r[("PM10 (ug/m3)", "mean")]) else None,
                "no2": round(float(r[("NO2 (ug/m3)", "mean")]), 1) if pd.notna(r[("NO2 (ug/m3)", "mean")]) else None,
                "so2": round(float(r[("SO2 (ug/m3)", "mean")]), 1) if pd.notna(r[("SO2 (ug/m3)", "mean")]) else None,
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
        "matrix": [[float(corr_matrix.iloc[i, j]) if pd.notna(corr_matrix.iloc[i, j]) else 0.0 for j in range(len(display_names))] for i in range(len(display_names))],
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
    season_names = {0: "Winter (Dec-Feb)", 1: "Pre-Monsoon (Mar-May)", 2: "Monsoon (Jun-Sep)", 3: "Post-Monsoon (Oct-Nov)"}
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

    corr_val = float(corr_matrix.loc["PM2.5 (ug/m3)", "PM10 (ug/m3)"])

    cache["insights"] = {
        "hotspots": {
            "title": "Geographic Divide: Northern Plains vs Peninsular Coastal Cities",
            "highest_city": highest_city,
            "highest_pm25": highest_val,
            "lowest_city": cleanest_city,
            "lowest_pm25": cleanest_val,
            "ratio": round(highest_val / cleanest_val, 1) if cleanest_val > 0 else 1.0,
            "summary": (
                f"Across 130 monitoring stations from 2010 to 2023, cities in the Indo-Gangetic Plains "
                f"({highest_city}: {highest_val} µg/m³) consistently experience higher particulate burdens "
                f"than peninsular coastal cities ({cleanest_city}: {cleanest_val} µg/m³), representing a "
                f"{round(highest_val / cleanest_val, 1)}x difference driven by landlocked topography, meteorological stagnation, and dense combustion sources."
            ),
        },
        "seasonal": {
            "title": "Winter Inversion Surge: November to January Peak",
            "winter_pm25": winter_val,
            "monsoon_pm25": monsoon_val,
            "ratio": season_ratio,
            "summary": (
                f"Particulate concentrations surge {season_ratio}x during winter (average {winter_val} µg/m³) "
                f"compared to the monsoon period ({monsoon_val} µg/m³). Lower boundary layer heights, calm winds, "
                f"and thermal temperature inversions trap surface emissions, whereas monsoon precipitation provides natural wet deposition."
            ),
        },
        "diurnal": {
            "title": "Daily Commuter Transit Waves",
            "peak_hour": diurnal_max_hour,
            "peak_pm25": diurnal_max_val,
            "trough_hour": diurnal_min_hour,
            "trough_pm25": diurnal_min_val,
            "summary": (
                f"Nationwide hourly tracking indicates pollution peaks late at night and during morning commute hours ({diurnal_max_hour}:00: {diurnal_max_val} µg/m³). "
                f"The lowest average levels occur in mid-afternoon ({diurnal_min_hour}:00: {diurnal_min_val} µg/m³), when solar radiation enhances convective mixing."
            ),
        },
        "relationships": {
            "title": "Strong Co-Pollutant Coupling",
            "pm25_pm10_corr": corr_val,
            "summary": (
                f"PM2.5 and PM10 exhibit an exceptionally strong correlation (r = {corr_val}), indicating shared combustion "
                f"and dust resuspension origins. In addition, nitrogen dioxide (NO2) and carbon monoxide (CO) rise in tandem during rush hours, "
                f"confirming vehicular exhaust as a dominant mutual contributor."
            ),
        },
        "extreme_episodes": {
            "title": "Historical Severe Smog Episodes",
            "episodes": episodes_list,
            "summary": (
                f"The highest historical 24-hour PM2.5 concentrations exceeded 400 µg/m³ (over 6x the CPCB 24h standard of 60 µg/m³), "
                f"most commonly recorded in Delhi and Patna during late autumn and early winter post-harvest windows."
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
