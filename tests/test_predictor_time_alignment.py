from unittest.mock import patch

from src.predictor import predict_from_live_observation


def test_live_prediction_uses_target_hour_at_midnight_weekday_boundary():
    captured = {}

    def fake_predict(**kwargs):
        captured.update(kwargs)
        return {"predicted_pm25": 35.0}

    live_data = {
        "city": "Delhi",
        "pollutants": {"PM2.5": 42.0},
        "observation_time": "2023-12-31 23:00:00",
        "is_live": True,
    }

    with patch(
        "src.predictor.predict_from_simple_inputs",
        side_effect=fake_predict,
    ):
        result = predict_from_live_observation(live_data)

    # The forecast target is Monday, 1 January 2024, at 00:00.
    assert captured["hour"] == 0
    assert captured["month"] == 1
    assert captured["day_of_week"] == 0  # Monday
    assert captured["is_weekend"] == 0

    # Preserve the original observation as the lag-1 PM2.5 input.
    assert captured["pm25_current"] == 42.0
    assert result["target_forecast_time"] == "2024-01-01 00:00:00"
