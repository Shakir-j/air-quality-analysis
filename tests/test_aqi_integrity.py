import pytest

from src.aqi import (
    calculate_composite_aqi,
    calculate_pollutant_subindex,
)


def test_pm25_subindex_breakpoints():
    cases = [
        (0, 0, "Good"),
        (30, 50, "Good"),
        (60, 100, "Satisfactory"),
        (90, 200, "Moderate"),
        (120, 300, "Poor"),
        (250, 400, "Very Poor"),
        (500, 500, "Severe"),
    ]

    for concentration, expected_index, expected_category in cases:
        result = calculate_pollutant_subindex("PM2.5", concentration)
        assert result is not None
        index, category, _ = result
        assert index == pytest.approx(expected_index)
        assert category == expected_category


def test_other_pollutant_breakpoints():
    for pollutant, concentration in [
        ("PM10", 50),
        ("NO2", 40),
        ("SO2", 40),
        ("CO", 1),
        ("O3", 50),
    ]:
        result = calculate_pollutant_subindex(pollutant, concentration)
        assert result is not None
        assert result[0] == pytest.approx(50)


def test_composite_requires_three_pollutants_and_particulate():
    values = {
        "PM2.5": [20.0] * 24,
        "NO2": [20.0] * 24,
    }

    result = calculate_composite_aqi(values)

    assert result["aqi"] is None
    assert result["status"] == "insufficient_data"
    assert result["category"] == "Insufficient data"


def test_composite_uses_worst_qualifying_subindex():
    values = {
        "PM2.5": [30.0] * 24,
        "PM10": [100.0] * 24,
        "NO2": [40.0] * 24,
    }

    result = calculate_composite_aqi(values)

    assert result["status"] == "calculated"
    assert result["aqi"] == pytest.approx(100)
    assert result["category"] == "Satisfactory"
    assert result["dominant_pollutant"] == "PM10"


def test_missing_hourly_values_are_not_imputed():
    values = {
        "PM2.5": ([20.0] * 15) + ([None] * 9),
        "PM10": [100.0] * 24,
        "NO2": [40.0] * 24,
        "SO2": [40.0] * 24,
    }

    result = calculate_composite_aqi(values)

    assert result["status"] == "calculated"
    assert "PM2.5" not in result["sub_indices"]
    assert result["dominant_pollutant"] in {"PM10", "NO2", "SO2"}


def test_eight_hour_pollutant_requires_eight_valid_values():
    values = {
        "PM2.5": [30.0] * 24,
        "PM10": [100.0] * 24,
        "NO2": [40.0] * 24,
        "O3": ([50.0] * 16) + ([50.0] * 7) + [None],
    }

    result = calculate_composite_aqi(values)

    assert result["status"] == "calculated"
    assert "O3" not in result["sub_indices"]
