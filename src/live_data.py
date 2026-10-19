"""
src/live_data.py
────────────────
Retrieves real-time ambient air quality and meteorological observations for
the 10 supported Indian metropolitan centers.

Data Sources:
  1. Primary Air Quality: Central Pollution Control Board (CPCB) real-time CAAQMS
     network via Open Government Data (OGD) Platform India (data.gov.in resource
     3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69).
  2. Ambient Meteorology: Open-Meteo open environmental API (temperature,
     humidity, wind speed, surface pressure).
  3. Offline Fallback: Precomputed CPCB historical dataset cache with explicit
     offline/provenance tagging.

Features:
  - In-memory TTL caching (15 minutes) to respect rate limits and reduce latency.
  - Transparent error, timeout, and HTTP 429 (rate-limit) handling.
  - Clear distinction between observation timestamp and retrieval timestamp.
  - CPCB PM2.5 sub-index calculation with official piecewise linear breakpoints.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Optional

from src.generate_cache import CITY_COORDINATES
from src.predictor import AQI_CATEGORIES, compute_aqi_from_pm25_scalar

logger = logging.getLogger("airwise.live_data")

# Official data.gov.in CPCB CAAQMS Resource ID
DATA_GOV_IN_RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
DATA_GOV_IN_BASE_URL = f"https://api.data.gov.in/resource/{DATA_GOV_IN_RESOURCE_ID}"

# Default public development key; overridden if DATA_GOV_IN_API_KEY is in environment
DEFAULT_DATA_GOV_IN_KEY = ""  # Configure the key locally.

# Cache TTL: 15 minutes (900 seconds)
CACHE_TTL_SECONDS = 900

# In-memory storage for live responses: city -> {timestamp, data}
_LIVE_CACHE: dict[str, dict[str, Any]] = {}


def _get_api_key() -> str:
    """Read the OGD API key from the environment or local .env.local file."""
    key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    if key:
        return key

    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env.local"
    )
    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() == "DATA_GOV_IN_API_KEY":
                    return value.strip().strip("\"").strip("'")
    except OSError:
        pass

    return ""


def _fetch_live_cpcb_city(city: str, timeout: int = 6) -> Optional[dict[str, Any]]:
    """
    Fetch live station records from data.gov.in CPCB resource.
    Returns parsed dictionary of pollutants and station metadata, or None on failure.
    """
    api_key = _get_api_key()
    params = urllib.parse.urlencode({
        "api-key": api_key,
        "format": "json",
        "filters[city]": city,
        "limit": 30,
    })
    url = f"{DATA_GOV_IN_BASE_URL}?{params}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AIRWISE-AirQuality/2.0 (University Research Project)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                body = response.read().decode("utf-8", errors="replace")
                data = json.loads(body)
                records = data.get("records", [])
                if not records:
                    return None

                # Aggregate station observations
                pollutants: dict[str, float] = {}
                station_names = set()
                latest_update = ""

                for r in records:
                    pollutant_id = str(r.get("pollutant_id", "")).strip().upper()
                    station_name = str(r.get("station", "")).strip()
                    if station_name:
                        station_names.add(station_name)

                    last_up = str(r.get("last_update", "")).strip()
                    if last_up and not latest_update:
                        latest_update = last_up

                    avg_val = r.get("avg_value") or r.get("pollutant_avg") or r.get("value")
                    try:
                        val_float = float(avg_val) if avg_val is not None and avg_val != "" else None
                    except (ValueError, TypeError):
                        val_float = None

                    if val_float is not None and val_float >= 0:
                        # Map common pollutant names
                        if pollutant_id in ("PM2.5", "PM25"):
                            pollutants["PM2.5"] = val_float
                        elif pollutant_id in ("PM10",):
                            pollutants["PM10"] = val_float
                        elif pollutant_id in ("NO2",):
                            pollutants["NO2"] = val_float
                        elif pollutant_id in ("SO2",):
                            pollutants["SO2"] = val_float
                        elif pollutant_id in ("CO",):
                            pollutants["CO"] = val_float
                        elif pollutant_id in ("OZONE", "O3"):
                            pollutants["Ozone"] = val_float
                        elif pollutant_id in ("NH3",):
                            pollutants["NH3"] = val_float

                chosen_station = list(station_names)[0] if station_names else f"{city} CAAQMS Station"

                return {
                    "station": chosen_station,
                    "last_update": latest_update,
                    "pollutants": pollutants,
                }
    except urllib.error.HTTPError as e:
        logger.warning(f"data.gov.in HTTP error for {city}: {e.code} {e.reason}")
    except Exception as e:
        logger.warning(f"data.gov.in fetch failed for {city}: {e}")

    return None


def _fetch_live_meteorology(city: str, timeout: int = 5) -> Optional[dict[str, float]]:
    """
    Fetch current ambient temperature, humidity, wind speed, and pressure
    from Open-Meteo for the city's coordinates.
    """
    coords = CITY_COORDINATES.get(city)
    if not coords:
        return None

    lat, lon = coords["lat"], coords["lon"]
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,surface_pressure",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AIRWISE-AirQuality/2.0"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                d = json.loads(response.read().decode("utf-8", errors="replace"))
                cur = d.get("current", {})
                return {
                    "temperature": round(float(cur.get("temperature_2m", 25.0)), 1),
                    "relative_humidity": round(float(cur.get("relative_humidity_2m", 60.0)), 1),
                    "wind_speed": round(float(cur.get("wind_speed_10m", 1.5)), 1),
                    "pressure": round(float(cur.get("surface_pressure", 1013.0)), 1),
                }
    except Exception as e:
        logger.warning(f"Open-Meteo fetch failed for {city}: {e}")

    return None


def _get_historical_fallback(city: str, historical_cache: dict[str, Any]) -> dict[str, Any]:
    """
    Construct safe offline fallback from precomputed historical cache.
    Clearly marks data as historical archive rather than active live telemetry.
    """
    city_info = historical_cache.get("cities", {}).get(city, {})
    latest = city_info.get("latest_recorded", {})
    avgs = city_info.get("pollutant_averages", {})
    coords = CITY_COORDINATES.get(city, {"lat": 28.6139, "lon": 77.2090, "state": ""})

    pm25_val = latest.get("PM2.5 (ug/m3)") or latest.get("pm25") or city_info.get("overall_pm25_mean", 50.0)
    aqi_subindex, cat = compute_aqi_from_pm25_scalar(pm25_val)
    cat_meta = AQI_CATEGORIES.get(cat, AQI_CATEGORIES["Moderate"])

    now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    obs_time = str(city_info.get("date_end", "2023-03-31 23:00:00"))

    pm10_val = round(float(latest.get("PM10 (ug/m3)") or latest.get("pm10") or avgs.get("PM10", 100.0)), 1)
    no2_val = round(float(latest.get("NO2 (ug/m3)") or latest.get("no2") or avgs.get("NO2", 30.0)), 1)
    so2_val = round(float(latest.get("SO2 (ug/m3)") or latest.get("so2") or avgs.get("SO2", 12.0)), 1)
    co_val = round(float(latest.get("CO (mg/m3)") or latest.get("co") or avgs.get("CO", 1.0)), 2)
    ozone_val = round(float(latest.get("Ozone (ug/m3)") or latest.get("ozone") or avgs.get("Ozone", 35.0)), 1)

    source_text = "CPCB CAAQMS Historical Archive (Offline Baseline)"
    attribution_text = "Central Pollution Control Board (CPCB) / MoEFCC"
    type_label = "Historical CPCB Archive Record"

    return {
        "city": city,
        "state": coords["state"],
        "station_name": f"{city} Historic CPCB Average",
        "is_live": False,
        "status": "historical_fallback",
        "status_message": "Live API currently unreachable or rate-limited. Displaying latest recorded observation from CPCB Historical Archive.",
        "observation_time": obs_time,
        "retrieval_time": now_iso,
        "source_name": source_text,
        "data_source": source_text,
        "source_attribution": attribution_text,
        "pollutants": {
            "PM2.5": round(float(pm25_val), 1),
            "PM10": pm10_val,
            "NO2": no2_val,
            "SO2": so2_val,
            "CO": co_val,
            "Ozone": ozone_val,
        },
        "pm25": round(float(pm25_val), 1),
        "pm10": pm10_val,
        "no2": no2_val,
        "so2": so2_val,
        "co": co_val,
        "ozone": ozone_val,
        "weather": {
            "temperature": 25.0,
            "relative_humidity": 60.0,
            "wind_speed": 1.5,
            "pressure": 1013.0,
        },
        "temperature": 25.0,
        "humidity": 60.0,
        "wind_speed": 1.5,
        "pressure": 1013.0,
        "aqi": aqi_subindex,
        "pm25_subindex": aqi_subindex,
        "category": cat,
        "aqi_category": cat,
        "color": cat_meta["color"],
        "aqi_color": cat_meta["color"],
        "aqi_badge_bg": cat_meta["badge_bg"],
        "aqi_type": type_label,
        "aqi_type_label": type_label,
        "advisory": cat_meta["advisory"],
        "precautions": cat_meta["precautions"],
    }


def get_current_air_quality(
    city: str,
    historical_cache: Optional[dict[str, Any]] = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Main entry-point for current air quality.
    Checks 15-minute in-memory cache, attempts live fetch from data.gov.in + Open-Meteo,
    and falls back to historical cache if needed.
    """
    if city not in CITY_COORDINATES:
        city = "Delhi"

    # Auto-load historical cache if not explicitly provided
    if historical_cache is None:
        try:
            from server import get_cache
            historical_cache = get_cache()
        except Exception:
            try:
                import json
                with open("data/cache/air_quality_cache.json", "r", encoding="utf-8") as f:
                    historical_cache = json.load(f)
            except Exception:
                pass

    now = datetime.datetime.now()
    now_ts = now.timestamp()
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S")

    live_enabled = os.environ.get(
        "AIRWISE_ENABLE_LIVE_DATA", "0"
    ).strip().lower() in {"1", "true", "yes", "on"}

    # 1. Reuse the in-memory cache only when live data is enabled.
    cached_entry = _LIVE_CACHE.get(city)
    if live_enabled and not force_refresh and cached_entry:
        cached_ts = cached_entry.get("cached_at") or cached_entry.get("timestamp", now_ts)
        age = now_ts - cached_ts
        if age < CACHE_TTL_SECONDS:
            res = dict(cached_entry.get("data", cached_entry))
            res["retrieval_time"] = cached_entry.get("retrieval_time", now_iso)
            res["cache_age_seconds"] = round(age)
            return res

    # 2. External requests are opt-in; dataset-only mode is the default.
    if live_enabled:
        cpcb_live = _fetch_live_cpcb_city(city)
        weather_live = _fetch_live_meteorology(city)
    else:
        cpcb_live = None
        weather_live = None

    if cpcb_live and cpcb_live.get("pollutants") and "PM2.5" in cpcb_live["pollutants"]:
        coords = CITY_COORDINATES[city]
        pm25 = float(cpcb_live["pollutants"]["PM2.5"])
        aqi_subindex, cat = compute_aqi_from_pm25_scalar(pm25)
        cat_meta = AQI_CATEGORIES.get(cat, AQI_CATEGORIES["Moderate"])

        obs_time = cpcb_live.get("last_update") or now_iso
        weather_dict = weather_live or {
            "temperature": 25.0,
            "relative_humidity": 60.0,
            "wind_speed": 1.5,
            "pressure": 1013.0,
        }

        source_name = "Central Pollution Control Board (CPCB) via data.gov.in"
        source_attribution = "Central Pollution Control Board (CPCB) / MoEFCC"
        aqi_type = "PM2.5 Sub-Index (CPCB Breakpoint Formula)"

        result = {
            "city": city,
            "state": coords["state"],
            "station_name": cpcb_live["station"],
            "is_live": True,
            "status": "live",
            "status_message": "Real-time observation retrieved from CPCB continuous monitoring network.",
            "observation_time": obs_time,
            "retrieval_time": now_iso,
            "source_name": source_name,
            "data_source": source_name,
            "source_attribution": source_attribution,
            "pollutants": cpcb_live["pollutants"],
            "pm25": pm25,
            "pm10": cpcb_live["pollutants"].get("PM10"),
            "no2": cpcb_live["pollutants"].get("NO2"),
            "so2": cpcb_live["pollutants"].get("SO2"),
            "co": cpcb_live["pollutants"].get("CO"),
            "ozone": cpcb_live["pollutants"].get("Ozone"),
            "weather": weather_dict,
            "temperature": weather_dict.get("temperature"),
            "humidity": weather_dict.get("relative_humidity"),
            "wind_speed": weather_dict.get("wind_speed"),
            "pressure": weather_dict.get("pressure"),
            "aqi": aqi_subindex,
            "pm25_subindex": aqi_subindex,
            "category": cat,
            "aqi_category": cat,
            "color": cat_meta["color"],
            "aqi_color": cat_meta["color"],
            "aqi_badge_bg": cat_meta["badge_bg"],
            "aqi_type": aqi_type,
            "aqi_type_label": aqi_type,
            "advisory": cat_meta["advisory"],
            "precautions": cat_meta["precautions"],
            "cache_age_seconds": 0,
        }

        _LIVE_CACHE[city] = {
            "cached_at": now_ts,
            "retrieval_time": now_iso,
            "data": result,
        }
        return result

    # 3. Fallback to historical cache
    if historical_cache:
        fallback = _get_historical_fallback(city, historical_cache)
        # Cache fallback for 2 minutes to prevent hammering a failing API
        _LIVE_CACHE[city] = {
            "cached_at": now_ts,
            "retrieval_time": now_iso,
            "data": fallback,
        }
        return fallback

    # 4. Minimal safety fallback if no historical cache passed
    aqi_subindex, cat = compute_aqi_from_pm25_scalar(50.0)
    cat_meta = AQI_CATEGORIES[cat]
    safe_fallback = {
        "city": city,
        "state": CITY_COORDINATES[city]["state"],
        "station_name": f"{city} Sensor",
        "is_live": False,
        "status": "unavailable",
        "status_message": "Current measurements temporarily unavailable.",
        "observation_time": now_iso,
        "retrieval_time": now_iso,
        "source_name": "CPCB CAAQMS Historical Baseline",
        "data_source": "CPCB CAAQMS Historical Baseline",
        "source_attribution": "CPCB / MoEFCC",
        "pollutants": {"PM2.5": 50.0},
        "pm25": 50.0,
        "weather": {"temperature": 25.0, "relative_humidity": 60.0, "wind_speed": 1.5, "pressure": 1013.0},
        "temperature": 25.0,
        "humidity": 60.0,
        "wind_speed": 1.5,
        "pressure": 1013.0,
        "aqi": aqi_subindex,
        "pm25_subindex": aqi_subindex,
        "category": cat,
        "aqi_category": cat,
        "color": cat_meta["color"],
        "aqi_color": cat_meta["color"],
        "aqi_badge_bg": cat_meta["badge_bg"],
        "aqi_type": "Historical Baseline",
        "aqi_type_label": "PM2.5 Sub-Index",
        "advisory": cat_meta["advisory"],
        "precautions": cat_meta["precautions"],
        "cache_age_seconds": 0,
    }
    return safe_fallback
