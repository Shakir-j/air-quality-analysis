# AIRWISE — Air Quality Analysis and Prediction

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![XGBoost](https://img.shields.io/badge/ML-XGBoost-1182C3)](https://xgboost.readthedocs.io/)
[![Tests](https://img.shields.io/badge/Tests-39%20Passed-brightgreen?logo=pytest&logoColor=white)](tests)

**AIRWISE** is a local-first web application for exploring historical air-quality observations across Indian cities and generating one-hour-ahead PM2.5 forecasts. It combines interactive historical analysis, city comparisons, environmental insights, maps and a machine-learning prediction interface.

The application uses a **Python FastAPI backend**, a lightweight **HTML/CSS/JavaScript frontend**, a precomputed historical analytics cache, and a saved **XGBoost regression model**.

> **Data note:** The bundled historical archive ends on **31 March 2023 at 23:00**. Historical dashboard values are not live readings. Predictions are model estimates, not guaranteed future conditions. A predicted PM2.5 AQI sub-index is not a complete multi-pollutant AQI forecast.

---

## Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Data and Coverage](#data-and-coverage)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Getting Started](#getting-started)
- [Using AIRWISE](#using-airwise)
- [Machine-Learning Model](#machine-learning-model)
- [Model Evaluation](#model-evaluation)
- [AQI Methodology](#aqi-methodology)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Regenerating the Analytics Cache](#regenerating-the-analytics-cache)
- [Limitations](#limitations)
- [SDG Alignment](#sdg-alignment)

---

## Project Overview

Air pollution changes with traffic, industrial activity, weather and seasonal conditions. AIRWISE makes historical measurements easier to explore and provides a machine-learning estimate of PM2.5 one hour ahead.

The project aims to:

1. Analyse a large historical air-quality archive.
2. Visualise pollution patterns over time and across locations.
3. Compare pollutant concentrations and historical conditions among cities.
4. Present data-derived environmental insights.
5. Estimate the next-hour PM2.5 concentration with a trained regression model.
6. Explain the prediction with a derived PM2.5 AQI sub-index and general health guidance.

## Features

### Home
Provides an overview of the application and its historical air-quality analysis capabilities.

### Air Quality
- Explore data by city and station where station-level data is available.
- Distinguish historical averages from the latest available archived observation.
- View monthly and yearly trends for PM2.5, PM10, NO2, SO2, CO and ozone where measurements are available.
- See units, observation counts and date coverage in chart details.
- Identify partial years, including 2023, and account for differences in coverage.

### Explore
Compare cities and explore geographical and pollutant patterns using the data available in the archive.

### Insights
View analytical summaries derived from historical data. These findings are retrospective patterns and should not be interpreted as proof that a particular factor caused a pollution event.

### Prediction
- Enter current PM2.5 and optional recent pollutant or weather inputs.
- Use preset scenarios or custom inputs.
- Receive a one-hour-ahead PM2.5 estimate.
- View the derived PM2.5 AQI sub-index, category and general health guidance.

## Data and Coverage

The bundled archive is described by the project as historical Indian ambient air-quality observations from the CPCB monitoring network.

| Property | Value |
|---|---|
| Records | 4,341,626 |
| Cities | 10 |
| Monitoring stations | 130 |
| First archive timestamp | 17 February 2010, 12:00 |
| Last archive timestamp | 31 March 2023, 23:00 |
| Runtime analytics file | `data/cache/air_quality_cache.json` |
| Processed input used for cache generation | `data/processed/air_quality_processed.parquet` |

### Approximate city coverage

The dates below describe broad archive coverage, not continuous hourly observations. Each city, station and pollutant can have different gaps and valid measurement counts.

| City | Approximate coverage |
|---|---|
| Ahmedabad | 2015–2023 |
| Bengaluru | 2015–2023 |
| Chennai | 2015–2023 |
| Delhi | 2010–2023 |
| Hyderabad | 2015–2023 |
| Kolkata | 2018–2023 |
| Lucknow | 2015–2023 |
| Mumbai | 2013–2023 |
| Patna | 2013–2023 |
| Pune | 2015–2023 |

The archive ends in March 2023, so 2023 is a partial year. Missing station-hours and pollutant readings may affect chart values and comparisons.

### Supported pollutants

| Pollutant | Abbreviation | Unit used in the interface |
|---|---|---|
| Fine particulate matter | PM2.5 | µg/m³ |
| Coarse particulate matter | PM10 | µg/m³ |
| Nitrogen dioxide | NO2 | µg/m³ |
| Sulphur dioxide | SO2 | µg/m³ |
| Carbon monoxide | CO | mg/m³ |
| Ozone | O3 | µg/m³ |

Values in different units should not be compared directly on one numerical scale without conversion and context.

## Technology Stack

| Layer | Technologies |
|---|---|
| Language | Python |
| Web server and API | FastAPI, Uvicorn |
| Data processing | Pandas, NumPy |
| Machine learning | XGBoost, scikit-learn |
| Model persistence | Joblib |
| Frontend | HTML, CSS, vanilla JavaScript |
| Charts | Plotly.js |
| Maps | Leaflet.js |
| Automated tests | pytest |
| Historical runtime data | Precomputed JSON cache |

The historical dashboard, bundled frontend assets and model inference run locally. Live-data integrations and online map tiles may require an internet connection.

## System Architecture

```text
Historical air-quality data
          |
          v
Data processing and feature engineering
          |
     +----+------------------+
     |                       |
     v                       v
Processed historical data  Model training/evaluation
     |                       |
     v                       v
Precomputed JSON cache     Saved XGBoost model
     |                     + preprocessing metadata
     +-----------+-----------+
                 |
                 v
           FastAPI backend
                 |
                 v
       HTML/CSS/JavaScript UI
        |        |         |
        v        v         v
      Home    Analytics  Prediction
               and maps
```

### Main components

- `server.py` — FastAPI application, API routes and frontend serving.
- `src/generate_cache.py` — Generates precomputed historical analytics from the processed dataset.
- `src/features.py` — Builds time-aware model features.
- `src/model_trainer.py` — Model training and evaluation workflow.
- `scripts/train_candidate_model.py` — Trains and evaluates a candidate model; it does not automatically promote it.
- `src/predictor.py` — Loads saved artifacts, prepares model inputs and generates forecasts.
- `src/aqi.py` — Pollutant sub-index and related AQI calculations.
- `frontend/` — Web pages, styles, JavaScript, charts and map assets.

## Getting Started

### Requirements

- Python 3.13, matching the current project dependency setup.
- Git.
- Internet access for initial repository cloning and package installation.

### 1. Clone the repository

```powershell
git clone https://github.com/Shakir-j/air-quality-analysis.git
Set-Location air-quality-analysis
```

### 2. Create a virtual environment

```powershell
py -3.13 -m venv .venv
```

### 3. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Start the application

```powershell
.\.venv\Scripts\python.exe server.py
```

Keep the terminal open while the server runs.

### 5. Open AIRWISE

Navigate to **http://127.0.0.1:8000** in your browser. To stop the server, press `Ctrl+C` in the terminal.

For an existing local installation:

```powershell
Set-Location "C:\Projects\air-quality-analysis"
& ".\.venv\Scripts\python.exe" server.py
```

## Using AIRWISE

### Historical analysis

1. Open **Air Quality**.
2. Choose a city or station where available.
3. Select a pollutant and inspect its monthly or yearly chart.
4. Read chart tooltips for units, valid observation counts and coverage dates.
5. Consider missing values and partial-year coverage when comparing results.

### Prediction

1. Open **Prediction**.
2. Select a preset or enter custom values.
3. Provide the current PM2.5 concentration and any other inputs available to you.
4. Submit the form.
5. Review the predicted PM2.5 concentration, derived sub-index, category and health guidance.

The prediction is a model estimate, not a current sensor reading or a guarantee of future conditions.

## Machine-Learning Model

### Objective and target

The saved model estimates **PM2.5 concentration one hour ahead**. It is not a multi-day forecast model.

### Model and features

The saved inference artifact is an XGBoost regressor with 28 input features, including:

- Calendar features such as year, month, hour, day of week, season and weekend status.
- PM2.5 lags at selected historical intervals.
- Rolling PM2.5 means and standard deviations.
- Recent co-pollutant values, including NO2, CO, SO2, ozone and NOx.
- Meteorological variables including relative humidity, wind speed, temperature, solar radiation and barometric pressure.

Feature engineering is station-aware and timestamp-aware. Missing input features at inference are filled using medians stored with the model's preprocessing metadata.

### Saved model artifacts

- `models/final_model.pkl` — model used by the prediction pipeline.
- `models/preprocessor.pkl` — expected feature names and training-set medians.
- `models/model_metrics.csv` — recorded model evaluation metrics.
- `models/final_model_evaluation.json` — evaluation details and baseline comparison.

The candidate training script is `scripts/train_candidate_model.py`. It saves candidate outputs separately and does not automatically promote a candidate. Running the training script is not necessary to start the website.

## Model Evaluation

The saved evaluation record reports the following results for the timestamp-aligned XGBoost candidate. These are recorded offline metrics; they were not recomputed while preparing this README.

### Candidate model

| Metric | Validation | Held-out test |
|---|---:|---:|
| MAE | 9.8476 µg/m³ | 9.1604 µg/m³ |
| RMSE | 18.4421 µg/m³ | 18.4241 µg/m³ |
| R² | 0.9463 | 0.9295 |
| Rows | 1,285,756 | 1,638,400 |

### Persistence baseline

| Metric | Validation | Held-out test |
|---|---:|---:|
| MAE | 10.7664 µg/m³ | 9.8178 µg/m³ |
| RMSE | 21.0613 µg/m³ | 20.8242 µg/m³ |

The evaluation file reports an RMSE improvement of **12.44% on validation** and **11.53% on the held-out test set** over the persistence baseline. R² is a regression metric, not the percentage of predictions that are correct. Historical offline scores do not guarantee the same performance on live conditions, new locations or later periods.

### Evaluation setup

- Split policy: chronological 70/15/15 by unique timestamp.
- Validation begins: `2019-06-11 16:00:00`.
- Test begins: `2021-05-06 08:00:00` and ends at `2023-03-31 23:00:00`.
- Training rows available: 1,167,513.
- Training rows used for this candidate: 800,000.
- Number of input features: 28.

### Artifact status clarification

The evaluation metadata retains `candidate_only_not_promoted` and `production_model_replaced: false` because the candidate-training script does not automatically promote its output. In the development working copy, SHA-256 checks showed that the model and preprocessor at the production paths were byte-for-byte identical to the corresponding candidate artifacts.

The candidate-validation directory is excluded by `.gitignore` and is not stored in Git. Therefore, that hash comparison was a **local verification** and cannot be repeated from a clean clone unless the candidate files are regenerated or supplied. The evaluation metrics above are the saved values; the status fields have not been silently reinterpreted as a new promotion event.

## AQI Methodology

AIRWISE has two distinct kinds of index output.

### Historical pollutant index calculations

The current implementation in `src/aqi.py` uses pollutant-specific concentration breakpoints and averaging-window requirements:

- PM2.5, PM10, NO2 and SO2: 24-hour windows with at least 16 valid hourly readings.
- CO and ozone: 8-hour windows with at least 8 valid hourly readings.
- The composite estimate requires at least three qualifying pollutant sub-indices, including at least one particulate pollutant.

Whether an index can be calculated depends on the available valid measurements.

### Prediction output

The Prediction tab converts the predicted PM2.5 concentration into a **PM2.5-derived sub-index**. This is **not a forecast of the complete multi-pollutant CPCB AQI**. An index derived from an hourly model prediction should not be mistaken for an official regulatory AQI based on the prescribed measurements and averaging periods.

Health guidance is general information and not a personalised medical assessment.

## API Reference

The frontend uses the FastAPI endpoints listed below.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/locations` | Available city and station information |
| `GET` | `/api/air-quality` | Air-quality summaries for the selected scope |
| `GET` | `/api/trends` | Historical monthly and yearly trends |
| `GET` | `/api/comparison` | Cross-city comparison data |
| `GET` | `/api/insights` | Data-derived environmental insights |
| `POST` | `/api/prediction` | Input-based one-hour-ahead PM2.5 prediction |
| `POST` | `/api/prediction/live` | Attempts prediction using recent observations and weather inputs |

### Example prediction request

Send a JSON body to `POST /api/prediction`:

```json
{
  "city": "Delhi",
  "pm25_current": 50,
  "pm25_lag_2h": 45,
  "pm25_lag_3h": 48,
  "no2": 25,
  "co": 0.8,
  "so2": 8,
  "ozone": 20,
  "hour": 18,
  "month": 11,
  "day_of_week": 2,
  "is_weekend": 0
}
```

`pm25_current` is required. Other supported inputs are optional and are handled according to the backend's feature-preparation logic.

An example successful response is shown below. The numbers are illustrative; results depend on request values.

```json
{
  "status": "success",
  "predicted_pm25": 65.49,
  "predicted_aqi": 118.3,
  "aqi_category": "Moderate",
  "provenance": "Model prediction (1-hour ahead forecast)"
}
```

The `/api/prediction/live` endpoint depends on configured upstream data sources and network availability. It may fail when an external service is unavailable.

## Project Structure

```text
air-quality-analysis/
├── server.py
├── requirements.txt
├── pytest.ini
├── README.md
├── data/
│   ├── cache/
│   │   └── air_quality_cache.json
│   ├── processed/
│   │   └── air_quality_processed.parquet
│   └── raw/
├── frontend/
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── static/
│       └── vendor/
├── models/
│   ├── final_model.pkl
│   ├── preprocessor.pkl
│   ├── model_metrics.csv
│   └── final_model_evaluation.json
├── scripts/
│   └── train_candidate_model.py
├── src/
│   ├── aqi.py
│   ├── config.py
│   ├── data_loader.py
│   ├── eda.py
│   ├── features.py
│   ├── generate_cache.py
│   ├── live_data.py
│   ├── model_trainer.py
│   ├── predictor.py
│   └── preprocessor.py
└── tests/
    ├── test_api.py
    └── test_predictor_time_alignment.py
```

Raw and processed datasets can vary between local setups. For normal website operation, the precomputed cache and saved model artifacts are the key runtime assets.

## Testing

Run the automated test suite from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The latest recorded local run passed **39 tests**. A separate browser walkthrough also verified the five application views. The Prediction tab was checked through Chrome DevTools: `POST /api/prediction` returned HTTP `200 OK`, and the UI values matched the API response after display rounding.

The timestamp-boundary regression test is in `tests/test_predictor_time_alignment.py`. It verifies that an observation at 23:00 on Sunday, 31 December 2023, is forecast for 00:00 on Monday, 1 January 2024, with the target hour, month, weekday and weekend features aligned to the forecast target.

These results describe the development environment and do not guarantee identical behaviour on every machine or dependency version.

## Regenerating the Analytics Cache

Only regenerate the cache after the processed dataset or cache-generation logic changes. Ensure the processed Parquet input exists, then run:

```powershell
.\.venv\Scripts\python.exe .\src\generate_cache.py
```

Review generated changes and rerun the tests before committing. The website does not need to run the cache generator on every startup.

## Limitations

- **Historical cutoff:** The bundled archive ends on 31 March 2023; it is not a live feed.
- **Uneven coverage:** Cities, stations and pollutants can have different observation periods and missing values.
- **Forecast horizon:** The model is intended for one-hour-ahead PM2.5 prediction, not multi-day forecasting.
- **Missing inputs:** Inference can substitute training-set medians for missing features; this may make a forecast less representative of unusual conditions.
- **Generalisation:** Offline metrics do not guarantee performance in current conditions or unseen locations.
- **AQI interpretation:** The prediction's PM2.5 sub-index is not a complete composite AQI forecast.
- **Live-data dependencies:** Current observations and weather integrations may require internet access and functioning external services.
- **Map tiles:** Map backgrounds may depend on an online tile provider even when the rest of the application runs locally.
- **Data licensing:** Check the original dataset's source, terms and attribution requirements before redistributing raw data.

## SDG Alignment

AIRWISE aligns with the aims of:

- **[SDG 11 — Sustainable Cities and Communities](https://sdgs.un.org/goals/goal11):** Helps users explore historical urban air-quality patterns.
- **[SDG 3 — Good Health and Well-Being](https://sdgs.un.org/goals/goal3):** Presents air-pollution information and general guidance about potential exposure concerns.

This is an educational and analytical project. It does not replace environmental regulators, official monitoring services or medical advice.

---

## Repository

**GitHub:** https://github.com/Shakir-j/air-quality-analysis

Contributions and further development should preserve the distinction between historical measurements, model predictions, pollutant sub-indices and full composite AQI values.

## Optional Live CPCB Telemetry

AIRWISE supports historical analysis and manual predictions without live mode. Live telemetry requires internet access and a valid CPCB API credential configured locally.

### Run with live data enabled (Windows PowerShell)

From the project root, run:

```powershell
$env:AIRWISE_ENABLE_LIVE_DATA = "1"
.\.venv\Scripts\python.exe server.py
```

Keep the terminal open while the server runs. The environment setting applies to that PowerShell session.

Keep credentials in the ignored local `.env.local` file. Never commit credentials to GitHub.

Validated PM2.5 observations are saved locally in `data/cache/live_pm25_history.json`, which is excluded from Git. Readings are separated by station and grouped by clock hour. Missing earlier-hour readings remain unavailable rather than being fabricated.

### Verification

The development test suite passed 54 tests on 24 October 2026. Browser checks covered Home, Air Quality, Explore, Insights and Prediction, including a live CPCB prediction. Local smoke checks returned HTTP 200 for `/`, `/api/insights` and `/openapi.json`.
