"""
api/main.py — JalDrishti — Phase 4 Final v2
"""
import csv
import io
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_db, SessionLocal
from app.models.station import DWLRReading, Station, Rainfall
from app.services.analytics import get_fluctuation_analysis, get_fluctuation_analysis_batch, get_anomalies
from app.services.recharge  import get_recharge_estimate, get_recharge_batch
from app.services.alerts    import (
    get_station_evaluation, get_active_alerts,
    get_district_scorecard, get_state_scorecard,
)

log    = logging.getLogger("jaldrishti.api")
router = APIRouter()


# ── AI Gateway Proxy Endpoints & Prediction Cache ─────────────────────────────
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8010")
_ai_forecasts_cache: dict[str, dict] = {}
_ai_forecasts_cached_at: float = 0.0


async def _fetch_ai_service(path: str, params: Optional[dict] = None):
    candidates = [
        AI_SERVICE_URL,
        "http://localhost:8010",
        "http://127.0.0.1:8010",
    ]
    for base in candidates:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base.rstrip('/')}/{path.lstrip('/')}", params=params)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 404:
                    detail = resp.json().get("detail", f"Resource not found in AI service: {path}")
                    raise HTTPException(404, detail)
        except httpx.HTTPStatusError:
            raise
        except HTTPException:
            raise
        except Exception:
            continue
    raise HTTPException(503, "AI forecasting service unreachable on port 8010")


async def _get_ai_forecasts_map() -> dict[str, dict]:
    global _ai_forecasts_cache, _ai_forecasts_cached_at
    now = time.time()
    if _ai_forecasts_cache and (now - _ai_forecasts_cached_at < 300):
        return _ai_forecasts_cache
    try:
        data = await _fetch_ai_service("/api/ai/forecasts")
        if isinstance(data, dict):
            _ai_forecasts_cache = data
            _ai_forecasts_cached_at = now
            return _ai_forecasts_cache
    except Exception as e:
        log.warning(f"Could not load AI forecasts map: {e}")
    return _ai_forecasts_cache


@router.get("/health", tags=["System"])
def health_check():
    from db.database import check_connection
    db_ok = check_connection()
    station_count = 0
    reading_count = 0
    rainfall_count = 0
    last_obs_time = None

    if db_ok:
        try:
            with SessionLocal() as db:
                station_count = db.query(func.count(Station.station_id)).scalar() or 0
                reading_count = db.query(func.count()).select_from(DWLRReading).scalar() or 0
                rainfall_count = db.query(func.count()).select_from(Rainfall).scalar() or 0
                max_ts = db.query(func.max(DWLRReading.timestamp)).scalar()
                if max_ts:
                    last_obs_time = max_ts.isoformat()
        except Exception:
            station_count = 0
            reading_count = 0
            rainfall_count = 0

    data_mode = "benchmark_fallback" if (station_count and station_count < 5000) else "live" if station_count else "empty"

    return {
        "status": "ok",
        "db": db_ok,
        "service": "JalDrishti API v1",
        "station_count": station_count,
        "reading_count": reading_count,
        "rainfall_count": rainfall_count,
        "data_mode": data_mode,
        "source_provenance": "calibrated_benchmark_and_historical_karnataka",
        "last_observation_time": last_obs_time,
        "upstream_telemetry_status": {
            "india_wris": "unavailable_upstream_redirect_loop",
            "imd": "unavailable_dns_nxdomain",
            "benchmark_active": True,
        },
    }


@router.get("/stations", tags=["Stations"])
async def list_stations(state: Optional[str]=Query(None), district: Optional[str]=Query(None), db: Session=Depends(get_db)):
    query = db.query(Station)
    if state:    query = query.filter(Station.state.ilike(f"%{state}%"))
    if district: query = query.filter(Station.district.ilike(f"%{district}%"))
    stations = query.all()
    if not stations: raise HTTPException(404, "No stations found")

    # Fetch latest water level, timestamp, and flag per station
    latest_rows = db.query(
        DWLRReading.station_id,
        DWLRReading.water_level_m,
        DWLRReading.timestamp,
        DWLRReading.data_quality_flag
    ).distinct(DWLRReading.station_id).order_by(
        DWLRReading.station_id,
        DWLRReading.timestamp.desc()
    ).all()
    latest_map = {r[0]: r for r in latest_rows}

    forecasts_map = await _get_ai_forecasts_map()

    res = []
    for s in stations:
        d = s.to_dict()
        latest = latest_map.get(s.station_id)
        d["current_level_m"] = latest[1] if latest else None
        d["last_observation_time"] = latest[2].isoformat() if (latest and latest[2]) else None
        d["data_provenance"] = "historical_annual" if (latest and latest[3] == "HISTORICAL_ANNUAL") else "benchmark_telemetry"

        fc = forecasts_map.get(s.station_id)
        if fc and fc.get("forecast_mbgl") is not None:
            pred = float(fc["forecast_mbgl"])
            d["predicted_depth_m"] = pred
            d["forecast_mbgl"] = pred
            d["forecast_year"] = fc.get("forecast_year")
            d["lower_mbgl"] = fc.get("lower_mbgl")
            d["upper_mbgl"] = fc.get("upper_mbgl")
            d["risk"] = fc.get("risk", "Unavailable")
        else:
            d["predicted_depth_m"] = None
            d["forecast_mbgl"] = None
            d["forecast_year"] = None
            d["lower_mbgl"] = None
            d["upper_mbgl"] = None
            d["risk"] = "Unavailable"
        res.append(d)
    return res


@router.get("/ai/health", tags=["AI Predictive Forecasting"])
async def ai_gateway_health():
    return await _fetch_ai_service("/health")


@router.get("/ai/metrics", tags=["AI Predictive Forecasting"])
async def ai_gateway_metrics():
    return await _fetch_ai_service("/api/ai/metrics")


@router.get("/ai/stations", tags=["AI Predictive Forecasting"])
async def ai_gateway_stations(limit: int = Query(500)):
    return await _fetch_ai_service("/api/ai/stations", params={"limit": limit})


@router.get("/ai/forecasts", tags=["AI Predictive Forecasting"])
async def ai_gateway_forecasts():
    return await _fetch_ai_service("/api/ai/forecasts")


@router.get("/ai/predictions", tags=["AI Predictive Forecasting"])
async def ai_gateway_predictions():
    return await _fetch_ai_service("/api/ai/predictions")


@router.get("/ai/forecast/{station_id}", tags=["AI Predictive Forecasting"])
async def ai_gateway_forecast(station_id: str):
    return await _fetch_ai_service(f"/api/ai/forecast/{station_id}")


@router.get("/stations/{station_id}", tags=["Stations"])
async def get_station(station_id: str, db: Session=Depends(get_db)):
    s = db.query(Station).filter(Station.station_id == station_id).first()
    if not s: raise HTTPException(404, f"Station {station_id} not found")
    d = s.to_dict()
    latest = db.query(DWLRReading).filter(DWLRReading.station_id == station_id).order_by(DWLRReading.timestamp.desc()).first()
    d["current_level_m"] = latest.water_level_m if latest else None
    d["last_observation_time"] = latest.timestamp.isoformat() if (latest and latest.timestamp) else None
    d["data_provenance"] = "historical_annual" if (latest and latest.data_quality_flag == "HISTORICAL_ANNUAL") else "benchmark_telemetry"
    try:
        fc = await _fetch_ai_service(f"/api/ai/forecast/{station_id}")
        if fc and fc.get("forecast_mbgl") is not None:
            pred = float(fc["forecast_mbgl"])
            d["predicted_depth_m"] = pred
            d["forecast_mbgl"] = pred
            d["forecast_year"] = fc.get("forecast_year")
            d["lower_mbgl"] = fc.get("lower_mbgl")
            d["upper_mbgl"] = fc.get("upper_mbgl")
            d["risk"] = fc.get("risk", "Unavailable")
        else:
            d["predicted_depth_m"] = None
            d["forecast_mbgl"] = None
            d["risk"] = "Unavailable"
    except Exception:
        d["predicted_depth_m"] = None
        d["forecast_mbgl"] = None
        d["risk"] = "Unavailable"
    return d


@router.get("/task1/{station_id}", tags=["Task 1 — Fluctuation"])
def task1_station(station_id: str, hours: int=Query(720), db: Session=Depends(get_db)):
    result = get_fluctuation_analysis(station_id, db, hours=hours)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/task1", tags=["Task 1 — Fluctuation"])
def task1_bulk(state: Optional[str]=Query(None), district: Optional[str]=Query(None), hours: int=Query(720), db: Session=Depends(get_db)):
    results = get_fluctuation_analysis_batch(db, state=state, district=district, hours=hours)
    if not results: raise HTTPException(404, "No data found")
    return results


@router.get("/task2/{station_id}", tags=["Task 2 — Recharge"])
def task2_station(station_id: str, days: int=Query(365), db: Session=Depends(get_db)):
    result = get_recharge_estimate(station_id, db, days=days)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/task2", tags=["Task 2 — Recharge"])
def task2_bulk(state: Optional[str]=Query(None), district: Optional[str]=Query(None), days: int=Query(365), db: Session=Depends(get_db)):
    results = get_recharge_batch(db, state=state, district=district, days=days)
    if not results: raise HTTPException(404, "No data found")
    return results


@router.get("/task3/{station_id}", tags=["Task 3 — Evaluation"])
def task3_station(station_id: str, days: int=Query(365), stage_of_dev: Optional[float]=Query(None), db: Session=Depends(get_db)):
    result = get_station_evaluation(station_id, db, days=days, stage_of_dev=stage_of_dev)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/alerts", tags=["Alerts"])
def active_alerts(state: Optional[str]=Query(None), district: Optional[str]=Query(None), hours: int=Query(48), db: Session=Depends(get_db)):
    alerts = get_active_alerts(db, state=state, district=district, days=hours // 24 or 2)
    return {"total": len(alerts), "alerts": alerts}


@router.get("/alerts/anomalies", tags=["Alerts"])
def anomaly_alerts(state: Optional[str]=Query(None), hours: int=Query(24), db: Session=Depends(get_db)):
    anomalies = get_anomalies(db, state=state, hours=hours)
    return {"total": len(anomalies), "anomalies": anomalies}


@router.get("/summary/{state}", tags=["Scorecards"])
def state_summary(state: str, db: Session=Depends(get_db)):
    result = get_state_scorecard(state, db)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/summary/{state}/{district}", tags=["Scorecards"])
def district_summary(state: str, district: str, db: Session=Depends(get_db)):
    result = get_district_scorecard(state, district, db)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/ranking/states", tags=["Ranking"])
def state_ranking(db: Session=Depends(get_db)):
    rows = (
        db.query(
            Station.state,
            func.count(Station.station_id.distinct()).label("total_stations"),
            func.avg(DWLRReading.water_level_m).label("avg_level"),
            func.min(DWLRReading.water_level_m).label("min_level"),
            func.max(DWLRReading.water_level_m).label("max_level"),
        )
        .join(DWLRReading, Station.station_id == DWLRReading.station_id)
        .filter(Station.state.isnot(None))
        .group_by(Station.state)
        .all()
    )
    results = []
    for row in rows:
        if not row.state or not row.avg_level: continue
        avg = float(row.avg_level)
        status = "safe" if avg < 8 else "semi_critical" if avg < 15 else "critical" if avg <= 25 else "over_exploited"
        rai = round(max(0, min(100, 100 - (avg / 80) * 100)), 1)
        results.append({
            "state": row.state, "total_stations": int(row.total_stations),
            "avg_water_level_m": round(avg, 2),
            "min_water_level_m": round(float(row.min_level), 2) if row.min_level else None,
            "max_water_level_m": round(float(row.max_level), 2) if row.max_level else None,
            "status": status, "assessment_type": "exploratory_depth_tier", "rai": rai,
        })
    results.sort(key=lambda x: x["rai"])
    return {"total_states": len(results), "states": results}


@router.get("/ranking/districts/{state}", tags=["Ranking"])
def district_ranking(state: str, db: Session=Depends(get_db)):
    rows = (
        db.query(
            Station.district,
            func.count(Station.station_id.distinct()).label("total_stations"),
            func.avg(DWLRReading.water_level_m).label("avg_level"),
        )
        .join(DWLRReading, Station.station_id == DWLRReading.station_id)
        .filter(Station.state.ilike(f"%{state}%"))
        .filter(Station.district.isnot(None))
        .group_by(Station.district)
        .all()
    )
    results = []
    for row in rows:
        if not row.district or not row.avg_level: continue
        avg = float(row.avg_level)
        status = "safe" if avg < 8 else "semi_critical" if avg < 15 else "critical" if avg <= 25 else "over_exploited"
        rai = round(max(0, min(100, 100 - (avg / 80) * 100)), 1)
        results.append({"district": row.district, "total_stations": int(row.total_stations), "avg_water_level_m": round(avg, 2), "status": status, "assessment_type": "exploratory_depth_tier", "rai": rai})
    results.sort(key=lambda x: x["rai"])
    return {"state": state, "total_districts": len(results), "districts": results}


# ── EXPORT: summary MUST come before {station_id} to avoid route conflict ──
@router.get("/export/summary/csv", tags=["Export"])
def export_summary_csv(db: Session=Depends(get_db)):
    """Export all stations — MUST be defined before /export/{station_id}/csv"""
    stations = db.query(Station).all()
    if not stations: raise HTTPException(404, "No stations")
    latest = db.query(DWLRReading.station_id, func.avg(DWLRReading.water_level_m).label("avg_level")).group_by(DWLRReading.station_id).all()
    latest_map = {r.station_id: float(r.avg_level) for r in latest if r.avg_level}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["station_id","station_name","state","district","block","latitude","longitude","aquifer_type","well_depth_m","avg_water_level_m","depth_tier_status","assessment_type"])
    for s in stations:
        avg = latest_map.get(s.station_id)
        status = "no_data" if avg is None else "safe" if avg < 8 else "semi_critical" if avg < 15 else "critical" if avg <= 25 else "over_exploited"
        w.writerow([s.station_id, s.station_name, s.state, s.district, s.block, s.latitude, s.longitude, s.aquifer_type, s.well_depth_m, round(avg,2) if avg else "", status, "exploratory_depth_tier"])
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=jaldrishti_all_stations.csv"})


@router.get("/export/{station_id}/csv", tags=["Export"])
def export_readings_csv(station_id: str, limit: int=Query(5000), db: Session=Depends(get_db)):
    station = db.query(Station).filter(Station.station_id == station_id).first()
    if not station: raise HTTPException(404, f"Station {station_id} not found")
    rows = db.query(DWLRReading).filter(DWLRReading.station_id == station_id).order_by(DWLRReading.timestamp).limit(limit).all()
    if not rows: raise HTTPException(404, "No readings to export")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["station_id","station_name","state","district","timestamp","water_level_m","data_quality_flag","is_anomaly","anomaly_reason"])
    for r in rows:
        w.writerow([station.station_id, station.station_name, station.state, station.district, r.timestamp.isoformat() if r.timestamp else "", r.water_level_m, r.data_quality_flag, r.is_anomaly, r.anomaly_reason or ""])
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={station_id}_{station.state}_readings.csv"})
