# JalDrishti — Local Non-Docker Setup & Execution Guide

This document describes how JalDrishti runs directly on Windows without Docker, Docker Desktop, or containers. All services—React frontend, FastAPI backend, FastAPI AI forecasting service, PostgreSQL 15 with TimescaleDB, and Redis—are configured and run locally with zero-admin portability.

---

## 1. Architecture Overview

| Component | Port | Technology | Local Directory / Command |
|---|---|---|---|
| **Frontend UI** | `3000` | React 18 / CRA | `frontend/` (`npm start`) |
| **Backend API** | `8000` | FastAPI, SQLAlchemy, TimescaleDB | `backend/` (`uvicorn main:app --port 8000`) |
| **AI Forecasting Service** | `8010` | FastAPI, PyTorch CPU, Scikit-Learn | `ai/` (`uvicorn service.app:app --port 8010`) |
| **Database** | `5432` | PostgreSQL 15.19 + TimescaleDB 2.28.3 | `.local_services\pgsql\` (`postgres.exe`) |
| **Cache** | `6379` | Redis 5.0.14.1 for Windows | `.local_services\redis\` (`redis-server.exe`) |

---

## 2. Prerequisites & Fresh-Clone Setup Walkthrough

### System Prerequisites
1. **Operating System:** Windows 10 / 11 (64-bit).
2. **Python:** Python 3.10+ installed and available in PATH.
3. **Node.js:** Node.js 18+ and npm in system PATH.
4. **PowerShell:** Windows PowerShell 5.1 or PowerShell 7+.

---

### Step-by-Step Setup from a Fresh Git Clone

#### Step 1: Clone and Configure Environment Files
```powershell
git clone https://github.com/abhishekjayagond/JalDrishti.git
cd JalDrishti

# Create root .env from template
Copy-Item .env.example .env
```

#### Step 2: Set Up Python Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r ai/requirements.txt
```

#### Step 3: Install Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

#### Step 4: Configure Local PostgreSQL & Redis
You can run PostgreSQL 15 and Redis via either portable binaries or system services:
- **Portable Setup (Default in `start-jaldrishti.ps1`):** Place portable PostgreSQL 15 with TimescaleDB in `.local_services\pgsql\` and Redis 5+ in `.local_services\redis\`.
- **System Service Setup:** If you have PostgreSQL 15 (with TimescaleDB) and Redis installed as Windows services on standard ports (`5432` and `6379`), verify that database `jaldrishti` exists with user `jaldrishti_user` and password `jaldrishti_pass`.

#### Step 5: Initialize Schema and Seed Data
```powershell
.\.venv\Scripts\Activate.ps1

# 1. Initialize tables and TimescaleDB hypertables
& psql -h localhost -U jaldrishti_user -d jaldrishti -f backend/db/init.sql

# 2. Seed 390 verified Karnataka CGWB observation stations (1994-2025 records)
python data/scripts/seed_ai_stations.py

# 3. Seed 78 nationwide benchmark fallback stations
python data/scripts/seed_all_states.py
python data/scripts/update_benchmark_coordinates.py
```

#### Step 6: Launch Full Stack
```powershell
.\start-jaldrishti.ps1
```

---

## 3. Environment & Configuration

### Root Configuration (`.env`)
The root `.env` configures database credentials, Redis URL, AI service proxy target, and data acquisition timeouts:
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

### Frontend Configuration (`frontend/.env`)
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_AI_URL=http://localhost:8010
PORT=3000
BROWSER=none
```

---

## 4. Starting and Stopping JalDrishti

### Starting All Services
Open PowerShell in `D:\major-project\JalDrishti` and run:
```powershell
.\start-jaldrishti.ps1
```

The script will automatically:
1. Verify virtualenv, Node.js, PostgreSQL, and Redis binaries.
2. Check for port conflicts (ports `5432`, `6379`, `8010`, `8000`, `3000`).
3. Start PostgreSQL 15 with TimescaleDB on port 5432 and wait for readiness.
4. Start Redis Server on port 6379 and verify `PONG` response.
5. Start the AI service on port 8010 and verify model initialization (`/health`).
6. Start the Backend API on port 8000 and verify database connectivity (`/api/health`).
7. Start the React frontend on port 3000.
8. Save all process IDs into `logs/*.pid` for clean shutdown.

### Stopping All Services
To stop only the processes launched by JalDrishti:
```powershell
.\stop-jaldrishti.ps1
```

This stops the frontend, backend, AI service, Redis, and PostgreSQL cleanly without affecting unrelated background processes.

---

## 5. Service URLs

- **Web Application Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend API Documentation (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **AI Service Health Check:** [http://localhost:8010/health](http://localhost:8010/health)
- **AI Forecasting Endpoints:** [http://localhost:8010/docs](http://localhost:8010/docs)

---

## 6. Logs & Diagnostics

All service outputs and error streams are stored in the project-local `logs` directory:
- `logs\pgsql.log` & `logs\pgsql_err.log` — PostgreSQL database engine logs.
- `logs\redis.log` & `logs\redis_err.log` — Redis cache engine logs.
- `logs\ai.log` & `logs\ai_err.log` — AI forecasting service logs.
- `logs\backend.log` & `logs\backend_err.log` — FastAPI backend server logs.
- `logs\frontend.log` & `logs\frontend_err.log` — React development server compilation logs.

---

## 7. Automated Testing

Run the test suites directly via `.venv` without containers:

### Backend Unit & Integration Tests
```powershell
cd backend
..\.venv\Scripts\pytest tests -v
```
*(Tests Task 1 fluctuation analysis, Task 2 recharge estimates, Task 3 CGWB evaluations, boundary conditions, and API health endpoints).*

### AI Pipeline Tests
```powershell
cd ai
..\.venv\Scripts\pytest tests -v
```
*(Tests data cleaning counts, candidate validation, classification boundaries, and forecast distribution).*

### Frontend Jest Tests
```powershell
cd frontend
npm test -- --watchAll=false
```
*(Tests map projection logic, geographic bounding boxes, and zoom invariants).*

### Production Frontend Build
```powershell
cd frontend
npm run build
```

---

## 8. Database Architecture & Extension Details

- **Database Engine:** PostgreSQL 15.19 (64-bit Windows portable).
- **Extension:** TimescaleDB 2.28.3 (`CREATE EXTENSION timescaledb;`).
- **Hypertables:** `dwlr_readings` is partitioned into 7-day chunks on the `timestamp` column.
- **Seeded Data:**
  - 468 total monitoring stations across 26 Indian states:
    - **390 verified real Karnataka CGWB observation wells** (32 years of annual pre-monsoon records, 1994–2025).
    - **78 nationwide benchmark fallback stations** (3 per state across 26 states, seeded with seasonal sinusoidal telemetry for UI continuity; strictly excluded from AI training).
  - Over 2,638,000 DWLR water level time-series readings.
  - Spatial coordinates mapped and verified within Indian state vector boundaries.

---

## 9. Troubleshooting

### Port Already In Use
If `start-jaldrishti.ps1` reports a port is in use:
1. Check what process owns the port:
   ```powershell
   Get-NetTCPConnection -LocalPort <port> -State Listen
   ```
2. If it is a leftover JalDrishti process, run:
   ```powershell
   .\stop-jaldrishti.ps1
   ```
3. If an unrelated application is occupying the port, change the respective port in `.env` or stop the conflicting application.

### Stale PostgreSQL Lock
If the machine shut down abruptly, `postmaster.pid` might remain:
```powershell
Remove-Item .local_services\pgsql\data\postmaster.pid -Force
```
`start-jaldrishti.ps1` automatically detects and clears stale `postmaster.pid` files if no matching process is running.

