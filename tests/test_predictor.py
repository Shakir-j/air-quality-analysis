"""
tests/test_predictor.py
───────────────────────
Unit tests for the prediction pipeline and CPCB air quality categorization.
"""

import pytest
from src.predictor import (
    compute_aqi_from_pm25_scalar,
    predict_from_simple_inputs,
    AQI_CATEGORIES,
)


def test_aqi_scalar_categories():
    """Verify exact category assignments across all CPCB bands."""
    test_cases = [
        (0.0, "Good"),
        (25.0, "Good"),
        (30.0, "Good"),
        (30.1, "Satisfactory"),
        (55.0, "Satisfactory"),
        (60.0, "Satisfactory"),
        (60.1, "Moderate"),
        (85.0, "Moderate"),
        (90.0, "Moderate"),
        (90.1, "Poor"),
        (115.0, "Poor"),
        (120.0, "Poor"),
        (120.1, "Very Poor"),
        (200.0, "Very Poor"),
        (250.0, "Very Poor"),
        (250.1, "Severe"),
        (400.0, "Severe"),
        (900.0, "Severe"),
    ]
    for pm25, expected_cat in test_cases:
        _, cat = compute_aqi_from_pm25_scalar(pm25)
        assert cat == expected_cat, f"PM2.5 {pm25} expected {expected_cat}, got {cat}"


def test_negative_clamping():
    """Negative particulate concentrations are physically impossible and must clamp to 0."""
    aqi, cat = compute_aqi_from_pm25_scalar(-15.0)
    assert aqi >= 0.0
    assert cat == "Good"


def test_aqi_category_metadata_completeness():
    """Verify all AQI categories define colors, advisories, and precautions."""
    required_cats = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
    for cat in required_cats:
        assert cat in AQI_CATEGORIES
        meta = AQI_CATEGORIES[cat]
        assert "color" in meta
        assert "advisory" in meta
        assert "precautions" in meta
        assert len(meta["precautions"]) >= 2
