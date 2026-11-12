from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from src.config import (
    CLEAN_CSV,
    NODE_CSV,
    PROCESSED,
    PRODUCTION_MODEL,
    LR_MODEL,
    METRICS_JSON,
    CALIBRATION_JSON,
    FORECAST_HORIZONS_JSON,
)
from src.models import FEATURES

clean: pd.DataFrame | None = None
nodes: pd.DataFrame | None = None
model: Any = None
metrics: dict[str, Any] = {}
validation_band: dict[str, Any] = {}
horizons_info: dict[str, Any] = {}
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

    # 1-year rolling forecast feature vector (h=1)
    feat1 = pd.DataFrame([{
        "latitude": float(row.iloc[0].latitude),
        "longitude": float(row.iloc[0].longitude),
        "gwl_lag_1": last4[-1],
        "gwl_lag_2": last4[-2],
        "gwl_lag_3": last4[-3],
        "gwl_lag_4": last4[-4],
        "years_back_1": float(forecast_year - prior_years[-1]),
        "years_back_2": float(forecast_year - prior_years[-2]),
        "years_back_3": float(forecast_year - prior_years[-3]),
        "years_back_4": float(forecast_year - prior_years[-4]),
        "gwl_mean_4": float(np.mean(last4)),
        "gwl_std_4": float(np.std(last4)),
        "gwl_slope_4": float(np.polyfit(prior_years, np.asarray(last4), 1)[0]),
    }])

    pred1 = float(model.predict(feat1[FEATURES])[0])
    radius = validation_band.get("uncertainty_radius_mbgl", validation_band.get("radius_mbgl"))
    lower1 = float(pred1 - radius) if radius is not None else None
    upper1 = float(pred1 + radius) if radius is not None else None
    status1 = classify_gwl_depth(pred1)

    # Multi-year recursive forecast projections (h=1, h=2, h=3)
    # At h=2, pred1 is used as lag_1
    last4_h2 = [last4[-3], last4[-2], last4[-1], pred1]
    years_h2 = [prior_years[-3], prior_years[-2], prior_years[-1], forecast_year]
    feat2 = pd.DataFrame([{
        "latitude": float(row.iloc[0].latitude),
        "longitude": float(row.iloc[0].longitude),
        "gwl_lag_1": last4_h2[-1],
        "gwl_lag_2": last4_h2[-2],
        "gwl_lag_3": last4_h2[-3],
        "gwl_lag_4": last4_h2[-4],
        "years_back_1": 1.0,
        "years_back_2": float(forecast_year + 1 - prior_years[-1]),
        "years_back_3": float(forecast_year + 1 - prior_years[-2]),
        "years_back_4": float(forecast_year + 1 - prior_years[-3]),
        "gwl_mean_4": float(np.mean(last4_h2)),
        "gwl_std_4": float(np.std(last4_h2)),
        "gwl_slope_4": float(np.polyfit(years_h2, np.asarray(last4_h2), 1)[0]),
    }])
    pred2 = float(model.predict(feat2[FEATURES])[0])

    # At h=3, pred2 is lag_1, pred1 is lag_2
    last4_h3 = [last4[-2], last4[-1], pred1, pred2]
    years_h3 = [prior_years[-2], prior_years[-1], forecast_year, forecast_year + 1]
    feat3 = pd.DataFrame([{
        "latitude": float(row.iloc[0].latitude),
        "longitude": float(row.iloc[0].longitude),
        "gwl_lag_1": last4_h3[-1],
        "gwl_lag_2": last4_h3[-2],
        "gwl_lag_3": last4_h3[-3],
        "gwl_lag_4": last4_h3[-4],
        "years_back_1": 1.0,
        "years_back_2": 2.0,
        "years_back_3": float(forecast_year + 2 - prior_years[-1]),
        "years_back_4": float(forecast_year + 2 - prior_years[-2]),
        "gwl_mean_4": float(np.mean(last4_h3)),
        "gwl_std_4": float(np.std(last4_h3)),
        "gwl_slope_4": float(np.polyfit(years_h3, np.asarray(last4_h3), 1)[0]),
    }])
    pred3 = float(model.predict(feat3[FEATURES])[0])

    # Multi-horizon projections:
    # Target 2026 is a retrospective estimate (pre-monsoon 2026 has already passed relative to Nov 12, 2026).
    # True future projections commence in 2027 and 2028.
    # Conformal calibration guarantees hold strictly for 1-step rolling predictions.
    # Multi-year recursive horizons (h=2, 3) report uncertainty as unavailable rather than applying arbitrary multipliers.
    multi_year_projections = [
        {
            "horizon_years": 1,
            "target_year": forecast_year,
            "predicted_depth_mbgl": round(pred1, 3),
            "lower_mbgl": round(lower1, 3) if lower1 is not None else None,
            "upper_mbgl": round(upper1, 3) if upper1 is not None else None,
            "uncertainty_radius_mbgl": round(radius, 3) if radius is not None else None,
            "uncertainty_status": "calibrated_conformal_interval" if radius is not None else "unavailable",
            "coverage_guarantee": "single_step_calibrated_split_conformal",
            "risk": status1,
            "forecast_type": "1_year_rolling_forecast",
            "temporal_classification": "retrospective_estimate" if forecast_year <= 2026 else "future_projection",
            "is_future_forecast": forecast_year > 2026,
        },
        {
            "horizon_years": 2,
            "target_year": forecast_year + 1,
            "predicted_depth_mbgl": round(pred2, 3),
            "lower_mbgl": None,
            "upper_mbgl": None,
            "uncertainty_radius_mbgl": None,
            "uncertainty_status": "unavailable",
            "uncertainty_note": "Multi-year recursive conformal calibration is unavailable; 1-step calibration does not provide valid coverage under recursive feedback.",
            "risk": classify_gwl_depth(pred2),
            "forecast_type": "2_year_recursive_forecast",
            "temporal_classification": "future_projection" if (forecast_year + 1) > 2026 else "retrospective_estimate",
            "is_future_forecast": (forecast_year + 1) > 2026,
            "error_compounding_note": "Autoregressive error compounds from 1-year recursive feedback.",
        },
        {
            "horizon_years": 3,
            "target_year": forecast_year + 2,
            "predicted_depth_mbgl": round(pred3, 3),
            "lower_mbgl": None,
            "upper_mbgl": None,
            "uncertainty_radius_mbgl": None,
            "uncertainty_status": "unavailable",
            "uncertainty_note": "Multi-year recursive conformal calibration is unavailable; 1-step calibration does not provide valid coverage under recursive feedback.",
            "risk": classify_gwl_depth(pred3),
            "forecast_type": "3_year_recursive_forecast",
            "temporal_classification": "future_projection" if (forecast_year + 2) > 2026 else "retrospective_estimate",
            "is_future_forecast": (forecast_year + 2) > 2026,
            "error_compounding_note": "Autoregressive error compounds from multi-year recursive feedback.",
        },
    ]

    return {
        "station_id": station_id,
        "forecast_year": forecast_year,
        "forecast_mbgl": round(pred1, 3),
        "predicted_depth_m": round(pred1, 3),
        "lower_mbgl": round(lower1, 3) if lower1 is not None else None,
        "upper_mbgl": round(upper1, 3) if upper1 is not None else None,
        "uncertainty_radius_mbgl": round(radius, 4) if radius is not None else None,
        "uncertainty_status": "calibrated_conformal_interval" if radius is not None else "unavailable",
        "interval_method": validation_band.get("method", "split_conformal_inference"),
        "interval_empirical_coverage": validation_band.get("test_empirical_coverage_overall"),
        "interval_note": validation_band.get("exchangeability_assumptions_and_limitations"),
        "temporal_classification": "retrospective_estimate" if forecast_year <= 2026 else "future_projection",
        "is_future_forecast": forecast_year > 2026,
        "temporal_note": (
            "Pre-monsoon 2026 occurred in April-May 2026 prior to current date (November 12, 2026). "
            "Target year 2026 is evaluated as a retrospective estimate / hindcast. True future projections commence in 2027."
            if forecast_year <= 2026 else "Future pre-monsoon projection."
        ),
        "risk": status1,
        "risk_rule_note": "Exploratory groundwater depth indicator (<8m: Safe depth, 8–<15m: Semi-Critical depth, 15–25m: Critical depth, >25m: Over-Exploited depth). Note: Official CGWB/GEC-2015 assessment requires administrative assessment-unit extraction and recharge accounting.",
        "assessment_type": "exploratory_depth_tier",
        "model": "calibrated_linear_regression",
        "forecast_horizon_years": 1,
        "forecast_type": "1_year_rolling_forecast",
        "frequency": "annual_pre_monsoon",
        "data_end_year": last_year,
        "multi_year_projections": multi_year_projections,
    }


def _load() -> None:
    """Load pre-trained production model, conformal calibration parameters, and precompute forecasts."""
    global clean, nodes, model, metrics, validation_band, horizons_info, all_forecasts

    clean = pd.read_csv(CLEAN_CSV)
    nodes = pd.read_csv(NODE_CSV)
    
    if METRICS_JSON.exists():
        metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    else:
        metrics = {}

    if CALIBRATION_JSON.exists():
        validation_band = json.loads(CALIBRATION_JSON.read_text(encoding="utf-8"))
    else:
        validation_band = {}

    if FORECAST_HORIZONS_JSON.exists():
        horizons_info = json.loads(FORECAST_HORIZONS_JSON.read_text(encoding="utf-8"))
    else:
        horizons_info = {}

    # Require exact calibrated model artifact. Silent fallback to uncalibrated models
    # while retaining calibrated conformal uncertainty intervals is strictly prohibited.
    if not LR_MODEL.exists():
        raise RuntimeError(
            f"Calibrated model artifact '{LR_MODEL.name}' not found at {LR_MODEL}. "
            "Silent fallback to an uncalibrated model while serving calibrated uncertainty intervals is strictly prohibited. "
            "Run ai/src/train.py to generate the exact calibrated model artifact."
        )

    model = joblib.load(LR_MODEL)

    # Verify that the loaded conformal calibration metadata explicitly matches the served model
    if validation_band:
        calibration_model_name = validation_band.get("calibration_model")
        if calibration_model_name and calibration_model_name != "linear_regression":
            raise RuntimeError(
                f"Conformal calibration metadata mismatch: calibration_model is '{calibration_model_name}', "
                f"expected 'linear_regression' matching {LR_MODEL.name}."
            )

    # Precompute forecasts for all candidate stations
    all_forecasts.clear()
    for _, row in nodes.iterrows():
        sid = str(row["station_id"])
        fc = _compute_station_forecast(sid)
        if fc is not None:
            all_forecasts[sid] = fc


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load()
    yield


app = FastAPI(title="JalDrishti Groundwater AI", version="1.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "model": "calibrated_linear_regression",
        "frequency": "annual_pre_monsoon",
        "forecast_horizon": "1_year_ahead_rolling",
        "precomputed_forecasts": int(len(all_forecasts)),
    }


@app.get("/api/ai/metrics", tags=["research"])
def get_metrics() -> dict[str, Any]:
    return metrics


@app.get("/api/ai/horizons", tags=["research"])
def get_horizons() -> dict[str, Any]:
    return horizons_info


@app.get("/api/ai/conformal", tags=["research"])
def get_conformal() -> dict[str, Any]:
    return validation_band


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
