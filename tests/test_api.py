"""
tests/test_api.py
─────────────────
Automated integration tests for the AIRWISE FastAPI backend service.
"""

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)


def test_root_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "AIRWISE" in response.text


def test_locations_endpoint():
    response = client.get("/api/locations")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "cities" in data
    assert len(data["cities"]) == 10
    first_city = data["cities"][0]
    assert "city" in first_city
    assert "station_count" in first_city
    assert "overall_pm25_mean" in first_city


def test_air_quality_endpoint():
    response = client.get("/api/air-quality?city=Delhi")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["city"] == "Delhi"
    assert "latest_recorded" in data
    assert "pollutant_averages" in data
    assert "recent_trend" in data
    assert len(data["recent_trend"]) > 0


def test_trends_endpoint():
    response = client.get("/api/trends?city=Delhi&pollutant=PM2.5")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["monthly_trend"]) > 0
    assert len(data["yearly_trend"]) > 0


def test_comparison_endpoint():
    response = client.get("/api/comparison?cities=Delhi,Mumbai,Bengaluru&pollutant=PM2.5")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["cities"]) == 3
    assert "correlations" in data
    assert "seasonal_patterns" in data


def test_insights_endpoint():
    response = client.get("/api/insights")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "hotspots" in data["insights"]
    assert "seasonal" in data["insights"]
    assert "diurnal" in data["insights"]


def test_prediction_endpoint():
    payload = {
        "city": "Delhi",
        "pm25_current": 140.0,
        "temperature": 18.0,
        "relative_humidity": 75.0,
        "wind_speed": 1.1,
        "month": 11,
        "hour": 20,
        "is_weekend": 0,
    }
    response = client.post("/api/prediction", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "predicted_pm25" in data
    assert data["predicted_pm25"] > 0
    assert "predicted_aqi" in data
    assert "aqi_category" in data
    assert "advisory" in data


def test_current_endpoint():
    """Verify that /api/current returns valid telemetry structure for a supported city."""
    response = client.get("/api/current?city=Delhi")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    data = res["data"]
    assert data["city"] == "Delhi"
    assert "is_live" in data
    assert "station_name" in data
    assert "observation_time" in data
    assert "retrieval_time" in data
    assert "source_name" in data
    assert "aqi" in data
    assert "category" in data


def test_air_quality_includes_current_live():
    """Verify that /api/air-quality includes the current_live field."""
    response = client.get("/api/air-quality?city=Delhi")
    assert response.status_code == 200
    data = response.json()
    assert "current_live" in data
    live = data["current_live"]
    assert "city" in live
    assert "pm25" in live
    assert "aqi" in live


def test_prediction_live_endpoint():
    """Verify that /api/prediction/live generates a 1-hour ahead forecast from telemetry."""
    response = client.post("/api/prediction/live", json={"city": "Delhi"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "predicted_pm25" in data
    assert "predicted_aqi" in data
    assert "forecast_target_time" in data
    assert "forecast_horizon_hours" in data
    assert data["forecast_horizon_hours"] == 1
    assert "current_pm25" in data
    assert "delta_pm25" in data

def test_recent_trend_is_48_hourly_city_averages():
    from datetime import datetime, timedelta

    response = client.get("/api/air-quality?city=Chennai")
    assert response.status_code == 200
    data = response.json()

    trend = data["recent_trend"]
    assert len(trend) == 48

    times = [datetime.fromisoformat(point["time"]) for point in trend]
    assert times == sorted(times)
    assert len(set(times)) == 48
    assert all(
        later - earlier == timedelta(hours=1)
        for earlier, later in zip(times, times[1:])
    )

    latest = data["latest_recorded"]
    assert latest["observation_type"] == "city_hourly_mean"
    assert latest["station_count_at_timestamp"] > 0
    assert latest["timestamp"] == trend[-1]["time"]
    assert "City-wide hourly mean" in latest["station_location"]


def test_station_selection_returns_station_specific_archive_data():
    city_response = client.get("/api/air-quality?city=Pune")
    assert city_response.status_code == 200

    city_data = city_response.json()
    assert city_data["data_scope"] == "citywide"
    assert city_data["stations"]

    station = city_data["stations"][0]
    response = client.get(
        "/api/air-quality",
        params={"city": "Pune", "station": station["station_id"]},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["data_scope"] == "station"
    assert data["selected_station"]["station_id"] == station["station_id"]
    assert data["latest_recorded"]["station_location"] == station["station_location"]
    assert data["latest_recorded"]["observation_type"] == "station_hourly_observation"
    assert data["current_live"] is None
    assert len(data["recent_trend"]) == 48

    timestamps = [row["time"] for row in data["recent_trend"]]
    assert len(set(timestamps)) == 48
    assert timestamps == sorted(timestamps)
    assert "PM2.5" in data["pollutant_averages"]
    assert len(data["diurnal_pattern"]) == 24


def test_unknown_station_is_rejected():
    response = client.get(
        "/api/air-quality",
        params={"city": "Pune", "station": "UNKNOWN_STATION_ID"},
    )
    assert response.status_code == 404
def test_prediction_endpoint_does_not_hide_model_failure(monkeypatch):
    from src import predictor

    def fail_model(*args, **kwargs):
        raise RuntimeError("simulated model failure")

    monkeypatch.setattr(
        predictor,
        "predict_from_simple_inputs",
        fail_model,
    )

    response = client.post(
        "/api/prediction",
        json={
            "city": "Delhi",
            "pm25_current": 40.0,
            "temperature": 25.0,
            "relative_humidity": 60.0,
            "wind_speed": 1.5,
            "month": 10,
            "hour": 12,
            "is_weekend": 0,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"].startswith(
        "PM2.5 prediction is temporarily unavailable"
    )
