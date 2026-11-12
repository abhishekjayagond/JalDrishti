from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import CLEAN_CSV, NODE_CSV, PROCESSED, LR_MODEL, METRICS_JSON
from src.models import FEATURES

app = FastAPI(title="JalDrishti Groundwater AI", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

clean: pd.DataFrame | None = None
nodes: pd.DataFrame | None = None
model: Any = None
metrics: dict[str, Any] = {}
validation_band: dict[str, Any] = {}


all_forecasts: dict[str, dict[str, Any]] = {}


def classify_gwl_depth(depth: float | None) -> str:
    """Apply consistent project thresholds:
    Safe <8 m; Semi-Critical 8–<15 m; Critical 15–25 m; Over-Exploited >25 m.
    Missing, invalid, or failed predictions are labeled 'Unavailable'.
    """
    if depth is None or not isinstance(depth, (int, float)) or np.isnan(depth) or not np.isfinite(depth):
        return "Unavailable"
    if depth < 8.0:
        return "Safe"
    if depth < 15.0:
        return "Semi-Critical"
    if depth <= 25.0:
        return "Critical"
    return "Over-Exploited"


def _compute_station_forecast(station_id: str) -> dict[str, Any] | None:
    assert clean is not None and nodes is not None and model is not None
    row = nodes[nodes.station_id == station_id]
    if row.empty:
        return None

    g = clean[clean.station_id == station_id].sort_values("year")
    if len(g) < 4:
        return None

    years = g.year.to_numpy(int)
    vals = g.water_level_mbgl.to_numpy(float)
    hist = {int(y): float(v) for y, v in zip(years, vals)}
    prior_years = sorted(hist)[-4:]
    if len(prior_years) < 4:
        return None

    last_year = int(max(hist))
    forecast_year = last_year + 1
    last4 = [hist[y] for y in prior_years]  # oldest to newest
    feat = pd.DataFrame([{
        "latitude": float(row.iloc[0].latitude),
        "longitude": float(row.iloc[0].longitude),
        "gwl_lag_1": last4[-1],
        "gwl_lag_2": last4[-2],
        "gwl_lag_3": last4[-3],
        "gwl_lag_4": last4[-4],
        # Offsets are measured from the target forecast year, matching training features.
        "years_back_1": float(forecast_year - prior_years[-1]),
        "years_back_2": float(forecast_year - prior_years[-2]),
        "years_back_3": float(forecast_year - prior_years[-3]),
        "years_back_4": float(forecast_year - prior_years[-4]),
        "gwl_mean_4": float(np.mean(last4)),
        "gwl_std_4": float(np.std(last4)),
        "gwl_slope_4": float(np.polyfit(np.arange(4), np.asarray(last4), 1)[0]),
    }])

    pred = float(model.predict(feat[FEATURES])[0])
    radius = validation_band.get("radius_mbgl")
    lower = float(pred - radius) if radius is not None else None
    upper = float(pred + radius) if radius is not None else None
    status = classify_gwl_depth(pred)

    return {
        "station_id": station_id,
        "forecast_year": forecast_year,
        "forecast_mbgl": pred,
        "predicted_depth_m": pred,
        "lower_mbgl": lower,
        "upper_mbgl": upper,
        "uncertainty_radius_mbgl": radius,
        "interval_method": validation_band.get("method"),
        "interval_note": validation_band.get("note"),
        "risk": status,
        "risk_rule_note": "Exploratory groundwater depth indicator (<8m: Safe depth, 8–<15m: Semi-Critical depth, 15–25m: Critical depth, >25m: Over-Exploited depth). Note: Official CGWB/GEC-2015 assessment requires assessment-unit extraction and recharge accounting.",
        "assessment_type": "exploratory_depth_tier",
        "model": "linear_regression",
        "frequency": "annual_pre_monsoon",
        "data_end_year": last_year,
    }


def _load() -> None:
    """Load data, estimate an LR validation error band, then refit LR for deployment."""
    global clean, nodes, model, metrics, validation_band, all_forecasts

    clean = pd.read_csv(CLEAN_CSV)
    nodes = pd.read_csv(NODE_CSV)
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    feature_path = PROCESSED / "annual_model_features.csv"
    features = pd.read_csv(feature_path)

    missing = sorted(set(FEATURES + ["target", "target_year"]) - set(features.columns))
    if missing:
        raise RuntimeError(f"Annual feature file is missing columns: {missing}")
    if features.empty:
        raise RuntimeError("Annual feature file is empty")

    # The saved Linear Regression model was trained on the original training years
    # (through 2018). Use the temporal validation years to calculate a model-specific
    # error band before refitting a production model with all available history.
    model = joblib.load(LR_MODEL)
    val_years = metrics.get("split", {}).get("validation_years", [])
    validation = features[features["target_year"].isin(val_years)].copy()
    if not validation.empty:
        val_pred = model.predict(validation[FEATURES])
        abs_resid = np.abs(validation["target"].to_numpy(float) - val_pred)
        radius = float(np.quantile(abs_resid, 0.90))
        validation_band = {
            "method": "90th_percentile_absolute_residual_on_temporal_validation_years",
            "quantile": 0.90,
            "radius_mbgl": radius,
            "n": int(len(abs_resid)),
            "validation_years": [int(y) for y in val_years],
            "note": "Approximate validation-error band, not a guaranteed prediction interval.",
        }
    else:
        validation_band = {
            "method": "unavailable",
            "radius_mbgl": None,
            "n": 0,
            "note": "No rows matched the saved validation years; interval is unavailable.",
        }

    # Refit after evaluating so the deployed model can use all available target years.
    # The metrics endpoint continues to report the prior, fixed 2023–2025 test results.
    model.fit(features[FEATURES], features["target"].to_numpy(float))
    metrics["deployment"] = {
        "model": "linear_regression",
        "fit_target_year_start": int(features["target_year"].min()),
        "fit_target_year_end": int(features["target_year"].max()),
        "validation_band": validation_band,
        "evaluation_caveat": (
            "The displayed comparison is from the 2023–2025 test period. Because the leading model was selected after viewing those test metrics, "
            "an untouched future period is still needed for an independent final assessment."
        ),
    }

    # Precompute forecasts for all candidate stations
    all_forecasts.clear()
    for _, row in nodes.iterrows():
        sid = str(row["station_id"])
        fc = _compute_station_forecast(sid)
        if fc is not None:
            all_forecasts[sid] = fc


@app.on_event("startup")
def startup() -> None:
    _load()


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "JalDrishti Groundwater AI", "status": "running", "mode": "annual_pre_monsoon"}


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def ui() -> str:
    return Path(__file__).with_name("ui.html").read_text(encoding="utf-8")


@app.get("/health", tags=["system"])
def health() -> dict[str, Any]:
    assert nodes is not None
    return {
        "status": "ok",
        "stations": int(len(nodes)),
        "model": "linear_regression",
        "frequency": "annual_pre_monsoon",
        "precomputed_forecasts": int(len(all_forecasts)),
    }


@app.get("/api/ai/metrics", tags=["research"])
def get_metrics() -> dict[str, Any]:
    return metrics


@app.get("/api/ai/stations", tags=["research"])
def get_stations(limit: int = Query(500, ge=1, le=500)) -> list[dict[str, Any]]:
    assert nodes is not None
    records = nodes.head(limit).to_dict(orient="records")
    for r in records:
        sid = r.get("station_id")
        fc = all_forecasts.get(sid)
        if fc and fc.get("forecast_mbgl") is not None:
            r["forecast_mbgl"] = fc["forecast_mbgl"]
            r["predicted_depth_m"] = fc["forecast_mbgl"]
            r["lower_mbgl"] = fc["lower_mbgl"]
            r["upper_mbgl"] = fc["upper_mbgl"]
            r["forecast_year"] = fc["forecast_year"]
            r["risk"] = fc["risk"]
        else:
            r["forecast_mbgl"] = None
            r["predicted_depth_m"] = None
            r["risk"] = "Unavailable"
    return records


@app.get("/api/ai/forecasts", tags=["forecast"])
def get_all_forecasts() -> dict[str, dict[str, Any]]:
    """Return all precomputed station forecasts keyed by station_id."""
    return all_forecasts


@app.get("/api/ai/predictions", tags=["forecast"])
def get_predictions() -> list[dict[str, Any]]:
    """Return all precomputed station predictions as a list."""
    return list(all_forecasts.values())


@app.get("/api/ai/forecast/{station_id}", tags=["forecast"])
def forecast(station_id: str) -> dict[str, Any]:
    assert clean is not None and nodes is not None and model is not None
    row = nodes[nodes.station_id == station_id]
    if row.empty:
        raise HTTPException(404, "Unknown station_id")

    if station_id in all_forecasts:
        return all_forecasts[station_id]

    fc = _compute_station_forecast(station_id)
    if fc is None:
        raise HTTPException(422, "Station does not have enough annual history")

    return fc
