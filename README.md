# 🌍 Air Quality Analysis and Prediction (India 2010–2023)

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.47-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![XGBoost](https://img.shields.io/badge/XGBoost-3.4-1182C5?style=for-the-badge&logo=xgboost&logoColor=white)](https://xgboost.readthedocs.io)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.7-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)](https://scikit-learn.org)
[![Plotly](https://img.shields.io/badge/Plotly-7.1-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com)
[![Pytest](https://img.shields.io/badge/Tests-10%20Passed-22C55E?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)

> **Official Problem Statement:**  
> *"Develop a data science and machine learning solution that analyzes environmental data to identify air quality patterns and predict air quality levels."*

An individual B.E. Computer Science semester project implementing an end-to-end environmental intelligence platform. Analyzes over **14.2 million historical observations** from Central Pollution Control Board (CPCB) stations across India, uncovers spatio-temporal and chemical pollution dynamics, and forecasts 1-hour-ahead particulate concentrations ($PM_{2.5}$) alongside official Indian National Air Quality Index (NAQI) classifications and public health advisories.

---

## 📑 Table of Contents
1. [Executive Summary](#-executive-summary)
2. [Dataset Lineage & Scope](#-dataset-lineage--scope)
3. [System Architecture](#-system-architecture)
4. [Data Preprocessing & CPCB NAQI Formulation](#-data-preprocessing--cpcb-naqi-formulation)
5. [Exploratory Data Analysis & Empirical Patterns](#-exploratory-data-analysis--empirical-patterns)
6. [Feature Engineering & Leakage-Free Validation](#-feature-engineering--leakage-free-validation)
7. [Machine Learning Benchmarking & Results](#-machine-learning-benchmarking--results)
8. [Interactive Streamlit Web Platform](#-interactive-streamlit-web-platform)
9. [UN Sustainable Development Goals (SDGs)](#-un-sustainable-development-goals-sdgs)
10. [Automated Verification & Unit Testing](#-automated-verification--unit-testing)
11. [Installation & Execution Guide](#-installation--execution-guide)
12. [Repository Directory Structure](#-repository-directory-structure)
13. [Limitations & Future Improvements](#-limitations--future-improvements)

---

## 🎯 Executive Summary
Particulate matter ($PM_{2.5}$) is the primary contributor to severe air pollution episodes across Indian metropolitan areas. This project provides an enterprise-grade analytics and predictive surveillance solution:
- **Big-Data Scale:** Ingests raw hourly readings across **453 monitoring stations in 241 cities** spanning 2010 to 2023. Focuses deep modeling on the top 10 metropolitan centers (**133 active stations**, **6,489,281 cleaned records**).
- **Leak-Free Temporal Progression:** Eliminates look-ahead bias by employing chronological train/validation/test partitions ($Train \le 2021$, $Val \in \text{H1 } 2022$, $Test \in \text{H2 } 2022\text{--}2023$).
- **Multi-Model Regression Benchmark:** Systematically benchmarks 5 distinct architectures: Linear Regression, Decision Tree, Random Forest, Gradient Boosting, and XGBoost.
- **Production Forecasting:** Achieves an $R^2$ of **0.9412** and test RMSE of **12.81 µg/m³**, delivering instantaneous next-hour forecasts, CPCB category badges, and actionable health guidance.
- **Modern Interactive Dashboard:** Features a dark environmental intelligence interface built with Streamlit and Plotly, with live prediction forms, geographic India mapping, correlation heatmaps, and diurnal cycle breakdowns.

---

## 📊 Dataset Lineage & Scope
- **Source:** [Kaggle Time Series Air Quality Data of India (2010–2023)](https://www.kaggle.com/datasets/abhisheksjha/time-series-air-quality-data-of-india-2010-2023) derived from the official Central Pollution Control Board (CPCB) continuous ambient air quality monitoring network.
- **Temporal Coverage:** January 1, 2010 – March 31, 2023 (Hourly sampling frequency).
- **Monitored Parameters:**
  - **Particulates:** $PM_{2.5}$ (primary target), $PM_{10}$.
  - **Gaseous Pollutants:** $NO_2$, $NO$, $NO_x$, $NH_3$, $SO_2$, $CO$, $Ozone$, $Benzene$, $Toluene$, $Xylene$.
  - **Meteorological Indicators:** Relative Humidity ($RH$), Wind Speed ($WS$), Ambient Temperature ($AT$), Solar Radiation ($SR$), Barometric Pressure ($BP$).

---

## 🏛 System Architecture

```
                                    +------------------------------------------+
                                    |  Raw Data: 453 CPCB CSVs (14.3M rows)    |
                                    +------------------------------------------+
                                                         |
                                                         v
                                    +------------------------------------------+
                                    | Phase 2: CPCB Cleaning & NAQI Engine     |
                                    |  - Negative sensor clamp (NaN)           |
                                    |  - Physical outlier capping              |
                                    |  - <=3h gap forward fill                 |
                                    |  - Official CPCB AQI sub-index formula   |
                                    |  - Parquet export (6.49M clean rows)     |
                                    +------------------------------------------+
                                                         |
                                                         v
                                    +------------------------------------------+
                                    | Phase 3: Multivariate EDA (11 Figures)   |
                                    |  - Seasonal, Correlation & City Heatmaps |
                                    |  - Diurnal bimodal commuter spikes       |
                                    +------------------------------------------+
                                                         |
                                                         v
                                    +------------------------------------------+
                                    | Phase 4-5: Feature Engineering           |
                                    |  - PM2.5 lags (1h, 2h, 3h, 6h, 12h, 24h) |
                                    |  - Rolling mean/std (3h, 6h, 24h)        |
                                    |  - 1h-lagged co-pollutants (NO2, CO, SO2)|
                                    |  - Chronological Train / Val / Test split|
                                    +------------------------------------------+
                                                         |
                                                         v
                                    +------------------------------------------+
                                    | Phase 6: ML Benchmarking & Selection     |
                                    |  - Linear, DecisionTree, RandomForest,   |
                                    |    GradientBoosting, XGBoost (Champion)  |
                                    |  - Metrics: MAE, MSE, RMSE, R2           |
                                    +------------------------------------------+
                                                         |
                                                         v
                                    +------------------------------------------+
                                    | Phase 7-8: Prediction Engine & Dashboard |
                                    |  - Real-time Streamlit Web Platform      |
                                    |  - Dynamic India Map & Health Advisories |
                                    |  - Model explainability (Feature Imp.)   |
                                    +------------------------------------------+
```

---

## 🧪 Data Preprocessing & CPCB NAQI Formulation

### 1. Robust Data Cleaning
- **Duplicate Handling:** Drops redundant timestamps per monitoring station.
- **Negative Value Clamping:** Environmental sensors occasionally report negative values during calibration drifts; these are systematically replaced with `NaN`.
- **Physical Outlier Capping:** Applied based on CPCB sensor measurement ceilings: $PM_{2.5} \le 500\text{ µg/m³}$, $PM_{10} \le 900\text{ µg/m³}$, $NO_2 \le 400\text{ µg/m³}$, $CO \le 50\text{ mg/m³}$, $RH \le 100\%$, $WS \le 50\text{ m/s}$.
- **Bounded Imputation:** Forward-filling is restricted strictly to gaps $\le 3\text{ hours}$ to prevent synthetic data creation over protracted sensor outages. Rows with unresolved $PM_{2.5}$ are dropped.

### 2. Official Indian NAQI Sub-Index Formula
The Central Pollution Control Board defines the sub-index $I_p$ for particulate concentration $C_p$ via piecewise linear interpolation across standard breakpoint bands:

$$I_p = \frac{I_{hi} - I_{lo}}{B_{hi} - B_{lo}} \times (C_p - B_{lo}) + I_{lo}$$

| Category | $PM_{2.5}$ Range (µg/m³) | NAQI Range | Color Code | Health Impact Summary |
|---|:---:|:---:|:---:|---|
| **Good** | 0 – 30 | 0 – 50 | `#10b981` (Green) | Minimal impact; clean outdoor air |
| **Satisfactory** | 31 – 60 | 51 – 100 | `#84cc16` (Lime) | Minor breathing discomfort to sensitive individuals |
| **Moderate** | 61 – 90 | 101 – 200 | `#f59e0b` (Amber) | Discomfort to people with asthma and heart conditions |
| **Poor** | 91 – 120 | 201 – 300 | `#f97316` (Orange) | Breathing discomfort on prolonged exposure |
| **Very Poor** | 121 – 250 | 301 – 400 | `#ef4444` (Red) | Respiratory illness on prolonged exposure |
| **Severe** | 251 – 500+ | 401 – 500 | `#991b1b` (Maroon) | Emergency condition; healthy people affected |

---

## 📈 Exploratory Data Analysis & Empirical Patterns
All 11 interactive Plotly figures are pre-generated in `reports/figures/`:
1. **Seasonal Smog Dynamics:** Winter concentrations in Delhi, Patna, and Lucknow are $3\times\text{--}4\times$ higher than summer levels due to temperature inversions and low planetary boundary layer heights.
2. **Coastal Atmospheric Ventilation:** Maritime centers (Bengaluru, Chennai, Mumbai) exhibit mean PM2.5 levels of 35–56 µg/m³ due to active sea-breeze dispersion and high convective boundary layers.
3. **Diurnal Bimodal Distribution:** Concentrations spike sharply between **08:00–10:00** (morning vehicular rush hour) and **20:00–23:00** (evening rush hour combined with nocturnal boundary layer subsidence).
4. **Co-Pollutant Interdependence:** Strong positive Pearson correlation ($r \approx 0.65\text{--}0.78$) between $PM_{2.5}$, $NO_2$, and $CO$, confirming vehicular combustion as a dominant local emission source.

---

## 🧠 Feature Engineering & Leakage-Free Validation

To guarantee strict compliance with real-world time-series conditions, **zero future data is leaked into the feature space**:
- **Temporal Lags:** $PM_{2.5}$ lagged at 1h, 2h, 3h, 6h, 12h, and 24h within each station group.
- **Rolling Statistics:** 3h, 6h, and 24h rolling mean and standard deviation computed with `closed='left'` (shifted by 1h) to ensure current-hour target values are strictly excluded.
- **Co-Pollutants:** 1h-lagged values of $NO_2$, $CO$, $SO_2$, and $Ozone$.
- **Concurrent Meteorology:** Current-hour Ambient Temperature, Relative Humidity, Wind Speed, and Solar Radiation.
- **Chronological Split:**
  - **Train Set:** Start date $\rightarrow$ **2021-12-31**
  - **Validation Set:** **2022-01-01** $\rightarrow$ **2022-06-30**
  - **Test Set (Untouched Final):** **2022-07-01** $\rightarrow$ **2023-03-31**

---

## 🏆 Machine Learning Benchmarking & Results

All models were evaluated on the chronological test partition. Root Mean Squared Error (RMSE) and Mean Absolute Error (MAE) are reported in µg/m³:

| Model Architecture | Test MAE | Test MSE | Test RMSE | Test $R^2$ | Train Time | Inference Latency | Architectural Role |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **XGBoost Regressor (Champion 🏆)** | **8.42** | **164.21** | **12.81** | **0.9412** | 248.5s | 1.2 ms | **Final Selected Model** |
| Random Forest Regressor | 8.95 | 182.44 | 13.51 | 0.9348 | 382.1s | 4.8 ms | Non-linear Ensemble Runner-Up |
| Gradient Boosting Regressor | 9.74 | 218.06 | 14.77 | 0.9221 | 420.0s | 2.1 ms | Boosting Baseline |
| Decision Tree Regressor | 12.18 | 345.82 | 18.60 | 0.8764 | 18.4s | 0.4 ms | Non-linear Baseline |
| Linear Regression (StandardScaler) | 15.65 | 532.19 | 23.07 | 0.8098 | 6.2s | 0.2 ms | Linear Baseline |

### Feature Importance & Interpretability
Extracting relative split contributions from the champion XGBoost architecture reveals:
1. `pm25_lag_1h` (44.2%): Strong temporal autocorrelation and particulate persistence.
2. `pm25_roll_mean_3h` (18.5%): Short-term particulate accumulation momentum.
3. `pm25_lag_2h` (8.9%): Intermediate persistence decay.
4. `hour` & `month` (6.7% combined): Diurnal commuter peaks and seasonal winter inversions.
5. `AT (degree C)` & `WS (m/s)` (7.0% combined): Thermodynamic atmospheric stability and mechanical dispersion.

---

## 💻 Interactive Streamlit Web Platform

The interactive dashboard is organized into 5 dedicated sections:
1. **🏠 Executive Dashboard:** High-level overview, nationwide KPI cards, interactive Plotly India Geo Map, and urban pollution rankings.
2. **📈 Pattern Analysis & EDA:** Dynamic filters for City, Pollutant, and Year range. Interactive time-series trends, correlation heatmaps, seasonal matrices, and diurnal cycle analyses.
3. **🔮 Real-Time Predictor:** Intuitive form for next-hour PM2.5 forecasting, realistic city presets (Delhi, Mumbai, Bengaluru, etc.), visual CPCB gauge charts, and health precautions.
4. **🧠 ML Models & Evaluation:** Full 5-model scorecard, RMSE & $R^2$ comparative charts, feature importance rankings, actual vs. predicted scatter plots, and residual diagnostics.
5. **📖 Methodology & SDGs:** End-to-end architectural documentation, CPCB interpolation formulas, leak-free time-series protocols, and UN Global Goals mapping.

---

## 🌍 UN Sustainable Development Goals (SDGs)

This project directly contributes to the United Nations 2030 Agenda:
- **SDG 3: Good Health and Well-Being (Target 3.9):** Reduces morbidity and mortality from toxic airborne particles by providing vulnerable populations (asthma/cardiac patients) with actionable 1-hour early warning advisories.
- **SDG 11: Sustainable Cities and Communities (Target 11.6):** Helps municipal authorities and environmental regulators isolate station-level hotspots and evaluate clean air action plans (NCAP).
- **SDG 13: Climate Action (Target 13.3):** Elevates public environmental awareness and provides open data tools for tracking atmospheric pollution.

---

## 🧪 Automated Verification & Unit Testing

A comprehensive test suite is located in `tests/` and verified with `pytest`:
- `tests/test_preprocessor.py`: Verifies CPCB breakpoint interpolation, vectorized AQI series calculation, non-negative variables, and physical outlier boundaries.
- `tests/test_features.py`: Verifies lag shift integrity, leakage-free rolling window bounds, and chronological non-overlapping train/val/test splits.
- `tests/test_predictor.py`: Verifies scalar AQI categorization across all 6 bands, negative value clamping, and advisory metadata completeness.

```bash
python -m pytest tests/ -v
# Result: 10 passed in 9.68s (100% pass rate)
```

---

## 🚀 Installation & Execution Guide

### Prerequisites
- Python 3.10+ (Recommended: Python 3.13)
- Windows / Linux / macOS

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/air-quality-analysis.git
cd air-quality-analysis
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Preprocessing Pipeline (Phase 2)
```bash
python scripts/run_preprocessing.py
```

### 4. Generate EDA Visualizations (Phase 3)
```bash
python scripts/run_eda.py
```

### 5. Train & Evaluate ML Models (Phase 6)
```bash
python scripts/run_training.py --no-tune
```

### 6. Launch Interactive Streamlit Web App (Phase 8)
```bash
streamlit run app/main.py
```

### 7. Run Unit Tests (Phase 9)
```bash
python -m pytest tests/ -v
```

---

## 📂 Repository Directory Structure

```
air-quality-analysis/
├── app/
│   ├── main.py                 # Streamlit application entry point & routing
│   ├── styles.py               # Dark environmental intelligence CSS & tokens
│   ├── pages_overview.py       # Page 1: Executive Dashboard & India Map
│   ├── pages_analysis.py       # Page 2: Pattern Analysis & Multivariate EDA
│   ├── pages_prediction.py     # Page 3: Real-Time Prediction & CPCB Health Advisory
│   ├── pages_models.py         # Page 4: ML Benchmarking, Explainability & Residuals
│   └── pages_methodology.py    # Page 5: Methodology, Architecture & UN SDGs
├── data/
│   ├── raw/                    # 453 Station CSVs + stations_info.csv
│   └── processed/              # air_quality_processed.parquet (6.49M clean rows)
├── models/
│   ├── final_model.pkl         # Serialized champion XGBoost model
│   ├── preprocessor.pkl        # Median imputers & feature metadata
│   └── model_metrics.csv       # Benchmark metrics across all 5 architectures
├── notebooks/                  # Interactive Jupyter exploration notebooks
├── reports/
│   └── figures/                # 11 Pre-rendered interactive Plotly HTML figures
├── scripts/
│   ├── run_preprocessing.py    # Standalone preprocessing CLI runner
│   ├── run_eda.py              # Standalone EDA figure generator
│   └── run_training.py         # Standalone ML training & evaluation runner
├── src/
│   ├── __init__.py
│   ├── config.py               # Global constants, paths, and pollutant mappings
│   ├── data_loader.py          # Station ingestion and multi-city filtering
│   ├── preprocessor.py         # CPCB cleaning, outlier capping & AQI formula
│   ├── eda.py                  # Plotly chart library (13 specialized functions)
│   ├── features.py             # Lag, rolling, and temporal feature engineering
│   ├── model_trainer.py        # 5-model training, time-aware split & tuning
│   └── predictor.py            # Production inference engine & health advisories
├── tests/
│   ├── test_preprocessor.py    # CPCB math and outlier unit tests
│   ├── test_features.py        # Feature engineering and split integrity tests
│   └── test_predictor.py       # Inference and category assignment tests
├── pytest.ini                  # Pytest configuration
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git tracking rules
└── README.md                   # Comprehensive project documentation
```

---

## 🔮 Limitations & Future Improvements
1. **Satellite Aerosol Optical Depth (AOD) Integration:** Incorporating NASA MODIS / VIIRS or ISRO INSAT-3D satellite aerosol optical thickness would allow accurate prediction during sudden, unscheduled regional biomass burning episodes.
2. **Multi-Horizon Sequence Modeling:** Extending the current 1-hour ahead regression model to multi-step recursive or direct 24-hour and 48-hour forecasting using Temporal Fusion Transformers (TFT) or bidirectional LSTMs.
3. **Spatial Graph Neural Networks (GNNs):** Integrating inter-station wind vector matrices to model cross-city transboundary particulate transport across the Indo-Gangetic Plain.

---

## 👤 Project Information
- **Project Title:** Air Quality Analysis and Prediction
- **Program:** Bachelor of Engineering (B.E.) in Computer Science & Engineering
- **Academic Year:** 2026
- **Status:** Completed & Validated ✅
