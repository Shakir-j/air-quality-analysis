"""
tests/test_preprocessor.py
──────────────────────────
Unit tests for data preprocessing and official CPCB AQI mathematical calculation.
"""

import numpy as np
import pandas as pd
import pytest

from src.preprocessor import (
    _compute_aqi_from_pm25,
    _get_aqi_category,
    OUTLIER_CAPS,
    NON_NEGATIVE_COLS,
)
from src.predictor import compute_aqi_from_pm25_scalar


def test_cpcb_aqi_breakpoints():
    """Verify that PM2.5 scalar mapping adheres to official CPCB NAQI boundaries."""
    # Good: 0-30 -> 0-50
    aqi, cat = compute_aqi_from_pm25_scalar(15.0)
    assert cat == "Good"
    assert 0 <= aqi <= 50

    # Satisfactory: 31-60 -> 51-100
    aqi, cat = compute_aqi_from_pm25_scalar(45.0)
    assert cat == "Satisfactory"
    assert 51 <= aqi <= 100

    # Moderate: 61-90 -> 101-200
    aqi, cat = compute_aqi_from_pm25_scalar(75.0)
    assert cat == "Moderate"
    assert 101 <= aqi <= 200

    # Poor: 91-120 -> 201-300
    aqi, cat = compute_aqi_from_pm25_scalar(105.0)
    assert cat == "Poor"
    assert 201 <= aqi <= 300

    # Very Poor: 121-250 -> 301-400
    aqi, cat = compute_aqi_from_pm25_scalar(180.0)
    assert cat == "Very Poor"
    assert 301 <= aqi <= 400

    # Severe: 251-500 -> 401-500
    aqi, cat = compute_aqi_from_pm25_scalar(300.0)
    assert cat == "Severe"
    assert 401 <= aqi <= 500


def test_aqi_vectorized_series():
    """Verify vectorized computation across a pandas Series."""
    s = pd.Series([15.0, 45.0, 75.0, 105.0, 180.0, 300.0, 600.0])
    aqi_series = _compute_aqi_from_pm25(s)
    cat_series = _get_aqi_category(aqi_series)

    assert len(aqi_series) == 7
    # Values above 500 capped at 500
    assert aqi_series.iloc[-1] == 500.0
    assert cat_series.iloc[0] == "Good"
    assert cat_series.iloc[-1] == "Severe"


def test_non_negative_pollutant_definition():
    """Verify that physical pollutants and meteorological variables are listed as non-negative."""
    assert "PM2.5 (ug/m3)" in NON_NEGATIVE_COLS
    assert "RH (%)" in NON_NEGATIVE_COLS
    assert "WS (m/s)" in NON_NEGATIVE_COLS


def test_outlier_caps_scientific_bounds():
    """Verify that sensor outlier caps conform to CPCB physical boundaries."""
    assert OUTLIER_CAPS["PM2.5 (ug/m3)"] == 500.0
    assert OUTLIER_CAPS["RH (%)"] == 100.0
    assert OUTLIER_CAPS["WS (m/s)"] == 50.0
