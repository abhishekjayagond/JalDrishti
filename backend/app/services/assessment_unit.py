"""
app/services/assessment_unit.py — JalDrishti
Service layer for Statutory CGWB GEC-2015 Administrative Assessment-Unit Evaluation.

METHODOLOGICAL REQUIREMENTS & SCIENTIFIC INTEGRITY:
  1. Assessment Unit Scope:
     Statutory GEC-2015 categorization evaluates administrative assessment units
     (Taluks / Blocks / Mandals / Watersheds) as contiguous hydrogeological units.
     Individual DWLR monitoring wells are NEVER classified as official assessment units.
     District fallback is strictly prohibited.
  2. Spatial Monitoring Network Representativeness (Item 1):
     Under standard hydrogeological network principles (WMO No. 168 / CGWB Network Design Principles),
     a single point well cannot establish spatial representativeness for an administrative block.
     Spatial representativeness requires a distributed monitoring network (>= 2 active stations) and
     at least 2 spatially distinct monitoring stations per representative year (min_stations_per_year=2).
     When representativeness cannot be established, the unit is evaluated as 'unassessed' with explicit rationale.
  3. Authoritative SOE Provenance & Volumetric Accounting (Item 2):
     Requires traceable source records containing:
       - Canonical assessment-unit identity
       - Official published CGWB source document
       - Assessment year (e.g. 2023, 2022)
       - Supporting volumetric accounting:
           * Existing Gross Groundwater Draft for All Uses (in ham)
           * Annual Extractable Groundwater Resource (in ham)
           * SOE (%) = (Gross Draft / Annual Extractable Groundwater Resource) * 100%
     Arbitrary user strings, missing volumetric components, or contradictory numbers are rejected as 'unassessed'.
  4. Observation Data-Quality Rules (Item 3):
     Before seasonal aggregation, observations are screened using documented data-quality rules:
       - Exclude water_level_m < 0.0 m bgl (unphysical negative depth)
       - Exclude water_level_m > 300.0 m bgl (exceeds physical monitoring well depth in India)
       - Exclude data_quality_flag in ('E', 'ERROR', 'ERR', 'S', 'SUSPECT', 'R', 'REJECTED', 'BAD', 'INVALID')
       - Exclude readings marked as sensor anomalies (is_anomaly=True)
     Exclusion counts, reasons, and surviving coverage are tracked and reported in data_quality_screening.
  5. Unambiguous Administrative Identification (Item 4):
     Exact case-insensitive match on block name (no substring matching). Where duplicate block names
     exist across multiple districts, explicit district identification or canonical ID is strictly
     required to prevent accidental merging of stations across districts.
  6. Equal Station-Year Weighting (Anti-Dominance Guard):
     Seasonal averages are calculated per station per year first, then averaged across stations with
     equal weighting, preventing high-frequency telemetry from overwhelming manual observation wells.
  7. Decadal Seasonal Completeness:
     Strictly requires at least 10 years of pre-monsoon (Apr-May) AND 10 years of post-monsoon (Oct-Nov)
     spatially representative records separately.
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
    lookup_trusted_hydrogeological_threshold,
    MIN_DECADAL_TREND_YEARS,
    DEFAULT_MIN_STATIONS_PER_YEAR,
    OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
)
from app.services.assessment_unit_registry import (
    validate_soe_provenance,
    lookup_authoritative_record,
    build_canonical_id,
)

log = logging.getLogger("jaldrishti.service.assessment_unit")


def evaluate_block_administrative_unit(
    block_name: str,
    stage_of_extraction_pct: Optional[float] = None,
    soe_source: Optional[str] = None,
    assessment_year: Optional[Any] = None,
    annual_extractable_groundwater_resource_ham: Optional[float] = None,
    existing_gross_draft_total_ham: Optional[float] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    canonical_id: Optional[str] = None,
    min_stations_per_year: int = DEFAULT_MIN_STATIONS_PER_YEAR,
    db: Optional[Session] = None,
    readings_df: Optional[pd.DataFrame] = None,
    stations_df: Optional[pd.DataFrame] = None,
    significant_decline_threshold_m_per_year: Optional[float] = None,
    fallback_to_documented_threshold: bool = True,
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
            "canonical_id": None,
            "district": district,
            "state": state,
            "administrative_level": "block_or_taluk",
            "is_official_assessment_unit": False,
            "official_category": "unassessed",
            "category": "unassessed",
            "category_label": "Unassessed",
            "trend_validation_status": "not_evaluated",
            "pre_monsoon_trend": None,
            "post_monsoon_trend": None,
            "trend_validation_reason": (
                "Unassessed: Valid administrative assessment unit (block/taluk) name is required. "
                "Individual monitoring wells cannot be classified as official blocks, and district fallback is prohibited."
            ),
            "stage_of_extraction_pct": None,
            "soe_source": str(soe_source).strip() if soe_source else None,
            "assessment_year": assessment_year,
            "volumetric_resource": None,
            "station_count": 0,
            "station_ids": [],
            "weighting_method": "equal_station_year_weighting",
            "pre_monsoon_years_count": 0,
            "post_monsoon_years_count": 0,
            "pre_monsoon_trend_decline": None,
            "post_monsoon_trend_decline": None,
            "pre_monsoon_slope_m_per_year": None,
            "post_monsoon_slope_m_per_year": None,
            "pre_monsoon_p_value": None,
            "post_monsoon_p_value": None,
            "pre_monsoon_exploratory_ols": None,
            "post_monsoon_exploratory_ols": None,
            "pre_monsoon_modified_mann_kendall": None,
            "post_monsoon_modified_mann_kendall": None,
            "significant_decline_threshold_m_per_year": None,
            "threshold_record": None,
            "threshold_source_publication": None,
            "threshold_source_url": None,
            "threshold_page_table_reference": None,
            "threshold_hydrogeological_formation": None,
            "threshold_justification": None,
            "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
            "pre_monsoon_annual_coverage": [],
            "post_monsoon_annual_coverage": [],
            "coverage_sufficient": False,
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

    # Ambiguity check across districts if district is not specified
    if not district and db is not None:
        base_block_query = db.query(Station).filter(func.lower(func.trim(Station.block)) == target_block.lower())
        all_block_stns = base_block_query.all()
        unique_dists = sorted(list(set(s.district for s in all_block_stns if s.district)))
        if len(unique_dists) > 1:
            return _unassessed_response(
                target_block,
                (
                    f"Unassessed: Ambiguous administrative block '{target_block}'. This block name exists in multiple "
                    f"districts ({', '.join(unique_dists)}). Unambiguous administrative identification requires "
                    "specifying the district or canonical administrative identifier to prevent accidental merging of stations across districts."
                ),
                stage_of_extraction_pct=stage_of_extraction_pct,
                soe_source=soe_source,
                assessment_year=assessment_year,
                canonical_id=canonical_id,
            )

    # Resolve district and state from passed stations_df or db stations if possible
    resolved_district = district
    resolved_state = state
    stations = []
    if stations_df is not None and not stations_df.empty:
        if not resolved_district and "district" in stations_df.columns:
            resolved_district = stations_df["district"].iloc[0]
        if not resolved_state and "state" in stations_df.columns:
            resolved_state = stations_df["state"].iloc[0]
    elif db is not None:
        stn_query = db.query(Station).filter(func.lower(func.trim(Station.block)) == target_block.lower())
        if state:
            stn_query = stn_query.filter(func.lower(func.trim(Station.state)) == state.strip().lower())
        if district:
            stn_query = stn_query.filter(func.lower(func.trim(Station.district)) == district.strip().lower())
        stations = stn_query.all()
        if stations:
            if not resolved_district:
                resolved_district = stations[0].district
            if not resolved_state:
                resolved_state = stations[0].state

    # Guard 2: Validate SOE Provenance against Authoritative CGWB Registry & Volumetric Accounting
    is_prov_valid, prov_payload, prov_rationale = validate_soe_provenance(
        block_name=target_block,
        stage_of_extraction_pct=stage_of_extraction_pct,
        soe_source=soe_source,
        assessment_year=assessment_year,
        annual_extractable_groundwater_resource_ham=annual_extractable_groundwater_resource_ham,
        existing_gross_draft_total_ham=existing_gross_draft_total_ham,
        district=resolved_district,
        state=resolved_state,
        canonical_id=canonical_id,
    )

    if not is_prov_valid or prov_payload is None:
        stn_ids = [s.station_id for s in stations] if stations else (
            sorted(list(set(stations_df["station_id"].astype(str)))) if stations_df is not None and not stations_df.empty else []
        )
        return _unassessed_response(
            block_name=target_block,
            reason=prov_rationale,
            stage_of_extraction_pct=round(float(stage_of_extraction_pct), 2) if stage_of_extraction_pct is not None and isinstance(stage_of_extraction_pct, (int, float)) and stage_of_extraction_pct >= 0 else None,
            soe_source=str(soe_source).strip() if soe_source else None,
            assessment_year=assessment_year,
            station_count=len(stn_ids),
            station_ids=stn_ids,
            district=resolved_district,
            state=resolved_state,
            canonical_id=canonical_id,
        )

    # Provenance verified: extract verified values
    verified_soe = prov_payload["stage_of_extraction_pct"]
    verified_source = prov_payload["soe_source"]
    verified_year = prov_payload["assessment_year"]
    verified_draft = prov_payload.get("existing_gross_draft_total_ham")
    verified_resource = prov_payload.get("annual_extractable_groundwater_resource_ham")
    resolved_canonical_id = prov_payload.get("canonical_id")

    volumetric_resource = {
        "existing_gross_draft_total_ham": verified_draft,
        "annual_extractable_groundwater_resource_ham": verified_resource,
        "units": "hectare-metres (ham)",
        "formula": "SOE (%) = (Existing Gross Draft / Annual Extractable Groundwater Resource) * 100%",
    }

    # Obtain station and reading DataFrames if not passed
    if stations_df is None or readings_df is None:
        if db is None:
            # Verified SOE with no local station history / DB session
            gec_res = classify_gec2015_assessment_unit(
                stage_of_extraction_pct=verified_soe,
                assessment_unit=target_block,
                soe_source=verified_source,
                assessment_year=verified_year,
                require_authoritative_metadata=True,
            )
            return {
                "assessment_unit": target_block,
                "canonical_id": resolved_canonical_id,
                "district": resolved_district,
                "state": resolved_state,
                "administrative_level": "block_or_taluk",
                "is_official_assessment_unit": True,
                "official_category": gec_res["official_category"],
                "category": gec_res["category"],
                "category_label": gec_res["category_label"],
                "trend_validation_status": "not_evaluated",
                "pre_monsoon_trend": None,
                "post_monsoon_trend": None,
                "trend_validation_reason": (
                    f"Verified official category from CGWB SOE ({verified_soe:.1f}%). "
                    "Database session or station/reading DataFrames not supplied for local seasonal trend validation."
                ),
                "stage_of_extraction_pct": gec_res["stage_of_extraction_pct"],
                "soe_source": verified_source,
                "assessment_year": verified_year,
                "volumetric_resource": volumetric_resource,
                "station_count": 0,
                "station_ids": [],
                "weighting_method": "equal_station_year_weighting",
                "weighting_rationale": "Equal station-year seasonal averaging across monitoring wells.",
                "spatial_representativeness": {
                    "criteria": f">= 2 monitoring stations per block, and >= {min_stations_per_year} stations per representative year",
                    "methodological_basis": "WMO No. 168 / CGWB Network Design Principles (sampling spatial variance)",
                    "is_met": False,
                },
                "data_quality_screening": {
                    "total_readings_screened": 0,
                    "valid_readings_count": 0,
                    "excluded_readings_count": 0,
                    "exclusion_breakdown": {},
                },
                "pre_monsoon_years_count": 0,
                "post_monsoon_years_count": 0,
                "pre_monsoon_trend_decline": None,
                "post_monsoon_trend_decline": None,
                "pre_monsoon_slope_m_per_year": None,
                "post_monsoon_slope_m_per_year": None,
                "pre_monsoon_p_value": None,
                "post_monsoon_p_value": None,
                "pre_monsoon_exploratory_ols": None,
                "post_monsoon_exploratory_ols": None,
                "pre_monsoon_modified_mann_kendall": None,
                "post_monsoon_modified_mann_kendall": None,
                "significant_decline_threshold_m_per_year": gec_res.get("significant_decline_threshold_m_per_year"),
                "threshold_record": gec_res.get("threshold_record"),
                "threshold_source_publication": gec_res.get("threshold_source_publication"),
                "threshold_source_url": gec_res.get("threshold_source_url"),
                "threshold_page_table_reference": gec_res.get("threshold_page_table_reference"),
                "threshold_hydrogeological_formation": gec_res.get("threshold_hydrogeological_formation"),
                "threshold_justification": gec_res.get("threshold_justification"),
                "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
                "pre_monsoon_annual_coverage": [],
                "post_monsoon_annual_coverage": [],
                "coverage_sufficient": False,
                "coverage_rationale": "No station readings available for trend validation.",
                "framework": "CGWB GEC-2015 Methodology",
                "statutory_scope": "administrative_assessment_unit",
                "rationale": gec_res["rationale"],
                "methodological_disclaimer": (
                    "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
                    "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
                    "screening points and cannot be classified as official blocks."
                ),
            }

        # Handle 0 stations located in block in DB
        if not stations:
            gec_res = classify_gec2015_assessment_unit(
                stage_of_extraction_pct=verified_soe,
                assessment_unit=target_block,
                soe_source=verified_source,
                assessment_year=verified_year,
                require_authoritative_metadata=True,
            )
            return {
                "assessment_unit": target_block,
                "canonical_id": resolved_canonical_id,
                "district": resolved_district,
                "state": resolved_state,
                "administrative_level": "block_or_taluk",
                "is_official_assessment_unit": True,
                "official_category": gec_res["official_category"],
                "category": gec_res["category"],
                "category_label": gec_res["category_label"],
                "trend_validation_status": "insufficient_data",
                "pre_monsoon_trend": "insufficient_data",
                "post_monsoon_trend": "insufficient_data",
                "trend_validation_reason": (
                    f"Administrative block '{target_block}' has 0 monitoring stations in the local database. "
                    f"Official category is retained from verified CGWB SOE ({verified_soe:.1f}%). "
                    "Decadal trend validation is unavailable."
                ),
                "stage_of_extraction_pct": gec_res["stage_of_extraction_pct"],
                "soe_source": verified_source,
                "assessment_year": verified_year,
                "volumetric_resource": volumetric_resource,
                "station_count": 0,
                "station_ids": [],
                "weighting_method": "equal_station_year_weighting",
                "weighting_rationale": "Equal station-year seasonal averaging across monitoring wells.",
                "spatial_representativeness": {
                    "criteria": f">= 2 monitoring stations per block, and >= {min_stations_per_year} stations per representative year",
                    "methodological_basis": "WMO No. 168 / CGWB Network Design Principles (sampling spatial variance)",
                    "is_met": False,
                },
                "data_quality_screening": {
                    "total_readings_screened": 0,
                    "valid_readings_count": 0,
                    "excluded_readings_count": 0,
                    "exclusion_breakdown": {},
                },
                "pre_monsoon_years_count": 0,
                "post_monsoon_years_count": 0,
                "pre_monsoon_trend_decline": None,
                "post_monsoon_trend_decline": None,
                "pre_monsoon_slope_m_per_year": None,
                "post_monsoon_slope_m_per_year": None,
                "pre_monsoon_p_value": None,
                "post_monsoon_p_value": None,
                "pre_monsoon_exploratory_ols": None,
                "post_monsoon_exploratory_ols": None,
                "pre_monsoon_modified_mann_kendall": None,
                "post_monsoon_modified_mann_kendall": None,
                "significant_decline_threshold_m_per_year": gec_res.get("significant_decline_threshold_m_per_year"),
                "threshold_record": gec_res.get("threshold_record"),
                "threshold_source_publication": gec_res.get("threshold_source_publication"),
                "threshold_source_url": gec_res.get("threshold_source_url"),
                "threshold_page_table_reference": gec_res.get("threshold_page_table_reference"),
                "threshold_hydrogeological_formation": gec_res.get("threshold_hydrogeological_formation"),
                "threshold_justification": gec_res.get("threshold_justification"),
                "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
                "pre_monsoon_annual_coverage": [],
                "post_monsoon_annual_coverage": [],
                "coverage_sufficient": False,
                "coverage_rationale": f"0 monitoring stations located in administrative block '{target_block}'.",
                "framework": "CGWB GEC-2015 Methodology",
                "statutory_scope": "administrative_assessment_unit",
                "rationale": gec_res["rationale"],
                "methodological_disclaimer": (
                    "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
                    "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
                    "screening points and cannot be classified as official blocks."
                ),
            }

        station_ids = [s.station_id for s in stations]

        # Spatial Monitoring Network Representativeness: Single-station network (<2 stations)
        if len(stations) < 2:
            gec_res = classify_gec2015_assessment_unit(
                stage_of_extraction_pct=verified_soe,
                assessment_unit=target_block,
                soe_source=verified_source,
                assessment_year=verified_year,
                require_authoritative_metadata=True,
            )
            return {
                "assessment_unit": target_block,
                "canonical_id": resolved_canonical_id,
                "district": resolved_district,
                "state": resolved_state,
                "administrative_level": "block_or_taluk",
                "is_official_assessment_unit": True,
                "official_category": gec_res["official_category"],
                "category": gec_res["category"],
                "category_label": gec_res["category_label"],
                "trend_validation_status": "insufficient_data",
                "pre_monsoon_trend": "insufficient_data",
                "post_monsoon_trend": "insufficient_data",
                "trend_validation_reason": (
                    f"Insufficient spatial monitoring network representativeness. Administrative block '{target_block}' "
                    f"has only {len(stations)} monitoring station(s). Under standard hydrogeological network principles "
                    "(WMO No. 168 / CGWB monitoring guidelines), a single point well cannot establish spatial "
                    "representativeness across an entire administrative block. Official category is retained from "
                    f"verified CGWB SOE ({verified_soe:.1f}%)."
                ),
                "stage_of_extraction_pct": gec_res["stage_of_extraction_pct"],
                "soe_source": verified_source,
                "assessment_year": verified_year,
                "volumetric_resource": volumetric_resource,
                "station_count": len(stations),
                "station_ids": station_ids,
                "weighting_method": "equal_station_year_weighting",
                "weighting_rationale": "Equal station-year seasonal averaging across monitoring wells.",
                "spatial_representativeness": {
                    "criteria": f">= 2 monitoring stations per block, and >= {min_stations_per_year} stations per representative year",
                    "methodological_basis": "WMO No. 168 / CGWB Network Design Principles (sampling spatial variance)",
                    "is_met": False,
                },
                "data_quality_screening": {
                    "total_readings_screened": 0,
                    "valid_readings_count": 0,
                    "excluded_readings_count": 0,
                    "exclusion_breakdown": {},
                },
                "pre_monsoon_years_count": 0,
                "post_monsoon_years_count": 0,
                "pre_monsoon_trend_decline": None,
                "post_monsoon_trend_decline": None,
                "pre_monsoon_slope_m_per_year": None,
                "post_monsoon_slope_m_per_year": None,
                "pre_monsoon_p_value": None,
                "post_monsoon_p_value": None,
                "pre_monsoon_exploratory_ols": None,
                "post_monsoon_exploratory_ols": None,
                "pre_monsoon_modified_mann_kendall": None,
                "post_monsoon_modified_mann_kendall": None,
                "significant_decline_threshold_m_per_year": gec_res.get("significant_decline_threshold_m_per_year"),
                "threshold_record": gec_res.get("threshold_record"),
                "threshold_source_publication": gec_res.get("threshold_source_publication"),
                "threshold_source_url": gec_res.get("threshold_source_url"),
                "threshold_page_table_reference": gec_res.get("threshold_page_table_reference"),
                "threshold_hydrogeological_formation": gec_res.get("threshold_hydrogeological_formation"),
                "threshold_justification": gec_res.get("threshold_justification"),
                "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
                "pre_monsoon_annual_coverage": [],
                "post_monsoon_annual_coverage": [],
                "coverage_sufficient": False,
                "coverage_rationale": f"Insufficient spatial monitoring network ({len(stations)} station; >=2 required).",
                "framework": "CGWB GEC-2015 Methodology",
                "statutory_scope": "administrative_assessment_unit",
                "rationale": gec_res["rationale"],
                "methodological_disclaimer": (
                    "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
                    "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
                    "screening points and cannot be classified as official blocks."
                ),
            }

        readings = (
            db.query(DWLRReading)
            .filter(DWLRReading.station_id.in_(station_ids))
            .all()
        )

        if not readings:
            gec_res = classify_gec2015_assessment_unit(
                stage_of_extraction_pct=verified_soe,
                assessment_unit=target_block,
                soe_source=verified_source,
                assessment_year=verified_year,
                require_authoritative_metadata=True,
            )
            return {
                "assessment_unit": target_block,
                "canonical_id": resolved_canonical_id,
                "district": resolved_district,
                "state": resolved_state,
                "administrative_level": "block_or_taluk",
                "is_official_assessment_unit": True,
                "official_category": gec_res["official_category"],
                "category": gec_res["category"],
                "category_label": gec_res["category_label"],
                "trend_validation_status": "insufficient_data",
                "pre_monsoon_trend": "insufficient_data",
                "post_monsoon_trend": "insufficient_data",
                "trend_validation_reason": (
                    f"No groundwater level readings available for {len(station_ids)} stations in block '{target_block}'. "
                    f"Official category is retained from verified CGWB SOE ({verified_soe:.1f}%)."
                ),
                "stage_of_extraction_pct": gec_res["stage_of_extraction_pct"],
                "soe_source": verified_source,
                "assessment_year": verified_year,
                "volumetric_resource": volumetric_resource,
                "station_count": len(station_ids),
                "station_ids": station_ids,
                "weighting_method": "equal_station_year_weighting",
                "weighting_rationale": "Equal station-year seasonal averaging across monitoring wells.",
                "spatial_representativeness": {
                    "criteria": f">= 2 monitoring stations per block, and >= {min_stations_per_year} stations per representative year",
                    "methodological_basis": "WMO No. 168 / CGWB Network Design Principles (sampling spatial variance)",
                    "is_met": True,
                },
                "data_quality_screening": {
                    "total_readings_screened": 0,
                    "valid_readings_count": 0,
                    "excluded_readings_count": 0,
                    "exclusion_breakdown": {},
                },
                "pre_monsoon_years_count": 0,
                "post_monsoon_years_count": 0,
                "pre_monsoon_trend_decline": None,
                "post_monsoon_trend_decline": None,
                "pre_monsoon_slope_m_per_year": None,
                "post_monsoon_slope_m_per_year": None,
                "pre_monsoon_p_value": None,
                "post_monsoon_p_value": None,
                "pre_monsoon_exploratory_ols": None,
                "post_monsoon_exploratory_ols": None,
                "pre_monsoon_modified_mann_kendall": None,
                "post_monsoon_modified_mann_kendall": None,
                "significant_decline_threshold_m_per_year": gec_res.get("significant_decline_threshold_m_per_year"),
                "threshold_record": gec_res.get("threshold_record"),
                "threshold_source_publication": gec_res.get("threshold_source_publication"),
                "threshold_source_url": gec_res.get("threshold_source_url"),
                "threshold_page_table_reference": gec_res.get("threshold_page_table_reference"),
                "threshold_hydrogeological_formation": gec_res.get("threshold_hydrogeological_formation"),
                "threshold_justification": gec_res.get("threshold_justification"),
                "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
                "pre_monsoon_annual_coverage": [],
                "post_monsoon_annual_coverage": [],
                "coverage_sufficient": False,
                "coverage_rationale": f"No readings available for {len(station_ids)} stations in block '{target_block}'.",
                "framework": "CGWB GEC-2015 Methodology",
                "statutory_scope": "administrative_assessment_unit",
                "rationale": gec_res["rationale"],
                "methodological_disclaimer": (
                    "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
                    "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
                    "screening points and cannot be classified as official blocks."
                ),
            }

        stations_df = pd.DataFrame([s.to_dict() for s in stations])
        readings_df = pd.DataFrame([{
            "station_id": r.station_id,
            "timestamp": r.timestamp,
            "water_level_m": r.water_level_m,
            "data_quality_flag": r.data_quality_flag or "G",
            "is_anomaly": getattr(r, "is_anomaly", False),
            "anomaly_reason": getattr(r, "anomaly_reason", None),
        } for r in readings])

    # Perform Station-Year Normalized Multi-Station Seasonal Aggregation with Data Quality Screening
    agg = aggregate_block_seasonal_trends(
        readings_df=readings_df,
        stations_df=stations_df,
        block_name=target_block,
        district=resolved_district,
        state=resolved_state,
        min_stations_per_year=min_stations_per_year,
        significant_decline_threshold_m_per_year=significant_decline_threshold_m_per_year,
        fallback_to_documented_threshold=fallback_to_documented_threshold,
    )

    station_count = agg["station_count"]
    station_ids = agg["station_ids"]
    pre_years = agg["pre_monsoon_years_count"]
    post_years = agg["post_monsoon_years_count"]
    pre_coverage = agg["pre_monsoon_annual_coverage"]
    post_coverage = agg["post_monsoon_annual_coverage"]
    screening_audit = agg.get("data_quality_screening", {})
    is_spatial_rep = bool(agg.get("spatial_representativeness_met", False) and station_count >= 2)
    coverage_sufficient = bool(agg.get("coverage_sufficient", False))

    # Evaluate official GEC-2015 categorization and independent trend validation
    gec_res = classify_gec2015_assessment_unit(
        stage_of_extraction_pct=verified_soe,
        pre_monsoon_trend_decline=agg["pre_monsoon_trend_decline"],
        post_monsoon_trend_decline=agg["post_monsoon_trend_decline"],
        assessment_unit=target_block,
        pre_monsoon_years_count=pre_years,
        post_monsoon_years_count=post_years,
        soe_source=verified_source,
        assessment_year=verified_year,
        require_authoritative_metadata=True,
        pre_monsoon_trend=agg.get("pre_monsoon_trend"),
        post_monsoon_trend=agg.get("post_monsoon_trend"),
        significant_decline_threshold_m_per_year=agg.get("significant_decline_threshold_m_per_year"),
        fallback_to_documented_threshold=fallback_to_documented_threshold,
        pre_monsoon_threshold_sensitivity=agg.get("pre_monsoon_threshold_sensitivity"),
        post_monsoon_threshold_sensitivity=agg.get("post_monsoon_threshold_sensitivity"),
        overall_trend_sensitivity=agg.get("overall_trend_sensitivity"),
        pre_monsoon_sen_slope_ci_95=agg.get("pre_monsoon_sen_slope_ci_95"),
        post_monsoon_sen_slope_ci_95=agg.get("post_monsoon_sen_slope_ci_95"),
    )

    return {
        "assessment_unit": target_block,
        "canonical_id": resolved_canonical_id,
        "district": resolved_district,
        "state": resolved_state,
        "administrative_level": "block_or_taluk",
        "is_official_assessment_unit": True,
        "official_category": gec_res["official_category"],
        "category": gec_res["category"],
        "category_label": gec_res["category_label"],
        "trend_validation_status": gec_res["trend_validation_status"],
        "pre_monsoon_trend": gec_res["pre_monsoon_trend"],
        "post_monsoon_trend": gec_res["post_monsoon_trend"],
        "pre_monsoon_threshold_sensitivity": agg.get("pre_monsoon_threshold_sensitivity", gec_res.get("pre_monsoon_threshold_sensitivity")),
        "post_monsoon_threshold_sensitivity": agg.get("post_monsoon_threshold_sensitivity", gec_res.get("post_monsoon_threshold_sensitivity")),
        "overall_trend_sensitivity": agg.get("overall_trend_sensitivity", gec_res.get("overall_trend_sensitivity")),
        "pre_monsoon_threshold_sensitivity_rationale": agg.get("pre_monsoon_threshold_sensitivity_rationale"),
        "post_monsoon_threshold_sensitivity_rationale": agg.get("post_monsoon_threshold_sensitivity_rationale"),
        "overall_trend_sensitivity_rationale": agg.get("overall_trend_sensitivity_rationale"),
        "pre_monsoon_sen_slope_ci_95": agg.get("pre_monsoon_sen_slope_ci_95"),
        "post_monsoon_sen_slope_ci_95": agg.get("post_monsoon_sen_slope_ci_95"),
        "trend_validation_reason": gec_res["trend_validation_reason"],
        "stage_of_extraction_pct": gec_res["stage_of_extraction_pct"],
        "soe_source": verified_source,
        "assessment_year": verified_year,
        "volumetric_resource": volumetric_resource,
        "station_count": station_count,
        "station_ids": station_ids,
        "weighting_method": agg["weighting_method"],
        "weighting_rationale": agg["weighting_rationale"],
        "spatial_representativeness": {
            "criteria": f">= 2 monitoring stations per block, and >= {min_stations_per_year} stations per representative year",
            "methodological_basis": "WMO No. 168 / CGWB Network Design Principles (sampling spatial variance)",
            "is_met": is_spatial_rep,
        },
        "data_quality_screening": screening_audit,
        "pre_monsoon_years_count": pre_years,
        "post_monsoon_years_count": post_years,
        "pre_monsoon_trend_decline": gec_res["pre_monsoon_trend_decline"],
        "post_monsoon_trend_decline": gec_res["post_monsoon_trend_decline"],
        "pre_monsoon_slope_m_per_year": agg.get("pre_monsoon_slope_m_per_year"),
        "post_monsoon_slope_m_per_year": agg.get("post_monsoon_slope_m_per_year"),
        "pre_monsoon_p_value": agg.get("pre_monsoon_p_value"),
        "post_monsoon_p_value": agg.get("post_monsoon_p_value"),
        "pre_monsoon_exploratory_ols": agg.get("pre_monsoon_exploratory_ols"),
        "post_monsoon_exploratory_ols": agg.get("post_monsoon_exploratory_ols"),
        "pre_monsoon_modified_mann_kendall": agg.get("pre_monsoon_modified_mann_kendall"),
        "post_monsoon_modified_mann_kendall": agg.get("post_monsoon_modified_mann_kendall"),
        "significant_decline_threshold_m_per_year": agg.get("significant_decline_threshold_m_per_year"),
        "threshold_record": agg.get("threshold_record"),
        "threshold_source_publication": agg.get("threshold_source_publication"),
        "threshold_source_url": agg.get("threshold_source_url"),
        "threshold_page_table_reference": agg.get("threshold_page_table_reference"),
        "threshold_hydrogeological_formation": agg.get("threshold_hydrogeological_formation"),
        "threshold_justification": agg.get("threshold_justification"),
        "statistical_limitations": agg.get("statistical_limitations", OLS_AUTOCORRELATION_LIMITATIONS_NOTE),
        "pre_monsoon_annual_coverage": pre_coverage,
        "post_monsoon_annual_coverage": post_coverage,
        "coverage_sufficient": coverage_sufficient,
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
    List all administrative assessment units (blocks/taluks) in the monitoring network,
    including canonical identification and spatial representativeness status.
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
        stn_cnt = int(r.station_count)
        has_spatial_rep = bool(stn_cnt >= 2)
        can_id = build_canonical_id(r.state, r.district, r.block)
        auth_rec = lookup_authoritative_record(r.block, r.district, r.state, canonical_id=can_id)

        units.append({
            "canonical_id": can_id,
            "block": r.block,
            "district": r.district,
            "state": r.state,
            "station_count": stn_cnt,
            "has_representative_spatial_network": has_spatial_rep,
            "spatial_network_status": "Representative (>=2 stations)" if has_spatial_rep else "Insufficient (single-well; unassessed under WMO/CGWB network principles)",
            "assessment_status": "authoritative_record_available" if auth_rec else "unassessed_pending_authoritative_soe",
            "cgwb_recorded_category": auth_rec.statutory_category if auth_rec else None,
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
    district: Optional[str] = None,
    state: Optional[str] = None,
    canonical_id: Optional[str] = None,
    data_quality_screening: Optional[Dict[str, Any]] = None,
    volumetric_resource: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    thresh_rec = lookup_trusted_hydrogeological_threshold(block_name)
    threshold_dict = thresh_rec.to_dict() if thresh_rec else None

    return {
        "assessment_unit": block_name,
        "canonical_id": canonical_id,
        "district": district,
        "state": state,
        "administrative_level": "block_or_taluk",
        "is_official_assessment_unit": True,
        "official_category": "unassessed",
        "category": "unassessed",
        "category_label": "Unassessed",
        "trend_validation_status": "not_evaluated",
        "pre_monsoon_trend": None,
        "post_monsoon_trend": None,
        "pre_monsoon_threshold_sensitivity": "not_evaluated",
        "post_monsoon_threshold_sensitivity": "not_evaluated",
        "overall_trend_sensitivity": "not_evaluated",
        "pre_monsoon_threshold_sensitivity_rationale": reason,
        "post_monsoon_threshold_sensitivity_rationale": reason,
        "overall_trend_sensitivity_rationale": reason,
        "pre_monsoon_sen_slope_ci_95": None,
        "post_monsoon_sen_slope_ci_95": None,
        "trend_validation_reason": reason,
        "stage_of_extraction_pct": stage_of_extraction_pct,
        "soe_source": soe_source,
        "assessment_year": assessment_year,
        "volumetric_resource": volumetric_resource,
        "station_count": station_count,
        "station_ids": station_ids or [],
        "weighting_method": "equal_station_year_weighting",
        "pre_monsoon_years_count": 0,
        "post_monsoon_years_count": 0,
        "pre_monsoon_trend_decline": None,
        "post_monsoon_trend_decline": None,
        "pre_monsoon_slope_m_per_year": None,
        "post_monsoon_slope_m_per_year": None,
        "pre_monsoon_p_value": None,
        "post_monsoon_p_value": None,
        "pre_monsoon_exploratory_ols": None,
        "post_monsoon_exploratory_ols": None,
        "pre_monsoon_modified_mann_kendall": None,
        "post_monsoon_modified_mann_kendall": None,
        "significant_decline_threshold_m_per_year": thresh_rec.threshold_m_per_year if thresh_rec else None,
        "threshold_record": threshold_dict,
        "threshold_source_publication": thresh_rec.source_publication_title if thresh_rec else None,
        "threshold_source_url": thresh_rec.source_url if thresh_rec else None,
        "threshold_page_table_reference": thresh_rec.page_table_reference if thresh_rec else None,
        "threshold_hydrogeological_formation": thresh_rec.hydrogeological_formation if thresh_rec else None,
        "threshold_justification": thresh_rec.justification if thresh_rec else None,
        "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
        "pre_monsoon_annual_coverage": [],
        "post_monsoon_annual_coverage": [],
        "coverage_sufficient": False,
        "coverage_rationale": "Insufficient data to establish decadal trend coverage.",
        "data_quality_screening": data_quality_screening or {
            "total_readings_screened": 0,
            "valid_readings_count": 0,
            "excluded_readings_count": 0,
            "exclusion_breakdown": {},
        },
        "framework": "CGWB GEC-2015 Methodology",
        "statutory_scope": "administrative_assessment_unit",
        "rationale": reason,
        "methodological_disclaimer": (
            "Statutory GEC-2015 categorization applies exclusively to administrative assessment units (taluks/blocks) "
            "using volumetric SOE and verified decadal trends. Individual monitoring wells are exploratory depth "
            "screening points and cannot be classified as official blocks."
        ),
    }
