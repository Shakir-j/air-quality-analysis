# 🌍 AIRWISE: Air Quality Analysis & Prediction

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![XGBoost](https://img.shields.io/badge/XGBoost-1182C3?style=for-the-badge&logo=xgboost&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-%23F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![Vanilla JS](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)

> An end-to-end environmental intelligence platform that analyzes historical observations from the Central Pollution Control Board (CPCB) across India, uncovers spatio-temporal pollution dynamics, and forecasts 1-hour-ahead particulate concentrations ($PM_{2.5}$) alongside official Indian National Air Quality Index (NAQI) public health advisories.

---

## 🎯 Project Overview
Particulate matter ($PM_{2.5}$) is the primary contributor to severe air pollution episodes across Indian metropolitan areas. This project provides a robust, full-stack analytics and predictive solution:
- **Large-Scale Data Analytics:** Processes raw hourly readings across monitoring stations in major cities spanning 2010 to 2023.
- **Leak-Free Temporal Progression:** Eliminates look-ahead bias by employing chronological train/validation/test partitions.
- **Production Forecasting:** Employs an XGBoost regression model to deliver next-hour forecasts, CPCB category badges, and actionable health guidance.
- **Modern Interactive Dashboard:** Features an environmental intelligence interface built with vanilla web technologies (HTML/CSS/JS) powered by a high-performance Python FastAPI backend.

---

## 🏛 System Architecture

- **Data Engineering (Python/Pandas):** Processes raw CPCB CSVs, interpolates NAQI sub-indices, performs physical outlier capping, and exports cleaned Parquet formats.
- **Machine Learning (Scikit-Learn/XGBoost):** Features time-lagged pollution levels and thermodynamic atmospheric indicators. Benchmarked across multiple tree-based and linear models.
- **Backend API (FastAPI):** Exposes RESTful JSON endpoints (`/api/locations`, `/api/air-quality`, `/api/trends`, `/api/prediction`). Uses a smart pre-computed JSON caching layer to serve complex analytics in milliseconds.
- **Frontend (Vanilla Web):** A responsive, dark-mode dashboard that dynamically consumes the API to render interactive metric cards, historical comparisons, and real-time ML inference results.

---

## 🚀 Installation & Execution Guide

### Prerequisites
- Python 3.10+
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/air-quality-analysis.git
cd air-quality-analysis
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application Server
```bash
python server.py
```
*The FastAPI server will boot up and automatically serve the frontend on `http://127.0.0.1:8000/`. Simply open this link in your web browser to interact with the dashboard.*

### 4. Run Unit Tests
```bash
pytest tests/ -v
```

---

## 📂 Repository Directory Structure

```text
air-quality-analysis/
├── frontend/                   # HTML, CSS, JS static assets for the web dashboard
├── data/
│   ├── raw/                    # Raw station CSVs (GitIgnored due to 2GB size)
│   ├── processed/              # Processed Parquet datasets (GitIgnored)
│   └── cache/                  # API JSON cache (Included to run app instantly without raw data)
├── models/                     # Serialized ML models (XGBoost) and preprocessors
├── reports/                    # Pre-rendered interactive figures and EDA reports
├── src/                        # Core Python engine (Data Loaders, Trainers, Predictor)
├── tests/                      # Automated unit tests (pytest)
├── server.py                   # FastAPI backend application server
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git tracking rules
└── README.md                   # Project documentation
```

---

## 🗺️ Product Roadmap & Future Improvements
As this project continues to evolve, the following features are planned for future releases:

### 1. Software Engineering & MLOps
- **Docker Containerization:** Add a `Dockerfile` and `docker-compose.yml` to ensure seamless deployment across any cloud environment without manual dependency installations.
- **CI/CD Pipeline (GitHub Actions):** Automate the `pytest` suite so tests run automatically every time new code is pushed.
- **Cloud Deployment:** Deploy the FastAPI backend and frontend to a cloud provider like AWS EC2, Render, or Heroku to make the app publicly accessible via a live URL.

### 2. Machine Learning Enhancements
- **Multi-Horizon Sequence Modeling:** Upgrade the current 1-hour ahead regression model to multi-step 24-hour forecasting using bidirectional LSTMs or Temporal Fusion Transformers (TFT).
- **Spatial Graph Neural Networks (GNNs):** Integrate inter-station wind vector matrices to model cross-city transboundary particulate transport across the Indo-Gangetic plain.
- **Satellite Data Integration:** Incorporate NASA MODIS / VIIRS satellite aerosol optical depth (AOD) to predict sudden regional biomass burning episodes.

---

## 👤 Project Information
- **Project Title:** AIRWISE - Air Quality Analysis and Prediction
- **Status:** Active Development
- **License:** MIT
