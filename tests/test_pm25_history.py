import json

from src.pm25_history import attach_pm25_lags
from src.predictor import predict_from_live_observation


def observation(hour, value, station="Station A", live=True):
    return {
        "city": "Chennai",
        "state": "Tamil Nadu",
        "station_name": station,
        "station_latitude": 13.1000,
        "station_longitude": 80.2000,
        "is_live": live,
        "observation_time": f"2026-10-23 {hour:02d}:00:00",
        "pollutants": {"PM2.5": value},
    }


def test_history_starts_blank_until_previous_hours_exist(tmp_path):
    path = tmp_path / "history.json"
    result = attach_pm25_lags(
        observation(12, 33.0), history_path=path
    )

    assert result["pm25_lag_2h"] is None
    assert result["pm25_lag_3h"] is None
    assert path.exists()


def test_exact_same_station_hourly_lags_are_attached(tmp_path):
    path = tmp_path / "history.json"

    attach_pm25_lags(observation(10, 10.0), history_path=path)
    attach_pm25_lags(observation(11, 11.0), history_path=path)
    result = attach_pm25_lags(observation(12, 12.0), history_path=path)

    # The forecast target is 13:00. Model t-2 is 11:00,
    # and model t-3 is 10:00.
    assert result["pm25_lag_2h"] == 11.0
    assert result["pm25_lag_3h"] == 10.0
    assert result["pm25_lag_2h_observation_time"] == "2026-10-23 11:00:00"
    assert result["pm25_lag_3h_observation_time"] == "2026-10-23 10:00:00"


def test_observations_from_another_station_are_not_mixed(tmp_path):
    path = tmp_path / "history.json"

    attach_pm25_lags(observation(10, 10.0, station="Station A"), history_path=path)
    attach_pm25_lags(observation(11, 11.0, station="Station A"), history_path=path)
    result = attach_pm25_lags(
        observation(12, 99.0, station="Station B"), history_path=path
    )

    assert result["pm25_lag_2h"] is None
    assert result["pm25_lag_3h"] is None


def test_missing_hour_is_not_filled_by_a_neighbouring_reading(tmp_path):
    path = tmp_path / "history.json"

    attach_pm25_lags(observation(10, 10.0), history_path=path)
    result = attach_pm25_lags(observation(12, 12.0), history_path=path)

    assert result["pm25_lag_2h"] is None
    assert result["pm25_lag_3h"] == 10.0


def test_duplicate_observation_timestamp_is_replaced_not_duplicated(tmp_path):
    path = tmp_path / "history.json"

    attach_pm25_lags(observation(10, 10.0), history_path=path)
    attach_pm25_lags(observation(10, 12.0), history_path=path)

    data = json.loads(path.read_text(encoding="utf-8"))
    entry = next(iter(data.values()))

    assert len(entry["observations"]) == 1
    assert entry["observations"]["2026-10-23 10:00:00"] == 12.0


def test_historical_fallback_is_not_saved_as_live_history(tmp_path):
    path = tmp_path / "history.json"

    result = attach_pm25_lags(
        observation(12, 33.0, live=False), history_path=path
    )

    assert result["pm25_lag_2h"] is None
    assert not path.exists()


def test_live_predictor_passes_verified_lags_into_model(monkeypatch):
    import src.predictor as predictor_module

    captured = {}

    def fake_predict(**kwargs):
        captured.update(kwargs)
        return {"predicted_pm25": 40.0}

    monkeypatch.setattr(
        predictor_module, "predict_from_simple_inputs", fake_predict
    )

    result = predict_from_live_observation({
        "city": "Chennai",
        "station_name": "Station A",
        "observation_time": "2026-10-23T20:00:00",
        "retrieval_time": "2026-10-23 20:15:00",
        "is_live": True,
        "pollutants": {"PM2.5": 33.0},
        "pm25_lag_2h": 22.0,
        "pm25_lag_3h": 17.0,
        "weather": {},
    })

    assert captured["pm25_lag_2h"] == 22.0
    assert captured["pm25_lag_3h"] == 17.0
    assert result["predicted_pm25"] == 40.0

def test_hour_bucket_lookup_handles_non_hour_aligned_source_timestamps(tmp_path):
    from src.pm25_history import attach_pm25_lags

    history_path = tmp_path / "live_pm25_history.json"
    station = {
        "is_live": True,
        "city": "Delhi",
        "state": "Delhi",
        "station_name": "Hour Bucket Test Station",
        "station_latitude": 28.6000,
        "station_longitude": 77.2000,
    }

    def ingest(timestamp, pm25):
        return attach_pm25_lags(
            {
                **station,
                "observation_time": timestamp,
                "pollutants": {"PM2.5": pm25},
            },
            history_path=history_path,
        )

    ingest("2026-10-24 11:42:11", 80.0)
    ingest("2026-10-24 12:08:49", 90.0)
    result = ingest("2026-10-24 13:37:46", 100.0)

    assert result["pm25_lag_2h"] == 90.0
    assert result["pm25_lag_3h"] == 80.0
    assert result["pm25_lag_2h_observation_time"] == "2026-10-24 12:08:49"
    assert result["pm25_lag_3h_observation_time"] == "2026-10-24 11:42:11"
