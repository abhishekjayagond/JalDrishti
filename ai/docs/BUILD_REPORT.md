# Build Report

Built from the supplied Karnataka CGWB pre-monsoon extraction:
- Raw observations: 28,579
- Exact duplicate rows removed: 1
- Clean station-year rows: 28,544
- Candidate stations with >=25 observed years: 390
- Graph nodes: 390
- Calendar range: 1994-2025
- Missing calendar year: 2021
- Test period: 2023-2025 (observed targets only)

Models:
- Persistence
- Linear Regression
- Random Forest
- LSTM
- Lightweight ST-GNN

Outputs:
- `models/metrics.json`
- `models/conformal.json`
- `data/processed/annual_model_features.csv`
- `data/processed/annual_nodes.csv`
- `data/processed/annual_adjacency.npy`
- `data/processed/rf_permutation_importance.csv`
- prediction CSV for each model

API:
- `/health`
- `/api/ai/metrics`
- `/api/ai/stations`
- `/api/ai/forecast/{station_id}`
- `/ui`
