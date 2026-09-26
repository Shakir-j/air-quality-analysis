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
