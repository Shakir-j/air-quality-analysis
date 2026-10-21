"""
src/predictor.py
────────────────
Air-quality prediction engine and inference module.

Key Capabilities:
  1. Load saved model and preprocessor artefacts (models/final_model.pkl, preprocessor.pkl).
  2. Transform user inputs or automated sensor streams into model-ready feature vectors.
  3. Impute any missing meteorological or co-pollutant values using training-set medians.
  4. Generate next-hour PM2.5 predictions (clipped at physical minimum >= 0).
  5. Compute official CPCB Indian Air Quality Index (AQI) sub-index & category.
  6. Return rich environmental health advisories and actionable public precautions.
  7. Extract feature importance rankings for model explainability.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from src.config import FINAL_MODEL, PREPROCESSOR, AQI_BREAKPOINTS_PM25

logger = logging.getLogger(__name__)

# ── Singleton Cache for Model & Preprocessor ─────────────────────────────────
_MODEL_CACHE: dict[str, Any] = {}

# ── AQI Category Definitions & Health Guidance ──────────────────────────────
AQI_CATEGORIES = {
    "Good": {
        "range_pm25": (0, 30),
        "range_aqi": (0, 50),
        "color": "#10b981",          # Emerald green
        "badge_bg": "rgba(16, 185, 129, 0.15)",
        "badge_border": "#10b981",
        "advisory": "Minimal impact. Air quality is clean and poses little or no risk.",
        "precautions": [
            "Ideal conditions for outdoor exercise, jogging, and walking.",
            "Open windows for natural ventilation in homes and offices.",
            "No special health precautions required for sensitive groups.",
        ],
    },
    "Satisfactory": {
        "range_pm25": (31, 60),
        "range_aqi": (51, 100),
        "color": "#84cc16",          # Lime green
        "badge_bg": "rgba(132, 204, 22, 0.15)",
        "badge_border": "#84cc16",
        "advisory": "Minor breathing discomfort to sensitive individuals.",
        "precautions": [
            "Generally safe for most people to engage in normal outdoor activities.",
            "Individuals with asthma or chronic respiratory conditions should keep medication handy.",
            "Consider reducing strenuous outdoor exertion if unusually sensitive.",
        ],
    },
    "Moderate": {
        "range_pm25": (61, 90),
        "range_aqi": (101, 200),
        "color": "#f59e0b",          # Amber
        "badge_bg": "rgba(245, 158, 11, 0.15)",
        "badge_border": "#f59e0b",
        "advisory": "Breathing discomfort to people with asthma, lung, and heart diseases.",
        "precautions": [
            "Children, the elderly, and cardiac/asthma patients should limit prolonged outdoor exertion.",
            "Keep indoor air filtered where possible; avoid early morning outdoor runs.",
            "Wear a lightweight mask if sensitive to dust and particulate haze.",
        ],
    },
    "Poor": {
        "range_pm25": (91, 120),
        "range_aqi": (201, 300),
        "color": "#f97316",          # Orange
        "badge_bg": "rgba(249, 115, 22, 0.15)",
        "badge_border": "#f97316",
        "advisory": "Breathing discomfort to most people on prolonged exposure.",
        "precautions": [
            "Avoid strenuous outdoor activities; shift workouts indoors.",
            "Sensitive groups should stay indoors and keep windows closed during peak hours.",
            "Wear an N95 mask when commuting or walking outside.",
            "Use home HEPA air purifiers if available.",
        ],
    },
    "Very Poor": {
        "range_pm25": (121, 250),
        "range_aqi": (301, 400),
        "color": "#ef4444",          # Crimson Red
        "badge_bg": "rgba(239, 68, 68, 0.15)",
        "badge_border": "#ef4444",
        "advisory": "Respiratory illness on prolonged exposure; severe impact on heart/lung patients.",
        "precautions": [
            "Everyone should strictly avoid prolonged or heavy exertion outdoors.",
            "Close all windows and doors; run HEPA air filtration indoors continuously.",
            "Wearing an N95 / FFP2 mask outdoors is strongly recommended for all citizens.",
            "High-risk individuals should consult physicians if experiencing chest tightness or wheezing.",
        ],
    },
    "Severe": {
        "range_pm25": (251, 1000),
        "range_aqi": (401, 500),
        "color": "#991b1b",          # Dark Maroon / Burgundy
        "badge_bg": "rgba(153, 27, 27, 0.2)",
        "badge_border": "#991b1b",
        "advisory": "Emergency condition. Healthy individuals affected; serious health impacts on all.",
        "precautions": [
            "Emergency public health situation: Stay indoors as much as possible.",
            "All outdoor sports, running, and heavy manual labor must be cancelled.",
            "Wear certified N95 / N99 respirators whenever exposure is unavoidable.",
            "Operate air purifiers with sealed rooms; keep inhalers and emergency medications ready.",
        ],
    },
}


def load_model_and_preprocessor() -> tuple[object, dict[str, Any]]:
    """
    Load the trained model and preprocessing artefacts from disk (cached).

    Returns
    -------
    (model, preproc_dict)
    """
    if "model" in _MODEL_CACHE and "preproc" in _MODEL_CACHE:
        return _MODEL_CACHE["model"], _MODEL_CACHE["preproc"]

    if not FINAL_MODEL.exists():
        raise FileNotFoundError(
            f"Final model not found at {FINAL_MODEL}. "
            f"Please re-run the training pipeline to generate models/final_model.pkl."
        )
    if not PREPROCESSOR.exists():
        raise FileNotFoundError(
            f"Preprocessor artefacts not found at {PREPROCESSOR}. "
            f"Please re-run the training pipeline to generate models/preprocessor.pkl."
        )

    model = joblib.load(FINAL_MODEL)
    preproc = joblib.load(PREPROCESSOR)

    _MODEL_CACHE["model"] = model
    _MODEL_CACHE["preproc"] = preproc
    return model, preproc


from src.aqi import calculate_pollutant_subindex

def compute_aqi_from_pm25_scalar(pm25: float) -> tuple[float, str]:
    """Return the central PM2.5 sub-index and category."""
    result = calculate_pollutant_subindex("PM2.5", pm25)
    if result is None:
        raise ValueError("PM2.5 concentration must be a finite number")
    index, category, _color = result
    return index, category

def predict_from_features(features_input: dict[str, Any] | pd.DataFrame) -> dict[str, Any]:
    """
    Generate next-hour PM2.5 prediction from a feature dictionary or single-row DataFrame.

    Parameters
    ----------
    features_input : dict or pd.DataFrame containing feature columns

    Returns
    -------
    dict with:
      - predicted_pm25: float (ug/m3)
      - predicted_aqi: float
      - aqi_category: str
      - color: hex color code
      - badge_bg: rgba string
      - advisory: str
      - precautions: list[str]
      - model_name: str
    """
    model, preproc = load_model_and_preprocessor()
    expected_cols = preproc["feature_names"]
    col_medians = preproc["col_medians"]
    model_name = preproc.get("model_name", "Trained ML Model")

    if isinstance(features_input, dict):
        df_in = pd.DataFrame([features_input])
    else:
        df_in = features_input.copy()

    # Ensure all expected columns exist; fill missing with training set medians
    for col in expected_cols:
        if col not in df_in.columns or pd.isna(df_in[col].iloc[0]):
            df_in[col] = col_medians.get(col, 0.0)

    # Reorder columns to exact order expected by the model
    X = df_in[expected_cols].astype("float32")

    # Predict
    raw_pred = model.predict(X)[0]
    predicted_pm25 = round(max(0.0, float(raw_pred)), 2)

    # Compute AQI & Category
    predicted_aqi, aqi_cat = compute_aqi_from_pm25_scalar(predicted_pm25)
    cat_meta = AQI_CATEGORIES.get(aqi_cat, AQI_CATEGORIES["Moderate"])

    return {
        "predicted_pm25": predicted_pm25,
        "predicted_aqi": predicted_aqi,
        "aqi_category": aqi_cat,
        "color": cat_meta["color"],
        "badge_bg": cat_meta["badge_bg"],
        "badge_border": cat_meta["badge_border"],
        "advisory": cat_meta["advisory"],
        "precautions": cat_meta["precautions"],
        "model_name": model_name,
    }


def predict_from_simple_inputs(
    pm25_current: float,
    pm25_lag_2h: Optional[float] = None,
    pm25_lag_3h: Optional[float] = None,
    hour: int = 12,
    month: int = 11,
    day_of_week: int = 2,
    season_num: Optional[int] = None,  # derived from month if not supplied
    is_weekend: int = 0,
    no2: Optional[float] = None,
    co: Optional[float] = None,
    so2: Optional[float] = None,
    ozone: Optional[float] = None,
    relative_humidity: Optional[float] = None,
    wind_speed: Optional[float] = None,
    temperature: Optional[float] = None,
    solar_radiation: Optional[float] = None,
    barometric_pressure: Optional[float] = None,
) -> dict[str, Any]:
    """
    Convenience method for interactive Streamlit UI prediction form.
    Automatically infers reasonable rolling and lag values when only
    the current/recent observation is supplied.
    """
    _, preproc = load_model_and_preprocessor()
    col_medians = preproc["col_medians"]

    # Derive season_num from month when not explicitly supplied (0=Winter,1=Pre-Monsoon,2=Monsoon,3=Post-Monsoon)
    if season_num is None:
        _month_to_season = {
            12: 0, 1: 0, 2: 0,
            3: 1, 4: 1, 5: 1,
            6: 2, 7: 2, 8: 2, 9: 2,
            10: 3, 11: 3,
        }
        season_num = _month_to_season.get(month, 3)

    import datetime
    current_year = datetime.datetime.now().year

    # The current observation is one hour before the forecast target.
    lag_1h = float(pm25_current)

    lag_2h = (
        float(pm25_lag_2h)
        if pm25_lag_2h is not None
        else float("nan")
    )
    lag_3h = (
        float(pm25_lag_3h)
        if pm25_lag_3h is not None
        else float("nan")
    )

    # The interactive form does not provide reliable values for these lags.
    # Leave them missing; do not copy the third-hour value into longer lags.
    lag_6h = float("nan")
    lag_12h = float("nan")
    lag_24h = float("nan")

    if pm25_lag_2h is not None and pm25_lag_3h is not None:
        recent_vals = [lag_1h, lag_2h, lag_3h]
        roll_mean_3h = float(np.mean(recent_vals))
        roll_std_3h = float(np.std(recent_vals, ddof=1))
    else:
        roll_mean_3h = float("nan")
        roll_std_3h = float("nan")

    # Do not pretend a few observations represent complete 6h/24h windows.
    roll_mean_6h = float("nan")
    roll_std_6h = float("nan")
    roll_mean_24h = float("nan")
    roll_std_24h = float("nan")

    feature_dict = {
        # Temporal — cap year at 2023 (training data max) to stay in-distribution
        "year": min(current_year, 2023),
        "month": month,
        "hour": hour,
        "day_of_week": day_of_week,
        "season_num": season_num,
        "is_weekend": is_weekend,
        # PM2.5 Lags
        "pm25_lag_1h": lag_1h,
        "pm25_lag_2h": lag_2h,
        "pm25_lag_3h": lag_3h,
        "pm25_lag_6h": lag_6h,
        "pm25_lag_12h": lag_12h,
        "pm25_lag_24h": lag_24h,
        # Rolling stats
        "pm25_roll_mean_3h": roll_mean_3h,
        "pm25_roll_std_3h": roll_std_3h,
        "pm25_roll_mean_6h": roll_mean_6h,
        "pm25_roll_std_6h": roll_std_6h,
        "pm25_roll_mean_24h": roll_mean_24h,
        "pm25_roll_std_24h": roll_std_24h,
        # Co-pollutant lags
        "no2_lag_1h": no2 if no2 is not None else col_medians.get("no2_lag_1h", 30.0),
        "co_lag_1h": co if co is not None else col_medians.get("co_lag_1h", 1.0),
        "so2_lag_1h": so2 if so2 is not None else col_medians.get("so2_lag_1h", 12.0),
        "ozone_lag_1h": ozone if ozone is not None else col_medians.get("ozone_lag_1h", 35.0),
        "nox_lag_1h": col_medians.get("nox_lag_1h", 25.0),
        # Meteorology
        "RH (%)": relative_humidity if relative_humidity is not None else col_medians.get("RH (%)", 60.0),
        "WS (m/s)": wind_speed if wind_speed is not None else col_medians.get("WS (m/s)", 1.5),
        "AT (degree C)": temperature if temperature is not None else col_medians.get("AT (degree C)", 25.0),
        "SR (W/mt2)": solar_radiation if solar_radiation is not None else col_medians.get("SR (W/mt2)", 120.0),
        "BP (mmHg)": barometric_pressure if barometric_pressure is not None else col_medians.get("BP (mmHg)", 745.0),
    }

    return predict_from_features(feature_dict)


def predict_from_live_observation(live_data: dict[str, Any]) -> dict[str, Any]:
    """
    Generate next-hour PM2.5 prediction using real-time or cached station observations.
    Bridges live sensor inputs (PM2.5, co-pollutants, weather) to the trained XGBoost model.
    """
    import datetime

    pollutants = live_data.get("pollutants", {})
    weather = live_data.get("weather", {})

    current_pm25 = float(pollutants.get("PM2.5", live_data.get("pm25", 50.0)))
    no2 = float(pollutants.get("NO2", live_data.get("no2"))) if ("NO2" in pollutants or "no2" in live_data) and pollutants.get("NO2", live_data.get("no2")) is not None else None
    co = float(pollutants.get("CO", live_data.get("co"))) if ("CO" in pollutants or "co" in live_data) and pollutants.get("CO", live_data.get("co")) is not None else None
    so2 = float(pollutants.get("SO2", live_data.get("so2"))) if ("SO2" in pollutants or "so2" in live_data) and pollutants.get("SO2", live_data.get("so2")) is not None else None
    ozone = float(pollutants.get("Ozone", live_data.get("ozone"))) if ("Ozone" in pollutants or "ozone" in live_data) and pollutants.get("Ozone", live_data.get("ozone")) is not None else None

    temp = float(weather.get("temperature", live_data.get("temperature"))) if ("temperature" in weather or "temperature" in live_data) and weather.get("temperature", live_data.get("temperature")) is not None else None
    rh = float(weather.get("relative_humidity", live_data.get("humidity"))) if ("relative_humidity" in weather or "humidity" in live_data) and weather.get("relative_humidity", live_data.get("humidity")) is not None else None
    ws = float(weather.get("wind_speed", live_data.get("wind_speed"))) if ("wind_speed" in weather or "wind_speed" in live_data) and weather.get("wind_speed", live_data.get("wind_speed")) is not None else None

    obs_time_str = live_data.get("observation_time", "")
    obs_dt = None
    if obs_time_str:
        for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                obs_dt = datetime.datetime.strptime(obs_time_str, fmt)
                break
            except Exception:
                pass

    if obs_dt is None:
        obs_dt = datetime.datetime.now()

    target_dt = obs_dt + datetime.timedelta(hours=1)
    target_time_str = target_dt.strftime("%Y-%m-%d %H:%M:00")

    forecast = predict_from_simple_inputs(
        pm25_current=current_pm25,
        hour=obs_dt.hour,
        month=obs_dt.month,
        day_of_week=obs_dt.weekday(),
        is_weekend=1 if obs_dt.weekday() >= 5 else 0,
        no2=no2,
        co=co,
        so2=so2,
        ozone=ozone,
        relative_humidity=rh,
        wind_speed=ws,
        temperature=temp,
    )

    pred_pm25 = forecast["predicted_pm25"]
    delta = round(pred_pm25 - current_pm25, 1)

    source = live_data.get("source_name") or live_data.get("data_source") or "CPCB Monitoring Network"

    forecast.update({
        "city": live_data.get("city", "Delhi"),
        "station_name": live_data.get("station_name", "CAAQMS Station"),
        "current_measured_pm25": current_pm25,
        "current_pm25": current_pm25,
        "delta_pm25": delta,
        "delta_direction": "up" if delta > 0.5 else ("down" if delta < -0.5 else "stable"),
        "observation_time": obs_time_str or obs_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "target_forecast_time": target_time_str,
        "forecast_target_time": target_time_str,
        "forecast_horizon": "1-hour ahead (t+1)",
        "forecast_horizon_hours": 1,
        "is_live_input": live_data.get("is_live", False),
        "data_source": source,
        "source_name": source,
    })

    return forecast


def get_feature_importances(top_n: int = 15) -> pd.DataFrame:
    """
    Extract feature importance scores from the final model (if tree-based/ensemble).

    Returns
    -------
    pd.DataFrame with ['feature', 'importance', 'relative_pct']
    """
    model, preproc = load_model_and_preprocessor()
    feature_names = preproc["feature_names"]

    # Extract importance attribute if available
    raw_model = model
    if hasattr(model, "named_steps"):
        raw_model = model.named_steps.get("model", model)

    if hasattr(raw_model, "feature_importances_"):
        importances = raw_model.feature_importances_
    elif hasattr(raw_model, "coef_"):
        importances = np.abs(raw_model.coef_)
    else:
        return pd.DataFrame(columns=["feature", "importance", "relative_pct"])

    df_imp = pd.DataFrame({
        "feature": feature_names,
        "importance": importances,
    }).sort_values("importance", ascending=False)

    total = df_imp["importance"].sum()
    df_imp["relative_pct"] = (
        (df_imp["importance"] / total * 100).round(2) if total > 0 else 0.0
    )
    return df_imp.head(top_n).reset_index(drop=True)
