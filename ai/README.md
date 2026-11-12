# JalDrishti_abhi Groundwater AI Service

**Author & Project Lead:** Abhishek Jayagond<br/>
**Part of:** JalDrishti_abhi (Groundwater Intelligence & Forecasting)

This service provides an annual/pre-monsoon groundwater forecasting layer built from Karnataka CGWB historical datasets and exposes it as a high-performance FastAPI service running alongside JalDrishti.

Included:
- Reproducible raw-data cleaning and audit pipeline
- 390 long-history candidate monitoring nodes (>=25 observed years)
- Annual station graph using geographic k-NN
- Persistence, Linear Regression, Random Forest, LSTM, and ST-GNN experiments
- MAE / RMSE / R² benchmark evaluation metrics
- Validation error band uncertainty analysis
- Feature importance explanation
- FastAPI forecast endpoint
- Containerized Docker deployment

The model target is the **next calendar-year pre-monsoon groundwater depth (mbgl)**. This corresponds to the official CGWB pre-monsoon historical time-series.

## Run Locally

```powershell
cd ai
python -m src.train
python -m uvicorn service.app:app --host 0.0.0.0 --port 8010
```

## Run with Docker Compose

Ensure `data/raw/phase1_karnataka_premonsoon_1994_2025.csv` exists in the repository.

```powershell
docker compose -f docker-compose.yml -f docker-compose.ai.yml up --build -d ai
```

Then open `http://localhost:8010/docs` or `http://localhost:8010/ui`.

## Main Endpoints

- `GET /health`
- `GET /api/ai/metrics`
- `GET /api/ai/stations?limit=500`
- `GET /api/ai/forecast/{station_id}`

The API uses standard CGWB depth thresholds (< 8m Safe, 8–15m Semi-Critical, 15–25m Critical, > 25m Over-Exploited) for exploratory risk categorization.
