import math
from urllib.parse import parse_qs, urlparse

import pytest

from src import live_data
from src.predictor import predict_from_live_observation


OBSERVATION = "2026-10-23 20:00:00"
WEATHER_HOUR = "2026-10-23T20:00"


def test_weather_fetch_uses_observation_hour_and_station_coordinates(monkeypatch):
    captured = {}

    def fake_request_json(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return {
            "hourly": {
                "time": [WEATHER_HOUR, "2026-10-23T21:00"],
                "temperature_2m": [23.9, 23.5],
                "relative_humidity_2m": [66, 65],
                "wind_speed_10m": [0.29, 0.35],
                "surface_pressure": [985.0, 987.0],
            },
            "hourly_units": {"surface_pressure": "hPa"},
        }

    monkeypatch.setattr(live_data, "_request_json", fake_request_json)

    result = live_data._fetch_live_meteorology(
        "Delhi",
        observation_time=OBSERVATION,
        latitude=28.62181,
        longitude=77.1944633,
    )

    assert result is not None
    assert result["time"] == WEATHER_HOUR
    assert result["temperature"] == 23.9
    assert result["relative_humidity"] == 66
    assert result["wind_speed"] == 0.29
    assert result["pressure"] == 985.0
    assert result["pressure_unit"] == "hPa"

    query = parse_qs(urlparse(captured["url"]).query)
    assert query["latitude"] == ["28.62181"]
    assert query["longitude"] == ["77.1944633"]
    assert query["timezone"] == ["Asia/Kolkata"]
    assert "hourly" in query
    assert "current" not in query


def test_weather_fetch_does_not_substitute_a_different_hour(monkeypatch):
    monkeypatch.setattr(
        live_data,
        "_request_json",
        lambda url, timeout: {
            "hourly": {
                "time": ["2026-10-23T21:00"],
                "temperature_2m": [23.5],
                "relative_humidity_2m": [65],
                "wind_speed_10m": [0.35],
                "surface_pressure": [987.0],
            },
            "hourly_units": {"surface_pressure": "hPa"},
        },
    )

    result = live_data._fetch_live_meteorology(
        "Delhi", observation_time=OBSERVATION
    )
    assert result is None


def test_live_prediction_excludes_out_of_range_co_and_omits_pressure(monkeypatch):
    captured = {}

    def fake_predict(**kwargs):
        captured.update(kwargs)
        return {"predicted_pm25": 260.0}

    monkeypatch.setattr(
        "src.predictor.predict_from_simple_inputs", fake_predict
    )

    result = predict_from_live_observation({
        "city": "Delhi",
        "station_name": "Talkatora Garden, Delhi - DPCC",
        "observation_time": OBSERVATION,
        "is_live": True,
        "source_name": "CPCB via data.gov.in",
        "pollutants": {
            "PM2.5": 249.0,
            "CO": 94.0,
            "NO2": 24.0,
            "SO2": 4.0,
            "Ozone": 19.0,
        },
        "weather": {
            "temperature": 23.9,
            "relative_humidity": 66.0,
            "wind_speed": 0.29,
            "pressure": 985.0,
            "pressure_unit": "hPa",
            "time": WEATHER_HOUR,
            "source_name": "Open-Meteo Weather API",
        },
    })

    assert captured["pm25_current"] == 249.0
    assert captured["co"] is None
    assert captured["temperature"] == 23.9
    assert captured["relative_humidity"] == 66.0
    assert captured["wind_speed"] == 0.29
    assert captured["barometric_pressure"] is None
    assert result["forecast_target_time"] == "2026-10-23 21:00:00"
    co_flags = [
        flag for flag in result["model_input_quality_flags"]
        if "CO" in flag
    ]
    assert len(co_flags) == 1
    assert "CO source value was excluded" in co_flags[0]
    assert "0 to 50 mg/m3" in co_flags[0]
    assert result["weather_observation_time"] == WEATHER_HOUR


def test_live_prediction_warns_when_target_hour_is_not_future(monkeypatch):
    def fake_predict(**kwargs):
        return {"predicted_pm25": 40.0}

    monkeypatch.setattr(
        "src.predictor.predict_from_simple_inputs", fake_predict
    )

    result = predict_from_live_observation({
        "city": "Chennai",
        "station_name": "Royapuram, Chennai - TNPCB",
        "observation_time": OBSERVATION,
        "retrieval_time": "2026-10-23 21:15:00",
        "is_live": True,
        "pollutants": {"PM2.5": 33.0},
        "weather": {},
    })

    assert result["forecast_target_time"] == "2026-10-23 21:00:00"
    assert any(
        "at or before the data retrieval time" in flag
        for flag in result["model_input_quality_flags"]
    )


def test_live_prediction_ignores_weather_from_a_different_hour(monkeypatch):
    captured = {}

    def fake_predict(**kwargs):
        captured.update(kwargs)
        return {"predicted_pm25": 250.0}

    monkeypatch.setattr(
        "src.predictor.predict_from_simple_inputs", fake_predict
    )

    result = predict_from_live_observation({
        "city": "Delhi",
        "observation_time": OBSERVATION,
        "is_live": True,
        "pollutants": {"PM2.5": 249.0},
        "weather": {
            "temperature": 23.5,
            "relative_humidity": 65.0,
            "wind_speed": 0.35,
            "pressure": 987.0,
            "pressure_unit": "hPa",
            "time": "2026-10-23T21:00",
        },
    })

    assert captured["temperature"] is None
    assert captured["relative_humidity"] is None
    assert captured["wind_speed"] is None
    assert captured["barometric_pressure"] is None
    assert result["weather_observation_time"] is None
    assert any(
        "no exact observation-hour match" in flag
        for flag in result["model_input_quality_flags"]
    )


def test_live_prediction_rejects_missing_pm25_and_observation_time():
    with pytest.raises(ValueError, match="valid CPCB observation timestamp"):
        predict_from_live_observation({
            "city": "Delhi",
            "pollutants": {"PM2.5": 249.0},
        })

    with pytest.raises(ValueError, match="valid PM2.5 observation"):
        predict_from_live_observation({
            "city": "Delhi",
            "observation_time": OBSERVATION,
            "pollutants": {"PM2.5": None},
        })
