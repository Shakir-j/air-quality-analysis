"""
tests/test_live_data.py
───────────────────────
Unit tests for the live air quality telemetry integration:
- CPCB CAAQMS official data.gov.in ingestion and record parsing
- CPCB piecewise linear sub-index calculation
- Caching TTL behavior
- Resilient fallback to historical CPCB baseline on network timeout/429
- Prediction from live telemetry pipeline
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from src.live_data import (
    get_current_air_quality,
    _LIVE_CACHE,
    CACHE_TTL_SECONDS,
)
from src.predictor import (
    compute_aqi_from_pm25_scalar,
    predict_from_live_observation,
)


def test_compute_cpcb_subindex():
    """Verify CPCB NAQI piecewise linear breakpoint interpolation for PM2.5."""
    # Good: 0-30 -> 0-50
    aqi, cat = compute_aqi_from_pm25_scalar(0.0)
    assert aqi == 0.0
    assert cat == "Good"

    aqi, cat = compute_aqi_from_pm25_scalar(30.0)
    assert aqi == 50.0
    assert cat == "Good"

    aqi, cat = compute_aqi_from_pm25_scalar(15.0)
    assert round(aqi, 1) == 25.0
    assert cat == "Good"

    # Satisfactory: 31-60 -> 51-100
    aqi, cat = compute_aqi_from_pm25_scalar(60.0)
    assert round(aqi, 1) == 100.0
    assert cat == "Satisfactory"

    # Moderate: 61-90 -> 101-200
    aqi, cat = compute_aqi_from_pm25_scalar(90.0)
    assert round(aqi, 1) == 200.0
    assert cat == "Moderate"

    # Poor: 91-120 -> 201-300
    aqi, cat = compute_aqi_from_pm25_scalar(120.0)
    assert round(aqi, 1) == 300.0
    assert cat == "Poor"

    # Very Poor: 121-250 -> 301-400
    aqi, cat = compute_aqi_from_pm25_scalar(250.0)
    assert round(aqi, 1) == 400.0
    assert cat == "Very Poor"

    # Severe: 251-500 -> 401-500
    aqi, cat = compute_aqi_from_pm25_scalar(500.0)
    assert round(aqi, 1) == 500.0
    assert cat == "Severe"

    # Over 500 capped at 500
    aqi, cat = compute_aqi_from_pm25_scalar(750.0)
    assert aqi == 500.0
    assert cat == "Severe"


def test_live_data_fallback_when_network_fails():
    """Verify that when network calls fail, get_current_air_quality falls back safely."""
    # Clear cache for isolated test
    _LIVE_CACHE.pop("Bengaluru", None)

    with patch("urllib.request.urlopen") as mock_url:
        mock_url.side_effect = Exception("Simulated network timeout")
        res = get_current_air_quality("Bengaluru")

    assert res["city"] == "Bengaluru"
    assert res["is_live"] is False
    assert "historical" in res["source_name"].lower() or "baseline" in res["source_name"].lower()
    assert res["pm25"] is not None
    assert res["aqi"] is not None
    assert res["category"] in ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]


def test_live_data_cpcb_success_mock(monkeypatch):
    """Verify parsing when data.gov.in returns valid CPCB CAAQMS records."""
    monkeypatch.setenv("AIRWISE_ENABLE_LIVE_DATA", "1")
    mock_response_data = {
        "records": [
            {
                "city": "Delhi",
                "station": "Anand Vihar, Delhi - DPCC",
                "pollutant_id": "PM2.5",
                "pollutant_avg": "135.4",
                "last_update": "19-10-2026 15:00:00",
            },
            {
                "city": "Delhi",
                "station": "Anand Vihar, Delhi - DPCC",
                "pollutant_id": "PM10",
                "pollutant_avg": "210.0",
                "last_update": "19-10-2026 15:00:00",
            },
            {
                "city": "Delhi",
                "station": "Anand Vihar, Delhi - DPCC",
                "pollutant_id": "NO2",
                "pollutant_avg": "45.2",
                "last_update": "19-10-2026 15:00:00",
            },
        ]
    }

    import json
    mock_bytes = json.dumps(mock_response_data).encode("utf-8")

    # Clear cache for isolated test
    _LIVE_CACHE.pop("Delhi", None)

    with patch("urllib.request.urlopen") as mock_url:
        mock_context = MagicMock()
        mock_context.status = 200
        mock_context.read.return_value = mock_bytes
        mock_context.__enter__.return_value = mock_context
        mock_url.return_value = mock_context

        res = get_current_air_quality("Delhi")

    assert res["city"] == "Delhi"
    assert res["is_live"] is True
    assert res["pm25"] == 135.4
    assert res["pm10"] == 210.0
    assert res["no2"] == 45.2
    assert "Anand Vihar" in res["station_name"]
    assert res["category"] == "Very Poor"
    assert res["aqi"] > 300.0


def test_live_data_caching_behavior(monkeypatch):
    """Verify that cached data is reused within the TTL window without making new requests."""
    monkeypatch.setenv("AIRWISE_ENABLE_LIVE_DATA", "1")
    _LIVE_CACHE["Delhi"] = {
        "timestamp": time.time(),
        "data": {
            "city": "Delhi",
            "is_live": True,
            "station_name": "Cached Station",
            "pm25": 99.0,
            "aqi": 230.0,
            "category": "Poor",
        },
    }

    # Even if network would fail, cached data should be returned immediately
    with patch("urllib.request.urlopen") as mock_url:
        mock_url.side_effect = Exception("Should not be called")
        res = get_current_air_quality("Delhi")

    assert res["station_name"] == "Cached Station"
    assert res["pm25"] == 99.0


def test_predict_from_live_observation():
    """Verify forecasting PM2.5 one hour ahead from a live telemetry observation."""
    live_obs = {
        "city": "Delhi",
        "station_name": "Anand Vihar, Delhi - DPCC",
        "observation_time": "2026-10-19 14:00:00",
        "is_live": True,
        "pm25": 120.0,
        "temperature": 22.0,
        "humidity": 60.0,
        "wind_speed": 1.5,
        "pressure": 1012.0,
        "no2": 40.0,
        "so2": 15.0,
        "co": 1.2,
        "ozone": 30.0,
        "source_name": "CPCB CAAQMS via data.gov.in",
    }

    pred = predict_from_live_observation(live_obs)

    assert "predicted_pm25" in pred
    assert pred["predicted_pm25"] > 0
    assert "predicted_aqi" in pred
    assert "aqi_category" in pred
    assert pred["current_pm25"] == 120.0
    assert "delta_pm25" in pred
    assert pred["forecast_horizon_hours"] == 1
    assert "forecast_target_time" in pred
    # Forecast target time should be 1h after 14:00:00 -> 15:00:00
    assert "15:00:00" in pred["forecast_target_time"]
