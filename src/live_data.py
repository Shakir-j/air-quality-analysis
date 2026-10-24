from __future__ import annotations

import datetime
import json
import logging
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from src.generate_cache import CITY_COORDINATES
from src.predictor import AQI_CATEGORIES, compute_aqi_from_pm25_scalar

logger = logging.getLogger("airwise.live_data")

DATA_GOV_IN_RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
DATA_GOV_IN_BASE_URL = (
    f"https://api.data.gov.in/resource/{DATA_GOV_IN_RESOURCE_ID}"
)

CACHE_TTL_SECONDS = 900
FAILURE_CACHE_TTL_SECONDS = 120
CPCB_PAGE_SIZE = 500
CPCB_MAX_PAGES = 10
MAX_OBSERVATION_AGE_SECONDS = 3 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 10 * 60
MAX_POLLUTANT_TIME_SKEW_SECONDS = 3 * 60 * 60

_LIVE_CACHE: dict[str, dict[str, Any]] = {}

POLLUTANT_IDS = {
    "PM2.5": "PM2.5",
    "PM25": "PM2.5",
    "PM10": "PM10",
    "NO2": "NO2",
    "SO2": "SO2",
    "CO": "CO",
    "OZONE": "Ozone",
    "O3": "Ozone",
    "NH3": "NH3",
}

POLLUTANT_ALIASES = {
    "PM2.5": ("PM2.5 (ug/m3)", "PM2.5", "PM25", "pm25"),
    "PM10": ("PM10 (ug/m3)", "PM10", "pm10"),
    "NO2": ("NO2 (ug/m3)", "NO2", "no2"),
    "SO2": ("SO2 (ug/m3)", "SO2", "so2"),
    "CO": ("CO (mg/m3)", "CO", "co"),
    "Ozone": ("Ozone (ug/m3)", "Ozone", "O3", "ozone"),
    "NH3": ("NH3 (ug/m3)", "NH3", "nh3"),
}


def _get_api_key() -> str:
    """Read the OGD API key without printing or logging its value."""
    key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    if key:
        return key

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, ".env.local")

    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() == "DATA_GOV_IN_API_KEY":
                    return value.strip().strip('"').strip("'")
    except OSError:
        pass

    return ""


def _parse_number(
    value: Any, *, allow_negative: bool = True
) -> Optional[float]:
    """Parse a finite numeric value; missing markers are never converted to zero."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, str):
        value = value.strip()
        if not value or value.upper() in {
            "NA", "N/A", "NULL", "NONE", "-", "--", "NAN", "NOT AVAILABLE"
        }:
            return None

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(number):
        return None
    if not allow_negative and number < 0:
        return None
    return number


def _parse_source_timestamp(value: Any) -> Optional[datetime.datetime]:
    """Parse known CPCB timestamp formats without inventing missing times."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    for fmt in (
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            pass

    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def _format_timestamp(value: datetime.datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _normalized_label(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _city_key(value: Any) -> str:
    key = _normalized_label(value)
    if key in {"bangalore", "bengaluru"}:
        return "bengaluru"
    return key


def _request_json(url: str, timeout: int) -> Optional[dict[str, Any]]:
    """Perform a GET without including query credentials in error logs."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AIRWISE-AirQuality/2.0 (University Research Project)"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                logger.warning("External data source returned HTTP %s", response.status)
                return None
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            return payload if isinstance(payload, dict) else None
    except urllib.error.HTTPError as exc:
        logger.warning("External data source returned HTTP %s", exc.code)
    except Exception as exc:
        logger.warning("External data request failed (%s)", type(exc).__name__)

    return None


def _fetch_cpcb_state_records(
    state: str, timeout: int = 10
) -> Optional[list[dict[str, Any]]]:
    """Fetch a state's records using documented state filtering and pagination."""
    api_key = _get_api_key()
    if not api_key:
        logger.warning("CPCB live lookup skipped: no data.gov.in API key is configured.")
        return None

    collected: list[dict[str, Any]] = []
    expected_total: Optional[int] = None

    for page in range(CPCB_MAX_PAGES):
        params = {
            "api-key": api_key,
            "format": "json",
            "filters[state]": state,
            "limit": str(CPCB_PAGE_SIZE),
            "offset": str(page * CPCB_PAGE_SIZE),
        }
        url = DATA_GOV_IN_BASE_URL + "?" + urllib.parse.urlencode(params)
        payload = _request_json(url, timeout)

        if payload is None:
            return None

        rows = payload.get("records")
        if not isinstance(rows, list):
            logger.warning("CPCB response does not contain a records list.")
            return None

        try:
            if payload.get("total") is not None:
                expected_total = int(payload["total"])
        except (TypeError, ValueError):
            expected_total = None

        rows = [row for row in rows if isinstance(row, dict)]
        collected.extend(rows)

        if expected_total is not None:
            if len(collected) >= expected_total:
                return collected[:expected_total]
            if len(rows) < CPCB_PAGE_SIZE:
                logger.warning(
                    "CPCB pagination ended before the reported total; "
                    "discarding incomplete state results."
                )
                return None
        elif len(rows) < CPCB_PAGE_SIZE:
            return collected

    if expected_total is not None and len(collected) < expected_total:
        logger.warning(
            "CPCB state response exceeds the configured pagination safety limit."
        )
        return None

    return collected


def _station_distance_km(
    station_lat: Optional[float],
    station_lon: Optional[float],
    city_coords: dict[str, Any],
) -> float:
    """Return distance from the configured city reference point for tie-breaking."""
    if station_lat is None or station_lon is None:
        return math.inf

    city_lat = _parse_number(city_coords.get("lat"))
    city_lon = _parse_number(city_coords.get("lon"))
    if city_lat is None or city_lon is None:
        return math.inf

    lat1, lat2 = math.radians(station_lat), math.radians(city_lat)
    dlat = lat2 - lat1
    dlon = math.radians(city_lon - station_lon)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def _fetch_live_cpcb_city(
    city: str, timeout: int = 10
) -> Optional[dict[str, Any]]:
    """
    Select one fresh PM2.5 station record without combining stations.

    Pollutant readings retain their own observation times. The chosen station
    must have a valid, recent PM2.5 value. Other values more than three hours
    away from that PM2.5 timestamp are excluded.
    """
    city_coords = CITY_COORDINATES.get(city)
    if not city_coords:
        return None

    state = str(city_coords.get("state", "")).strip()
    if not state:
        return None

    records = _fetch_cpcb_state_records(state, timeout=timeout)
    if not records:
        return None

    grouped: dict[str, dict[str, Any]] = {}

    for record in records:
        if _city_key(record.get("city")) != _city_key(city):
            continue

        record_state = str(record.get("state", "")).strip()
        if record_state and _normalized_label(record_state) != _normalized_label(state):
            continue

        station = " ".join(str(record.get("station", "")).split())
        if not station:
            continue

        pollutant_id = str(record.get("pollutant_id", "")).strip().upper()
        pollutant = POLLUTANT_IDS.get(pollutant_id)
        if not pollutant:
            continue

        raw_value = None
        for field in ("avg_value", "pollutant_avg", "value"):
            if field in record and record[field] is not None and str(record[field]).strip():
                raw_value = record[field]
                break

        value = _parse_number(raw_value, allow_negative=False)
        if value is None:
            continue

        observed_at = _parse_source_timestamp(record.get("last_update"))
        if observed_at is None:
            continue

        entry = grouped.setdefault(
            station,
            {
                "station": station,
                "city": record.get("city", city),
                "state": record.get("state", state),
                "latitude": _parse_number(record.get("latitude")),
                "longitude": _parse_number(record.get("longitude")),
                "values": {},
            },
        )

        current = entry["values"].get(pollutant)
        if current is None or observed_at >= current["datetime"]:
            entry["values"][pollutant] = {
                "value": value,
                "datetime": observed_at,
                "source_timestamp": str(record.get("last_update", "")).strip(),
            }

    now = datetime.datetime.now()
    fresh_candidates: list[dict[str, Any]] = []

    for entry in grouped.values():
        pm25 = entry["values"].get("PM2.5")
        if pm25 is None:
            continue

        age_seconds = (now - pm25["datetime"]).total_seconds()
        if age_seconds > MAX_OBSERVATION_AGE_SECONDS:
            continue
        if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
            continue

        fresh_candidates.append(entry)

    if not fresh_candidates:
        logger.warning(
            "No fresh, timestamped PM2.5 station record was validated for %s.",
            city,
        )
        return None

    freshest_time = max(
        entry["values"]["PM2.5"]["datetime"] for entry in fresh_candidates
    )
    fresh_candidates = [
        entry for entry in fresh_candidates
        if entry["values"]["PM2.5"]["datetime"] == freshest_time
    ]

    def selection_key(entry: dict[str, Any]) -> tuple[Any, ...]:
        pm25_time = entry["values"]["PM2.5"]["datetime"]
        compatible_count = sum(
            abs((item["datetime"] - pm25_time).total_seconds())
            <= MAX_POLLUTANT_TIME_SKEW_SECONDS
            for item in entry["values"].values()
        )
        distance = _station_distance_km(
            entry["latitude"], entry["longitude"], city_coords
        )
        return (-compatible_count, distance, entry["station"].casefold())

    chosen = min(fresh_candidates, key=selection_key)
    pm25_time = chosen["values"]["PM2.5"]["datetime"]

    pollutants: dict[str, float] = {}
    pollutant_times: dict[str, str] = {}

    for name, item in chosen["values"].items():
        skew = abs((item["datetime"] - pm25_time).total_seconds())
        if skew > MAX_POLLUTANT_TIME_SKEW_SECONDS:
            continue
        pollutants[name] = item["value"]
        pollutant_times[name] = _format_timestamp(item["datetime"])

    if "PM2.5" not in pollutants:
        return None

    return {
        "station": chosen["station"],
        "city": chosen["city"],
        "state": chosen["state"],
        "latitude": chosen["latitude"],
        "longitude": chosen["longitude"],
        "last_update": _format_timestamp(pm25_time),
        "source_last_update": chosen["values"]["PM2.5"]["source_timestamp"],
        "pollutants": pollutants,
        "pollutant_observation_times": pollutant_times,
        "candidate_station_count": len(fresh_candidates),
    }


def _fetch_live_meteorology(
    city: str,
    timeout: int = 8,
    observation_time: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """
    Retrieve Open-Meteo hourly weather aligned with a CPCB station reading.

    No current-hour substitution is made when the requested observation hour
    is missing. Pressure remains in the API's documented hPa unit here;
    model-unit conversion occurs in the predictor.
    """
    target = _parse_source_timestamp(observation_time)
    if target is None:
        logger.warning(
            "Weather lookup skipped for %s: no valid CPCB observation timestamp.",
            city,
        )
        return None

    coords = CITY_COORDINATES.get(city)
    if not coords:
        return None

    lat = _parse_number(latitude)
    lon = _parse_number(longitude)
    if lat is None or lon is None:
        lat = _parse_number(coords.get("lat"))
        lon = _parse_number(coords.get("lon"))

    if lat is None or lon is None:
        return None

    target_hour = target.strftime("%Y-%m-%dT%H:00")
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": (
            "temperature_2m,relative_humidity_2m,"
            "wind_speed_10m,surface_pressure"
        ),
        "past_days": "2",
        "forecast_days": "1",
        "timezone": "Asia/Kolkata",
        "wind_speed_unit": "ms",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    payload = _request_json(url, timeout)

    if not payload:
        return None

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        return None

    times = hourly.get("time")
    if not isinstance(times, list) or target_hour not in times:
        logger.warning(
            "No exact hourly weather match for %s at %s; weather will be omitted.",
            city,
            target_hour,
        )
        return None

    idx = times.index(target_hour)

    def hourly_value(name: str) -> Optional[float]:
        values = hourly.get(name)
        if not isinstance(values, list) or idx >= len(values):
            return None
        return _parse_number(values[idx])

    temperature = hourly_value("temperature_2m")
    humidity = hourly_value("relative_humidity_2m")
    wind_speed = hourly_value("wind_speed_10m")
    pressure = hourly_value("surface_pressure")

    if humidity is not None and not 0 <= humidity <= 100:
        humidity = None
    if wind_speed is not None and wind_speed < 0:
        wind_speed = None
    if temperature is not None and not -10 <= temperature <= 55:
        temperature = None
    if pressure is not None and not 800 <= pressure <= 1100:
        pressure = None

    if all(
        value is None
        for value in (temperature, humidity, wind_speed, pressure)
    ):
        return None

    units = payload.get("hourly_units", {})
    pressure_unit = (
        units.get("surface_pressure", "hPa")
        if isinstance(units, dict)
        else "hPa"
    )

    return {
        "temperature": temperature,
        "relative_humidity": humidity,
        "wind_speed": wind_speed,
        "pressure": pressure,
        "pressure_unit": pressure_unit,
        "time": target_hour,
        "source_name": "Open-Meteo Weather API",
    }


def _empty_weather() -> dict[str, Optional[float]]:
    return {
        "temperature": None,
        "relative_humidity": None,
        "wind_speed": None,
        "pressure": None,
    }


def _resolve_historical_value(
    latest: dict[str, Any],
    averages: dict[str, Any],
    aliases: tuple[str, ...],
) -> tuple[Optional[float], str]:
    for key in aliases:
        number = _parse_number(latest.get(key), allow_negative=False)
        if number is not None:
            return number, "latest_archived_record"

    for key in aliases:
        number = _parse_number(averages.get(key), allow_negative=False)
        if number is not None:
            return number, "historical_city_average"

    return None, "unavailable"


def _unavailable_result(city: str, message: str) -> dict[str, Any]:
    coords = CITY_COORDINATES.get(city, {})
    retrieval_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pollutants = {name: None for name in POLLUTANT_IDS.values()}
    weather = _empty_weather()

    return {
        "city": city,
        "state": coords.get("state", ""),
        "station_name": f"{city} ? no validated reading available",
        "is_live": False,
        "status": "unavailable",
        "status_message": message,
        "observation_time": None,
        "retrieval_time": retrieval_time,
        "source_name": "No validated measurement available",
        "data_source": "Unavailable",
        "source_attribution": "",
        "pollutants": pollutants,
        "pollutant_observation_times": {},
        "pollutant_value_basis": {name: "unavailable" for name in pollutants},
        "pm25": None,
        "pm10": None,
        "no2": None,
        "so2": None,
        "co": None,
        "ozone": None,
        "weather": weather,
        "weather_source": None,
        "weather_observation_time": None,
        "temperature": None,
        "humidity": None,
        "wind_speed": None,
        "pressure": None,
        "aqi": None,
        "pm25_subindex": None,
        "category": "Unavailable",
        "aqi_category": "Unavailable",
        "color": "#94a3b8",
        "aqi_color": "#94a3b8",
        "aqi_badge_bg": "#e2e8f0",
        "aqi_type": "Unavailable",
        "aqi_type_label": "Unavailable",
        "advisory": "No valid PM2.5 measurement or historical reference is available.",
        "precautions": [],
        "cache_age_seconds": 0,
    }


def _get_historical_fallback(
    city: str,
    historical_cache: dict[str, Any],
    status_message: Optional[str] = None,
) -> dict[str, Any]:
    """
    Return an explicitly historical reference without inventing measurements.

    Each pollutant records whether its value came from the latest archived
    record, a city average, or was unavailable. Archive coverage end is not
    misrepresented as the observation time for every pollutant.
    """
    city_info = historical_cache.get("cities", {}).get(city, {})
    latest = city_info.get("latest_recorded", {})
    averages = city_info.get("pollutant_averages", {})
    coords = CITY_COORDINATES.get(city, {})

    latest = latest if isinstance(latest, dict) else {}
    averages = averages if isinstance(averages, dict) else {}

    values: dict[str, Optional[float]] = {}
    basis: dict[str, str] = {}

    for pollutant, aliases in POLLUTANT_ALIASES.items():
        value, value_basis = _resolve_historical_value(latest, averages, aliases)
        values[pollutant] = value
        basis[pollutant] = value_basis

    if values.get("PM2.5") is None:
        mean_pm25 = _parse_number(
            city_info.get("overall_pm25_mean"), allow_negative=False
        )
        if mean_pm25 is not None:
            values["PM2.5"] = mean_pm25
            basis["PM2.5"] = "historical_city_average"

    pm25 = values.get("PM2.5")
    if pm25 is None:
        return _unavailable_result(
            city,
            status_message or (
                "No usable PM2.5 measurement or historical reference is available."
            ),
        )

    aqi, category = compute_aqi_from_pm25_scalar(pm25)
    cat_meta = AQI_CATEGORIES.get(category, AQI_CATEGORIES["Moderate"])

    archive_end = (
        city_info.get("date_end")
        or historical_cache.get("metadata", {}).get("date_end")
    )

    # Use a timestamp only if the archive actually records one for its
    # latest-value entry. The archive-wide end date is tracked separately.
    latest_time = _parse_source_timestamp(
        latest.get("timestamp") or latest.get("last_update")
    )
    observation_time = (
        _format_timestamp(latest_time)
        if latest_time is not None and basis.get("PM2.5") == "latest_archived_record"
        else None
    )

    rounded = {
        name: (round(value, 2 if name == "CO" else 1) if value is not None else None)
        for name, value in values.items()
    }
    weather = _empty_weather()
    retrieval_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = status_message or (
        "Live source requests are disabled. Displaying historical archive values; "
        "a value may be an archived record or a historical city average."
    )
    source_name = "CPCB Historical Archive (Offline Baseline)"

    return {
        "city": city,
        "state": coords.get("state", city_info.get("state", "")),
        "station_name": f"{city} Historical Archive Summary",
        "is_live": False,
        "status": "historical_fallback",
        "status_message": message,
        "observation_time": observation_time,
        "retrieval_time": retrieval_time,
        "archive_coverage_end": archive_end,
        "source_name": source_name,
        "data_source": source_name,
        "source_attribution": "Central Pollution Control Board (CPCB) / MoEFCC",
        "pollutants": rounded,
        "pollutant_observation_times": {},
        "pollutant_value_basis": basis,
        "pm25": rounded.get("PM2.5"),
        "pm10": rounded.get("PM10"),
        "no2": rounded.get("NO2"),
        "so2": rounded.get("SO2"),
        "co": rounded.get("CO"),
        "ozone": rounded.get("Ozone"),
        "weather": weather,
        "weather_source": None,
        "weather_observation_time": None,
        "temperature": None,
        "humidity": None,
        "wind_speed": None,
        "pressure": None,
        "aqi": aqi,
        "pm25_subindex": aqi,
        "category": category,
        "aqi_category": category,
        "color": cat_meta["color"],
        "aqi_color": cat_meta["color"],
        "aqi_badge_bg": cat_meta["badge_bg"],
        "aqi_type": "Historical PM2.5 Sub-Index",
        "aqi_type_label": "Historical PM2.5 Sub-Index",
        "advisory": cat_meta["advisory"],
        "precautions": cat_meta["precautions"],
        "cache_age_seconds": 0,
    }


def get_current_air_quality(
    city: str,
    historical_cache: Optional[dict[str, Any]] = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Return one validated current CPCB station reading, or an explicit archive
    fallback. External access remains opt-in via AIRWISE_ENABLE_LIVE_DATA=1.
    """
    if city not in CITY_COORDINATES:
        city = "Delhi"

    if historical_cache is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            from server import get_cache
            historical_cache = get_cache()
        except Exception:
            try:
                cache_path = os.path.join(
                    project_root, "data", "cache", "air_quality_cache.json"
                )
                with open(cache_path, "r", encoding="utf-8") as cache_file:
                    historical_cache = json.load(cache_file)
            except Exception:
                historical_cache = {}

    historical_cache = historical_cache or {}
    now = datetime.datetime.now()
    now_ts = now.timestamp()
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S")

    live_enabled = os.environ.get(
        "AIRWISE_ENABLE_LIVE_DATA", "0"
    ).strip().lower() in {"1", "true", "yes", "on"}

    cached_entry = _LIVE_CACHE.get(city)
    if live_enabled and not force_refresh and cached_entry:
        cached_ts = cached_entry.get(
            "cached_at", cached_entry.get("timestamp", now_ts)
        )
        age = now_ts - cached_ts
        cached_data = cached_entry.get("data", cached_entry)
        ttl = (
            CACHE_TTL_SECONDS
            if cached_data.get("is_live") is True
            else FAILURE_CACHE_TTL_SECONDS
        )
        if 0 <= age < ttl:
            result = dict(cached_data)
            result["retrieval_time"] = cached_entry.get("retrieval_time", now_iso)
            result["cache_age_seconds"] = round(age)
            return result

    if live_enabled:
        cpcb_live = _fetch_live_cpcb_city(city)
        weather_live = (
            _fetch_live_meteorology(
                city,
                observation_time=cpcb_live.get("last_update"),
                latitude=cpcb_live.get("latitude"),
                longitude=cpcb_live.get("longitude"),
            )
            if cpcb_live
            else None
        )
    else:
        cpcb_live = None
        weather_live = None

    if cpcb_live and cpcb_live.get("pollutants", {}).get("PM2.5") is not None:
        coords = CITY_COORDINATES[city]
        pollutants = cpcb_live["pollutants"]
        pm25 = float(pollutants["PM2.5"])
        aqi, category = compute_aqi_from_pm25_scalar(pm25)
        cat_meta = AQI_CATEGORIES.get(category, AQI_CATEGORIES["Moderate"])

        weather = {
            "temperature": weather_live.get("temperature") if weather_live else None,
            "relative_humidity": (
                weather_live.get("relative_humidity") if weather_live else None
            ),
            "wind_speed": weather_live.get("wind_speed") if weather_live else None,
            "pressure": weather_live.get("pressure") if weather_live else None,
        }

        source_name = "Central Pollution Control Board (CPCB) via data.gov.in"
        result = {
            "city": city,
            "state": coords["state"],
            "station_name": cpcb_live["station"],
            "station_latitude": cpcb_live.get("latitude"),
            "station_longitude": cpcb_live.get("longitude"),
            "is_live": True,
            "status": "live",
            "status_message": (
                "Validated CPCB station-level PM2.5 reading. Pollutant values "
                "retain their own observation timestamps; missing and stale "
                "measurements are not filled with defaults."
            ),
            "observation_time": cpcb_live["last_update"],
            "retrieval_time": now_iso,
            "source_last_update": cpcb_live.get("source_last_update"),
            "source_name": source_name,
            "data_source": source_name,
            "source_attribution": (
                "Central Pollution Control Board (CPCB) / MoEFCC; "
                "Open Government Data Platform India"
            ),
            "pollutants": pollutants,
            "pollutant_observation_times": cpcb_live.get(
                "pollutant_observation_times", {}
            ),
            "pollutant_value_basis": {
                name: "CPCB station measurement" for name in pollutants
            },
            "pm25": pm25,
            "pm10": pollutants.get("PM10"),
            "no2": pollutants.get("NO2"),
            "so2": pollutants.get("SO2"),
            "co": pollutants.get("CO"),
            "ozone": pollutants.get("Ozone"),
            "nh3": pollutants.get("NH3"),
            "weather": weather,
            "weather_source": weather_live.get("source_name") if weather_live else None,
            "weather_observation_time": weather_live.get("time") if weather_live else None,
            "temperature": weather["temperature"],
            "humidity": weather["relative_humidity"],
            "wind_speed": weather["wind_speed"],
            "pressure": weather["pressure"],
            "aqi": aqi,
            "pm25_subindex": aqi,
            "category": category,
            "aqi_category": category,
            "color": cat_meta["color"],
            "aqi_color": cat_meta["color"],
            "aqi_badge_bg": cat_meta["badge_bg"],
            "aqi_type": "PM2.5 Sub-Index (not complete multi-pollutant AQI)",
            "aqi_type_label": "PM2.5 Sub-Index",
            "advisory": cat_meta["advisory"],
            "precautions": cat_meta["precautions"],
            "cache_age_seconds": 0,
        }

        from src.pm25_history import attach_pm25_lags
        result = attach_pm25_lags(result)

        _LIVE_CACHE[city] = {
            "cached_at": now_ts,
            "retrieval_time": now_iso,
            "data": result,
        }
        return result

    if live_enabled:
        fallback_message = (
            "Live CPCB data was unavailable, stale, or failed validation. "
            "Displaying historical archive values instead."
        )
    else:
        fallback_message = (
            "Live source requests are disabled. Displaying historical archive "
            "values; a value may be an archived record or a historical city average."
        )

    fallback = _get_historical_fallback(
        city, historical_cache, status_message=fallback_message
    )

    # Cache only failed live lookups briefly. Never let this cache masquerade
    # as a successful live response or retain it for the live-response TTL.
    if live_enabled:
        _LIVE_CACHE[city] = {
            "cached_at": now_ts,
            "retrieval_time": now_iso,
            "data": fallback,
        }

    return fallback
