"""
algorithms/task3_evaluation.py — JalDrishti
Task 3: Evaluate Groundwater Resources, Point-Level Depth Tiers & GEC-2015 Categories

Computes:
  - Exploratory point-level groundwater depth indicator tier:
      Safe Depth (<8m), Semi-Critical Depth (8–<15m), Critical Depth (15–25m), Over-Exploited Depth (>25m)
  - Statutory CGWB GEC-2015 Assessment-Unit Classification (Safe, Semi-Critical, Critical, Over-Exploited)
    based on Stage of Groundwater Extraction (SOE) and decadal pre/post-monsoon water level trends.
  - Cadence-aware annual depletion rates using exact timestamps (supports annual CGWB historical & 15-min DWLR telemetry)
  - Illustrative years to depletion per station (with explicit scientific disclaimers on unmeasured well depths)
  - District and state-level resource scorecards
  - Resource Availability Index (RAI)

METHODOLOGICAL SEPARATION (Statutory CGWB/GEC-2015 vs. Point-Level Depth Tiers):
  1. Statutory CGWB GEC-2015 Categorization:
     Evaluates administrative assessment units (taluks/blocks/watersheds) using volumetric
     Stage of Groundwater Extraction (SOE = Total Annual Extraction / Annual Extractable Recharge * 100%)
     and long-term (10-year) pre-monsoon and post-monsoon water table decline trends.
  2. Point-Level Depth Indicator Tier:
     Point-level depth-to-water categories (<8m, 8–15m, 15–25m, >25m) used strictly as operational
     field screening indicators. Point depths must NEVER be merged into GEC-2015 categories or labeled
     as official block assessments.
"""

import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import numpy as np
import pandas as pd

log = logging.getLogger("jaldrishti.task3")

# ── Operational Depth Indicator Thresholds (metres below ground level - bgl) ──
SAFE_DEPTH_MAX          =  8.0
SEMI_CRITICAL_DEPTH_MAX = 15.0
CRITICAL_DEPTH_MAX      = 25.0
# > 25.0m = Over-Exploited Depth

# ── Statutory CGWB GEC-2015 Stage of Extraction (SOE) Thresholds (%) ───────────
GEC_SAFE_STAGE_MAX          =  70.0
GEC_SEMI_CRITICAL_STAGE_MAX =  90.0
GEC_CRITICAL_STAGE_MAX      = 100.0
# > 100.0% = Over-Exploited Stage of Extraction

# Minimum readings required for cadence-aware regression
MIN_READINGS_TELEMETRY = 24
MIN_READINGS_ANNUAL    = 3

# Display properties for status codes
STATUS_CONFIG = {
    "safe":           {"label": "Safe",           "color": "#27AE60", "priority": 1},
    "semi_critical":  {"label": "Semi-Critical",  "color": "#F39C12", "priority": 2},
    "critical":       {"label": "Critical",        "color": "#E74C3C", "priority": 3},
    "over_exploited": {"label": "Over-Exploited",  "color": "#2C3E50", "priority": 4},
    "unknown":        {"label": "Unknown",          "color": "#95A5A6", "priority": 0},
}

# Aliases for backwards compatibility with tests and callers
SAFE_MAX          = SAFE_DEPTH_MAX
SEMI_CRITICAL_MAX = SEMI_CRITICAL_DEPTH_MAX
CRITICAL_MAX      = CRITICAL_DEPTH_MAX
SAFE_STAGE_MAX          = GEC_SAFE_STAGE_MAX
SEMI_CRITICAL_STAGE_MAX = GEC_SEMI_CRITICAL_STAGE_MAX
CRITICAL_STAGE_MAX      = GEC_CRITICAL_STAGE_MAX


# ═══════════════════════════════════════════════════════════════
# 1. POINT-LEVEL DEPTH INDICATOR CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

def classify_depth_tier(current_level_m: Optional[float]) -> Dict[str, Any]:
    """
    Classify point-level groundwater observation into operational depth indicator tiers.

    Thresholds (depth to water table below ground level):
      - Safe Depth:           < 8.0 m bgl
      - Semi-Critical Depth:  8.0 m to < 15.0 m bgl
      - Critical Depth:       15.0 m to <= 25.0 m bgl
      - Over-Exploited Depth: > 25.0 m bgl

    Returns:
        Structured dict with tier, label, thresholds, and methodological disclaimer.
    """
    if (
        current_level_m is None
        or not isinstance(current_level_m, (int, float))
        or np.isnan(current_level_m)
        or not np.isfinite(current_level_m)
    ):
        return {
            "tier": "unknown",
            "tier_label": "Unknown Depth",
            "current_level_m": None,
            "thresholds": {
                "safe_max": SAFE_DEPTH_MAX,
                "semi_critical_max": SEMI_CRITICAL_DEPTH_MAX,
                "critical_max": CRITICAL_DEPTH_MAX,
            },
            "indicator_type": "point_level_depth_screening",
            "note": "Invalid or missing water level observation.",
        }

    lvl = float(current_level_m)

    if lvl < SAFE_DEPTH_MAX:
        tier = "safe"
        tier_label = "Safe Depth (<8m)"
    elif lvl < SEMI_CRITICAL_DEPTH_MAX:
        tier = "semi_critical"
        tier_label = "Semi-Critical Depth (8–<15m)"
    elif lvl <= CRITICAL_DEPTH_MAX:
        tier = "critical"
        tier_label = "Critical Depth (15–25m)"
    else:
        tier = "over_exploited"
        tier_label = "Over-Exploited Depth (>25m)"

    return {
        "tier": tier,
        "tier_label": tier_label,
        "current_level_m": round(lvl, 3),
        "thresholds": {
            "safe_max": SAFE_DEPTH_MAX,
            "semi_critical_max": SEMI_CRITICAL_DEPTH_MAX,
            "critical_max": CRITICAL_DEPTH_MAX,
        },
        "indicator_type": "point_level_depth_screening",
        "note": (
            "Point-level exploratory depth indicator. Does NOT substitute for statutory "
            "CGWB/GEC-2015 assessment-unit categorization."
        ),
    }


# ═══════════════════════════════════════════════════════════════
# 2. STATUTORY GEC-2015 ASSESSMENT-UNIT CATEGORIZATION
# ═══════════════════════════════════════════════════════════════

def classify_gec2015_assessment_unit(
    stage_of_extraction_pct: Optional[float],
    pre_monsoon_trend_decline: bool = False,
    post_monsoon_trend_decline: bool = False,
    assessment_unit: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Statutory CGWB GEC-2015 Assessment-Unit Categorization Matrix.

    Evaluates administrative assessment units (Taluk / Block / Mandal / Watershed)
    based on:
      - Stage of Groundwater Extraction (SOE) = (Existing Gross Draft / Annual Extractable Resource) * 100%
      - Long-term (10-year) pre-monsoon and post-monsoon water level trends.

    Decision Rules (CGWB GEC-2015):
      1. SOE <= 70%:
         - If both pre- and post-monsoon trends show significant decline: Semi-Critical
         - Otherwise: Safe
      2. 70% < SOE <= 90%:
         - Semi-Critical
      3. 90% < SOE <= 100%:
         - If either pre- or post-monsoon trend shows significant decline: Critical
         - If neither trend shows decline: Semi-Critical
      4. SOE > 100%:
         - Over-Exploited

    Returns:
        Structured dict with category, label, SOE, trend flags, and statutory rationale.
    """
    if (
        stage_of_extraction_pct is None
        or not isinstance(stage_of_extraction_pct, (int, float))
        or np.isnan(stage_of_extraction_pct)
        or not np.isfinite(stage_of_extraction_pct)
    ):
        return {
            "category": "unassessed",
            "category_label": "Unassessed",
            "stage_of_extraction_pct": None,
            "pre_monsoon_trend_decline": pre_monsoon_trend_decline,
            "post_monsoon_trend_decline": post_monsoon_trend_decline,
            "assessment_unit": assessment_unit,
            "framework": "CGWB GEC-2015 Methodology",
            "rationale": "Assessment-unit stage of groundwater extraction (SOE) data not provided.",
        }

    soe = float(stage_of_extraction_pct)

    if soe <= GEC_SAFE_STAGE_MAX:
        if pre_monsoon_trend_decline and post_monsoon_trend_decline:
            category = "semi_critical"
            category_label = "Semi-Critical"
            rationale = "SOE <= 70% but significant decline observed in both pre- and post-monsoon decadal trends."
        else:
            category = "safe"
            category_label = "Safe"
            rationale = "SOE <= 70% with no significant dual decadal trend decline."
    elif soe <= GEC_SEMI_CRITICAL_STAGE_MAX:
        category = "semi_critical"
        category_label = "Semi-Critical"
        rationale = "SOE between 70% and 90%."
    elif soe <= GEC_CRITICAL_STAGE_MAX:
        if pre_monsoon_trend_decline or post_monsoon_trend_decline:
            category = "critical"
            category_label = "Critical"
            rationale = "SOE between 90% and 100% with significant decadal trend decline."
        else:
            category = "semi_critical"
            category_label = "Semi-Critical"
            rationale = "SOE between 90% and 100% without significant decadal trend decline."
    else:
        category = "over_exploited"
        category_label = "Over-Exploited"
        rationale = f"SOE exceeds 100% ({soe:.1f}%); groundwater draft exceeds annual extractable recharge."

    return {
        "category": category,
        "category_label": category_label,
        "stage_of_extraction_pct": round(soe, 2),
        "pre_monsoon_trend_decline": bool(pre_monsoon_trend_decline),
        "post_monsoon_trend_decline": bool(post_monsoon_trend_decline),
        "assessment_unit": assessment_unit,
        "framework": "CGWB GEC-2015 Methodology",
        "rationale": rationale,
    }


def _classify_status(
    current_level_m: Optional[float],
    stage_of_dev: Optional[float] = None,
) -> str:
    """
    Backward-compatible screening classification.
    Returns primary depth-tier status ('safe', 'semi_critical', 'critical', 'over_exploited', 'unknown').
    Note: For separate statutory reporting, use classify_depth_tier() and classify_gec2015_assessment_unit().
    """
    depth_res = classify_depth_tier(current_level_m)
    return depth_res["tier"]


# ═══════════════════════════════════════════════════════════════
# 3. CADENCE-AWARE DEPLETION RATE CALCULATION
# ═══════════════════════════════════════════════════════════════

def _compute_depletion_rate(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute annual depletion rate using linear regression on actual timestamps.
    Automatically detects observation cadence:
      - 'annual_historical': Annual CGWB ground observation records (~1 obs/year)
      - 'seasonal_monitoring': Seasonal CGWB pre/post monsoon records (2–4 obs/year)
      - 'sub_daily_telemetry': Automated DWLR hourly/15-minute telemetry

    Converts timestamps directly into elapsed time in fractional years:
      t_years = (timestamp - timestamp_0) / (365.25 * 86400)
    The regression slope (polyfit) directly yields metres per year (m/yr).
    NO arbitrary '365 * 96' multiplier is applied to annual data.

    Positive rate = water level deepening (depletion).
    Negative rate = water level rising (recovery).
    """
    if df is None or df.empty or "timestamp" not in df.columns or "water_level_m" not in df.columns:
        return {
            "annual_rate_m": 0.0,
            "confidence": "low",
            "cadence": "no_data",
            "timespan_years": 0.0,
            "reading_count": 0,
            "r_squared": 0.0,
            "trend_direction": "stable",
        }

    clean_df = df.dropna(subset=["timestamp", "water_level_m"]).copy()
    if len(clean_df) < 2:
        return {
            "annual_rate_m": 0.0,
            "confidence": "low",
            "cadence": "insufficient_data",
            "timespan_years": 0.0,
            "reading_count": len(clean_df),
            "r_squared": 0.0,
            "trend_direction": "stable",
        }

    clean_df["timestamp"] = pd.to_datetime(clean_df["timestamp"])
    clean_df = clean_df.sort_values("timestamp").reset_index(drop=True)

    # Detect cadence via median inter-arrival time
    time_deltas = clean_df["timestamp"].diff().dropna()
    if time_deltas.empty:
        median_delta = pd.Timedelta(days=365)
    else:
        median_delta = time_deltas.median()

    if median_delta < pd.Timedelta(hours=2):
        cadence = "sub_daily_telemetry"
        min_required = MIN_READINGS_TELEMETRY
    elif median_delta < pd.Timedelta(days=14):
        cadence = "daily_to_weekly"
        min_required = 14
    elif median_delta < pd.Timedelta(days=150):
        cadence = "seasonal_monitoring"
        min_required = 4
    else:
        cadence = "annual_historical"
        min_required = MIN_READINGS_ANNUAL

    if len(clean_df) < min_required:
        return {
            "annual_rate_m": 0.0,
            "confidence": "low",
            "cadence": cadence,
            "timespan_years": 0.0,
            "reading_count": len(clean_df),
            "r_squared": 0.0,
            "trend_direction": "stable",
        }

    # Elapsed time in fractional years
    t0 = clean_df["timestamp"].iloc[0]
    total_seconds = (clean_df["timestamp"] - t0).dt.total_seconds().values
    total_span_years = float(total_seconds[-1] / (365.25 * 86400.0))

    if total_span_years < 1e-4:
        # Avoid division by zero on identical timestamps
        return {
            "annual_rate_m": 0.0,
            "confidence": "low",
            "cadence": cadence,
            "timespan_years": 0.0,
            "reading_count": len(clean_df),
            "r_squared": 0.0,
            "trend_direction": "stable",
        }

    t_years = total_seconds / (365.25 * 86400.0)
    y = clean_df["water_level_m"].values.astype(float)

    # Fit linear slope: dy/dt_years directly gives m/year
    slope, intercept = np.polyfit(t_years, y, 1)
    y_pred = slope * t_years + intercept

    # Compute R-squared
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    ss_res = np.sum((y - y_pred) ** 2)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-8 else 0.0
    r_squared = float(max(0.0, min(1.0, r_squared)))

    # Determine confidence based on observation history and fit quality
    if cadence == "annual_historical":
        confidence = "high" if (len(clean_df) >= 15 and total_span_years >= 15) else "medium" if len(clean_df) >= 7 else "low"
    else:
        confidence = "high" if len(clean_df) >= 500 else "medium" if len(clean_df) >= 100 else "low"

    annual_rate = round(float(slope), 3)

    if annual_rate > 0.05:
        trend_direction = "depleting"
    elif annual_rate < -0.05:
        trend_direction = "recovering"
    else:
        trend_direction = "stable"

    return {
        "annual_rate_m":   annual_rate,
        "confidence":      confidence,
        "cadence":         cadence,
        "timespan_years":  round(total_span_years, 2),
        "reading_count":   len(clean_df),
        "r_squared":       round(r_squared, 3),
        "trend_direction": trend_direction,
    }


# ═══════════════════════════════════════════════════════════════
# 4. YEARS TO DEPLETION (WITH SCIENTIFIC DISCLAIMER)
# ═══════════════════════════════════════════════════════════════

def _compute_years_to_depletion(
    current_level_m:   Optional[float],
    well_depth_m:      Optional[float],
    annual_depletion:  float,
) -> Dict[str, Any]:
    """
    Estimate years until the water table reaches estimated aquifer/well threshold.

    METHODOLOGICAL NOTE:
      In many DWLR monitoring stations, total drilled depth is estimated or heuristic
      (e.g., 1.35 * max observed water depth) rather than lithologically measured.
      Consequently, depletion horizons are strictly illustrative screening projections
      rather than engineering dry-well predictions.
    """
    if current_level_m is None or not np.isfinite(current_level_m):
        return {
            "years": None,
            "status": "unassessed",
            "is_illustrative": True,
            "remaining_head_m": None,
            "well_depth_source": "none",
            "disclaimer": "Water level observation is missing or invalid.",
        }

    if annual_depletion <= 0.001:
        return {
            "years": None,
            "status": "stable_or_recovering",
            "is_illustrative": True,
            "remaining_head_m": None,
            "well_depth_source": "none",
            "disclaimer": "Water table is recovering or stable; depletion horizon not applicable.",
        }

    # Determine reference baseline depth
    if well_depth_m and np.isfinite(well_depth_m) and float(well_depth_m) > current_level_m:
        reference_depth = float(well_depth_m)
        depth_source = "metadata_record_or_heuristic"
    else:
        # Conservative CGWB threshold for severe depression
        reference_depth = max(CRITICAL_DEPTH_MAX, current_level_m + 10.0)
        depth_source = "threshold_heuristic"

    remaining_head = max(0.0, reference_depth - float(current_level_m))
    if remaining_head <= 0.0:
        years = 0.0
    else:
        years = round(remaining_head / annual_depletion, 1)

    return {
        "years": years,
        "status": "illustrative_estimate",
        "is_illustrative": True,
        "remaining_head_m": round(remaining_head, 2),
        "well_depth_source": depth_source,
        "disclaimer": (
            "Illustrative estimate only. Aquifer bottom / well depth is based on heuristic "
            "or unverified metadata. Actual depletion depends on seasonal monsoon recharge, "
            "local pumping variance, and hydrogeologic boundary conditions."
        ),
    }


# ═══════════════════════════════════════════════════════════════
# 5. HISTORICAL TREND (PRE/POST MONSOON DECADAL ANALYSIS)
# ═══════════════════════════════════════════════════════════════

def _compute_historical_trend(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyse long-term trends and pre/post monsoon decadal patterns.
    Pre-monsoon: Months 4–5 (April–May)
    Post-monsoon: Months 10–11 (October–November)
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["year"]      = df["timestamp"].dt.year
    df["month"]     = df["timestamp"].dt.month

    yearly = (
        df.groupby("year")["water_level_m"]
        .mean()
        .round(3)
        .reset_index()
        .rename(columns={"water_level_m": "avg_level_m"})
    )

    if len(yearly) < 2:
        return {
            "data": yearly.to_dict(orient="records"),
            "long_term_direction": "insufficient_data",
            "pre_monsoon_trend_decline": False,
            "post_monsoon_trend_decline": False,
        }

    # Overall trend direction
    first_year_avg = float(yearly["avg_level_m"].iloc[0])
    last_year_avg  = float(yearly["avg_level_m"].iloc[-1])
    total_change   = last_year_avg - first_year_avg

    if total_change > 1.0:
        direction = "long_term_depletion"
    elif total_change < -1.0:
        direction = "long_term_recovery"
    else:
        direction = "long_term_stable"

    # Pre-monsoon trend analysis
    pre_df = df[df["month"].isin([4, 5])]
    pre_decline = False
    if len(pre_df["year"].unique()) >= 3:
        pre_yearly = pre_df.groupby("year")["water_level_m"].mean().sort_index()
        if len(pre_yearly) >= 3:
            pre_slope = np.polyfit(pre_yearly.index, pre_yearly.values, 1)[0]
            pre_decline = bool(pre_slope > 0.05)  # deepening water table

    # Post-monsoon trend analysis
    post_df = df[df["month"].isin([10, 11])]
    post_decline = False
    if len(post_df["year"].unique()) >= 3:
        post_yearly = post_df.groupby("year")["water_level_m"].mean().sort_index()
        if len(post_yearly) >= 3:
            post_slope = np.polyfit(post_yearly.index, post_yearly.values, 1)[0]
            post_decline = bool(post_slope > 0.05)

    return {
        "data":                       yearly.to_dict(orient="records"),
        "long_term_direction":        direction,
        "total_change_m":             round(total_change, 3),
        "years_of_data":              len(yearly),
        "pre_monsoon_trend_decline":  pre_decline,
        "post_monsoon_trend_decline": post_decline,
    }


# ═══════════════════════════════════════════════════════════════
# 6. RESOURCE AVAILABILITY INDEX (RAI)
# ═══════════════════════════════════════════════════════════════

def _compute_resource_availability_index(
    current_level_m:  Optional[float],
    stage_of_dev:     Optional[float],
    annual_depletion: float,
) -> float:
    """
    Composite index from 0 (severely depleted) to 100 (abundant/sustainable).
    Combines: current depth tier, stage of extraction (if available), and depletion rate.
    """
    if current_level_m is None or not np.isfinite(current_level_m):
        return 0.0

    # Component 1: Level score (0–40 points)
    if current_level_m <= SAFE_DEPTH_MAX:
        level_score = 40.0
    elif current_level_m <= SEMI_CRITICAL_DEPTH_MAX:
        level_score = 40 * (1 - (current_level_m - SAFE_DEPTH_MAX) / (SEMI_CRITICAL_DEPTH_MAX - SAFE_DEPTH_MAX)) * 0.7 + 12
    elif current_level_m <= CRITICAL_DEPTH_MAX:
        level_score = 12 * (1 - (current_level_m - SEMI_CRITICAL_DEPTH_MAX) / (CRITICAL_DEPTH_MAX - SEMI_CRITICAL_DEPTH_MAX)) * 0.5 + 2
    else:
        level_score = max(0, 2 - (current_level_m - CRITICAL_DEPTH_MAX) * 0.1)

    # Component 2: Stage of extraction score (0–35 points)
    if stage_of_dev is None or not np.isfinite(stage_of_dev):
        stage_score = 17.5  # Neutral default when volumetric SOE is unassessed
    elif stage_of_dev <= GEC_SAFE_STAGE_MAX:
        stage_score = 35.0
    elif stage_of_dev <= GEC_SEMI_CRITICAL_STAGE_MAX:
        stage_score = 35 * (1 - (stage_of_dev - GEC_SAFE_STAGE_MAX) / 20) * 0.5 + 5
    elif stage_of_dev <= GEC_CRITICAL_STAGE_MAX:
        stage_score = 5 * (1 - (stage_of_dev - GEC_SEMI_CRITICAL_STAGE_MAX) / 10) * 0.5
    else:
        stage_score = 0.0

    # Component 3: Depletion rate score (0–25 points)
    if annual_depletion <= 0:
        depletion_score = 25.0  # recovering
    elif annual_depletion < 0.5:
        depletion_score = 25 * (1 - annual_depletion / 0.5) * 0.7 + 7.5
    elif annual_depletion < 1.0:
        depletion_score = 7.5 * (1 - (annual_depletion - 0.5) / 0.5)
    else:
        depletion_score = 0.0

    rai = round(level_score + stage_score + depletion_score, 1)
    return min(100.0, max(0.0, rai))


# ═══════════════════════════════════════════════════════════════
# 7. MAIN EVALUATION FUNCTION
# ═══════════════════════════════════════════════════════════════

def evaluate_station(
    readings_df:    pd.DataFrame,
    station_meta:   dict,
    stage_of_dev:   Optional[float] = None,
) -> dict:
    """
    Comprehensive Task 3 evaluation for a single station.
    Maintains strict methodological separation between:
      1. Point-level depth indicator tier (safe, semi_critical, critical, over_exploited)
      2. Statutory GEC-2015 assessment-unit categorization (when SOE is supplied)

    Args:
        readings_df   : DWLR readings with timestamp and water_level_m
        station_meta  : Dict with station_id, state, district, block, well_depth_m, aquifer_type
        stage_of_dev  : Stage of groundwater extraction (%) from CGWB block assessment

    Returns dict containing both depth_indicator and gec_assessment, plus backward-compatible fields.
    """
    station_id = station_meta.get("station_id", "unknown")
    df = readings_df[readings_df["station_id"] == station_id].copy() if not readings_df.empty and "station_id" in readings_df.columns else readings_df.copy()

    if df.empty or "water_level_m" not in df.columns or df["water_level_m"].dropna().empty:
        return _empty_result(station_id, "No valid readings available")

    df = df.dropna(subset=["water_level_m"]).sort_values("timestamp").reset_index(drop=True)

    current_level     = float(df["water_level_m"].iloc[-1])
    current_time      = pd.Timestamp(df["timestamp"].iloc[-1])

    # 1. Point-level depth tier classification
    depth_indicator   = classify_depth_tier(current_level)
    primary_status    = depth_indicator["tier"]

    # 2. Cadence-aware depletion rate
    depletion         = _compute_depletion_rate(df)

    # 3. Illustrative years to depletion
    depletion_est     = _compute_years_to_depletion(
        current_level,
        station_meta.get("well_depth_m"),
        depletion["annual_rate_m"],
    )

    # 4. Long-term trend & decadal pre/post monsoon analysis
    historical_trend  = _compute_historical_trend(df)

    # 5. Statutory GEC-2015 assessment-unit categorization
    gec_assessment    = classify_gec2015_assessment_unit(
        stage_of_extraction_pct=stage_of_dev,
        pre_monsoon_trend_decline=historical_trend.get("pre_monsoon_trend_decline", False),
        post_monsoon_trend_decline=historical_trend.get("post_monsoon_trend_decline", False),
        assessment_unit=station_meta.get("block") or station_meta.get("district"),
    )

    # 6. Composite Resource Availability Index
    rai               = _compute_resource_availability_index(
        current_level, stage_of_dev, depletion["annual_rate_m"]
    )

    alert_required    = primary_status in ("critical", "over_exploited") or (
        gec_assessment.get("category") in ("critical", "over_exploited")
    )

    result = {
        "station_id":                 station_id,
        "state":                      station_meta.get("state", ""),
        "district":                   station_meta.get("district", ""),
        "block":                      station_meta.get("block", ""),
        "aquifer_type":               station_meta.get("aquifer_type", "Unknown"),
        "current_level_m":            round(current_level, 3),
        "as_of":                      current_time.isoformat(),
        # Backwards compatibility for existing UI
        "status":                     primary_status,
        "status_label":               STATUS_CONFIG[primary_status]["label"],
        "status_color":               STATUS_CONFIG[primary_status]["color"],
        # Distinct scientific indicators
        "depth_indicator":            depth_indicator,
        "gec_assessment":             gec_assessment,
        "assessment_type":            "dual_screening_and_gec2015" if stage_of_dev is not None else "point_level_depth_tier",
        "classification_note":        (
            f"Point-Level Depth: {depth_indicator['tier_label']} ({current_level:.2f}m bgl). "
            f"Statutory GEC-2015 Assessment: {gec_assessment['category_label']} "
            f"({gec_assessment['stage_of_extraction_pct']}% SOE) — {gec_assessment['rationale']}"
            if stage_of_dev is not None else
            f"Point-Level Depth: {depth_indicator['tier_label']} ({current_level:.2f}m bgl). "
            "Statutory GEC-2015 block assessment requires assessment-unit volumetric extraction accounting."
        ),
        "stage_of_development_pct":   stage_of_dev,
        "annual_depletion_rate_m":    depletion["annual_rate_m"],
        "depletion_details":          depletion,
        "years_to_depletion":         depletion_est["years"],
        "depletion_estimate":         depletion_est,
        "historical_trend":           historical_trend,
        "resource_availability_index": rai,
        "alert_required":             alert_required,
        "summary":                    _build_summary(
            station_id, current_level, depth_indicator, gec_assessment, depletion_est["years"], rai
        ),
    }

    log.info(
        f"Task3 [{station_id}] level={current_level}m "
        f"depth_tier={primary_status} gec={gec_assessment['category']} "
        f"depletion_rate={depletion['annual_rate_m']}m/yr alert={alert_required}"
    )
    return result


# ═══════════════════════════════════════════════════════════════
# 8. SCORECARDS & HELPERS
# ═══════════════════════════════════════════════════════════════

def generate_district_scorecard(station_results: list[dict]) -> dict:
    """Aggregate station-level Task 3 results into a district scorecard."""
    if not station_results:
        return {"error": "No station data"}

    df = pd.DataFrame(station_results)

    status_counts = df["status"].value_counts().to_dict()
    avg_rai       = round(float(df["resource_availability_index"].mean()), 1)
    avg_level     = round(float(df["current_level_m"].dropna().mean()), 3)
    alert_count   = int(df["alert_required"].sum())

    worst_status  = df.loc[df["status"].map(
        {k: v["priority"] for k, v in STATUS_CONFIG.items()}
    ).fillna(0).idxmax(), "status"]

    df_ranked = df.nsmallest(5, "resource_availability_index")[
        ["station_id", "current_level_m", "status", "resource_availability_index"]
    ]

    return {
        "total_stations":        len(df),
        "district_status":       worst_status,
        "avg_resource_index":    avg_rai,
        "avg_water_level_m":     avg_level,
        "status_breakdown":      status_counts,
        "alerts_active":         alert_count,
        "most_stressed_stations": df_ranked.to_dict(orient="records"),
    }


def generate_state_scorecard(district_scorecards: dict) -> dict:
    """Aggregate district scorecards into a state-level summary."""
    if not district_scorecards:
        return {"error": "No district data"}

    all_statuses   = []
    all_rai        = []
    total_alerts   = 0
    total_stations = 0

    for district, card in district_scorecards.items():
        all_statuses.append(card.get("district_status", "unknown"))
        all_rai.append(card.get("avg_resource_index", 50))
        total_alerts   += card.get("alerts_active", 0)
        total_stations += card.get("total_stations", 0)

    status_counts = pd.Series(all_statuses).value_counts().to_dict()

    return {
        "total_districts":   len(district_scorecards),
        "total_stations":    total_stations,
        "avg_resource_index": round(float(np.mean(all_rai)), 1),
        "total_alerts":      total_alerts,
        "status_breakdown":  status_counts,
        "district_ranking":  sorted(
            [{"district": d, "rai": district_scorecards[d].get("avg_resource_index", 0)}
             for d in district_scorecards],
            key=lambda x: x["rai"]
        ),
    }


def evaluate_all_stations(
    readings_df:  pd.DataFrame,
    stations_df:  pd.DataFrame,
    stage_map:    Optional[dict] = None,
) -> list[dict]:
    """Run Task 3 evaluation for all stations."""
    log.info(f"Task 3 batch evaluation — {len(stations_df)} stations")
    results = []
    for _, station in stations_df.iterrows():
        sid   = station.get("station_id")
        stage = (stage_map or {}).get(sid)
        try:
            result = evaluate_station(readings_df, station.to_dict(), stage)
            results.append(result)
        except Exception as e:
            log.error(f"Task3 failed for {sid}: {e}")
            results.append(_empty_result(sid, str(e)))
    return results


def _build_summary(
    station_id:        str,
    current_level:     float,
    depth_indicator:   Dict[str, Any],
    gec_assessment:    Dict[str, Any],
    years_to_depletion: Optional[float],
    rai:               float,
) -> str:
    depletion_str = (
        f" Illustrative depletion horizon: ~{years_to_depletion} years."
        if years_to_depletion is not None and years_to_depletion < 50
        else ""
    )
    gec_str = (
        f" Assessment unit GEC-2015 category: {gec_assessment['category_label']}."
        if gec_assessment.get("category") != "unassessed"
        else ""
    )
    return (
        f"Station {station_id}: water level {current_level}m ({depth_indicator['tier_label']}).{gec_str} "
        f"Resource Availability Index: {rai}/100.{depletion_str}"
    )


def _empty_result(station_id: str, reason: str) -> dict:
    return {
        "station_id":                  station_id,
        "state":                       "",
        "district":                    "",
        "block":                       "",
        "aquifer_type":                "Unknown",
        "current_level_m":             None,
        "as_of":                       None,
        "status":                      "unknown",
        "status_label":                "Unknown",
        "status_color":                "#95A5A6",
        "depth_indicator":             classify_depth_tier(None),
        "gec_assessment":              classify_gec2015_assessment_unit(None),
        "stage_of_development_pct":    None,
        "annual_depletion_rate_m":     0.0,
        "depletion_details":           {},
        "years_to_depletion":          None,
        "depletion_estimate":          _compute_years_to_depletion(None, None, 0.0),
        "historical_trend":            {"data": [], "long_term_direction": "unknown"},
        "resource_availability_index": 0.0,
        "alert_required":              False,
        "summary":                     reason,
    }
