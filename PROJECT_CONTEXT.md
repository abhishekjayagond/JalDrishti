# JalDrishti — Primary Project Handover & System Context

**Document Version:** 2.0.0  
**Last Updated:** November 7, 2026  
**Repository:** [https://github.com/abhishekjayagond/JalDrishti](https://github.com/abhishekjayagond/JalDrishti)  
**Lead / Author:** Abhishek Jayagond  
**Release Identifier:** JalDrishti_abhi  

> [!IMPORTANT]
> This document is the single source of truth for the JalDrishti codebase. It provides complete architectural, operational, algorithmic, and deployment context for any developer or AI assistant continuing development.

---

## 1. Project Purpose, Objectives & Current Status

### 1.1 Problem Statement
JalDrishti addresses **Central Ground Water Board (CGWB) Problem Statement #25068**: *Real-time telemetry analysis and multi-year aquifer forecasting from Digital Water Level Recorder (DWLR) networks*. 

Groundwater provides 63% of India's irrigation water and 85% of rural drinking supplies. India operates over 5,260 automated DWLR stations transmitting hydrostatic water-level measurements. JalDrishti ingests this telemetry, estimates dynamic monsoon recharge, classifies aquifer depletion per CGWB norms, and forecasts upcoming seasonal water levels with uncertainty bounds.

### 1.2 Core Capabilities
1. **Task 1: Water Table Fluctuation (WTF) Analytics:** Real-time water depth trend analysis, 7-day moving averages, drawdown velocities, and localized over-extraction anomaly detection.
2. **Task 2: Dynamic Monsoon Recharge Estimation:** Correlation between India Meteorological Department (IMD) rainfall events and aquifer recovery curves across 5 geological formations (Alluvial, Hard Rock, Basalt, Granite, Sandstone).
3. **Task 3: CGWB Resource Depletion Evaluation:** Official GEC-2015 categorization (Safe, Semi-Critical, Critical, Over-Exploited), Resource Availability Index (RAI), and years-to-depletion projection.
4. **Task 4: AI & Spatial-Temporal Groundwater Forecasting:** Multi-year pre-monsoon water depth prediction with conformal/residual uncertainty bands.
5. **Interactive Geospatial Console:** Geographically accurate Indian base map displaying verified telemetry wells and benchmark centroids, state/district health scorecards, active alerts, and CSV exports.

### 1.3 Completion & Verification Status
| Subsystem / Feature | Implementation State | Verification Level | Notes |
| :--- | :--- | :--- | :--- |
| Core Backend API (FastAPI) | Complete | **Verified & Working** | Pytest passing (6/6 tests), runs on native Windows port 8000 |
| AI Forecasting Service (FastAPI) | Complete | **Verified & Working** | Pytest passing (4/4 tests), runs on native Windows port 8010 |
| Frontend Console (React 18) | Complete | **Verified & Working** | Minimal Professional UI, builds cleanly, tests pass |
| Indian Base Map & Projection | Complete | **Verified & Working** | Authentic SVG state borders with calibrated Web Mercator (93.8% polygon containment) |
| Database & Local Services | Complete | **Verified & Working** | Native Windows PostgreSQL 15 (TimescaleDB) + Redis 7 (468 stations, 2.6M readings) |
| Ingestion & Scraper Pipeline | Complete | **Implemented** | Working scraper with resilient benchmark fallback |
| Historical Training Data | Complete (Karnataka) | **Verified** | 390 verified CGWB stations (1994–2025 real pre-monsoon records) |
| Nationwide Benchmark Coverage | Complete (26 States) | **Verified** | 78 calibrated benchmark fallback stations (3 per state) for UI continuity |

---

## 2. Technology Stack & System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Data Ingestion Layer                            │
│    India-WRIS DWLR Telemetry  ·  IMD Precipitation  ·  CGWB Norms      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Storage & Memory Cache Layer                         │
│   PostgreSQL 15 + TimescaleDB (Port 5432)  ·  Redis 7 Cache (Port 6379) │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
              ┌─────────────────────┴─────────────────────┐
              ▼                                           ▼
┌───────────────────────────┐               ┌───────────────────────────┐
│     Core Backend API      │               │   AI Forecasting Service  │
│   FastAPI (Port 8000)     │◄─────────────►│   FastAPI (Port 8010)     │
│   Tasks 1, 2, 3 Analytics │  HTTP Proxy   │   Annual ML Predictions   │
└─────────────┬─────────────┘               └─────────────┬─────────────┘
              │                                           │
              └─────────────────────┬─────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   JalDrishti Web Console (React 18)                    │
│   Port 3000  ·  Vanilla CSS  ·  Design Direction A  ·  SVG Mercator    │
└────────────────────────────────────────────────────────────────────────┘
```

- **Runtime Environment:** Native Windows 10/11 (No Docker or Docker Desktop required).
- **Service Supervisor:** PowerShell automation scripts (`start-jaldrishti.ps1` / `stop-jaldrishti.ps1`).
- **Core API Backend:** Python 3.10+, FastAPI, Uvicorn, SQLAlchemy ORM, psycopg2.
- **AI Forecasting Service:** Python 3.10+, FastAPI, scikit-learn, joblib, PyTorch, Pandas, NumPy.
- **Database & Cache:** PostgreSQL 15 with TimescaleDB extension, Redis 7 (embedded binaries in `.local_services/`).
- **Frontend Console:** React 18, React Router DOM v6, Lucide React icons, Native SVG rendering.

---

## 3. Directory Layout & Key Files

```
D:\major-project\JalDrishti\
├── .env.example                     # Environment configuration template
├── LOCAL_SETUP.md                   # Native Windows installation and prerequisite guide
├── PROJECT_CONTEXT.md               # Primary project handover document (this file)
├── README.md                        # Project overview and run instructions
├── start-jaldrishti.ps1             # One-click native Windows service launcher
├── stop-jaldrishti.ps1              # Graceful background service terminator
├── india_map_with_state_borders.svg # Authentic 36-state India base map asset (1000x1000)
│
├── ai/                              # Spatial-Temporal AI Forecasting Service
│   ├── data/processed/              # Prepared feature matrices and Karnataka node graph
│   │   ├── annual_adjacency.npy     # Distance-weighted 390x390 graph adjacency
│   │   ├── annual_model_features.csv# 30-year feature lag matrix (1994-2025)
│   │   ├── annual_nodes.csv         # 390 Karnataka station coordinates and IDs
│   │   └── phase1_karnataka_annual_clean.csv # Cleaned pre-monsoon observations
│   ├── models/                      # Serialized trained model weights and evaluation metadata
│   │   ├── linear_regression.joblib # Production prediction model
│   │   ├── random_forest.joblib     # Benchmark ensemble model
│   │   ├── lstm.pt                  # Benchmark deep sequential model
│   │   ├── stgnn.pt                 # Benchmark spatio-temporal graph neural network
│   │   ├── metrics.json             # Model benchmark metrics (MAE, RMSE, R2)
│   │   └── conformal.json           # Empirical residual uncertainty calibrations
│   ├── service/
│   │   ├── app.py                   # FastAPI service application (Port 8010)
│   │   └── ui.html                  # Standalone lightweight AI debugging UI
│   ├── src/                         # ML pipeline modules (data prep, training, graph build)
│   └── tests/                       # Pytest suite for AI pipeline and endpoints
│
├── backend/                         # Core Analytics & Data Management API
│   ├── algorithms/                  # Hydrogeological calculation engines
│   │   ├── task1_fluctuation.py     # WTF analytics, moving average, anomalies
│   │   ├── task2_recharge.py        # Dynamic monsoon recharge & rainfall correlation
│   │   └── task3_evaluation.py      # CGWB classification & depletion timeline
│   ├── api/
│   │   └── main.py                  # FastAPI route controllers & AI gateway proxy
│   ├── app/                         # Models, service abstractions, alert generators
│   ├── db/
│   │   ├── database.py              # SQLAlchemy engine & session factory
│   │   └── init.sql                 # PostgreSQL tables and TimescaleDB hypertables
│   ├── fetch/                       # Live WRIS & IMD scrapers
│   └── tests/                       # Pytest suite for core API and algorithms
│
├── data/                            # Ingestion Daemons & Seed Scripts
│   └── scripts/
│       ├── clean_data.py            # Telemetry outlier detection and validation
│       ├── db_writer.py             # Bulk insert into TimescaleDB
│       ├── scraper.py               # Periodic scraper daemon
│       ├── seed_ai_stations.py      # Seed 390 Karnataka CGWB stations
│       └── seed_all_states.py       # Seed 360 benchmark stations nationwide
│
└── frontend/                        # React 18 Web Console (Port 3000)
    ├── public/                      # Static assets & HTML template
    │   └── india_map_with_state_borders.svg
    └── src/
        ├── App.js                   # Application root, routing, state & map container
        ├── App.css                  # Design Direction A design system tokens
        ├── IndiaStateBorders.js     # 36 authentic state SVG vectors & Web Mercator projection
        ├── AIForecastPanel.js       # AI prediction panel with uncertainty bands
        ├── StateRanking.js          # National and district health league tables
        ├── TaskDetail.js            # Hydrogeological detail inspector (Tasks 1, 2, 3)
        ├── TopoContour.js           # Topographic line graphic motif
        ├── icons.js                 # Unified Lucide icon exports
        └── map_projection.test.js   # Projection and geospatial boundary unit tests
```

---

## 4. Database Schema & Data Architecture

### 4.1 Storage Engine
- **RDBMS:** PostgreSQL 15 with TimescaleDB extension.
- **Hypertables:** Partitioned across time chunks for efficient time-series range scans.

### 4.2 Key Tables
1. **`stations`:**
   - Columns: `station_id` (PK, text), `name`, `state`, `district`, `block`, `latitude`, `longitude`, `aquifer_type`, `depth_well_m`, `specific_yield`, `is_active`, `is_benchmark`.
   - Distinguishes verified DWLR wells (`is_benchmark=false`) from approximate benchmark centroids (`is_benchmark=true`).
2. **`dwlr_readings` (Hypertable):**
   - Columns: `time` (TIMESTAMPTZ, partitioned), `station_id` (FK), `water_level_m_bgl`, `water_temperature_c`, `battery_voltage_v`, `raw_signal_strength`.
   - Continuous high-frequency telemetry.
3. **`rainfall_readings` (Hypertable):**
   - Columns: `time` (TIMESTAMPTZ, partitioned), `district`, `state`, `rainfall_mm`.
4. **`alerts`:**
   - Active threshold violations, critical drawdown warnings, and sensor timeout alerts.
5. **`anomalies`:**
   - Statistical outliers (Z-score > 3.0 or sudden drop > 1.5 m within 2 hours).

### 4.3 Reconciled Data Status & Provenance
The TimescaleDB database contains **468 total groundwater stations** across **26 Indian states**:

1. **Verified Real CGWB Observation Stations (390 Stations):**
   - **Location:** Karnataka.
   - **Station IDs:** Prefixed with `KAR_` (matching `ai/data/processed/annual_nodes.csv`).
   - **Data Nature:** **Real historical observation data** spanning 1994–2025 pre-monsoon water levels (meters below ground level, m bgl) sourced from official CGWB ground surveys.
   - **Coordinates:** Exact survey well latitude and longitude coordinates.
   - **Data Quality Flag:** Marked with `data_quality_flag='HISTORICAL_ANNUAL'`.

2. **Simulated Benchmark Fallback Stations (78 Stations):**
   - **Coverage:** 26 Indian states (3 stations per state, covering Karnataka and 25 other states).
   - **Station IDs:** Prefixed with `CGWB_<STATE_CODE>_0001` through `0003` (e.g. `CGWB_MH_0001`, `CGWB_RJ_0001`, `CGWB_KA_0001`).
   - **Data Nature:** **Simulated time-series telemetry** generated with realistic regional base depths, seasonal monsoon recharge recovery dips, and diurnal fluctuations.
   - **Purpose:** Enables end-to-end testing of national dashboards, state rankings, and alerts even when public India-WRIS APIs are throttled or unauthenticated.
   - **Coordinates:** Approximate district centroid / headquarters coordinates (calibrated in `data/scripts/update_benchmark_coordinates.py`).
   - **Visual Distinction:** Rendered on the map with a dashed outer focus ring and tooltips explicitly stating *"Approximate Benchmark Placement"*. Never presented as verified borehole locations.

3. **Total Calculation:**
   $$\text{Total Stations} = 390\text{ (Real Karnataka CGWB)} + 78\text{ (Benchmark Fallback across 26 states)} = \mathbf{468\text{ stations}}$$
   *(Note: 3 of the 78 benchmark stations reside in Karnataka alongside the 390 real wells, giving Karnataka 393 total entries in the database).*

---

## 5. Hydrogeological Algorithms (Tasks 1, 2, 3)

### Task 1: Water Table Fluctuation (WTF) Analytics
- **File:** [`backend/algorithms/task1_fluctuation.py`](file:///D:/major-project/JalDrishti/backend/algorithms/task1_fluctuation.py)
- **Hourly/Daily Fluctuation:** $\Delta h = h(t) - h(t - \Delta t)$.
- **Moving Average:** Rolling 7-day window to eliminate diurnal barometric and tidal noise.
- **Anomaly Detection:** Flags sudden extraction drawdowns exceeding $1.5\text{ m}$ in 2 hours or readings deviating $> 3\sigma$ from rolling mean.

### Task 2: Dynamic Monsoon Recharge Estimation
- **File:** [`backend/algorithms/task2_recharge.py`](file:///D:/major-project/JalDrishti/backend/algorithms/task2_recharge.py)
- **Equation:** $R = S_y \times \Delta h_{\text{recovery}} \times A$, where $S_y$ is specific yield based on aquifer formation:
  - Alluvial: $0.12 - 0.16$
  - Hard Rock / Basalt: $0.02 - 0.04$
  - Granite: $0.03$
  - Sandstone: $0.06 - 0.08$
- **Correlation:** Computes lag-time correlation between IMD precipitation pulses and aquifer recharge response curves.

### Task 3: CGWB Resource Depletion Evaluation
- **File:** [`backend/algorithms/task3_evaluation.py`](file:///D:/major-project/JalDrishti/backend/algorithms/task3_evaluation.py)
- **Classification Criteria (GEC-2015 Norms):**
  - **Safe:** Water level $< 8\text{ m bgl}$, stage of extraction $< 70\%$.
  - **Semi-Critical:** Water level $8 - 15\text{ m bgl}$, stage of extraction $70 - 90\%$.
  - **Critical:** Water level $15 - 25\text{ m bgl}$, stage of extraction $90 - 100\%$.
  - **Over-Exploited:** Water level $> 25\text{ m bgl}$, stage of extraction $> 100\%$.
- **Depletion Timeline:** Linear extrapolation of 3-year drawdown trend to calculate years remaining until well bottom ($d_{\text{well}}$).
- **Resource Availability Index (RAI):** Scaled index from $0$ (exhausted) to $100$ (pristine).

---

## 6. AI & Spatial-Temporal Forecasting

### 6.1 Model Architecture & Pipeline
- **Target Variable:** Pre-monsoon groundwater level (depth to water table, $\text{m bgl}$) for the upcoming water year ($t+1$).
- **Spatial Graph:** 390-node spatial graph across Karnataka; edge weights computed via Gaussian distance kernel:
  $$A_{ij} = \exp\left(-\frac{\text{dist}(i, j)^2}{2\sigma^2}\right)$$
- **Features:**
  - Historical water depths: $t-1, t-2, t-3$
  - 3-year rolling mean and standard deviation
  - Spatial neighbor weighted drawdown averages
  - Aquifer formation one-hot encoding

### 6.2 Model Comparison & Selection
- **Evaluated Models:** Linear Regression, Random Forest, LSTM, Spatio-Temporal Graph Neural Network (STGNN).
- **Production Selection:** **Linear Regression** is deployed for operational serving due to robust out-of-sample temporal generalization (1994–2022 train, 2023–2025 test) and minimal overfitting:
  - Test MAE: $1.25\text{ m}$
  - Test RMSE: $1.68\text{ m}$
  - Test $R^2$: $0.81$
- **Uncertainty Quantification:** 90th-percentile conformal prediction residual band ($\pm 1.83\text{ m}$). Missing station histories display explicitly as *"Unavailable"* rather than defaulting to safe.

---

## 7. Geospatial Base Map & Web Mercator Transformation

### 7.1 Authentic Base Map
- **Asset:** `india_map_with_state_borders.svg` (`viewBox="0 0 1000 1000"`).
- Contains 36 authentic state and union territory vector polygons. The outer boundary is formed organically by the tiling state paths; no synthetic approximations or separate outline traces are used.

### 7.2 Calibrated Projection Formula
The SVG uses a true **spherical Web Mercator projection (EPSG:3857)**. Coordinates are transformed using:

$$\text{rad}(\text{lat}) = \text{lat} \times \frac{\pi}{180}$$

$$y_{\text{merc}} = \ln\left(\tan\left(\frac{\pi}{4} + \frac{\text{rad}(\text{lat})}{2}\right)\right)$$

$$x = 27.31481 \times \text{lon} - 1762.88855$$

$$y = 1138.53371 - 1565.02338 \times y_{\text{merc}}$$

- **Residual Error:** Mean error is $2.27\text{ px}$ across the entire $1000 \times 1000$ canvas when calibrated against 14 national landmarks.

### 7.3 Multi-Region Reference Point Verification
The projection was validated across geographically separated reference points in India:
- **Karnataka:**
  - Ferozabad, Kalaburagi ($17.0833^\circ\text{N}, 76.7958^\circ\text{E}$): SVG $(334.77, 664.84)$ $\rightarrow$ **PASS** (strictly inside Karnataka polygon `INKA`).
  - Bengaluru ($12.9716^\circ\text{N}, 77.5946^\circ\text{E}$): SVG $(356.59, 781.15)$ $\rightarrow$ **PASS** (inside `INKA`).
- **Maharashtra:**
  - Mumbai City ($19.0760^\circ\text{N}, 72.8777^\circ\text{E}$): SVG $(227.75, 607.57)$ $\rightarrow$ **PASS** (inside `INMH`).
  - Pune ($18.5204^\circ\text{N}, 73.8567^\circ\text{E}$): SVG $(254.49, 623.61)$ $\rightarrow$ **PASS** (inside `INMH`).
  - Nagpur ($21.1458^\circ\text{N}, 79.0882^\circ\text{E}$): SVG $(397.39, 547.36)$ $\rightarrow$ **PASS** (inside `INMH`).
- **Rajasthan:**
  - Jaipur ($26.9124^\circ\text{N}, 75.7873^\circ\text{E}$): SVG $(307.23, 374.80)$ $\rightarrow$ **PASS** (inside `INRJ`).
  - Jodhpur ($26.2389^\circ\text{N}, 73.0243^\circ\text{E}$): SVG $(231.76, 395.37)$ $\rightarrow$ **PASS** (inside `INRJ`).
  - Jaisalmer ($26.9157^\circ\text{N}, 70.9083^\circ\text{E}$): SVG $(173.96, 374.70)$ $\rightarrow$ **PASS** (inside `INRJ`).
- **Northeast India:**
  - Guwahati, Assam ($26.1445^\circ\text{N}, 91.7362^\circ\text{E}$): SVG $(742.87, 398.25)$ $\rightarrow$ **PASS** (inside `INAS`).
  - Shillong, Meghalaya ($25.5788^\circ\text{N}, 91.8933^\circ\text{E}$): SVG $(747.16, 415.42)$ $\rightarrow$ **PASS** (inside `INML`).
  - Imphal, Manipur ($24.8170^\circ\text{N}, 93.9368^\circ\text{E}$): SVG $(802.98, 438.41)$ $\rightarrow$ **PASS** (inside `INMN`).
  - Kohima, Nagaland ($25.6751^\circ\text{N}, 94.1086^\circ\text{E}$): SVG $(807.67, 412.50)$ $\rightarrow$ **PASS** (inside `INNL`).
  - Itanagar, Arunachal Pradesh ($27.0844^\circ\text{N}, 93.6053^\circ\text{E}$): SVG $(793.92, 369.53)$ $\rightarrow$ **PASS** (inside `INAR`).

### 7.4 Database-Wide Point-in-Polygon Audit
When projecting all 468 database stations against the SVG state path boundaries:
- **Strictly Inside State Polygon:** **439 / 468 (93.80%)** stations fall directly within their respective state boundary.
- **Immediate Border Buffer:** **13 stations** lie within 1–2 px of neighbor state borders due to district centroid approximations.
- **Coastal Margins:** **16 stations** (e.g., coastal Karnataka wells along the Arabian Sea) lie within 1.5 px of the coastal vector line due to spline simplification in the SVG boundary.

### 7.5 Known Projection Limitations
1. **SVG Coastline Generalization:** Natural coastlines (e.g. Mangaluru, Karwar) are vectorized with low-order Bézier curves; real GPS well coordinates within 500 meters of the shore can project 1–2 pixels offshore.
2. **State Name Aliases:** The SVG encodes historical/variant names (`INOR` as "Orissa", `INUT` as "Uttaranchal"). The frontend handles this via `normalizeStateName` to transparently match modern database records ("Odisha", "Uttarakhand").

### 7.6 Marker Differentiation
- **Verified Stations:** Solid colored dots with risk-based palette (Forest Green / Safe, Amber / Warning, Crimson / Critical).
- **Benchmark Centroids:** Rendered with dashed outer rings and explicit tooltips denoting *"Approximate Benchmark Placement"*.

---

## 8. Frontend User Experience (Design Direction A)

The user interface follows **Design Direction A: Minimal Professional Dashboard**:
- **Palette:** Clean white and light grey canvas (`#f8fafc`, `#ffffff`), dark slate typography (`#0f172a`, `#334155`), restrained teal/forest green accents (`#0d9488`, `#047857`), and subtle borders (`#e2e8f0`).
- **Layout:** Generous whitespace, card-based groupings with restrained elevations, no excessive animations or neon badges.
- **Views:**
  1. **Overview Dashboard:** 4 key KPI metrics, state health summary, active warning alerts.
  2. **Monitoring & Map:** Large interactive base map with pan, zoom presets (All India, Karnataka, North-East), state filters, and station selection inspector.
  3. **AI Forecast:** Station prediction card, predicted depth vs historical trend, uncertainty bands, and expandable model metrics.
  4. **State & District Rankings:** Searchable, sortable national league tables and district scorecards.
  5. **Active Alerts:** Threshold violations with severity filters and CSV report export.
  6. **Methodology:** Detailed CGWB formulas, WTF theory, GEC-2015 criteria, and limitations.

---

## 9. Local Service Setup & Port Allocations

| Service | Protocol / Port | Technology | Working Directory / Script |
| :--- | :--- | :--- | :--- |
| Core Backend API | `http://localhost:8000` | FastAPI / Uvicorn | `backend/main.py` |
| AI Forecasting Service | `http://localhost:8010` | FastAPI / Uvicorn | `ai/service/app.py` |
| Frontend Web Console | `http://localhost:3000` | React 18 / WDS | `frontend/` |
| PostgreSQL + TimescaleDB | `localhost:5432` | PostgreSQL 15 | `.local_services/pgsql/` |
| Redis Cache | `localhost:6379` | Redis 7 | `.local_services/redis/` |

### Environment Variables (`.env`)
```env
POSTGRES_DB=jaldrishti
POSTGRES_USER=jaldrishti_user
POSTGRES_PASSWORD=jaldrishti_pass
DATABASE_URL=postgresql://jaldrishti_user:jaldrishti_pass@localhost:5432/jaldrishti
REDIS_URL=redis://localhost:6379
AI_SERVICE_URL=http://localhost:8010
SECRET_KEY=change-this-in-production
WRIS_BASE_URL=https://indiawris.gov.in
IMD_BASE_URL=https://imdaws.imd.gov.in
FETCH_INTERVAL_SEC=900
MAX_RETRIES=3
RETRY_BACKOFF_SEC=10
REQUEST_TIMEOUT_SEC=30
```

---

## 10. Operational Commands

### 10.1 Start Full Stack
From PowerShell at the repository root:
```powershell
.\start-jaldrishti.ps1
```

### 10.2 Stop Full Stack
```powershell
.\stop-jaldrishti.ps1
```

### 10.3 Run Automated Tests
```powershell
# Activate Python environment
.\.venv\Scripts\Activate.ps1

# Core backend tests (6 tests)
pytest backend/tests -v

# AI service tests (4 tests)
pytest ai/tests -v

# Data pipeline tests
pytest data/scripts/test_pipeline.py -v

# Frontend tests (Projection & Geospatial Envelopes)
npm --prefix frontend test -- --watchAll=false
```

### 10.4 Build Frontend for Production
```powershell
npm --prefix frontend run build
```

---

## 11. Known Limitations & Technical Debt

1. **AI Training Coverage:** Historical multi-year training records (1994–2025) are currently sourced from Karnataka CGWB data. Stations outside Karnataka use regional transfer parameters and benchmark models until nationwide historical archives are ingested.
2. **Upstream Scraping Throttling:** India-WRIS APIs periodically throttle high-frequency unauthenticated scraping; the system gracefully falls back to cached TimescaleDB observations and benchmark data.
3. **Coastal SVG Coastline Resolution:** Out of 390 Karnataka wells, 15 wells along the Arabian Sea coast fall within $1.5\text{ px}$ outside the vector line due to coastline simplification in the SVG.

---

## 12. Next Development Priorities

1. **Ingest Additional State Datasets:** Expand raw pre-monsoon archives to include Maharashtra, Rajasthan, and Tamil Nadu.
2. **Dynamic Specific Yield Mapping:** Replace district-level specific yield assumptions with high-resolution CGWB lithology shapefiles.
3. **Automated Alert Notification Webhooks:** Integrate email/SMS webhooks for critical depletion notifications to regional water boards.
4. **Offline Mobile PWA:** Enable Service Worker caching for field hydrologists with low internet connectivity.

---

## 13. Critical Precautions for Future Modifications

> [!CAUTION]
> 1. **DO NOT reintroduce Docker.** The project is configured for native Windows execution via `.local_services` and `.venv`.
> 2. **DO NOT alter the SVG projection coefficients** in `IndiaStateBorders.js` without running `npm test` and `verify_states_coverage.py`.
> 3. **DO NOT commit secrets, `.env`, or `.local_services` binaries.** Ensure `.gitignore` rules remain active.
> 4. **DO NOT fabricate station coordinates.** Always preserve true CGWB latitude/longitude values.

