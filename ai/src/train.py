from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import *
from .data_pipeline import load_clean, candidate_stations, build_nodes, build_wide, build_station_features, consecutive_gaps
from .graph import build_knn_graph, save_graph
from .metrics import regression_metrics
from .models import fit_tabular_models, fit_lstm, fit_stgnn


def persistence_eval(features: pd.DataFrame, test_years):
    te = features[features.target_year.isin(test_years)].copy()
    p = te.gwl_lag_1.to_numpy()
    return regression_metrics(te.target, p), pd.DataFrame({"station_id": te.station_id, "target_year": te.target_year, "y_true": te.target, "prediction": p})


def conformal_calibration(features: pd.DataFrame, val_years):
    # Calibrate on a simple persistence residual because it is model-independent and stable.
    va = features[features.target_year.isin(val_years)].copy()
    resid = np.abs(va.target.to_numpy() - va.gwl_lag_1.to_numpy())
    q = float(np.quantile(resid, 0.90)) if len(resid) else 0.0
    return {"method": "split_conformal_style", "calibration": "absolute_persistence_residual", "quantile": 0.90, "radius_mbgl": q, "n": int(len(resid))}


def permutation_importance_from_rf(features: pd.DataFrame, train_years, test_years):
    from sklearn.inspection import permutation_importance
    import joblib
    model = joblib.load(RF_MODEL)
    te = features[features.target_year.isin(test_years)]
    r = permutation_importance(model, te[__import__('src.models', fromlist=['FEATURES']).FEATURES], te.target, n_repeats=8, random_state=42, scoring="neg_mean_absolute_error", n_jobs=-1)
    imp = pd.DataFrame({"feature": __import__('src.models', fromlist=['FEATURES']).FEATURES, "importance": r.importances_mean}).sort_values("importance", ascending=False)
    return imp


def main():
    for p in [PROCESSED, MODELS]: p.mkdir(parents=True, exist_ok=True)
    clean = load_clean(RAW_CSV)
    clean.to_csv(CLEAN_CSV, index=False)
    cand = candidate_stations(clean, min_years=25)
    cand.to_csv(CANDIDATE_CSV, index=False)
    nodes = build_nodes(clean, cand)
    nodes.to_csv(NODE_CSV, index=False)
    gaps = consecutive_gaps(clean)
    gaps.to_csv(PROCESSED / "station_gap_audit.csv", index=False)
    wide, masks = build_wide(clean, nodes)
    wide.to_csv(PROCESSED / "annual_water_level_matrix.csv")
    masks.to_csv(PROCESSED / "annual_observation_mask.csv")
    A = build_knn_graph(nodes, k=8)
    save_graph(nodes, A, GRAPH_NPY, ORDER_JSON)
    features = build_station_features(clean, nodes, min_history=4)
    features.to_csv(PROCESSED / "annual_model_features.csv", index=False)
    bres, bpred, train_years, val_years, test_years = fit_tabular_models(features, MODELS)
    pres, ppred = persistence_eval(features, test_years)
    lres, lpred = fit_lstm(clean, nodes, MODELS)
    sres, spred = fit_stgnn(clean, nodes, A, MODELS)
    conf = conformal_calibration(features, val_years)
    CALIBRATION_JSON.write_text(json.dumps(conf, indent=2), encoding="utf-8")
    imp = permutation_importance_from_rf(features, train_years, test_years)
    imp.to_csv(PROCESSED / "rf_permutation_importance.csv", index=False)
    preds = {"persistence": ppred, **bpred, "lstm": lpred, "stgnn": spred}
    for name, df in preds.items():
        df.to_csv(PROCESSED / f"predictions_{name}.csv", index=False)
    metrics = {"persistence": pres, **bres, "lstm": lres, "stgnn": sres}
    METRICS_JSON.write_text(json.dumps({
        "data": {"raw_rows": int(pd.read_csv(RAW_CSV).shape[0]), "clean_station_years": int(len(clean)), "candidate_stations": int(len(cand)), "graph_nodes": int(len(nodes)), "years": [int(clean.year.min()), int(clean.year.max())], "missing_calendar_years": [int(y) for y in sorted(set(range(int(clean.year.min()), int(clean.year.max()) + 1)) - {int(v) for v in clean.year.unique()})]},
        "split": {"train_years": [int(v) for v in train_years], "validation_years": [int(v) for v in val_years], "test_years": [int(v) for v in test_years]},
        "metrics": metrics,
        "model_notes": {"target": "next calendar-year pre-monsoon groundwater depth (mbgl)", "historical_source": "CGWB pre-monsoon Karnataka extraction from Pre-monsoon_WL_1994-2025.pdf", "annual_frequency": True}
    }, indent=2), encoding="utf-8")
    MODEL_META_JSON.write_text(json.dumps({"station_count": len(nodes), "node_file": str(NODE_CSV.name), "graph_file": str(GRAPH_NPY.name), "rf_features": __import__('src.models', fromlist=['FEATURES']).FEATURES}, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "calibration": conf, "top_rf_features": imp.head(10).to_dict(orient="records")}, indent=2))

if __name__ == "__main__":
    main()
