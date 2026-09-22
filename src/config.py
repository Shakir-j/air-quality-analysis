"""
src/config.py
Central configuration — paths, column names, model constants.
All other modules import from here; no hard-coded paths elsewhere.
"""
from pathlib import Path

# ── Directory roots ──────────────────────────────────────────────────────────
ROOT_DIR     = Path(__file__).resolve().parent.parent
DATA_RAW     = ROOT_DIR / "data" / "raw"
DATA_PROC    = ROOT_DIR / "data" / "processed"
MODELS_DIR   = ROOT_DIR / "models"
REPORTS_DIR  = ROOT_DIR / "reports"
FIGURES_DIR  = REPORTS_DIR / "figures"
APP_DIR      = ROOT_DIR / "app"

# ── Key files ─────────────────────────────────────────────────────────────────
STATIONS_FILE   = DATA_RAW / "stations_info.csv"
PROCESSED_FILE  = DATA_PROC / "air_quality_processed.parquet"
FINAL_MODEL     = MODELS_DIR / "final_model.pkl"
PREPROCESSOR    = MODELS_DIR / "preprocessor.pkl"
METRICS_FILE    = MODELS_DIR / "model_metrics.csv"

# ── Pollutant columns present in dataset ─────────────────────────────────────
POLLUTANT_COLS = [
    "PM2.5 (ug/m3)",
    "PM10 (ug/m3)",
    "NO (ug/m3)",
    "NO2 (ug/m3)",
    "NOx (ppb)",
    "NH3 (ug/m3)",
    "SO2 (ug/m3)",
    "CO (mg/m3)",
    "Ozone (ug/m3)",
    "Benzene (ug/m3)",
    "Toluene (ug/m3)",
    "Xylene (ug/m3)",
]

MET_COLS = [
    "RH (%)",
    "WS (m/s)",
    "SR (W/mt2)",
    "AT (degree C)",
    "BP (mmHg)",
]

# Short display names for UI
POLLUTANT_DISPLAY = {
    "PM2.5 (ug/m3)": "PM2.5",
    "PM10 (ug/m3)":  "PM10",
    "NO (ug/m3)":    "NO",
    "NO2 (ug/m3)":   "NO2",
    "NOx (ppb)":     "NOx",
    "NH3 (ug/m3)":   "NH3",
    "SO2 (ug/m3)":   "SO2",
    "CO (mg/m3)":    "CO",
    "Ozone (ug/m3)": "Ozone",
    "Benzene (ug/m3)":"Benzene",
}

# ── ML target ─────────────────────────────────────────────────────────────────
TARGET_COL = "PM2.5 (ug/m3)"   # Primary prediction target

# ── Indian AQI breakpoints for PM2.5 (µg/m³, 24-h average) ──────────────────
# Source: CPCB National Air Quality Index
AQI_BREAKPOINTS_PM25 = [
    (0,   30,   0,   50,  "Good"),
    (30,  60,   51, 100,  "Satisfactory"),
    (60,  90,  101, 200,  "Moderate"),
    (90, 120,  201, 300,  "Poor"),
    (120, 250, 301, 400,  "Very Poor"),
    (250, 500, 401, 500,  "Severe"),
]

# ── Time-aware split dates (to be refined after actual data inspection) ───────
TRAIN_END_DATE = "2021-12-31"
VAL_END_DATE   = "2022-06-30"
# Everything after VAL_END_DATE is the final test set

# ── Model random state ────────────────────────────────────────────────────────
RANDOM_STATE = 42
