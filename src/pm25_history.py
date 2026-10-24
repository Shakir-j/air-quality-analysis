from __future__ import annotations

import datetime
import json
import logging
import math
import os
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("airwise.pm25_history")

DEFAULT_HISTORY_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "cache" / "live_pm25_history.json"
)
MAX_OBSERVATIONS_PER_STATION = 168
_HISTORY_LOCK = threading.Lock()


def _parse_timestamp(value: Any) -> Optional[datetime.datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    try:
        parsed = datetime.datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)

    return parsed.replace(microsecond=0)


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(result) or result < 0:
        return None
    return result


def _station_key(record: dict[str, Any]) -> Optional[str]:
    def norm(value: Any) -> str:
        return " ".join(str(value or "").split()).casefold()

    city = norm(record.get("city"))
    state = norm(record.get("state"))
    station = norm(record.get("station_name"))

    if not city or not state or not station:
        return None

    # CPCB records in this integration do not expose a stable station ID.
    # Use name + city + state, plus rounded coordinates when available.
    key = f"{city}|{state}|{station}"

    try:
        lat = float(record.get("station_latitude"))
        lon = float(record.get("station_longitude"))
        if math.isfinite(lat) and math.isfinite(lon):
            key += f"|{lat:.4f}|{lon:.4f}"
    except (TypeError, ValueError, OverflowError):
        pass

    return key


def attach_pm25_lags(
    live_data: dict[str, Any],
    *,
    history_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Store a live PM2.5 observation and attach exact prior-hour lag values.

    The target prediction is one hour after the current observation:
      * model lag_2h is the reading one hour before the current observation
      * model lag_3h is the reading two hours before the current observation

    No nearest-hour substitution or cross-station fallback is used.
    """
    result = dict(live_data)
    result["pm25_lag_2h"] = None
    result["pm25_lag_3h"] = None
    result["pm25_lag_2h_observation_time"] = None
    result["pm25_lag_3h_observation_time"] = None

    if result.get("is_live") is not True:
        return result

    station_key = _station_key(result)
    current_dt = _parse_timestamp(result.get("observation_time"))
    pollutants = result.get("pollutants") or {}
    current_pm25 = _number(pollutants.get("PM2.5"))

    if station_key is None or current_dt is None or current_pm25 is None:
        return result

    current_observation_key = current_dt.strftime("%Y-%m-%d %H:%M:%S")
    current_bucket_dt = current_dt.replace(
        minute=0, second=0, microsecond=0
    )
    current_key = current_bucket_dt.strftime("%Y-%m-%d %H:%M:%S")
    path = Path(history_path) if history_path is not None else DEFAULT_HISTORY_PATH

    with _HISTORY_LOCK:
        try:
            if path.exists():
                history = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(history, dict):
                    raise ValueError("History file root must be a JSON object.")
            else:
                history = {}
        except Exception as exc:
            # Do not overwrite a malformed existing file automatically.
            logger.warning(
                "Live PM2.5 history could not be read (%s).",
                type(exc).__name__,
            )
            return result

        entry = history.get(station_key, {})
        if not isinstance(entry, dict):
            entry = {}

        old_observations = entry.get("observations", {})
        if not isinstance(old_observations, dict):
            old_observations = {}

        old_observation_times = entry.get("observation_times", {})
        if not isinstance(old_observation_times, dict):
            old_observation_times = {}

        observations: dict[str, float] = {}
        observation_times: dict[str, str] = {}

        # Align readings to clock-hour buckets while retaining the actual
        # source timestamp for traceability. Older history files are supported.
        for key, value in old_observations.items():
            timestamp = _parse_timestamp(old_observation_times.get(key) or key)
            number = _number(value)
            if timestamp is None or number is None:
                continue

            bucket = timestamp.replace(minute=0, second=0, microsecond=0)
            bucket_key = bucket.strftime("%Y-%m-%d %H:%M:%S")
            existing_time = _parse_timestamp(observation_times.get(bucket_key))

            # Keep the latest source reading when several readings fall
            # inside the same clock hour.
            if existing_time is None or timestamp >= existing_time:
                observations[bucket_key] = number
                observation_times[bucket_key] = timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        # Update the current hour only if this source reading is not older
        # than the observation already retained for that hour.
        existing_current_time = _parse_timestamp(
            observation_times.get(current_key)
        )
        if existing_current_time is None or current_dt >= existing_current_time:
            observations[current_key] = current_pm25
            observation_times[current_key] = current_observation_key

        ordered = sorted(
            observations.items(),
            key=lambda item: _parse_timestamp(item[0])
                or datetime.datetime.min,
        )
        observations = dict(ordered[-MAX_OBSERVATIONS_PER_STATION:])
        observation_times = {
            key: observation_times.get(key, key) for key in observations
        }

        history[station_key] = {
            "city": result.get("city"),
            "state": result.get("state"),
            "station_name": result.get("station_name"),
            "station_latitude": result.get("station_latitude"),
            "station_longitude": result.get("station_longitude"),
            "observations": observations,
            "observation_times": observation_times,
        }

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_name(path.name + ".tmp")
            temp_path.write_text(
                json.dumps(history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, path)
        except Exception as exc:
            logger.warning(
                "Live PM2.5 history could not be saved (%s).",
                type(exc).__name__,
            )
            return result

        # Look up the previous clock-hour buckets only. Missing hours are
        # never interpolated and readings from other stations are not used.
        lag_2h_dt = current_bucket_dt - datetime.timedelta(hours=1)
        lag_3h_dt = current_bucket_dt - datetime.timedelta(hours=2)
        lag_2h_key = lag_2h_dt.strftime("%Y-%m-%d %H:%M:%S")
        lag_3h_key = lag_3h_dt.strftime("%Y-%m-%d %H:%M:%S")

        if lag_2h_key in observations:
            result["pm25_lag_2h"] = observations[lag_2h_key]
            result["pm25_lag_2h_observation_time"] = observation_times.get(
                lag_2h_key, lag_2h_key
            )

        if lag_3h_key in observations:
            result["pm25_lag_3h"] = observations[lag_3h_key]
            result["pm25_lag_3h_observation_time"] = observation_times.get(
                lag_3h_key, lag_3h_key
            )

    return result
