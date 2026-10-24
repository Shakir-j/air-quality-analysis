"""
server.py
─────────
FastAPI Application Server for AIRWISE: Air Quality Analysis and Prediction.
Connects the Python data intelligence engine to the consumer web frontend.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import MODELS_DIR

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
CACHE_PATH = ROOT_DIR / "data" / "cache" / "air_quality_cache.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("airwise")

# ── Load In-Memory Analytics Cache ──────────────────────────────────────────
_CACHE: dict[str, Any] = {}

def get_cache() -> dict[str, Any]:
    global _CACHE
    if not _CACHE:
        if not CACHE_PATH.exists():
            logger.info("Cache not found, generating now...")
            from src.generate_cache import compute_cache
            _CACHE = compute_cache()
        else:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _CACHE = json.load(f)
    return _CACHE

# Initialize FastAPI App
app = FastAPI(
    title="AIRWISE API",
    description="Backend environmental intelligence API for Air Quality Analysis & Prediction",
    version="2.0.0",
)

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prevent browser stale caching during local development
@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ── Request / Response Models ───────────────────────────────────────────────
class PredictionRequest(BaseModel):
    city: Optional[str] = "Delhi"
    pm25_current: float = Field(..., ge=0.0, le=1000.0, description="Current recorded PM2.5 in ug/m3")
    pm25_lag_2h: Optional[float] = Field(None, ge=0.0, le=1000.0)
    pm25_lag_3h: Optional[float] = Field(None, ge=0.0, le=1000.0)
    no2: Optional[float] = Field(None, ge=0.0, le=500.0)
    co: Optional[float] = Field(None, ge=0.0, le=50.0)
    so2: Optional[float] = Field(None, ge=0.0, le=300.0)
    ozone: Optional[float] = Field(None, ge=0.0, le=500.0)
    relative_humidity: Optional[float] = Field(None, ge=0.0, le=100.0)
    wind_speed: Optional[float] = Field(None, ge=0.0, le=30.0)
    temperature: Optional[float] = Field(None, ge=-20.0, le=60.0)
    month: Optional[int] = Field(11, ge=1, le=12)
    hour: Optional[int] = Field(18, ge=0, le=23)
    is_weekend: Optional[int] = Field(0, ge=0, le=1)
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="Monday=0 through Sunday=6")


class LivePredictionRequest(BaseModel):
    city: Optional[str] = Field("Delhi", description="Target city for real-data prediction")



# ── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/locations")
def get_locations():
    """Return all 10 monitored cities, station details, coordinates, and overview metrics."""
    cache = get_cache()
    cities_data = []
    for city_name, city_info in cache["cities"].items():
        cities_data.append({
            "city": city_name,
            "state": city_info["state"],
            "lat": city_info["lat"],
            "lon": city_info["lon"],
            "station_count": city_info["station_count"],
            "total_records": city_info["total_records"],
            "date_start": city_info["date_start"],
            "date_end": city_info["date_end"],
            "overall_pm25_mean": city_info["overall_pm25_mean"],
            "overall_pm25_median": city_info["overall_pm25_median"],
            "overall_aqi": city_info["overall_aqi"],
            "overall_category": city_info["overall_category"],
            "overall_color": city_info["overall_color"],
            "latest_recorded": city_info["latest_recorded"],
            "pollutant_averages": city_info["pollutant_averages"],
        })
    # Sort cities by highest overall PM2.5
    cities_data.sort(key=lambda x: x["overall_pm25_mean"], reverse=True)
    return {
        "status": "success",
        "metadata": cache["metadata"],
        "cities": cities_data,
    }


@app.get("/api/air-quality")
def get_air_quality(
    city: str = Query("Delhi", description="City name"),
    station: Optional[str] = Query(None, description="Optional station ID"),
):
    """Return comprehensive air quality snapshot, pollutant breakdown, and recent trend."""
    cache = get_cache()
    if city not in cache["cities"]:
        # Fallback to Delhi if not found
        city = "Delhi"
    
    city_data = cache["cities"][city]
    
    # A station selection must change the returned observation data.
    stations = city_data["stations"]
    requested_station = station.strip() if station else ""
    selected_station = None

    if requested_station and requested_station.lower() != "all":
        for item in stations:
            if (
                item["station_id"] == requested_station
                or item["station_location"] == requested_station
            ):
                selected_station = item
                break

        if selected_station is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"Station '{requested_station}' was not found in {city}.",
            )

        selected_data = city_data.get("station_data", {}).get(
            selected_station["station_id"]
        )
        if selected_data is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail="Historical readings are unavailable for this station.",
            )

        latest_recorded = selected_data["latest_recorded"]
        pollutant_averages = selected_data["pollutant_averages"]
        recent_trend = selected_data["recent_trend"]
        diurnal_pattern = selected_data["diurnal_pattern"]

        # City-level telemetry must not be presented as station telemetry.
        current_live = None
        data_scope = "station"
    else:
        latest_recorded = city_data["latest_recorded"]
        pollutant_averages = city_data["pollutant_averages"]
        recent_trend = city_data["recent_trend"]
        diurnal_pattern = cache["diurnal_patterns"].get(
            city, cache["diurnal_patterns"]["National"]
        )

        from src.live_data import get_current_air_quality
        current_live = get_current_air_quality(city, historical_cache=cache)
        data_scope = "citywide"

    return {
        "status": "success",
        "city": city,
        "state": city_data["state"],
        "lat": city_data["lat"],
        "lon": city_data["lon"],
        "station_count": city_data["station_count"],
        "stations": stations,
        "selected_station": selected_station,
        "data_scope": data_scope,
        "archive_coverage": {
            "start": selected_station.get("date_min") if selected_station else city_data["date_start"],
            "end": selected_station.get("date_max") if selected_station else city_data["date_end"],
        },
        "latest_recorded": latest_recorded,
        "pollutant_averages": pollutant_averages,
        "recent_trend": recent_trend,
        "diurnal_pattern": diurnal_pattern,
        "national_diurnal": cache["diurnal_patterns"]["National"],
        "current_live": current_live,
    }


@app.get("/api/current")
def get_current(city: str = Query("Delhi", description="Target city")):
    """
    Return the latest available air-quality observation and weather data.
    External live requests require AIRWISE_ENABLE_LIVE_DATA to be enabled;
    otherwise, the historical archive baseline is returned.
    """
    from src.live_data import get_current_air_quality
    cache = get_cache()
    live_info = get_current_air_quality(city, historical_cache=cache)
    return {
        "status": "success",
        "data": live_info,
    }


@app.get("/api/trends")
def get_trends(
    city: str = Query("Delhi", description="Target city"),
    pollutant: str = Query("PM2.5", description="Pollutant (PM2.5, PM10, NO2, SO2, CO, Ozone)"),
):
    """Return historical monthly and yearly time-series trends."""
    cache = get_cache()
    if city not in cache["cities"]:
        city = "Delhi"

    monthly = cache["monthly_trends"].get(city, [])
    yearly = cache["yearly_trends"].get(city, [])

    return {
        "status": "success",
        "city": city,
        "pollutant": pollutant,
        "monthly_trend": monthly,
        "yearly_trend": yearly,
    }


@app.get("/api/comparison")
def get_comparison(
    cities: str = Query("Delhi,Mumbai,Bengaluru,Kolkata,Chennai", description="Comma-separated city list"),
    pollutant: str = Query("PM2.5", description="Pollutant name"),
):
    """Compare air quality metrics and seasonal profiles across selected cities."""
    cache = get_cache()
    requested_cities = [c.strip() for c in cities.split(",") if c.strip() in cache["cities"]]
    if not requested_cities:
        requested_cities = ["Delhi", "Mumbai", "Bengaluru", "Chennai", "Kolkata"]

    comparisons = []
    for c in requested_cities:
        c_info = cache["cities"][c]
        comparisons.append({
            "city": c,
            "mean_pm25": c_info["overall_pm25_mean"],
            "median_pm25": c_info["overall_pm25_median"],
            "pollutant_avg": c_info["pollutant_averages"].get(pollutant),
            "aqi": c_info["overall_aqi"],
            "category": c_info["overall_category"],
            "color": c_info["overall_color"],
            "stations": c_info["station_count"],
        })

    comparisons.sort(
        key=lambda item: (
            item["pollutant_avg"] is None,
            -(item["pollutant_avg"] if item["pollutant_avg"] is not None else 0.0),
        )
    )

    return {
        "status": "success",
        "pollutant": pollutant,
        "cities": comparisons,
        "correlations": cache["correlations"],
        "city_pollutant_matrix": cache["city_pollutant_matrix"],
        "seasonal_patterns": cache["seasonal_patterns"],
    }


@app.get("/api/insights")
def get_insights():
    """Return verified data-backed insights on hotspots, seasonal spikes, commuter waves, and smog episodes."""
    cache = get_cache()
    return {
        "status": "success",
        "metadata": cache["metadata"],
        "insights": cache["insights"],
        "diurnal_patterns": cache["diurnal_patterns"],
        "seasonal_patterns": cache["seasonal_patterns"],
        "city_pollutant_matrix": cache["city_pollutant_matrix"],
        "correlations": cache["correlations"],
    }


@app.post("/api/prediction")
def predict_air_quality(req: PredictionRequest):
    """Predict next-hour PM2.5 and calculate its PM2.5-derived sub-index."""
    try:
        from src.predictor import predict_from_simple_inputs, compute_aqi_from_pm25_scalar, AQI_CATEGORIES
        
        target_month = req.month if req.month is not None else 11
        target_hour = req.hour if req.hour is not None else 18
        if req.day_of_week is not None:
            target_weekday = req.day_of_week
        else:
            target_weekday = 5 if req.is_weekend else 2
        target_is_weekend = int(target_weekday >= 5)
        season_by_month = {
            12: 0, 1: 0, 2: 0,
            3: 1, 4: 1, 5: 1,
            6: 2, 7: 2, 8: 2, 9: 2,
            10: 3, 11: 3,
        }

        result = predict_from_simple_inputs(
            pm25_current=req.pm25_current,
            pm25_lag_2h=req.pm25_lag_2h,
            pm25_lag_3h=req.pm25_lag_3h,
            hour=target_hour,
            month=target_month,
            day_of_week=target_weekday,
            season_num=season_by_month[target_month],
            is_weekend=target_is_weekend,
            no2=req.no2,
            co=req.co,
            so2=req.so2,
            ozone=req.ozone,
            relative_humidity=req.relative_humidity,
            wind_speed=req.wind_speed,
            temperature=req.temperature,
        )
        return {
            "status": "success",
            "predicted_pm25": result["predicted_pm25"],
            "predicted_aqi": result["predicted_aqi"],
            "aqi_category": result["aqi_category"],
            "color": result["color"],
            "badge_bg": result["badge_bg"],
            "advisory": result["advisory"],
            "precautions": result["precautions"],
            "provenance": "Model prediction (1-hour ahead forecast)",
        }
    except Exception as e:
        logger.exception("PM2.5 model inference failed")
        raise HTTPException(
            status_code=503,
            detail=(
                "PM2.5 prediction is temporarily unavailable because model "
                "inference failed. Check model artifacts and retry."
            ),
        ) from e


@app.post("/api/prediction/live")
def predict_from_live(req: LivePredictionRequest):
    """
    Generate next-hour PM2.5 prediction using current real-world observations.
    Bridges live CPCB sensor telemetry and Open-Meteo weather to the XGBoost model.
    """
    try:
        from src.live_data import get_current_air_quality
        from src.predictor import predict_from_live_observation

        cache = get_cache()
        target_city = req.city or "Delhi"
        live_info = get_current_air_quality(target_city, historical_cache=cache)
        forecast = predict_from_live_observation(live_info)

        return {
            "status": "success",
            "forecast": forecast,
            "input_telemetry": live_info,
            "predicted_pm25": forecast["predicted_pm25"],
            "predicted_aqi": forecast["predicted_aqi"],
            "aqi_category": forecast["aqi_category"],
            "forecast_target_time": forecast.get("forecast_target_time"),
            "forecast_horizon_hours": 1,
            "current_pm25": forecast.get("current_pm25"),
            "delta_pm25": forecast.get("delta_pm25"),
        }
    except Exception as e:
        logger.error(f"Live prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ── Mount Frontend Static Assets ─────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/privacy-policy")
def serve_privacy_policy():
    return FileResponse(FRONTEND_DIR / "privacy-policy.html")


@app.get("/terms")
def serve_terms():
    return FileResponse(FRONTEND_DIR / "terms.html")


if __name__ == "__main__":
    import uvicorn
    # Warm up cache before listening
    get_cache()
    print("Starting AIRWISE Web Application on http://127.0.0.1:8000...")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
