"""
algorithms/task3_evaluation.py — JalDrishti
Task 3: Evaluate Groundwater Resources, Point-Level Depth Tiers & GEC-2015 Categories

Computes:
  - Exploratory point-level groundwater depth indicator tier:
      Safe Depth (<8m), Semi-Critical Depth (8–<15m), Critical Depth (15–25m), Over-Exploited Depth (>25m)
  - Statutory CGWB GEC-2015 Administrative Assessment-Unit Classification (Safe, Semi-Critical, Critical, Over-Exploited, Unassessed)
    applied strictly at the taluk/block/mandal administrative level based on Stage of Groundwater Extraction (SOE)
    and verified 10-year pre/post-monsoon water level trend evidence.
  - Cadence-aware annual depletion rates using exact timestamps, timespan duration, autocorrelation, and seasonal bias guards.
  - Depletion horizon estimation (suppressed from primary results unless verified drilled-well & hydrogeological data exist).
  - Exploratory Resource Availability Index (RAI) clearly documented as an unvalidated heuristic scoring model.
  - District and state-level resource scorecards.

METHODOLOGICAL SEPARATION (Statutory CGWB/GEC-2015 vs. Point-Level Depth Tiers):
  1. Statutory CGWB GEC-2015 Categorization:
     Evaluates administrative assessment units (taluks/blocks/watersheds) using volumetric
     Stage of Groundwater Extraction (SOE = Total Annual Extraction / Annual Extractable Recharge * 100%)
     and verified long-term (10-year) pre-monsoon and post-monsoon water table decline trends.
     Individual monitoring wells are NEVER classified as officially assessed blocks.
  2. Point-Level Depth Indicator Tier:
     Point-level depth-to-water categories (<8m, 8–15m, 15–25m, >25m) used strictly as operational
     field screening indicators.
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

# Statutory GEC-2015 requires at least 10 years of pre/post-monsoon observation
MIN_DECADAL_TREND_YEARS = 10

# Minimum readings required for cadence-aware regression
MIN_READINGS_TELEMETRY = 24
MIN_READINGS_ANNUAL    = 3

# Display properties for status codes
STATUS_CONFIG = {
    "safe":           {"label": "Safe",           "color": "#27AE60", "priority": 1},
    "semi_critical":  {"label": "Semi-Critical",  "color": "#F39C12", "priority": 2},
    "critical":       {"label": "Critical",        "color": "#E74C3C", "priority": 3},
    "over_exploited": {"label": "Over-Exploited",  "color": "#2C3E50", "priority": 4},
    "unassessed":     {"label": "Unassessed",      "color": "#95A5A6", "priority": 0},
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
    pre_monsoon_trend_decline: Optional[bool] = None,
    post_monsoon_trend_decline: Optional[bool] = None,
    assessment_unit: Optional[str] = None,
    trend_years_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Statutory CGWB GEC-2015 Assessment-Unit Categorization Matrix.

    Evaluates administrative assessment units (Taluk / Block / Mandal / Watershed)
    strictly at the administrative unit level, NEVER on individual monitoring wells.

    Requires:
      1. Valid administrative assessment unit name (e.g., taluk or block).
      2. Valid assessment-unit Stage of Groundwater Extraction (SOE):
         SOE = (Existing Gross Draft for All Uses / Annual Extractable Resource) * 100%
      3. Statutory 10-year pre-monsoon and post-monsoon water level trend evidence.

    Where extraction data, assessment unit, or required 10-year trend evidence is
    missing or insufficient, returns category='unassessed'.

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
    # Guard 1: Must be an administrative assessment unit, not an unmapped well
    if (
        assessment_unit is None
        or not str(assessment_unit).strip()
        or str(assessment_unit).strip().lower() in ("unknown", "none", "unassigned", "")
    ):
        return {
            "category": "unassessed",
            "category_label": "Unassessed",
            "stage_of_extraction_pct": None,
            "pre_monsoon_trend_decline": None,
            "post_monsoon_trend_decline": None,
            "assessment_unit": None,
            "framework": "CGWB GEC-2015 Methodology",
            "statutory_scope": "administrative_assessment_unit",
            "rationale": (
                "Unassessed: Statutory GEC-2015 assessments apply exclusively to administrative assessment "
                "units (taluks/blocks/watersheds). No valid administrative assessment unit was specified. "
                "Individual monitoring wells cannot be classified as official blocks."
            ),
        }

    unit_name = str(assessment_unit).strip()

    # Guard 2: Must have valid volumetric Stage of Groundwater Extraction (SOE)
    if (
        stage_of_extraction_pct is None
        or not isinstance(stage_of_extraction_pct, (int, float))
        or np.isnan(stage_of_extraction_pct)
        or not np.isfinite(stage_of_extraction_pct)
        or float(stage_of_extraction_pct) <= 0.0
    ):
        return {
            "category": "unassessed",
            "category_label": "Unassessed",
            "stage_of_extraction_pct": None,
            "pre_monsoon_trend_decline": pre_monsoon_trend_decline,
            "post_monsoon_trend_decline": post_monsoon_trend_decline,
            "assessment_unit": unit_name,
            "framework": "CGWB GEC-2015 Methodology",
            "statutory_scope": "administrative_assessment_unit",
            "rationale": (
                f"Unassessed for {unit_name}: Valid assessment-unit Stage of Groundwater Extraction (SOE) "
                "data is unavailable. GEC-2015 categorization requires volumetric gross draft and "
                "annual extractable resource accounting."
            ),
        }

    soe = float(stage_of_extraction_pct)

    # Guard 3: Required 10-year decadal trend evidence for statutory assessment
    has_trend_evidence = (
        pre_monsoon_trend_decline is not None
        and post_monsoon_trend_decline is not None
        and (trend_years_count is None or trend_years_count >= MIN_DECADAL_TREND_YEARS)
    )

    # For SOE > 100%, extraction exceeds recharge (Over-Exploited draft pressure)
    if soe > GEC_CRITICAL_STAGE_MAX:
        category = "over_exploited"
        category_label = "Over-Exploited"
        trend_note = (
            f" (Verified with {trend_years_count} years of decadal trends)"
            if trend_years_count and trend_years_count >= MIN_DECADAL_TREND_YEARS
            else " (Note: Statutory 10-year trend series is incomplete or provisional)"
        )
        rationale = f"SOE exceeds 100% ({soe:.1f}%); groundwater draft exceeds annual extractable recharge.{trend_note}"
        return {
            "category": category,
            "category_label": category_label,
            "stage_of_extraction_pct": round(soe, 2),
            "pre_monsoon_trend_decline": bool(pre_monsoon_trend_decline) if pre_monsoon_trend_decline is not None else None,
            "post_monsoon_trend_decline": bool(post_monsoon_trend_decline) if post_monsoon_trend_decline is not None else None,
            "assessment_unit": unit_name,
            "trend_years_count": trend_years_count,
            "framework": "CGWB GEC-2015 Methodology",
            "statutory_scope": "administrative_assessment_unit",
            "rationale": rationale,
        }

    # For SOE <= 100%, statutory categorization between Safe, Semi-Critical, and Critical
    # strictly requires verified 10-year pre/post monsoon trend evidence.
    if not has_trend_evidence:
        return {
            "category": "unassessed",
            "category_label": "Unassessed",
            "stage_of_extraction_pct": round(soe, 2),
            "pre_monsoon_trend_decline": pre_monsoon_trend_decline,
            "post_monsoon_trend_decline": post_monsoon_trend_decline,
            "assessment_unit": unit_name,
            "trend_years_count": trend_years_count,
            "framework": "CGWB GEC-2015 Methodology",
            "statutory_scope": "administrative_assessment_unit",
            "rationale": (
                f"Unassessed for {unit_name}: Insufficient statutory trend evidence. GEC-2015 categorization "
                f"for SOE <= 100% strictly requires verified 10-year pre- and post-monsoon water level trend data. "
                f"Available trend record: {trend_years_count or 0} years (minimum required: {MIN_DECADAL_TREND_YEARS} years)."
            ),
        }

    # Evaluate with verified 10-year trend evidence
    pre_dec = bool(pre_monsoon_trend_decline)
    post_dec = bool(post_monsoon_trend_decline)

    if soe <= GEC_SAFE_STAGE_MAX:
        if pre_dec and post_dec:
            category = "semi_critical"
            category_label = "Semi-Critical"
            rationale = f"SOE <= 70% ({soe:.1f}%) in {unit_name}, but significant decline observed in both pre- and post-monsoon 10-year trends."
        else:
            category = "safe"
            category_label = "Safe"
            rationale = f"SOE <= 70% ({soe:.1f}%) in {unit_name} with no significant dual decadal trend decline."
    elif soe <= GEC_SEMI_CRITICAL_STAGE_MAX:
        category = "semi_critical"
        category_label = "Semi-Critical"
        rationale = f"SOE between 70% and 90% ({soe:.1f}%) in {unit_name}."
    else:  # 90% < SOE <= 100%
        if pre_dec or post_dec:
            category = "critical"
            category_label = "Critical"
            rationale = f"SOE between 90% and 100% ({soe:.1f}%) in {unit_name} with significant decadal trend decline."
        else:
            category = "semi_critical"
            category_label = "Semi-Critical"
            rationale = f"SOE between 90% and 100% ({soe:.1f}%) in {unit_name} without significant decadal trend decline."

    return {
        "category": category,
        "category_label": category_label,
        "stage_of_extraction_pct": round(soe, 2),
        "pre_monsoon_trend_decline": pre_dec,
        "post_monsoon_trend_decline": post_dec,
        "assessment_unit": unit_name,
        "trend_years_count": trend_years_count,
        "framework": "CGWB GEC-2015 Methodology",
        "statutory_scope": "administrative_assessment_unit",
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
# 3. CADENCE-AWARE DEPLETION RATE & STATISTICAL CONFIDENCE
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
    The regression slope directly yields metres per year (m/yr).

    STATISTICAL CONFIDENCE & SEASONAL GUARDS:
      - Sub-daily telemetry exhibits heavy serial autocorrelation and diurnal/pumping cycles.
      - Short duration (<90 days) captures transient weather/pumping drawdown rather than secular depletion.
      - Unadjusted sub-annual telemetry (<365 days) is flagged for seasonal bias and assigned low/medium confidence.
      - Annual historical data requires >=15 years for high confidence, >=7 years for medium confidence.
    """
    if df is None or df.empty or "timestamp" not in df.columns or "water_level_m" not in df.columns:
        return {
            "annual_rate_m": 0.0,
            "confidence": "low",
            "confidence_rationale": "No observation records available.",
            "seasonal_bias": "unassessed",
            "autocorrelation_lag1": 0.0,
            "cadence": "no_data",
            "timespan_years": 0.0,
            "timespan_days": 0.0,
            "reading_count": 0,
            "r_squared": 0.0,
            "trend_direction": "stable",
        }

    clean_df = df.dropna(subset=["timestamp", "water_level_m"]).copy()
    if len(clean_df) < 2:
        return {
            "annual_rate_m": 0.0,
            "confidence": "low",
            "confidence_rationale": "Fewer than 2 observation records.",
            "seasonal_bias": "unassessed",
            "autocorrelation_lag1": 0.0,
            "cadence": "insufficient_data",
            "timespan_years": 0.0,
            "timespan_days": 0.0,
            "reading_count": len(clean_df),
            "r_squared": 0.0,
            "trend_direction": "stable",
        }

    clean_df["timestamp"] = pd.to_datetime(clean_df["timestamp"])
    clean_df = clean_df.sort_values("timestamp").reset_index(drop=True)

    # Detect cadence via median inter-arrival time
    time_deltas = clean_df["timestamp"].diff().dropna()
    median_delta = time_deltas.median() if not time_deltas.empty else pd.Timedelta(days=365)

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

    t0 = clean_df["timestamp"].iloc[0]
    total_seconds = (clean_df["timestamp"] - t0).dt.total_seconds().values
    total_span_days = float(total_seconds[-1] / 86400.0)
    total_span_years = float(total_seconds[-1] / (365.25 * 86400.0))

    if len(clean_df) < min_required or total_span_days < 0.1:
        return {
            "annual_rate_m": 0.0,
            "confidence": "low",
            "confidence_rationale": f"Insufficient sample size ({len(clean_df)} readings) for cadence {cadence}.",
            "seasonal_bias": "insufficient_duration",
            "autocorrelation_lag1": 0.0,
            "cadence": cadence,
            "timespan_years": round(total_span_years, 2),
            "timespan_days": round(total_span_days, 1),
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

    # Compute lag-1 serial autocorrelation
    if len(y) > 2:
        y_dev = y - np.mean(y)
        denom = np.sum(y_dev ** 2)
        autocorr_lag1 = float(np.sum(y_dev[1:] * y_dev[:-1]) / denom) if denom > 1e-8 else 0.0
        autocorr_lag1 = float(max(-1.0, min(1.0, autocorr_lag1)))
    else:
        autocorr_lag1 = 0.0

    # Determine confidence based on observation duration, cadence, autocorrelation, and seasonal completeness
    if cadence == "sub_daily_telemetry":
        if total_span_days < 90.0:
            confidence = "low"
            confidence_rationale = (
                f"Short telemetry duration ({total_span_days:.1f} days) captures transient pumping drawdown / storm infiltration "
                f"rather than secular depletion. High serial autocorrelation (r={autocorr_lag1:.2f}) limits effective sample size."
            )
            seasonal_bias = "unadjusted_sub_seasonal_transient"
        elif total_span_days < 365.0:
            confidence = "low_to_medium"
            confidence_rationale = (
                f"Telemetry duration ({total_span_days:.1f} days) covers an incomplete seasonal cycle (<365 days). "
                "Unadjusted linear slope reflects intra-annual monsoon/dry-season cycle rather than long-term secular depletion."
            )
            seasonal_bias = "partial_annual_cycle"
        else:
            confidence = "high" if (len(clean_df) >= 2000 and r_squared >= 0.3) else "medium"
            confidence_rationale = f"Telemetry record spans {total_span_years:.2f} years, covering complete annual hydrologic cycles."
            seasonal_bias = "complete_annual_cycles"
    elif cadence in ("seasonal_monitoring", "daily_to_weekly"):
        if total_span_years < 3.0:
            confidence = "low"
            confidence_rationale = f"Timespan ({total_span_years:.1f} years) is too brief to distinguish secular trend from climate variability."
            seasonal_bias = "insufficient_multi_year_baseline"
        elif total_span_years < 7.0:
            confidence = "medium"
            confidence_rationale = f"Moderate monitoring baseline ({total_span_years:.1f} years)."
            seasonal_bias = "moderate_baseline"
        else:
            confidence = "high"
            confidence_rationale = f"Decadal monitoring baseline ({total_span_years:.1f} years)."
            seasonal_bias = "long_term_baseline"
    else:  # annual_historical
        if total_span_years < 7.0 or len(clean_df) < 7:
            confidence = "low"
            confidence_rationale = f"Fewer than 7 annual observations ({len(clean_df)} obs across {total_span_years:.1f} years)."
            seasonal_bias = "limited_historical_depth"
        elif total_span_years < 15.0 or len(clean_df) < 15:
            confidence = "medium"
            confidence_rationale = f"Adequate baseline ({len(clean_df)} annual observations across {total_span_years:.1f} years)."
            seasonal_bias = "adequate_historical_depth"
        else:
            confidence = "high"
            confidence_rationale = f"Decadal historical baseline ({len(clean_df)} annual observations across {total_span_years:.1f} years)."
            seasonal_bias = "decadal_historical_depth"

    annual_rate = round(float(slope), 3)

    if annual_rate > 0.05:
        trend_direction = "depleting"
    elif annual_rate < -0.05:
        trend_direction = "recovering"
    else:
        trend_direction = "stable"

    return {
        "annual_rate_m":         annual_rate,
        "confidence":            confidence,
        "confidence_rationale":  confidence_rationale,
        "seasonal_bias":         seasonal_bias,
        "autocorrelation_lag1":  round(autocorr_lag1, 3),
        "cadence":               cadence,
        "timespan_years":        round(total_span_years, 2),
        "timespan_days":         round(total_span_days, 1),
        "reading_count":         len(clean_df),
        "r_squared":             round(r_squared, 3),
        "trend_direction":       trend_direction,
    }


# ═══════════════════════════════════════════════════════════════
# 4. YEARS TO DEPLETION (REQUIRING VERIFIED HYDROGEOLOGY)
# ═══════════════════════════════════════════════════════════════

def _compute_years_to_depletion(
    current_level_m:        Optional[float],
    well_depth_m:           Optional[float],
    annual_depletion:       float,
    well_depth_verified:    bool = False,
    hydrogeology_verified:  bool = False,
) -> Dict[str, Any]:
    """
    Estimate years until the water table reaches verified well/aquifer bottom.

    METHODOLOGICAL REQUIREMENT:
      In DWLR monitoring networks, total drilled depth is frequently estimated, heuristic
      (e.g., 1.35 * max water depth), or absent.
      Extrapolating depletion rates against estimated well depth or fixed thresholds produces
      scientifically unsound and misleading predictions.
      Consequently, years-to-depletion is SUPPRESSED from primary results unless verified
      drilled well depth, casing depth, and hydrogeological boundary data exist.
    """
    if current_level_m is None or not np.isfinite(current_level_m):
        return {
            "years": None,
            "status": "unassessed",
            "is_dependable_prediction": False,
            "remaining_head_m": None,
            "well_depth_source": "none",
            "disclaimer": "Water level observation is missing or invalid.",
        }

    # If recovering or stable, depletion horizon is not applicable
    if annual_depletion <= 0.001:
        return {
            "years": None,
            "status": "stable_or_recovering",
            "is_dependable_prediction": False,
            "remaining_head_m": None,
            "well_depth_source": "none",
            "disclaimer": "Water table is recovering or stable; depletion horizon is not applicable.",
        }

    # Strict scientific guard: Require verified drilled-well and hydrogeological data
    if not well_depth_verified or not hydrogeology_verified or not well_depth_m or float(well_depth_m) <= current_level_m:
        return {
            "years": None,
            "status": "suppressed_unverified_well_depth",
            "is_dependable_prediction": False,
            "remaining_head_m": None,
            "well_depth_source": "unverified_or_missing",
            "disclaimer": (
                "Years-to-depletion is suppressed from primary results: Verified drilled well depth, "
                "casing depth, and hydrogeological aquifer boundary data are unavailable. Extrapolating depletion "
                "against estimated well depth or fixed depth thresholds produces unscientific and misleading predictions."
            ),
        }

    # Compute only when both well depth and hydrogeology are verified
    reference_depth = float(well_depth_m)
    remaining_head = max(0.0, reference_depth - float(current_level_m))
    years = round(remaining_head / annual_depletion, 1) if remaining_head > 0 else 0.0

    return {
        "years": years,
        "status": "verified_hydrogeological_estimate",
        "is_dependable_prediction": True,
        "remaining_head_m": round(remaining_head, 2),
        "well_depth_source": "verified_drilled_well_record",
        "disclaimer": (
            "Verified estimate based on lithologically confirmed drilled well depth and boundary conditions. "
            "Actual depletion trajectory remains subject to future seasonal recharge and local pumping variance."
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
            "pre_monsoon_trend_decline": None,
            "post_monsoon_trend_decline": None,
            "trend_years_count": len(yearly),
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
    pre_decline = None
    pre_years = len(pre_df["year"].unique())
    if pre_years >= 3:
        pre_yearly = pre_df.groupby("year")["water_level_m"].mean().sort_index()
        if len(pre_yearly) >= 3:
            pre_slope = np.polyfit(pre_yearly.index, pre_yearly.values, 1)[0]
            pre_decline = bool(pre_slope > 0.05)  # deepening water table

    # Post-monsoon trend analysis
    post_df = df[df["month"].isin([10, 11])]
    post_decline = None
    post_years = len(post_df["year"].unique())
    if post_years >= 3:
        post_yearly = post_df.groupby("year")["water_level_m"].mean().sort_index()
        if len(post_yearly) >= 3:
            post_slope = np.polyfit(post_yearly.index, post_yearly.values, 1)[0]
            post_decline = bool(post_slope > 0.05)

    return {
        "data":                       yearly.to_dict(orient="records"),
        "long_term_direction":        direction,
        "total_change_m":             round(total_change, 3),
        "years_of_data":              len(yearly),
        "trend_years_count":          len(yearly),
        "pre_monsoon_trend_decline":  pre_decline,
        "post_monsoon_trend_decline": post_decline,
    }


# ═══════════════════════════════════════════════════════════════
# 6. RESOURCE AVAILABILITY INDEX (RAI — UNVALIDATED HEURISTIC)
# ═══════════════════════════════════════════════════════════════

def _compute_resource_availability_index(
    current_level_m:  Optional[float],
    stage_of_dev:     Optional[float],
    annual_depletion: float,
) -> float:
    """
    Exploratory operational heuristic composite index (0 to 100).

    METHODOLOGICAL DISCLAIMER:
      The Resource Availability Index (RAI) is an exploratory operational heuristic
      combining depth tier (0-40), stage of extraction (0-35), and depletion rate (0-25).
      It is NOT an official or validated CGWB metric, nor has it been empirically or
      hydrogeologically validated against physical aquifer yields or statutory criteria.
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
      2. Statutory GEC-2015 administrative assessment-unit categorization (when valid block and 10-yr trends exist)

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

    # 2. Cadence-aware depletion rate with statistical confidence guards
    depletion         = _compute_depletion_rate(df)

    # 3. Years to depletion (suppressed from primary results unless verified)
    well_depth_verified = bool(station_meta.get("well_depth_verified", False))
    hydro_verified = bool(station_meta.get("hydrogeology_verified", False))
    depletion_est     = _compute_years_to_depletion(
        current_level,
        station_meta.get("well_depth_m"),
        depletion["annual_rate_m"],
        well_depth_verified=well_depth_verified,
        hydrogeology_verified=hydro_verified,
    )

    # 4. Long-term trend & decadal pre/post monsoon analysis
    historical_trend  = _compute_historical_trend(df)

    # 5. Statutory GEC-2015 assessment-unit categorization strictly at the administrative block level
    assessment_unit_name = station_meta.get("block") or station_meta.get("district")
    gec_assessment    = classify_gec2015_assessment_unit(
        stage_of_extraction_pct=stage_of_dev,
        pre_monsoon_trend_decline=historical_trend.get("pre_monsoon_trend_decline"),
        post_monsoon_trend_decline=historical_trend.get("post_monsoon_trend_decline"),
        assessment_unit=assessment_unit_name,
        trend_years_count=historical_trend.get("trend_years_count"),
    )

    # 6. Exploratory Resource Availability Index (heuristic)
    rai               = _compute_resource_availability_index(
        current_level, stage_of_dev, depletion["annual_rate_m"]
    )
    rai_meta = {
        "index_name": "Resource Availability Index (RAI)",
        "value": rai,
        "scale": "0_to_100",
        "scientific_status": "exploratory_unvalidated_heuristic",
        "is_statutory_cgwb_index": False,
        "scoring_weights": {"water_level_depth_score": 40, "stage_of_extraction_score": 35, "depletion_rate_score": 25},
        "disclaimer": (
            "The Resource Availability Index (RAI) is an exploratory heuristic scoring model developed "
            "for project screening. It is NOT an official CGWB metric, nor has it been empirically or "
            "hydrogeologically validated against ground truth aquifer yield or statutory sustainability indices."
        ),
    }

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
        "is_station_official_assessment": False,
        "statutory_note": (
            "This station is an individual observation well. GEC-2015 assessments apply to the entire "
            "administrative assessment unit (taluk/block), not to single observation points."
        ),
        "assessment_type":            "dual_screening_and_gec2015" if stage_of_dev is not None else "point_level_depth_tier",
        "classification_note":        (
            f"Point-Level Depth: {depth_indicator['tier_label']} ({current_level:.2f}m bgl). "
            f"Statutory GEC-2015 Assessment for {assessment_unit_name}: {gec_assessment['category_label']} — {gec_assessment['rationale']}"
            if gec_assessment.get("category") != "unassessed" else
            f"Point-Level Depth: {depth_indicator['tier_label']} ({current_level:.2f}m bgl). "
            f"Statutory GEC-2015 Assessment: {gec_assessment['category_label']} ({gec_assessment['rationale']})"
        ),
        "stage_of_development_pct":   stage_of_dev,
        "annual_depletion_rate_m":    depletion["annual_rate_m"],
        "depletion_details":          depletion,
        # Years to depletion is None unless verified hydrogeology exists
        "years_to_depletion":         depletion_est["years"],
        "depletion_estimate":         depletion_est,
        "historical_trend":           historical_trend,
        "resource_availability_index": rai,
        "resource_availability_index_meta": rai_meta,
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
        "rai_scientific_status": "exploratory_unvalidated_heuristic",
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
        "rai_scientific_status": "exploratory_unvalidated_heuristic",
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
        f" Verified depletion horizon: ~{years_to_depletion} years."
        if years_to_depletion is not None
        else " (Depletion horizon unassessed: requires verified drilled well depth)."
    )
    gec_str = (
        f" Assessment unit GEC-2015 category: {gec_assessment['category_label']}."
        if gec_assessment.get("category") != "unassessed"
        else " (Statutory GEC-2015 block category: Unassessed)."
    )
    return (
        f"Station {station_id}: water level {current_level}m ({depth_indicator['tier_label']}).{gec_str} "
        f"Exploratory RAI (heuristic): {rai}/100.{depletion_str}"
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
        "is_station_official_assessment": False,
        "statutory_note":              "This station is an individual observation well. GEC-2015 assessments apply to administrative units.",
        "stage_of_development_pct":    None,
        "annual_depletion_rate_m":     0.0,
        "depletion_details":           {},
        "years_to_depletion":          None,
        "depletion_estimate":          _compute_years_to_depletion(None, None, 0.0),
        "historical_trend":            {"data": [], "long_term_direction": "unknown"},
        "resource_availability_index": 0.0,
        "resource_availability_index_meta": {
            "index_name": "Resource Availability Index (RAI)",
            "value": 0.0,
            "scientific_status": "exploratory_unvalidated_heuristic",
        },
        "alert_required":              False,
        "summary":                     reason,
    }
