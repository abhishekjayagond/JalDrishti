# JalDrishti_abhi

**Groundwater Intelligence & Forecasting**<br/>
*National DWLR Telemetry Analytics & Multi-Year Aquifer Forecasting Platform*<br/>
*Addressing Central Ground Water Board (CGWB) Problem Statement #25068*

**Author & Project Lead:** Abhishek Jayagond<br/>
**Repository:** [https://github.com/abhishekjayagond/JalDrishti](https://github.com/abhishekjayagond/JalDrishti)<br/>
**Release Identity:** JalDrishti_abhi

---

## Executive Summary

Groundwater accounts for **63% of India's irrigation water** and **85% of rural drinking water supply**. Across India, over 5,260 Digital Water Level Recorder (DWLR) stations form the national automated groundwater telemetry network deployed by the Central Ground Water Board (CGWB) under the National Hydrology Project. Historically, turning sensor telemetry and sparse historical records into actionable, forward-looking intelligence has been hindered by fragmented data pipelines and inconsistent analytical frameworks.

**JalDrishti** provides an operational platform that bridges real-time telemetry analytics, dynamic recharge modeling, and scientific multi-year AI forecasting. In its current implementation baseline, JalDrishti operates on **390 verified real Karnataka CGWB observation wells** (with 32 years of annual pre-monsoon records spanning 1994–2025) and **78 nationwide benchmark fallback stations** (seeded with sinusoidal signals across 26 states for UI continuity), while providing ingestion pipelines ready to receive live continuous DWLR telemetry streams.

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

### 3. Aquifer Resource Evaluation, Depth Indicators & Statutory GEC-2015 Categorization
- **Operational Point-Level Depth Screening Tiers** (Field exploratory screening indicators for individual observation wells; strictly distinguished from official administrative block assessments):
  - **Safe Depth Tier**: Water depth < 8 m bgl
  - **Semi-Critical Depth Tier**: Water depth 8–15 m bgl
  - **Critical Depth Tier**: Water depth 15–25 m bgl
  - **Over-Exploited Depth Tier**: Water depth > 25 m bgl
  *(Note: Point-level depth screening tiers are exploratory operational indicators. They must NOT be confused with or substituted for official statutory CGWB GEC-2015 assessment-unit categorizations.)*
- **Statutory CGWB GEC-2015 Administrative Assessment-Unit Categorization**:
  - Evaluates administrative assessment units (Taluks / Blocks / Mandals / Watersheds) strictly as contiguous hydrogeological units. Individual monitoring wells are NEVER classified as official assessment units, and district fallback is strictly prohibited.
  - Requires authoritative volumetric **Stage of Groundwater Extraction (SOE)**:
    $$\text{SOE (\%)} = \frac{\text{Existing Gross Groundwater Draft for All Uses}}{\text{Annual Extractable Groundwater Resource}} \times 100\%$$
  - Validates SOE provenance against traceable records containing canonical assessment-unit identity, official CGWB publication citation, assessment year, and supporting volumetric accounting (in hectare-metres, ham). Rejects arbitrary user descriptions or unverified percentages as `Unassessed`.
  - Enforces spatial network representativeness: requires a distributed monitoring network ($\ge 2$ active stations) and $\ge 2$ spatially distinct monitoring stations per representative year under WMO No. 168 / CGWB network design principles. Solitary single-well blocks return `Unassessed`.
  - Requires at least 10 years of spatially representative pre-monsoon (Apr–May) AND 10 years of post-monsoon (Oct–Nov) records separately.
  - Station-year normalized Equal Station-Year Weighting prevents high-frequency telemetry wells from dominating manual observation wells.
  - Documented observation data-quality screening filters out invalid/suspect flags (`E`, `S`, `R`), anomalies, and unphysical levels before seasonal aggregation.
- Computes cadence-aware depletion rate velocity (m/year) and heuristic Resource Availability Index (RAI).

### 4. Machine Learning & Spatial-Temporal AI Forecasting
- Pre-monsoon groundwater level forecasting trained on 390 long-history Karnataka CGWB observation wells (1994–2025).
- Leakage-safe chronological validation split: Training (1998–2018, $n=7,633$), Validation (2019–2022, $n=717$), and Test holdout (2023–2025, $n=997$).
- Imputers and scalers fitted strictly on training data (preventing temporal data leakage).
- Model selection performed on the separate validation period, selecting Linear Regression ($R^2 = 0.580$, $\text{MAE} = 1.63\text{ m}$ on unseen test set).
- Split conformal prediction calibrated on validation residuals, providing transparent 90% uncertainty envelopes ($q = 4.98\text{ m}$, 95.1% verified empirical test coverage).
- Strictly distinguishes verified Karnataka observation wells from synthetic nationwide benchmark demo nodes (which are 100% excluded from model training and evaluation).

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
- `GET /api/task3/{station_id}?days=365` — Task 3 Exploratory point-level depth screening indicator and cadence-aware depletion metrics (non-statutory)
- `GET /api/gec/assessment-unit/{block_name}` — Statutory CGWB GEC-2015 Administrative Assessment-Unit Evaluation (requires authoritative SOE provenance & decadal seasonal trends)
- `GET /api/gec/assessment-units` — List administrative assessment units across monitoring network with spatial representativeness status
- `GET /api/ranking/states` — National state groundwater health ranking
- `GET /api/ranking/districts/{state}` — District-level groundwater health ranking
- `GET /api/alerts?hours=48` — Active threshold violation alerts (exploratory depth screening)
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
