"""
app/services/assessment_unit.py — JalDrishti
Service layer for Statutory CGWB GEC-2015 Administrative Assessment-Unit Evaluation.

METHODOLOGICAL REQUIREMENTS:
  1. Assessment Unit Scope:
     Statutory GEC-2015 categorization evaluates administrative assessment units
     (Taluks / Blocks / Mandals / Watersheds) as contiguous hydrogeological units.
     Individual DWLR monitoring wells are NEVER classified as official assessment units.
     District fallback is strictly prohibited.
  2. Multi-Station Network Aggregation & Anti-Dominance Guard:
     Observations across all active stations in the block are aggregated by:
       a) First computing station-year seasonal averages:
          h_bar(s, y, season) = (1 / N_{s, y, season}) * sum_{k} h_{s, y, season, k}
       b) Then aggregating station-year values into block-level seasonal values using Equal Station-Year Weighting:
          H_bar_{block}(y, season) = (1 / |S_{y, season}|) * sum_{s in S_{y, season}} h_bar(s, y, season)
     This guarantees that high-frequency telemetry wells (15-min data) do NOT dominate
     the block average over manual CGWB monitoring wells.
  3. Decadal Seasonal Evidence Verification:
     Strictly requires at least 10 years of pre-monsoon (Apr-May) AND 10 years of
     post-monsoon (Oct-Nov) observations separately. Arbitrary annual readings do not qualify.
  4. Authoritative Stage of Groundwater Extraction (SOE):
     Requires volumetric SOE (Draft / Extractable Recharge * 100%) with documented
     source citation and assessment year. SOE CANNOT be derived from local well depths.
  5. Unassessed Guard:
     Returns 'unassessed' with an explicit scientific rationale whenever required administrative
     data, coverage, or decadal records are missing or insufficient.
"""

import logging
from typing import Optional, Dict, Any, List
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.station import Station, DWLRReading
from algorithms.task3_evaluation import (
    aggregate_block_seasonal_trends,
    classify_gec2015_assessment_unit,
    MIN_DECADAL_TREND_YEARS,
)

log = logging.getLogger("jaldrishti.service.assessment_unit")


def evaluate_block_administrative_unit(
    block_name: str,
    stage_of_extraction_pct: Optional[float] = None,
    soe_source: Optional[str] = None,
    assessment_year: Optional[Any] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    min_stations_per_year: int = 1,
    db: Optional[Session] = None,
    readings_df: Optional[pd.DataFrame] = None,
    stations_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Evaluate an administrative assessment unit (block/taluk) under statutory GEC-2015 methodology.
    """
    # Guard 1: Valid block name
    if (
        not block_name
        or not str(block_name).strip()
        or str(block_name).strip().lower() in ("unknown", "none", "unassigned", "")
    ):
        return {
            "assessment_unit": None,
            "administrative_level": "block_or_taluk",
            "is_official_assessment_unit": False,
            "category": "unassessed",
            "category_label": "Unassessed",
            "stage_of_extraction_pct": None,
            "soe_source": str(soe_source).strip() if soe_source else None,
            "assessment_year": assessment_year,
            "station_count": 0,
            "station_ids": [],
            "weighting_method": "equal_station_year_weighting",
            "pre_monsoon_years_count": 0,
            "post_monsoon_years_count": 0,
            "pre_monsoon_trend_decline": None,
            "post_monsoon_trend_decline": None,
            "pre_monsoon_annual_coverage": [],
            "post_monsoon_annual_coverage": [],
            "framework": "CGWB GEC-2015 Methodology",
            "statutory_scope": "administrative_assessment_unit",
            "rationale": (
                "Unassessed: Valid administrative assessment unit (block/taluk) name is required. "
                "Individual monitoring wells cannot be classified as official blocks, and district fallback is prohibited."
            ),
            "methodological_disclaimer": (
                "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
                "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
                "screening points and cannot be classified as official blocks."
            ),
        }

    target_block = str(block_name).strip()

    # Guard 2: Authoritative SOE data requirements
    if (
        stage_of_extraction_pct is None
        or not isinstance(stage_of_extraction_pct, (int, float))
        or stage_of_extraction_pct < 0.0
    ):
        reason = (
            f"Unassessed for {target_block}: Invalid Stage of Groundwater Extraction ({stage_of_extraction_pct}%). "
            "SOE must be a non-negative percentage (>= 0.0%)."
            if stage_of_extraction_pct is not None and stage_of_extraction_pct < 0.0
            else (
                f"Unassessed for {target_block}: Missing authoritative Stage of Groundwater Extraction (SOE) data. "
                "GEC-2015 categorization requires volumetric gross draft and annual extractable resource accounting "
                "from official CGWB Dynamic Ground Water Resource Assessments. "
                "SOE cannot be derived or estimated from point-level groundwater depth or localized well trends."
            )
        )
        return _unassessed_response(
            target_block,
            reason,
            stage_of_extraction_pct=None,
            soe_source=str(soe_source).strip() if soe_source else None,
            assessment_year=assessment_year,
        )

    if not soe_source or not str(soe_source).strip():
        return _unassessed_response(
            target_block,
            (
                f"Unassessed for {target_block}: Authoritative SOE data source citation is required "
                "(e.g., 'CGWB Dynamic Ground Water Resources Assessment of India (2023)'). "
                "SOE cannot be derived from local well observations."
            ),
            stage_of_extraction_pct=round(float(stage_of_extraction_pct), 2),
            soe_source=None,
            assessment_year=assessment_year,
        )

    if assessment_year is None or not str(assessment_year).strip():
        return _unassessed_response(
            target_block,
            (
                f"Unassessed for {target_block}: Authoritative SOE assessment year must be specified (e.g., 2022, 2023)."
            ),
            stage_of_extraction_pct=round(float(stage_of_extraction_pct), 2),
            soe_source=str(soe_source).strip(),
            assessment_year=None,
        )

    # Obtain station and reading data (either from pre-supplied DataFrames or database)
    if stations_df is None or readings_df is None:
        if db is None:
            return _unassessed_response(
                target_block,
                f"Unassessed for {target_block}: Database session or station/reading DataFrames required.",
                stage_of_extraction_pct=round(float(stage_of_extraction_pct), 2),
                soe_source=str(soe_source).strip(),
                assessment_year=assessment_year,
            )

        query = db.query(Station).filter(Station.block.ilike(f"%{target_block}%"))
        if state:
            query = query.filter(Station.state.ilike(f"%{state}%"))
        if district:
            query = query.filter(Station.district.ilike(f"%{district}%"))
        stations = query.all()

        if not stations:
            return _unassessed_response(
                target_block,
                f"Unassessed for {target_block}: Insufficient monitoring network: 0 monitoring stations located in administrative block '{target_block}'.",
                stage_of_extraction_pct=round(float(stage_of_extraction_pct), 2),
                soe_source=str(soe_source).strip(),
                assessment_year=assessment_year,
                station_count=0,
            )

        station_ids = [s.station_id for s in stations]
        readings = (
            db.query(DWLRReading)
            .filter(DWLRReading.station_id.in_(station_ids))
            .all()
        )

        if not readings:
            return _unassessed_response(
                target_block,
                f"Unassessed for {target_block}: No groundwater level readings available for {len(station_ids)} stations in block '{target_block}'.",
                stage_of_extraction_pct=round(float(stage_of_extraction_pct), 2),
                soe_source=str(soe_source).strip(),
                assessment_year=assessment_year,
                station_count=len(station_ids),
                station_ids=station_ids,
            )

        stations_df = pd.DataFrame([s.to_dict() for s in stations])
        readings_df = pd.DataFrame([{
            "station_id": r.station_id,
            "timestamp": r.timestamp,
            "water_level_m": r.water_level_m,
            "data_quality_flag": r.data_quality_flag or "G",
        } for r in readings])

    # Perform Station-Year Normalized Multi-Station Seasonal Aggregation
    agg = aggregate_block_seasonal_trends(
        readings_df=readings_df,
        stations_df=stations_df,
        block_name=target_block,
        min_stations_per_year=min_stations_per_year,
    )

    station_count = agg["station_count"]
    station_ids = agg["station_ids"]
    pre_years = agg["pre_monsoon_years_count"]
    post_years = agg["post_monsoon_years_count"]
    pre_coverage = agg["pre_monsoon_annual_coverage"]
    post_coverage = agg["post_monsoon_annual_coverage"]

    # Guard 3: Insufficient station coverage in block
    if station_count == 0:
        return _unassessed_response(
            target_block,
            f"Unassessed for {target_block}: Insufficient monitoring network: 0 monitoring stations located in administrative block '{target_block}'.",
            stage_of_extraction_pct=round(float(stage_of_extraction_pct), 2),
            soe_source=str(soe_source).strip(),
            assessment_year=assessment_year,
            station_count=0,
            station_ids=[],
        )

    # Guard 4: Decadal Seasonal Completeness (must have >= 10 years pre- AND post-monsoon separately)
    if pre_years < MIN_DECADAL_TREND_YEARS or post_years < MIN_DECADAL_TREND_YEARS:
        return {
            "assessment_unit": target_block,
            "administrative_level": "block_or_taluk",
            "is_official_assessment_unit": True,
            "category": "unassessed",
            "category_label": "Unassessed",
            "stage_of_extraction_pct": round(float(stage_of_extraction_pct), 2),
            "soe_source": str(soe_source).strip(),
            "assessment_year": assessment_year,
            "station_count": station_count,
            "station_ids": station_ids,
            "weighting_method": agg["weighting_method"],
            "weighting_rationale": agg["weighting_rationale"],
            "pre_monsoon_years_count": pre_years,
            "post_monsoon_years_count": post_years,
            "pre_monsoon_trend_decline": agg["pre_monsoon_trend_decline"],
            "post_monsoon_trend_decline": agg["post_monsoon_trend_decline"],
            "pre_monsoon_slope_m_per_year": agg["pre_monsoon_slope_m_per_year"],
            "post_monsoon_slope_m_per_year": agg["post_monsoon_slope_m_per_year"],
            "pre_monsoon_annual_coverage": pre_coverage,
            "post_monsoon_annual_coverage": post_coverage,
            "coverage_sufficient": False,
            "coverage_rationale": agg["coverage_rationale"],
            "framework": "CGWB GEC-2015 Methodology",
            "statutory_scope": "administrative_assessment_unit",
            "rationale": (
                f"Unassessed for {target_block}: Insufficient statutory seasonal trend evidence. "
                f"GEC-2015 categorization strictly requires at least {MIN_DECADAL_TREND_YEARS} years of actual "
                f"pre-monsoon AND post-monsoon trend records separately. Available records: "
                f"pre-monsoon={pre_years} years, post-monsoon={post_years} years (station-year normalized). "
                "Station-year aggregated records do not meet the 10-year statutory threshold."
            ),
            "methodological_disclaimer": (
                "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
                "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
                "screening points and cannot be classified as official blocks."
            ),
        }

    # Evaluate official GEC-2015 categorization
    gec_res = classify_gec2015_assessment_unit(
        stage_of_extraction_pct=float(stage_of_extraction_pct),
        pre_monsoon_trend_decline=agg["pre_monsoon_trend_decline"],
        post_monsoon_trend_decline=agg["post_monsoon_trend_decline"],
        assessment_unit=target_block,
        pre_monsoon_years_count=pre_years,
        post_monsoon_years_count=post_years,
        soe_source=str(soe_source).strip(),
        assessment_year=assessment_year,
        require_authoritative_metadata=True,
    )

    return {
        "assessment_unit": target_block,
        "administrative_level": "block_or_taluk",
        "is_official_assessment_unit": True,
        "category": gec_res["category"],
        "category_label": gec_res["category_label"],
        "stage_of_extraction_pct": gec_res["stage_of_extraction_pct"],
        "soe_source": str(soe_source).strip(),
        "assessment_year": assessment_year,
        "station_count": station_count,
        "station_ids": station_ids,
        "weighting_method": agg["weighting_method"],
        "weighting_rationale": agg["weighting_rationale"],
        "pre_monsoon_years_count": pre_years,
        "post_monsoon_years_count": post_years,
        "pre_monsoon_trend_decline": agg["pre_monsoon_trend_decline"],
        "post_monsoon_trend_decline": agg["post_monsoon_trend_decline"],
        "pre_monsoon_slope_m_per_year": agg["pre_monsoon_slope_m_per_year"],
        "post_monsoon_slope_m_per_year": agg["post_monsoon_slope_m_per_year"],
        "pre_monsoon_annual_coverage": pre_coverage,
        "post_monsoon_annual_coverage": post_coverage,
        "coverage_sufficient": True,
        "coverage_rationale": agg["coverage_rationale"],
        "framework": "CGWB GEC-2015 Methodology",
        "statutory_scope": "administrative_assessment_unit",
        "rationale": gec_res["rationale"],
        "methodological_disclaimer": (
            "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
            "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
            "screening points and cannot be classified as official blocks."
        ),
    }


def list_administrative_assessment_units(
    db: Session,
    state: Optional[str] = None,
    district: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List all administrative assessment units (blocks/taluks) in the monitoring network.
    """
    query = (
        db.query(
            Station.block,
            Station.district,
            Station.state,
            func.count(Station.station_id.distinct()).label("station_count"),
        )
        .filter(Station.block.isnot(None))
        .filter(Station.block != "")
    )
    if state:
        query = query.filter(Station.state.ilike(f"%{state}%"))
    if district:
        query = query.filter(Station.district.ilike(f"%{district}%"))

    rows = (
        query.group_by(Station.block, Station.district, Station.state)
        .order_by(Station.state, Station.district, Station.block)
        .all()
    )

    units = []
    for r in rows:
        units.append({
            "block": r.block,
            "district": r.district,
            "state": r.state,
            "station_count": int(r.station_count),
            "assessment_status": "unassessed_pending_authoritative_soe",
            "statutory_note": (
                "Statutory GEC-2015 assessment requires authoritative CGWB Stage of Groundwater Extraction (SOE) "
                "compilation data and verified 10-year seasonal trend evidence."
            ),
        })

    return {
        "total_units": len(units),
        "assessment_units": units,
        "framework": "CGWB GEC-2015 Methodology",
    }


def _unassessed_response(
    block_name: str,
    reason: str,
    stage_of_extraction_pct: Optional[float] = None,
    soe_source: Optional[str] = None,
    assessment_year: Optional[Any] = None,
    station_count: int = 0,
    station_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "assessment_unit": block_name,
        "administrative_level": "block_or_taluk",
        "is_official_assessment_unit": True,
        "category": "unassessed",
        "category_label": "Unassessed",
        "stage_of_extraction_pct": stage_of_extraction_pct,
        "soe_source": soe_source,
        "assessment_year": assessment_year,
        "station_count": station_count,
        "station_ids": station_ids or [],
        "weighting_method": "equal_station_year_weighting",
        "pre_monsoon_years_count": 0,
        "post_monsoon_years_count": 0,
        "pre_monsoon_trend_decline": None,
        "post_monsoon_trend_decline": None,
        "pre_monsoon_annual_coverage": [],
        "post_monsoon_annual_coverage": [],
        "coverage_sufficient": False,
        "coverage_rationale": "Insufficient data to establish decadal trend coverage.",
        "framework": "CGWB GEC-2015 Methodology",
        "statutory_scope": "administrative_assessment_unit",
        "rationale": reason,
        "methodological_disclaimer": (
            "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
            "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
            "screening points and cannot be classified as official blocks."
        ),
    }
