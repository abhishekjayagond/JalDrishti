# JalDrishti_abhi

**Groundwater Intelligence & Forecasting**<br/>
*National DWLR Telemetry Analytics & Multi-Year Aquifer Forecasting Platform*<br/>
*Addressing Central Ground Water Board (CGWB) Problem Statement #25068*

**Author & Project Lead:** Abhishek Jayagond<br/>
**Repository:** [https://github.com/abhishekjayagond/JalDrishti](https://github.com/abhishekjayagond/JalDrishti)<br/>
**Release Identity:** JalDrishti_abhi

---

## Executive Summary

Groundwater accounts for **63% of India's irrigation water** and **85% of rural drinking water supply**. Across India, over 5,260 Digital Water Level Recorder (DWLR) telemetry stations continuously transmit hydrostatic water level observations. Historically, turning this high-frequency sensor telemetry into actionable, forward-looking intelligence has been hindered by fragmented data pipelines and inconsistent analytical frameworks.

**JalDrishti** provides an end-to-end operational platform that transforms continuous DWLR sensor telemetry, IMD precipitation data, and hydrogeological parameters into real-time aquifer evaluations and scientific multi-year forecasts.

---

## Core Capabilities

### 1. Water Table Fluctuation (WTF) Analytics
- Ingests high-frequency sensor readings across monitoring stations.
- Calculates hourly, daily, and weekly rate of rise/fall metrics with 7-day moving averages.
- Automated anomaly detection identifying sudden drops indicative of localized over-extraction.
- Interactive geospatial vector cartography projecting station status across India.

### 2. Dynamic Monsoon Recharge Estimation
- Correlates water table recovery with India Meteorological Department (IMD) district precipitation.
- Derives net recharge volumes and recharge rates (m/day) across distinct aquifer formations (Alluvial, Hard Rock, Basalt, Granite, Sandstone).
- Detects recharge lag times and identifies critically stressed zones experiencing zero or negative seasonal recovery.

### 3. CGWB Resource Depletion Evaluation
- Implements standard Central Ground Water Board classification logic:
  - **Safe**: Water depth < 8 m, development stage < 70%
  - **Semi-Critical**: Water depth 8–15 m, development stage 70–90%
  - **Critical**: Water depth 15–25 m, development stage 90–100%
  - **Over-Exploited**: Water depth > 25 m, development stage > 100%
- Estimates depletion velocity and projected years-to-depletion.
- Computes aggregated District and State Resource Availability Indices (RAI).

### 4. Machine Learning & Spatial-Temporal AI Forecasting
- Pre-monsoon groundwater level forecasting trained on historical Karnataka DWLR records (1994–2025).
- Model benchmarks comparing persistence baselines, Linear Regression, Random Forest, LSTM, and Spatio-Temporal Graph Neural Networks.
- Calibrated 90th-percentile validation error bands providing transparent uncertainty quantification.
- Exploratory risk classification for upcoming seasonal water years.

### 5. Automated Early Warning & Alert Engine
- Continuous telemetry scanning for rapid drawdown spikes and sensor timeouts.
- Real-time notification feed identifying critically stressed blocks.
- One-click CSV exports for hydrogeological field reports and regulatory summaries.

---

## System Architecture

```
┌────────────────────────────────────────────────────────┐
│                      Data Sources                       │
│   India-WRIS (DWLR)  ·  IMD Telemetry  ·  CGWB Norms   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Data Ingestion Engine                │
│    Scraper Daemon  ·  Validation  ·  Anomaly Filter    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Storage & Cache Layer                │
│    TimescaleDB (7-day Hypertables)  ·  Redis Cache    │
└───────────────────────────┬────────────────────────────┘
                            │
             ┌──────────────┴──────────────┐
             ▼                             ▼
┌───────────────────────────┐ ┌───────────────────────────┐
│       Core API Backend    │ │   Predictive AI Service   │
│   FastAPI (Port 8000)     │ │   FastAPI (Port 8010)     │
│   Tasks 1, 2, 3 Analytics │ │   Annual ML Forecasting   │
└─────────────┬─────────────┘ └─────────────┬─────────────┘
              │                             │
              └──────────────┬──────────────┘
                             ▼
┌────────────────────────────────────────────────────────┐
│                   JalDrishti Web Console               │
│   React 18 · Vanilla CSS · Vector Telemetry Mapping   │
└────────────────────────────────────────────────────────┘
```

---

## Technology Stack

- **Frontend**: React 18, Vanilla CSS design system, Topographic contour motif, SVG geospatial mapping.
- **Backend API**: Python 3.10+, FastAPI, Uvicorn, SQLAlchemy ORM.
- **Database & Cache**: TimescaleDB (PostgreSQL 15), Redis 7.
- **Machine Learning**: scikit-learn, joblib, PyTorch, NumPy, Pandas.
- **Runtime Environment**: Native Windows & cross-platform services (PowerShell service supervisor).

---

## Quick Start

### Prerequisites
- **Python**: 3.10+ (with venv)
- **Node.js**: v18+ & npm
- **Database**: PostgreSQL 15 with TimescaleDB extension
- **Cache**: Redis 7
- For automated setup of local dependencies and database initialization, refer to [LOCAL_SETUP.md](./LOCAL_SETUP.md).

---

### Starting the Full Stack (Automated Launcher)

From an elevated or standard PowerShell terminal in the repository root:

```powershell
# Verify dependencies, start PostgreSQL, Redis, Backend, AI service, and Frontend UI
.\start-jaldrishti.ps1
```

This single command:
1. Validates Python virtual environment and Node.js/npm.
2. Starts native PostgreSQL (TimescaleDB) on port `5432`.
3. Starts native Redis on port `6379`.
4. Spawns the AI Forecasting FastAPI service on `http://localhost:8010`.
5. Spawns the Core Backend FastAPI service on `http://localhost:8000`.
6. Spawns the React Web Console on `http://localhost:3000`.
7. Monitors health endpoints and opens `http://localhost:3000` in the default browser.

To gracefully stop all background services without affecting unrelated processes:
```powershell
.\stop-jaldrishti.ps1
```

---

### Manual Service Execution

#### 1. Backend Service (Port 8000)
```powershell
# From repository root:
.\.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. AI Forecasting Service (Port 8010)
```powershell
# From repository root:
.\.venv\Scripts\Activate.ps1
cd ai
python -m uvicorn service.app:app --host 0.0.0.0 --port 8010 --reload
```

#### 3. Frontend Web Console (Port 3000)
```powershell
cd frontend
npm start
```
The application opens at `http://localhost:3000`.

---

## API Reference

### System & Telemetry Endpoints
- `GET /` — Service metadata and operational status
- `GET /api/health` — Database connectivity and telemetry counts
- `GET /api/stations` — Query monitoring stations with state/district filters
- `GET /api/stations/{station_id}` — Station metadata and well specifications

### Analytical Modules
- `GET /api/task1/{station_id}?hours=720` — Task 1 Water level fluctuation, trend, and anomalies
- `GET /api/task2/{station_id}?days=365` — Task 2 Dynamic recharge estimation and rainfall correlation
- `GET /api/task3/{station_id}?days=365` — Task 3 CGWB classification and depletion timeline
- `GET /api/ranking/states` — National state groundwater health ranking
- `GET /api/ranking/districts/{state}` — District-level groundwater health ranking
- `GET /api/alerts?hours=48` — Active threshold violation alerts
- `GET /api/alerts/anomalies?hours=24` — Detected sensor anomaly events
- `GET /api/export/summary/csv` — Export comprehensive station evaluation dataset

### AI Forecasting Endpoints
- `GET /health` — AI service health and node counts
- `GET /api/ai/metrics` — Model evaluation benchmarks (MAE, RMSE, R²)
- `GET /api/ai/stations?limit=500` — Candidate stations with long-term observations
- `GET /api/ai/forecast/{station_id}` — Multi-year pre-monsoon prediction with validation error band

---

## Testing & Verification

Run the automated test suite across all subsystems:

```bash
# Run backend, AI service, and data pipeline tests
pytest backend/tests ai/tests data/scripts/test_pipeline.py -v

# Run frontend production build
cd frontend
npm run build
```

---

## Authoritative Data Sources

- **Central Ground Water Board (CGWB)**: Hydrogeological norms, aquifer classification, and extraction thresholds.
- **India-WRIS (Water Resources Information System)**: Telemetry records from automated DWLR monitoring wells.
- **India Meteorological Department (IMD)**: District-level daily precipitation telemetry.

---

## Project Ownership

- **Project**: JalDrishti
- **Creator & Owner**: Abhishek Jayagond
- **Repository**: https://github.com/abhishekjayagond/JalDrishti
- **Copyright**: © 2026 Abhishek Jayagond
- **License**: All Rights Reserved

JalDrishti is an independently developed groundwater monitoring, analysis, and forecasting platform created by Abhishek Jayagond.
