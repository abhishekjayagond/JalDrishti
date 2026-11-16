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
     Stage of Groundwater Extraction (SOE = Existing Gross Groundwater Draft for All Uses / Annual Extractable Groundwater Resource * 100%)
     and verified long-term (10-year) pre-monsoon and post-monsoon water table decline trends.
     Individual monitoring wells are NEVER classified as officially assessed blocks.
  2. Point-Level Depth Indicator Tier:
     Point-level depth-to-water categories (<8m, 8–15m, 15–25m, >25m) used strictly as operational
     field screening indicators.
"""

import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from scipy import stats

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
DEFAULT_MIN_STATIONS_PER_YEAR = 2


@dataclass(frozen=True)
class HydrogeologicalThresholdRecord:
    """
    Authoritative Server-Side Hydrogeological Threshold Provenance Record.

    Statutory Basis:
      CGWB Ground Water Estimation Committee (GEC-2015) guidance defines significant
      groundwater level decline as approximately 10–20 cm/year (0.10–0.20 m/year)
      depending on local hydrogeology (aquifer storativity / specific yield).
      Every block threshold must be independently justified by published CGWB
      district groundwater reports with verifiable citations.
    """
    block: str
    state: str
    district: str
    threshold_m_per_year: float
    source_publication_title: str
    source_url: str
    page_table_reference: str
    hydrogeological_formation: str
    justification: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Trusted Server-Side Hydrogeological Threshold Registry
# Strictly verified against official published CGWB Ground Water Information Booklets.
# All unsupported blocks without independent justification are excluded.
# Statutory Basis:
#   CGWB GEC-2015 guidance specifies 10–20 cm/year (0.10–0.20 m/year) as a general
#   benchmark range. However, published CGWB district groundwater booklets do not
#   statutorily establish specific decline thresholds for individual blocks.
#   Per scientific integrity standards, no block threshold is assumed without explicit
#   independent documentation. Unsupported blocks evaluate trend validation as 'not_evaluated'.
TRUSTED_HYDROGEOLOGICAL_THRESHOLDS: Dict[str, HydrogeologicalThresholdRecord] = {}

# Derived mapping for backward compatibility with threshold lookups
DOCUMENTED_ASSESSMENT_UNIT_THRESHOLDS: Dict[str, float] = {}


def register_trusted_hydrogeological_threshold(record: HydrogeologicalThresholdRecord) -> None:
    """Register or update an independently verified hydrogeological threshold record."""
    norm_key = str(record.block).strip().lower()
    TRUSTED_HYDROGEOLOGICAL_THRESHOLDS[norm_key] = record
    DOCUMENTED_ASSESSMENT_UNIT_THRESHOLDS[norm_key] = record.threshold_m_per_year


def clear_trusted_hydrogeological_thresholds() -> None:
    """Clear all registered hydrogeological threshold records (for test isolation/reset)."""
    TRUSTED_HYDROGEOLOGICAL_THRESHOLDS.clear()
    DOCUMENTED_ASSESSMENT_UNIT_THRESHOLDS.clear()


def lookup_trusted_hydrogeological_threshold(block_name: Optional[str]) -> Optional[HydrogeologicalThresholdRecord]:
    """Look up authoritative, independently verified hydrogeological threshold record for an administrative block."""
    if not block_name:
        return None
    return TRUSTED_HYDROGEOLOGICAL_THRESHOLDS.get(str(block_name).strip().lower(), None)


OLS_AUTOCORRELATION_LIMITATIONS_NOTE = (
    "Ordinary least-squares (OLS) linear regression p-values are restricted strictly to an exploratory "
    "diagnostic screening metric. OLS regression assumes independent and identically distributed (i.i.d.) "
    "residuals, which is routinely violated in annual groundwater observations due to serial autocorrelation "
    "and multi-year climatic lag effects. Ordinary OLS p-values MUST NOT be presented as definitive hydrogeological "
    "significance. Definitive trend significance requires serial-correlation robust non-parametric testing "
    "(Modified Mann-Kendall per Hamed & Rao, 1998) combined with physical verification against the trusted "
    "server-side hydrogeological threshold."
)


def compute_sens_slope_confidence_interval(
    pairwise_slopes: List[float],
    variance_s: float,
    confidence_level: float = 0.95,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Non-parametric (1 - alpha) confidence interval for Sen's slope estimator (Sen 1968, Gilbert 1987).

    Methodology:
      Gilbert, R. O. (1987). Statistical Methods for Environmental Pollution Monitoring.
      Van Nostrand Reinhold, New York. pp. 217-219.
      Hollander, M., Wolfe, D. A., & Chicken, E. (2013). Nonparametric Statistical Methods.
      John Wiley & Sons.
    """
    if not pairwise_slopes or variance_s <= 0.0:
        return None, None
    N_prime = len(pairwise_slopes)
    sorted_slopes = sorted(pairwise_slopes)
    alpha = 1.0 - confidence_level
    z = float(stats.norm.ppf(1.0 - alpha / 2.0))
    C_alpha = z * np.sqrt(variance_s)
    M1 = (N_prime - C_alpha) / 2.0
    M2 = (N_prime + C_alpha) / 2.0 + 1.0
    k1 = max(1, min(N_prime, int(np.round(M1))))
    k2 = max(1, min(N_prime, int(np.round(M2))))
    ci_lower = float(sorted_slopes[k1 - 1])
    ci_upper = float(sorted_slopes[k2 - 1])
    return ci_lower, ci_upper


def evaluate_trend_threshold_sensitivity(
    sen_slope_m_per_year: Optional[float],
    p_value: Optional[float],
    ci_lower: Optional[float] = None,
    ci_upper: Optional[float] = None,
    years_count: Optional[int] = None,
    min_years: int = MIN_DECADAL_TREND_YEARS,
    lower_threshold_m_per_year: float = 0.10,
    upper_threshold_m_per_year: float = 0.20,
    is_statistically_significant: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Evaluate groundwater trend evidence as a threshold-sensitivity diagnostic
    against the statutory CGWB GEC-2015 guideline range (0.10–0.20 m/year = 10–20 cm/year).

    Exact Diagnostic Outcomes:
      - 'significant_across_guideline_range':
          Decline is supported above the entire guideline range (Sen's slope >= 0.20 m/yr
          and statistically significant p < 0.05).
      - 'below_guideline_range':
          Decline is demonstrably below guideline range (Sen's slope < 0.10 m/yr
          or non-positive / recovering water table or lack of statistical significance).
      - 'threshold_sensitive':
          Evidence falls within or overlaps guideline range (0.10 <= slope < 0.20 m/yr
          with statistical significance, or slope >= 0.20 m/yr but confidence interval
          extends below upper threshold); outcome depends on local formation threshold.
      - 'insufficient_data':
          Fewer than min_years (10) decadal seasonal observation records.
      - 'not_evaluated':
          Trend evaluation could not be performed (e.g. missing inputs, constant series).
    """
    guideline = {"lower": lower_threshold_m_per_year, "upper": upper_threshold_m_per_year}

    if years_count is None or years_count < min_years:
        return {
            "status": "insufficient_data",
            "outcome": "insufficient_data",
            "guideline_range_m_per_year": guideline,
            "sen_slope_m_per_year": sen_slope_m_per_year,
            "p_value": p_value,
            "sen_slope_ci_95": {"lower": ci_lower, "upper": ci_upper} if ci_lower is not None and ci_upper is not None else None,
            "rationale": (
                f"Insufficient data: {years_count or 0} seasonal observations available "
                f"(statutory GEC-2015 requires >= {min_years} representative decadal years)."
            ),
        }

    if sen_slope_m_per_year is None or p_value is None:
        return {
            "status": "not_evaluated",
            "outcome": "not_evaluated",
            "guideline_range_m_per_year": guideline,
            "sen_slope_m_per_year": None,
            "p_value": None,
            "sen_slope_ci_95": None,
            "rationale": "Trend criteria were not evaluated or statistical model assumptions were not met.",
        }

    slope = float(sen_slope_m_per_year)
    pval = float(p_value)
    sig = is_statistically_significant if is_statistically_significant is not None else (pval < 0.05)

    ci_dict = {"lower": ci_lower, "upper": ci_upper} if ci_lower is not None and ci_upper is not None else None

    # Case 1: Below guideline range (slope < 0.10 or non-significant or recovering water table <= 0)
    if slope <= 0.0 or not sig or slope < lower_threshold_m_per_year:
        if slope <= 0.0:
            rat = f"Water level trend ({slope:.4f} m/yr) indicates stable or recovering water table (below guideline range)."
        elif not sig:
            rat = f"Water level trend ({slope:.4f} m/yr) is not statistically significant (p={pval:.4f} >= 0.05), below guideline range."
        else:
            rat = f"Water level trend ({slope:.4f} m/yr) is demonstrably below CGWB guideline range (< {lower_threshold_m_per_year:.2f} m/yr)."
        return {
            "status": "below_guideline_range",
            "outcome": "below_guideline_range",
            "guideline_range_m_per_year": guideline,
            "sen_slope_m_per_year": round(slope, 4),
            "p_value": round(pval, 4),
            "sen_slope_ci_95": ci_dict,
            "rationale": rat,
        }

    # Case 2: Significant across guideline range (slope >= 0.20 and significant)
    if slope >= upper_threshold_m_per_year and sig:
        if ci_lower is not None and ci_lower < lower_threshold_m_per_year:
            return {
                "status": "threshold_sensitive",
                "outcome": "threshold_sensitive",
                "guideline_range_m_per_year": guideline,
                "sen_slope_m_per_year": round(slope, 4),
                "p_value": round(pval, 4),
                "sen_slope_ci_95": ci_dict,
                "rationale": (
                    f"Water table decline slope ({slope:.4f} m/yr) meets upper threshold, but 95% confidence interval "
                    f"[{ci_lower:.4f}, {ci_upper:.4f}] extends below {lower_threshold_m_per_year:.2f} m/yr; "
                    "interpretation is sensitive to local formation storativity threshold."
                ),
            }
        return {
            "status": "significant_across_guideline_range",
            "outcome": "significant_across_guideline_range",
            "guideline_range_m_per_year": guideline,
            "sen_slope_m_per_year": round(slope, 4),
            "p_value": round(pval, 4),
            "sen_slope_ci_95": ci_dict,
            "rationale": (
                f"Statistically significant water table decline ({slope:.4f} m/yr, p={pval:.4f}) "
                f"meets or exceeds the entire CGWB guideline range (>= {upper_threshold_m_per_year:.2f} m/yr)."
            ),
        }

    # Case 3: Threshold-sensitive (0.10 <= slope < 0.20 and significant)
    return {
        "status": "threshold_sensitive",
        "outcome": "threshold_sensitive",
        "guideline_range_m_per_year": guideline,
        "sen_slope_m_per_year": round(slope, 4),
        "p_value": round(pval, 4),
        "sen_slope_ci_95": ci_dict,
        "rationale": (
            f"Statistically significant water table decline ({slope:.4f} m/yr, p={pval:.4f}) "
            f"falls within CGWB guideline range ({lower_threshold_m_per_year:.2f}–{upper_threshold_m_per_year:.2f} m/yr); "
            "classification is sensitive to local hydrogeological formation storativity threshold."
        ),
    }


def compute_modified_mann_kendall(
    y_values: np.ndarray,
    year_coords: Optional[np.ndarray] = None,
    allow_irregular: bool = False,
) -> Dict[str, Any]:
    """
    Modified Mann-Kendall Trend Test for Autocorrelated Data (Hamed & Rao, 1998).

    Methodology:
      Hamed, K. H., & Rao, A. R. (1998). A modified Mann-Kendall trend test for autocorrelated data.
      Journal of Hydrology, 204(1-4), 182-196.

    Statutory Basis & Scientific Integrity:
      1. Irregular annual observations & missing calendar years:
         Hamed & Rao (1998) Eq. (7) variance correction weights (n-k)(n-k-1)(n-k-2) are derived
         analytically assuming contiguous equidistant time series (delta_t = 1.0 yr).
         When calendar years are missing (e.g. 2011..2021 with 2015 missing), adjacent array positions
         do NOT represent 1-year lags. Treating non-equidistant array indices as 1-year lags distorts
         the empirical lag autocorrelation structure and invalidates the variance correction factor.
         By default (allow_irregular=False), when non-equidistant intervals are detected, the test reports
         is_equidistant=False and trend_direction='not_evaluated', without inventing an unsupported statistical result.
         When allow_irregular=True, continuous-time / distance-aware rank autocorrelation adjustment is applied.
      2. Tied values:
         Tied values in observations reduce the baseline variance V0(S) per the standard tie correction:
         V0(S) = (1/18) * [n(n-1)(2n+5) - sum_t t(t-1)(2t+5)].
      3. Non-parametric Confidence Interval for Sen's Slope:
         Calculated per Sen (1968) and Gilbert (1987) using non-parametric rank order statistics.
      4. Autocorrelation lag truncation & detrending:
         Empirical serial correlation coefficients rho_k of detrended ranks are evaluated for lags
         k = 1, ..., n-2. Only statistically significant rho_k (|rho_k| > 1.96 / sqrt(n)) are included
         in the variance inflation factor (n / n*).
      5. Conservatism:
         The variance correction factor is bounded below by 1.0 (var_factor >= 1.0) so negative
         autocorrelation does not artificially shrink variance and inflate false positives.
    """
    if y_values is None or len(y_values) < 3:
        return {
            "method": "Modified Mann-Kendall (Hamed & Rao, 1998)",
            "n_observations": int(len(y_values)) if y_values is not None else 0,
            "is_equidistant": False,
            "s_statistic": None,
            "kendall_tau": None,
            "sen_slope_m_per_year": None,
            "sen_slope_ci_lower_m_per_year": None,
            "sen_slope_ci_upper_m_per_year": None,
            "sen_slope_ci_95": None,
            "variance_s": None,
            "modified_variance_s": None,
            "variance_correction_factor": None,
            "z_stat": None,
            "p_value": None,
            "is_statistically_significant": False,
            "trend_direction": "insufficient_data",
            "limitation_note": "Fewer than 3 observations available for trend analysis.",
        }

    y_arr = np.asarray(y_values, dtype=float)
    t_arr = np.asarray(year_coords, dtype=float) if year_coords is not None else np.arange(len(y_arr), dtype=float)

    # Filter out non-finite (NaN / Inf) values
    finite_mask = np.isfinite(y_arr) & np.isfinite(t_arr)
    y_arr = y_arr[finite_mask]
    t_arr = t_arr[finite_mask]
    n = len(y_arr)

    if n < 3:
        return {
            "method": "Modified Mann-Kendall (Hamed & Rao, 1998)",
            "n_observations": int(n),
            "is_equidistant": False,
            "s_statistic": None,
            "kendall_tau": None,
            "sen_slope_m_per_year": None,
            "sen_slope_ci_lower_m_per_year": None,
            "sen_slope_ci_upper_m_per_year": None,
            "sen_slope_ci_95": None,
            "variance_s": None,
            "modified_variance_s": None,
            "variance_correction_factor": None,
            "z_stat": None,
            "p_value": None,
            "is_statistically_significant": False,
            "trend_direction": "insufficient_data",
            "limitation_note": "Fewer than 3 valid, finite observations available for trend analysis.",
        }

    # Sort strictly by calendar time
    sort_order = np.argsort(t_arr)
    t_arr = t_arr[sort_order]
    y_arr = y_arr[sort_order]

    # Verify equidistant spacing (e.g. annual series where delta_t == 1.0)
    dt_diffs = np.diff(t_arr)
    is_equidistant = bool(np.all(np.isclose(dt_diffs, 1.0)))

    # Compute Mann-Kendall S statistic and Sen's slope using actual calendar coordinates
    pairwise_diffs = []
    pairwise_slopes = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            dy = float(y_arr[j] - y_arr[i])
            dt = float(t_arr[j] - t_arr[i])
            pairwise_diffs.append(dy)
            if dt != 0.0:
                pairwise_slopes.append(dy / dt)

    S = int(np.sum(np.sign(pairwise_diffs)))
    sen_slope = float(np.median(pairwise_slopes)) if pairwise_slopes else 0.0
    tau = float(S / (0.5 * n * (n - 1))) if n > 1 else 0.0

    # Tied values adjustment in baseline variance V0(S)
    _, tie_counts = np.unique(y_arr, return_counts=True)
    tie_term = np.sum(tie_counts * (tie_counts - 1) * (2 * tie_counts + 5))
    v0 = float((n * (n - 1) * (2 * n + 5) - tie_term) / 18.0)

    # Non-parametric Sen's slope confidence interval (Sen 1968, Gilbert 1987)
    ci_low, ci_high = compute_sens_slope_confidence_interval(pairwise_slopes, v0)
    ci_dict = {"lower": round(ci_low, 4), "upper": round(ci_high, 4)} if ci_low is not None and ci_high is not None else None

    # If series is non-equidistant (contains missing calendar years or irregular intervals),
    # Hamed & Rao (1998) serial correlation lag summation cannot be defensibly computed without allow_irregular=True.
    if not is_equidistant and not allow_irregular:
        return {
            "method": "Modified Mann-Kendall (Hamed & Rao, 1998)",
            "n_observations": int(n),
            "is_equidistant": False,
            "s_statistic": S,
            "kendall_tau": round(tau, 4),
            "sen_slope_m_per_year": round(sen_slope, 4),
            "sen_slope_ci_lower_m_per_year": round(ci_low, 4) if ci_low is not None else None,
            "sen_slope_ci_upper_m_per_year": round(ci_high, 4) if ci_high is not None else None,
            "sen_slope_ci_95": ci_dict,
            "variance_s": round(v0, 4) if v0 > 0 else 0.0,
            "modified_variance_s": None,
            "variance_correction_factor": None,
            "z_stat": None,
            "p_value": None,
            "is_statistically_significant": False,
            "trend_direction": "not_evaluated",
            "limitation_note": (
                "Missing calendar years or irregular annual intervals detected in observation series. "
                "Hamed & Rao (1998) variance correction analytically assumes contiguous, equidistant annual "
                "spacing (delta_t = 1.0 yr). Autocorrelation lag structure cannot be defensibly evaluated on "
                "irregular time series without interpolation; Modified Mann-Kendall test is marked 'not_evaluated'."
            ),
        }

    # Constant or completely tied series (zero variance)
    if v0 <= 0 or np.all(y_arr == y_arr[0]):
        return {
            "method": "Modified Mann-Kendall (Hamed & Rao, 1998)",
            "n_observations": int(n),
            "is_equidistant": is_equidistant,
            "s_statistic": 0,
            "kendall_tau": 0.0,
            "sen_slope_m_per_year": 0.0,
            "sen_slope_ci_lower_m_per_year": 0.0,
            "sen_slope_ci_upper_m_per_year": 0.0,
            "sen_slope_ci_95": {"lower": 0.0, "upper": 0.0},
            "variance_s": 0.0,
            "modified_variance_s": 0.0,
            "variance_correction_factor": 1.0,
            "z_stat": 0.0,
            "p_value": 1.0,
            "is_statistically_significant": False,
            "trend_direction": "stable",
            "limitation_note": None,
        }

    # Detrend data using Sen's slope per Hamed & Rao (1998)
    detrended = y_arr - sen_slope * (t_arr - t_arr[0])
    ranks = stats.rankdata(detrended)
    mean_rank = (n + 1.0) / 2.0
    rank_dev = ranks - mean_rank
    var_rank = float(np.sum(rank_dev ** 2))

    crit_val = 1.96 / np.sqrt(n)
    correction_sum = 0.0
    if var_rank > 1e-12 and n > 3:
        for k in range(1, n - 2):
            cov = float(np.sum(rank_dev[:-k] * rank_dev[k:]))
            rho_k = cov / var_rank
            if abs(rho_k) > crit_val:
                weight = (n - k) * (n - k - 1) * (n - k - 2)
                correction_sum += weight * rho_k

        var_factor = max(1.0, 1.0 + (2.0 / (n * (n - 1) * (n - 2))) * correction_sum)
    else:
        var_factor = 1.0

    v_star = max(v0 * var_factor, 1e-9)

    # Re-evaluate confidence interval using modified variance V*(S) to reflect autocorrelation
    ci_low_star, ci_high_star = compute_sens_slope_confidence_interval(pairwise_slopes, v_star)
    if ci_low_star is not None and ci_high_star is not None:
        ci_low, ci_high = ci_low_star, ci_high_star
        ci_dict = {"lower": round(ci_low, 4), "upper": round(ci_high, 4)}

    if S > 0:
        z_stat = (S - 1.0) / np.sqrt(v_star)
    elif S < 0:
        z_stat = (S + 1.0) / np.sqrt(v_star)
    else:
        z_stat = 0.0

    p_val = float(2.0 * (1.0 - stats.norm.cdf(abs(z_stat))))
    is_sig = bool(p_val < 0.05)

    if S > 0:
        direction = "declining"
    elif S < 0:
        direction = "rising"
    else:
        direction = "stable"

    return {
        "method": "Modified Mann-Kendall (Hamed & Rao, 1998)",
        "n_observations": int(n),
        "is_equidistant": is_equidistant,
        "s_statistic": S,
        "kendall_tau": round(tau, 4),
        "sen_slope_m_per_year": round(sen_slope, 4),
        "sen_slope_ci_lower_m_per_year": round(ci_low, 4) if ci_low is not None else None,
        "sen_slope_ci_upper_m_per_year": round(ci_high, 4) if ci_high is not None else None,
        "sen_slope_ci_95": ci_dict,
        "variance_s": round(v0, 4),
        "modified_variance_s": round(v_star, 4),
        "variance_correction_factor": round(float(var_factor), 4),
        "z_stat": round(float(z_stat), 4),
        "p_value": round(p_val, 4),
        "is_statistically_significant": is_sig,
        "trend_direction": direction,
        "limitation_note": None if is_equidistant else "Irregular annual observation coordinates evaluated via continuous-time rank autocorrelation.",
    }

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
    stage_of_extraction_pct: Optional[float] = None,
    pre_monsoon_trend_decline: Optional[bool] = None,
    post_monsoon_trend_decline: Optional[bool] = None,
    assessment_unit: Optional[str] = None,
    trend_years_count: Optional[int] = None,
    pre_monsoon_years_count: Optional[int] = None,
    post_monsoon_years_count: Optional[int] = None,
    soe_source: Optional[str] = None,
    assessment_year: Optional[int | str] = None,
    require_authoritative_metadata: bool = False,
    pre_monsoon_trend: Optional[str] = None,
    post_monsoon_trend: Optional[str] = None,
    significant_decline_threshold_m_per_year: Optional[float] = None,
    fallback_to_documented_threshold: bool = True,
    pre_monsoon_threshold_sensitivity: Optional[str] = None,
    post_monsoon_threshold_sensitivity: Optional[str] = None,
    overall_trend_sensitivity: Optional[str] = None,
    pre_monsoon_sen_slope_ci_95: Optional[dict] = None,
    post_monsoon_sen_slope_ci_95: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Statutory CGWB GEC-2015 Assessment-Unit Categorization Matrix.

    Evaluates administrative assessment units (Taluk / Block / Mandal / Watershed)
    strictly at the administrative unit level, NEVER on individual monitoring wells.

    Requires:
      1. Valid administrative assessment unit name (e.g., taluk or block).
         District fallback is strictly prohibited.
      2. Valid assessment-unit Stage of Groundwater Extraction (SOE):
         SOE = (Existing Gross Draft for All Uses / Annual Extractable Groundwater Resource) * 100%
         A legitimate 0.0% extraction is valid; strictly negative values are rejected.
         Authoritative source citation and assessment year required for official evaluations.
         SOE CANNOT be derived from local well depth or water table levels.

    Official Quantity-Based Categorization (GEC-2015 Methodology):
      - SOE <= 70%: Safe
      - 70% < SOE <= 90%: Semi-Critical
      - 90% < SOE <= 100%: Critical
      - SOE > 100%: Over-Exploited

    Independent Long-Term Trend Validation:
      Decadal seasonal trends (pre-monsoon and post-monsoon >= 10 years separately)
      are evaluated independently from official categorization and return separate fields:
      - official_category (derived strictly from SOE)
      - trend_validation_status ("consistent", "needs_reassessment", "insufficient_data", "not_evaluated")
      - pre_monsoon_trend ("declining", "no_decline", "insufficient_data", "not_evaluated", None)
      - post_monsoon_trend ("declining", "no_decline", "insufficient_data", "not_evaluated", None)
      - trend_validation_reason

      Hydrogeological vs Statistical Significance:
      - Statistical Significance: Linear regression p-value < 0.05 (supporting only).
        Note: OLS p-values have documented limitations on temporally autocorrelated groundwater series.
      - Hydrogeological Significance: Rate of deepening (m/year) must meet or exceed a configured
        threshold within the CGWB locally justified range (approx 10–20 cm/year = 0.10–0.20 m/year).
      - If no defensible threshold is available for the assessment unit, trend validation returns
        'not_evaluated' rather than inventing a significant-decline result.

      Reassessment checks (applied as informational advisories without altering official category):
      - SOE <= 70% with significant decline in both seasonal trends -> needs_reassessment
      - SOE > 100% with no significant decline in either seasonal trend -> needs_reassessment

    Returns:
        Structured dict with official_category, category, trend_validation_status,
        pre_monsoon_trend, post_monsoon_trend, trend_validation_reason, and metadata.
    """
    # Resolve hydrogeological threshold record for assessment unit early for uniform returns
    unit_name = str(assessment_unit).strip() if assessment_unit else ""
    thresh_rec = lookup_trusted_hydrogeological_threshold(unit_name) if unit_name else None
    threshold_dict = thresh_rec.to_dict() if thresh_rec else None

    if significant_decline_threshold_m_per_year is not None:
        threshold = float(significant_decline_threshold_m_per_year)
    elif fallback_to_documented_threshold and thresh_rec:
        threshold = thresh_rec.threshold_m_per_year
    else:
        threshold = None

    # Guard 1: Must be a valid administrative assessment unit, not an unmapped well or district
    if (
        assessment_unit is None
        or not str(assessment_unit).strip()
        or str(assessment_unit).strip().lower() in ("unknown", "none", "unassigned", "")
    ):
        return {
            "official_category": "unassessed",
            "category": "unassessed",
            "category_label": "Unassessed",
            "trend_validation_status": "not_evaluated",
            "pre_monsoon_trend": None,
            "post_monsoon_trend": None,
            "trend_validation_reason": (
                "Unassessed: Statutory GEC-2015 assessments apply exclusively to administrative assessment "
                "units (taluks/blocks/watersheds). No valid administrative assessment unit was specified. "
                "Individual monitoring wells cannot be classified as official blocks, and district fallback is prohibited."
            ),
            "stage_of_extraction_pct": None,
            "soe_source": str(soe_source).strip() if soe_source else None,
            "assessment_year": assessment_year,
            "pre_monsoon_trend_decline": None,
            "post_monsoon_trend_decline": None,
            "pre_monsoon_years_count": pre_monsoon_years_count,
            "post_monsoon_years_count": post_monsoon_years_count,
            "significant_decline_threshold_m_per_year": None,
            "threshold_record": None,
            "threshold_source_publication": None,
            "threshold_source_url": None,
            "threshold_page_table_reference": None,
            "threshold_hydrogeological_formation": None,
            "threshold_justification": None,
            "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
            "assessment_unit": None,
            "framework": "CGWB GEC-2015 Methodology",
            "statutory_scope": "administrative_assessment_unit",
            "rationale": (
                "Unassessed: Statutory GEC-2015 assessments apply exclusively to administrative assessment "
                "units (taluks/blocks/watersheds). No valid administrative assessment unit was specified. "
                "Individual monitoring wells cannot be classified as official blocks, and district fallback is prohibited."
            ),
        }

    # Guard 2: Must have valid volumetric Stage of Groundwater Extraction (SOE >= 0.0%)
    # 0.0% is legitimate (e.g. unextracted wildlife sanctuary or zero draft watershed); strictly negative (<0) is invalid.
    if (
        stage_of_extraction_pct is None
        or not isinstance(stage_of_extraction_pct, (int, float))
        or np.isnan(stage_of_extraction_pct)
        or not np.isfinite(stage_of_extraction_pct)
        or float(stage_of_extraction_pct) < 0.0
    ):
        return {
            "official_category": "unassessed",
            "category": "unassessed",
            "category_label": "Unassessed",
            "trend_validation_status": "not_evaluated",
            "pre_monsoon_trend": None,
            "post_monsoon_trend": None,
            "trend_validation_reason": (
                f"Unassessed for {unit_name}: Valid assessment-unit Stage of Groundwater Extraction (SOE >= 0.0%) "
                "data is unavailable. GEC-2015 categorization requires volumetric gross draft and "
                "Annual Extractable Groundwater Resource accounting from official CGWB Dynamic Ground Water Resource Assessments. "
                "SOE cannot be derived from well depth or local water level trends."
            ),
            "stage_of_extraction_pct": None,
            "soe_source": str(soe_source).strip() if soe_source else None,
            "assessment_year": assessment_year,
            "pre_monsoon_trend_decline": None,
            "post_monsoon_trend_decline": None,
            "pre_monsoon_years_count": pre_monsoon_years_count,
            "post_monsoon_years_count": post_monsoon_years_count,
            "significant_decline_threshold_m_per_year": threshold,
            "threshold_record": threshold_dict,
            "threshold_source_publication": thresh_rec.source_publication_title if thresh_rec else None,
            "threshold_source_url": thresh_rec.source_url if thresh_rec else None,
            "threshold_page_table_reference": thresh_rec.page_table_reference if thresh_rec else None,
            "threshold_hydrogeological_formation": thresh_rec.hydrogeological_formation if thresh_rec else None,
            "threshold_justification": thresh_rec.justification if thresh_rec else None,
            "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
            "assessment_unit": unit_name,
            "framework": "CGWB GEC-2015 Methodology",
            "statutory_scope": "administrative_assessment_unit",
            "rationale": (
                f"Unassessed for {unit_name}: Valid assessment-unit Stage of Groundwater Extraction (SOE >= 0.0%) "
                "data is unavailable. GEC-2015 categorization requires volumetric gross draft and "
                "Annual Extractable Groundwater Resource accounting from official CGWB Dynamic Ground Water Resource Assessments. "
                "SOE cannot be derived from well depth or local water level trends."
            ),
        }

    # Guard 2b: Strict authoritative source citation and assessment year check
    if require_authoritative_metadata:
        if not soe_source or not str(soe_source).strip():
            return {
                "official_category": "unassessed",
                "category": "unassessed",
                "category_label": "Unassessed",
                "trend_validation_status": "not_evaluated",
                "pre_monsoon_trend": None,
                "post_monsoon_trend": None,
                "trend_validation_reason": (
                    f"Unassessed for {unit_name}: Authoritative SOE data source must be specified from official "
                    "CGWB Dynamic Ground Water Resource Assessments. SOE cannot be derived from local well depth or water levels."
                ),
                "stage_of_extraction_pct": round(float(stage_of_extraction_pct), 2),
                "soe_source": None,
                "assessment_year": assessment_year,
                "pre_monsoon_trend_decline": None,
                "post_monsoon_trend_decline": None,
                "pre_monsoon_years_count": pre_monsoon_years_count,
                "post_monsoon_years_count": post_monsoon_years_count,
                "significant_decline_threshold_m_per_year": threshold,
                "threshold_record": threshold_dict,
                "threshold_source_publication": thresh_rec.source_publication_title if thresh_rec else None,
                "threshold_source_url": thresh_rec.source_url if thresh_rec else None,
                "threshold_page_table_reference": thresh_rec.page_table_reference if thresh_rec else None,
                "threshold_hydrogeological_formation": thresh_rec.hydrogeological_formation if thresh_rec else None,
                "threshold_justification": thresh_rec.justification if thresh_rec else None,
                "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
                "assessment_unit": unit_name,
                "framework": "CGWB GEC-2015 Methodology",
                "statutory_scope": "administrative_assessment_unit",
                "rationale": (
                    f"Unassessed for {unit_name}: Authoritative SOE data source must be specified from official "
                    "CGWB Dynamic Ground Water Resource Assessments. SOE cannot be derived from local well depth or water levels."
                ),
            }
        if assessment_year is None or not str(assessment_year).strip():
            return {
                "official_category": "unassessed",
                "category": "unassessed",
                "category_label": "Unassessed",
                "trend_validation_status": "not_evaluated",
                "pre_monsoon_trend": None,
                "post_monsoon_trend": None,
                "trend_validation_reason": (
                    f"Unassessed for {unit_name}: Authoritative SOE assessment year must be specified (e.g., 2022, 2023)."
                ),
                "stage_of_extraction_pct": round(float(stage_of_extraction_pct), 2),
                "soe_source": str(soe_source).strip(),
                "assessment_year": None,
                "pre_monsoon_trend_decline": None,
                "post_monsoon_trend_decline": None,
                "pre_monsoon_years_count": pre_monsoon_years_count,
                "post_monsoon_years_count": post_monsoon_years_count,
                "significant_decline_threshold_m_per_year": threshold,
                "threshold_record": threshold_dict,
                "threshold_source_publication": thresh_rec.source_publication_title if thresh_rec else None,
                "threshold_source_url": thresh_rec.source_url if thresh_rec else None,
                "threshold_page_table_reference": thresh_rec.page_table_reference if thresh_rec else None,
                "threshold_hydrogeological_formation": thresh_rec.hydrogeological_formation if thresh_rec else None,
                "threshold_justification": thresh_rec.justification if thresh_rec else None,
                "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
                "assessment_unit": unit_name,
                "framework": "CGWB GEC-2015 Methodology",
                "statutory_scope": "administrative_assessment_unit",
                "rationale": (
                    f"Unassessed for {unit_name}: Authoritative SOE assessment year must be specified (e.g., 2022, 2023)."
                ),
            }

    soe = float(stage_of_extraction_pct)

    # 1. Statutory GEC-2015 Official Quantity-Based Categorization:
    # Strictly derived from Stage of Groundwater Extraction (SOE)
    if soe <= GEC_SAFE_STAGE_MAX:
        official_category = "safe"
        category_label = "Safe"
    elif soe <= GEC_SEMI_CRITICAL_STAGE_MAX:
        official_category = "semi_critical"
        category_label = "Semi-Critical"
    elif soe <= GEC_CRITICAL_STAGE_MAX:
        official_category = "critical"
        category_label = "Critical"
    else:
        official_category = "over_exploited"
        category_label = "Over-Exploited"

    # 2. Independent Seasonal Trend Validation:
    def _resolve_trend(trend_str: Optional[str], trend_bool: Optional[bool]) -> Optional[str]:
        if trend_str is not None and str(trend_str).strip():
            norm = str(trend_str).strip().lower()
            if norm in ("declining", "decline"):
                return "declining"
            elif norm in ("no_decline", "not_declining", "stable", "rising", "recovering"):
                return "no_decline"
            elif norm in ("insufficient_data", "insufficient"):
                return "insufficient_data"
            elif norm in ("not_evaluated", "none", "unassessed"):
                return "not_evaluated"
        if trend_bool is True:
            return "declining"
        elif trend_bool is False:
            return "no_decline"
        return None

    resolved_pre_trend = _resolve_trend(pre_monsoon_trend, pre_monsoon_trend_decline)
    resolved_post_trend = _resolve_trend(post_monsoon_trend, post_monsoon_trend_decline)

    has_trend_inputs = (
        resolved_pre_trend is not None
        or resolved_post_trend is not None
        or pre_monsoon_years_count is not None
        or post_monsoon_years_count is not None
        or trend_years_count is not None
        or pre_monsoon_threshold_sensitivity is not None
        or post_monsoon_threshold_sensitivity is not None
    )

    if not has_trend_inputs:
        trend_validation_status = "not_evaluated"
        out_pre_trend = None
        out_post_trend = None
        out_pre_dec = None
        out_post_dec = None
        out_pre_sensitivity = "not_evaluated"
        out_post_sensitivity = "not_evaluated"
        out_overall_sensitivity = "not_evaluated"
        trend_validation_reason = (
            "Seasonal groundwater trend validation was not evaluated (no local trend data supplied)."
        )
    else:
        pre_count = pre_monsoon_years_count if pre_monsoon_years_count is not None else trend_years_count
        post_count = post_monsoon_years_count if post_monsoon_years_count is not None else trend_years_count

        pre_has_data = pre_count is not None and pre_count >= MIN_DECADAL_TREND_YEARS
        post_has_data = post_count is not None and post_count >= MIN_DECADAL_TREND_YEARS

        # Check for insufficient decadal observations or explicit insufficient_data status
        if not (pre_has_data and post_has_data) or resolved_pre_trend == "insufficient_data" or resolved_post_trend == "insufficient_data":
            trend_validation_status = "insufficient_data"
            out_pre_trend = resolved_pre_trend if (pre_has_data and resolved_pre_trend in ("declining", "no_decline")) else "insufficient_data"
            out_post_trend = resolved_post_trend if (post_has_data and resolved_post_trend in ("declining", "no_decline")) else "insufficient_data"
            out_pre_dec = bool(out_pre_trend == "declining") if out_pre_trend in ("declining", "no_decline") else None
            out_post_dec = bool(out_post_trend == "declining") if out_post_trend in ("declining", "no_decline") else None
            out_pre_sensitivity = pre_monsoon_threshold_sensitivity or "insufficient_data"
            out_post_sensitivity = post_monsoon_threshold_sensitivity or "insufficient_data"
            out_overall_sensitivity = "insufficient_data"

            missing_parts = []
            if not pre_has_data or resolved_pre_trend == "insufficient_data":
                pre_count_str = f"{pre_count} yrs" if pre_count is not None else "missing"
                missing_parts.append(f"pre-monsoon ({pre_count_str}, requires >={MIN_DECADAL_TREND_YEARS} yrs)")
            if not post_has_data or resolved_post_trend == "insufficient_data":
                post_count_str = f"{post_count} yrs" if post_count is not None else "missing"
                missing_parts.append(f"post-monsoon ({post_count_str}, requires >={MIN_DECADAL_TREND_YEARS} yrs)")

            trend_validation_reason = (
                f"Insufficient statutory seasonal trend records to validate official category: {', '.join(missing_parts)}. "
                f"Official category is retained from verified SOE ({soe:.1f}%)."
            )
        # Check if observations are sufficient, but no defensible hydrogeological threshold was configured
        elif (
            resolved_pre_trend == "not_evaluated"
            or resolved_post_trend == "not_evaluated"
            or (resolved_pre_trend is None and resolved_post_trend is None and threshold is None and pre_monsoon_threshold_sensitivity is None)
        ):
            trend_validation_status = "not_evaluated"
            out_pre_trend = "not_evaluated"
            out_post_trend = "not_evaluated"
            out_pre_dec = None
            out_post_dec = None
            out_pre_sensitivity = pre_monsoon_threshold_sensitivity or "not_evaluated"
            out_post_sensitivity = post_monsoon_threshold_sensitivity or "not_evaluated"
            out_overall_sensitivity = "not_evaluated"
            trend_validation_reason = (
                f"Decadal seasonal records are available (>={MIN_DECADAL_TREND_YEARS} years), but no defensible hydrogeological "
                f"decline threshold was configured for assessment unit '{unit_name}' or statistical trend criteria were not evaluable (e.g. missing calendar years). "
                "CGWB GEC-2015 guidance describes significant groundwater decline as approximately 10–20 cm/year (0.10–0.20 m/year) "
                "depending on local hydrogeology. Without a defensible threshold, trend validation was not evaluated, and official category is retained from verified SOE."
            )
        else:
            out_pre_trend = resolved_pre_trend
            out_post_trend = resolved_post_trend
            out_pre_dec = bool(resolved_pre_trend == "declining")
            out_post_dec = bool(resolved_post_trend == "declining")

            # Resolve threshold sensitivity
            def _map_sensitivity(sens: Optional[str], trend_dir: Optional[str]) -> str:
                if sens:
                    return sens
                if trend_dir == "declining":
                    return "significant_across_guideline_range" if threshold and threshold >= 0.20 else "threshold_sensitive"
                elif trend_dir == "no_decline":
                    return "below_guideline_range"
                return "not_evaluated"

            out_pre_sensitivity = _map_sensitivity(pre_monsoon_threshold_sensitivity, out_pre_trend)
            out_post_sensitivity = _map_sensitivity(post_monsoon_threshold_sensitivity, out_post_trend)

            if out_pre_sensitivity == "significant_across_guideline_range" and out_post_sensitivity == "significant_across_guideline_range":
                out_overall_sensitivity = "significant_across_guideline_range"
            elif out_pre_sensitivity == "below_guideline_range" and out_post_sensitivity == "below_guideline_range":
                out_overall_sensitivity = "below_guideline_range"
            else:
                out_overall_sensitivity = "threshold_sensitive"

            # Official GEC-2015 Reassessment Checks:
            # 1. SOE <= 70% (Safe) with significant decline in BOTH seasonal trends:
            if soe <= GEC_SAFE_STAGE_MAX and out_pre_dec and out_post_dec:
                trend_validation_status = "needs_reassessment"
                trend_validation_reason = (
                    f"Official category is Safe (SOE {soe:.1f}% <= 70%), but significant long-term decline observed in both "
                    f"pre-monsoon ({pre_count} yrs) and post-monsoon ({post_count} yrs) trends. "
                    "Advisory warning: indicates localized groundwater stress requiring reassessment per GEC-2015 methodology."
                )
            # 2. SOE > 100% (Over-Exploited) with NO significant decline in EITHER seasonal trend:
            elif soe > GEC_CRITICAL_STAGE_MAX and (not out_pre_dec) and (not out_post_dec):
                trend_validation_status = "needs_reassessment"
                trend_validation_reason = (
                    f"Official category is Over-Exploited (SOE {soe:.1f}% > 100%), but neither pre-monsoon "
                    f"({pre_count} yrs) nor post-monsoon ({post_count} yrs) trend exhibits significant decline. "
                    "Advisory warning: indicates potential localized recharge buffer or accounting discrepancy requiring reassessment per GEC-2015 methodology."
                )
            else:
                trend_validation_status = "consistent"
                trend_validation_reason = (
                    f"Official category '{category_label}' is consistent with long-term seasonal water table trends "
                    f"(pre-monsoon {out_pre_trend}, post-monsoon {out_post_trend})."
                )

    rationale = (
        f"Statutory GEC-2015 assessment for {unit_name}: Official category is {category_label} "
        f"based on Stage of Groundwater Extraction ({soe:.1f}%). "
        f"Trend validation status: {trend_validation_status}. {trend_validation_reason}"
    )

    thresh_rec = lookup_trusted_hydrogeological_threshold(unit_name)

    return {
        "official_category": official_category,
        "category": official_category,
        "category_label": category_label,
        "trend_validation_status": trend_validation_status,
        "pre_monsoon_trend": out_pre_trend,
        "post_monsoon_trend": out_post_trend,
        "pre_monsoon_threshold_sensitivity": out_pre_sensitivity,
        "post_monsoon_threshold_sensitivity": out_post_sensitivity,
        "overall_trend_sensitivity": out_overall_sensitivity,
        "pre_monsoon_sen_slope_ci_95": pre_monsoon_sen_slope_ci_95,
        "post_monsoon_sen_slope_ci_95": post_monsoon_sen_slope_ci_95,
        "trend_validation_reason": trend_validation_reason,
        "stage_of_extraction_pct": round(soe, 2),
        "soe_source": str(soe_source).strip() if soe_source else None,
        "assessment_year": assessment_year,
        "pre_monsoon_trend_decline": out_pre_dec,
        "post_monsoon_trend_decline": out_post_dec,
        "pre_monsoon_years_count": pre_monsoon_years_count,
        "post_monsoon_years_count": post_monsoon_years_count,
        "significant_decline_threshold_m_per_year": threshold,
        "threshold_record": thresh_rec.to_dict() if thresh_rec else None,
        "threshold_source_publication": thresh_rec.source_publication_title if thresh_rec else None,
        "threshold_source_url": thresh_rec.source_url if thresh_rec else None,
        "threshold_page_table_reference": thresh_rec.page_table_reference if thresh_rec else None,
        "threshold_hydrogeological_formation": thresh_rec.hydrogeological_formation if thresh_rec else None,
        "threshold_justification": thresh_rec.justification if thresh_rec else None,
        "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
        "assessment_unit": unit_name,
        "framework": "CGWB GEC-2015 Methodology",
        "statutory_scope": "administrative_assessment_unit",
        "rationale": rationale,
    }


DEFAULT_MIN_STATIONS_PER_YEAR = 2


def aggregate_block_seasonal_trends(
    readings_df: pd.DataFrame,
    stations_df: pd.DataFrame,
    block_name: str,
    district: Optional[str] = None,
    state: Optional[str] = None,
    min_stations_per_year: int = DEFAULT_MIN_STATIONS_PER_YEAR,
    significant_decline_threshold_m_per_year: Optional[float] = None,
    fallback_to_documented_threshold: bool = True,
) -> Dict[str, Any]:
    """
    Aggregate station-level observations across an administrative assessment unit (block)
    to compute block-wide pre-monsoon (Apr-May) and post-monsoon (Oct-Nov) decadal trends.

    METHODOLOGICAL REQUIREMENTS & DATA INTEGRITY:
      1. Spatial Representation & Network Design:
         Under standard hydrogeological network principles (WMO No. 168 / CGWB Network Design Principles),
         a single point-source observation well cannot establish spatial representativeness for an
         entire administrative block. A block must have a distributed monitoring network (>= 2 stations),
         and at least 2 spatially distinct monitoring stations must contribute qualifying seasonal data
         for a year to be considered spatially representative.
      2. Observation Data-Quality Filtering:
         Screen all readings before seasonal aggregation:
           - Exclude water_level_m < 0.0 m bgl (unphysical negative depth)
           - Exclude water_level_m > 300.0 m bgl (exceeds physical monitoring well depth in India)
           - Exclude data_quality_flag in ('E', 'ERROR', 'ERR', 'S', 'SUSPECT', 'R', 'REJECTED', 'BAD', 'INVALID')
           - Exclude readings marked as sensor anomalies (is_anomaly=True)
           - Exclude null, NaN, or non-finite readings
         Detailed screening exclusions and surviving coverage counts are tracked and reported.
      3. Unambiguous Administrative Identification:
         Exact case-insensitive match on block name. If stations matching the block name span
         multiple districts, explicit district identification is required to prevent accidental
         cross-district station merging.
      4. Station-Year Normalization (Anti-Dominance Guard):
         Seasonal water level averages are calculated per station per year first:
             h_bar(s, y, season) = (1 / N_{s, y, season}) * sum_{k} h_{s, y, season, k}
         Then aggregated into block-level seasonal values using Equal Station-Year Weighting:
             H_bar_{block}(y, season) = (1 / |S_{y, season}|) * sum_{s in S_{y, season}} h_bar(s, y, season)
         This guarantees that high-frequency telemetry stations (thousands of readings/season)
         do NOT dominate the block average over manual CGWB monitoring wells.
      5. Decadal Seasonal Completeness:
         Statutory GEC-2015 requires at least MIN_DECADAL_TREND_YEARS (10) separate spatially
         representative years for pre-monsoon AND 10 years for post-monsoon.
      6. Hydrogeological vs. Statistical Significance:
         The linear trend slope is calculated directly in metres per year (m/yr) using actual observation years.
         Statistical significance (p < 0.05) is retained strictly as supporting diagnostic screening;
         ordinary regression p-values have documented limitations on temporally autocorrelated groundwater series.
         Hydrogeological significance requires the deepening rate (m/yr) to meet or exceed a locally
         justified threshold (CGWB GEC-2015 guidance specifies approx 10–20 cm/year = 0.10–0.20 m/year).
         When no defensible threshold is available, trend significance is reported as 'not_evaluated'.
    """
    target_block = str(block_name).strip() if block_name else ""

    # Resolve hydrogeological threshold and provenance record for assessment unit
    thresh_rec = lookup_trusted_hydrogeological_threshold(target_block)
    threshold_dict = thresh_rec.to_dict() if thresh_rec else None

    if significant_decline_threshold_m_per_year is not None:
        threshold = float(significant_decline_threshold_m_per_year)
    elif fallback_to_documented_threshold and target_block:
        threshold = thresh_rec.threshold_m_per_year if thresh_rec else None
    else:
        threshold = None

    if (
        readings_df is None
        or readings_df.empty
        or stations_df is None
        or stations_df.empty
        or not block_name
        or not str(block_name).strip()
    ):
        return {
            "assessment_unit": block_name,
            "district": district,
            "state": state,
            "station_count": 0,
            "station_ids": [],
            "weighting_method": "equal_station_year_weighting",
            "pre_monsoon_years_count": 0,
            "post_monsoon_years_count": 0,
            "pre_monsoon_trend": "insufficient_data",
            "post_monsoon_trend": "insufficient_data",
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
            "significant_decline_threshold_m_per_year": threshold,
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
            "spatial_representativeness_met": False,
            "coverage_rationale": f"Insufficient monitoring network: 0 stations located in block '{block_name}'.",
            "data_quality_screening": {
                "total_readings_screened": 0,
                "valid_readings_count": 0,
                "excluded_readings_count": 0,
                "exclusion_breakdown": {},
            },
        }

    target_block = str(block_name).strip()

    def _empty_agg_result(
        stn_count: int,
        stn_ids: list,
        dist: Optional[str],
        st: Optional[str],
        rationale: str,
        screening: Optional[dict] = None,
        spatial_met: bool = False,
    ) -> Dict[str, Any]:
        return {
            "assessment_unit": target_block,
            "district": dist,
            "state": st,
            "station_count": stn_count,
            "station_ids": stn_ids,
            "weighting_method": "equal_station_year_weighting",
            "pre_monsoon_years_count": 0,
            "post_monsoon_years_count": 0,
            "pre_monsoon_trend": "insufficient_data",
            "post_monsoon_trend": "insufficient_data",
            "pre_monsoon_threshold_sensitivity": "insufficient_data",
            "post_monsoon_threshold_sensitivity": "insufficient_data",
            "overall_trend_sensitivity": "insufficient_data",
            "pre_monsoon_threshold_sensitivity_rationale": rationale,
            "post_monsoon_threshold_sensitivity_rationale": rationale,
            "overall_trend_sensitivity_rationale": rationale,
            "pre_monsoon_sen_slope_ci_95": None,
            "post_monsoon_sen_slope_ci_95": None,
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
            "significant_decline_threshold_m_per_year": threshold,
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
            "spatial_representativeness_met": spatial_met,
            "coverage_rationale": rationale,
            "data_quality_screening": screening or {
                "total_readings_screened": 0,
                "valid_readings_count": 0,
                "excluded_readings_count": 0,
                "exclusion_breakdown": {},
            },
        }

    # Exact case-insensitive block matching (no substring)
    matched_stations = stations_df[stations_df["block"].astype(str).str.strip().str.lower() == target_block.lower()].copy()

    # Disambiguation by state and district
    if state and "state" in matched_stations.columns:
        matched_stations = matched_stations[matched_stations["state"].astype(str).str.strip().str.lower() == state.strip().lower()]
    if district and "district" in matched_stations.columns:
        matched_stations = matched_stations[matched_stations["district"].astype(str).str.strip().str.lower() == district.strip().lower()]

    if matched_stations.empty:
        return _empty_agg_result(
            stn_count=0,
            stn_ids=[],
            dist=district,
            st=state,
            rationale=f"Insufficient monitoring network: 0 stations located in block '{target_block}'.",
        )

    # Cross-district duplicate block name check (Item 4)
    if not district and "district" in matched_stations.columns:
        unique_districts = sorted(list(set(matched_stations["district"].dropna().astype(str).str.strip().unique())))
        if len(unique_districts) > 1:
            return _empty_agg_result(
                stn_count=len(matched_stations),
                stn_ids=sorted(list(set(matched_stations["station_id"].astype(str)))),
                dist=None,
                st=state,
                rationale=(
                    f"Unassessed: Ambiguous administrative block '{target_block}'. This block name exists in multiple "
                    f"districts ({', '.join(unique_districts)}). Unambiguous administrative identification requires "
                    "specifying the district or canonical administrative identifier to prevent accidental merging of stations across districts."
                ),
            )

    station_ids = sorted(list(set(matched_stations["station_id"].astype(str))))
    block_district = matched_stations["district"].iloc[0] if "district" in matched_stations.columns else district
    block_state = matched_stations["state"].iloc[0] if "state" in matched_stations.columns else state

    # Spatial Network Representativeness: Guard against 1-station insufficiency (Item 1)
    if len(station_ids) < 2:
        return _empty_agg_result(
            stn_count=len(station_ids),
            stn_ids=station_ids,
            dist=block_district,
            st=block_state,
            rationale=(
                f"Unassessed for {target_block}: Insufficient spatial monitoring network representativeness. "
                f"Administrative block '{target_block}' has only {len(station_ids)} monitoring station(s). "
                "Under standard hydrogeological network principles (WMO No. 168 / CGWB monitoring guidelines), "
                "a single point well cannot establish spatial representativeness across an entire administrative block. "
                "At least 2 spatially distinct monitoring stations are required to capture hydrogeological heterogeneity."
            ),
        )

    df = readings_df[readings_df["station_id"].astype(str).isin(station_ids)].copy()
    if df.empty or "water_level_m" not in df.columns or "timestamp" not in df.columns:
        return _empty_agg_result(
            stn_count=len(station_ids),
            stn_ids=station_ids,
            dist=block_district,
            st=block_state,
            rationale=f"No valid water level readings found for {len(station_ids)} stations in block '{target_block}'.",
        )

    # Data Quality Screening (Item 3)
    total_screened = len(df)
    numeric_levels = pd.to_numeric(df["water_level_m"], errors="coerce")
    nan_mask = numeric_levels.isna() | ~np.isfinite(numeric_levels)
    unphysical_mask = (numeric_levels < 0.0) | (numeric_levels > 300.0)

    flag_mask = pd.Series(False, index=df.index)
    if "data_quality_flag" in df.columns:
        bad_flags = {"E", "ERROR", "ERR", "S", "SUSPECT", "R", "REJECTED", "BAD", "INVALID"}
        flag_mask = df["data_quality_flag"].astype(str).str.strip().str.upper().isin(bad_flags)

    anomaly_mask = pd.Series(False, index=df.index)
    if "is_anomaly" in df.columns:
        anomaly_mask = df["is_anomaly"].fillna(False).astype(bool)

    invalid_mask = nan_mask | unphysical_mask | flag_mask | anomaly_mask
    excluded_count = int(invalid_mask.sum())
    valid_df = df[~invalid_mask].copy()

    screening_audit = {
        "total_readings_screened": total_screened,
        "valid_readings_count": int(len(valid_df)),
        "excluded_readings_count": excluded_count,
        "exclusion_breakdown": {
            "missing_or_non_finite": int(nan_mask.sum()),
            "unphysical_range": int(unphysical_mask.sum()),
            "quality_flag_suspect_or_error": int(flag_mask.sum()),
            "marked_anomaly": int(anomaly_mask.sum()),
        },
        "screening_rules": [
            "Exclude water_level_m < 0.0 m bgl (unphysical negative depth to water table)",
            "Exclude water_level_m > 300.0 m bgl (exceeds physical monitoring well depth in India)",
            "Exclude quality flags: E (Error), S (Suspect), R (Rejected), BAD, INVALID",
            "Exclude sensor readings flagged as anomalies (is_anomaly=True)",
        ],
    }

    if valid_df.empty:
        return _empty_agg_result(
            stn_count=len(station_ids),
            stn_ids=station_ids,
            dist=block_district,
            st=block_state,
            rationale=(
                f"Unassessed for {target_block}: All {total_screened} observations were excluded during data-quality "
                "screening (suspect/error flags, unphysical ranges, or anomalies)."
            ),
            screening=screening_audit,
        )

    valid_df["timestamp"] = pd.to_datetime(valid_df["timestamp"])
    valid_df["year"] = valid_df["timestamp"].dt.year
    valid_df["month"] = valid_df["timestamp"].dt.month
    valid_df["water_level_m"] = valid_df["water_level_m"].astype(float)

    def _process_season(season_months: list[int]) -> tuple[
        int, Optional[bool], Optional[float], Optional[float], str, list[dict], Optional[dict], Optional[dict], dict
    ]:
        season_df = valid_df[valid_df["month"].isin(season_months)]
        if season_df.empty:
            empty_sens = {
                "status": "insufficient_data",
                "outcome": "insufficient_data",
                "guideline_range_m_per_year": {"lower": 0.10, "upper": 0.20},
                "sen_slope_m_per_year": None,
                "p_value": None,
                "sen_slope_ci_95": None,
                "rationale": "No seasonal observations available for assessment.",
            }
            return 0, None, None, None, "insufficient_data", [], None, None, empty_sens

        # Step 1: Calculate seasonal averages per station per year first
        stn_yr = (
            season_df.groupby(["year", "station_id"])["water_level_m"]
            .agg(mean_level="mean", obs_count="count")
            .reset_index()
        )

        annual_records = []
        for y, group in stn_yr.groupby("year"):
            contributing_stns = sorted(group["station_id"].astype(str).unique().tolist())
            stn_count = len(contributing_stns)
            total_obs = int(group["obs_count"].sum())
            # Step 2: Equal station-year weighting (mean of station seasonal means)
            block_seasonal_mean = float(group["mean_level"].mean())
            is_rep = bool(stn_count >= min_stations_per_year)
            annual_records.append({
                "year": int(y),
                "mean_water_level_mbgl": round(block_seasonal_mean, 3),
                "contributing_stations_count": stn_count,
                "contributing_station_ids": contributing_stns,
                "total_readings_count": total_obs,
                "is_representative": is_rep,
                "representativeness_criterion": f">={min_stations_per_year} spatially distinct stations",
                "weighting_method": "equal_station_year_weighting",
            })

        annual_records.sort(key=lambda r: r["year"])
        rep_records = [r for r in annual_records if r["is_representative"]]
        years_count = len(rep_records)

        if years_count >= MIN_DECADAL_TREND_YEARS:
            y_vals = np.array([r["year"] for r in rep_records], dtype=float)
            lvl_vals = np.array([r["mean_water_level_mbgl"] for r in rep_records], dtype=float)

            # 1. Exploratory OLS Linear Regression Diagnostic (assuming i.i.d. residuals)
            reg = stats.linregress(y_vals, lvl_vals)
            ols_slope = float(reg.slope)
            ols_pval = float(reg.pvalue) if not np.isnan(reg.pvalue) else 1.0
            ols_r2 = float(reg.rvalue ** 2) if not np.isnan(reg.rvalue) else 0.0

            ols_diagnostic = {
                "method": "Ordinary Least Squares (OLS) Linear Regression",
                "status": "exploratory_diagnostic_only",
                "slope_m_per_year": round(ols_slope, 4),
                "p_value": round(ols_pval, 4),
                "r_squared": round(ols_r2, 4),
                "is_statistically_significant": bool(ols_pval < 0.05),
                "caveat": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
            }

            # 2. Serial-Correlation Robust Non-Parametric Test (Modified Mann-Kendall per Hamed & Rao, 1998)
            mmk_result = compute_modified_mann_kendall(lvl_vals, y_vals)

            slope = ols_slope
            p_val = ols_pval

            # 3. Threshold-sensitivity diagnostic against CGWB 0.10–0.20 m/yr guideline range
            ci_95 = mmk_result.get("sen_slope_ci_95") if mmk_result else None
            ci_l = ci_95.get("lower") if ci_95 else None
            ci_u = ci_95.get("upper") if ci_95 else None
            is_sig_mmk = mmk_result.get("is_statistically_significant", False) if mmk_result else False
            sen_slope_val = mmk_result.get("sen_slope_m_per_year", slope) if mmk_result else slope

            if not mmk_result.get("is_equidistant", True):
                sensitivity_res = {
                    "status": "not_evaluated",
                    "outcome": "not_evaluated",
                    "guideline_range_m_per_year": {"lower": 0.10, "upper": 0.20},
                    "sen_slope_m_per_year": sen_slope_val,
                    "p_value": None,
                    "sen_slope_ci_95": ci_95,
                    "rationale": "Missing calendar years or irregular annual intervals detected in observation series; Modified Mann-Kendall test is marked 'not_evaluated'.",
                }
            else:
                sensitivity_res = evaluate_trend_threshold_sensitivity(
                    sen_slope_m_per_year=sen_slope_val,
                    p_value=mmk_result.get("p_value", p_val) if mmk_result else p_val,
                    ci_lower=ci_l,
                    ci_upper=ci_u,
                    years_count=years_count,
                    min_years=MIN_DECADAL_TREND_YEARS,
                    lower_threshold_m_per_year=0.10,
                    upper_threshold_m_per_year=0.20,
                    is_statistically_significant=is_sig_mmk,
                )

            # Separation of statistical significance from hydrogeological significance:
            if threshold is None:
                trend_str = "not_evaluated"
                trend_decline = None
            elif not mmk_result.get("is_equidistant", True):
                # Non-equidistant missing calendar years violate Hamed & Rao (1998) equidistant assumptions
                trend_str = "not_evaluated"
                trend_decline = None
            else:
                thresh_val = float(threshold)
                # Significant decline requires:
                # (a) hydrogeological significance: slope >= threshold
                # (b) supporting significance / positive deepening: slope > 0 and supporting statistical evidence
                # Both exploratory OLS p < 0.05 and serial-correlation robust MMK significance are required
                is_decline = bool(slope >= thresh_val and (ols_pval < 0.05 and is_sig_mmk))
                trend_str = "declining" if is_decline else "no_decline"
                trend_decline = is_decline
        else:
            slope = None
            p_val = None
            trend_str = "insufficient_data"
            trend_decline = None
            ols_diagnostic = None
            mmk_result = None
            sensitivity_res = {
                "status": "insufficient_data",
                "outcome": "insufficient_data",
                "guideline_range_m_per_year": {"lower": 0.10, "upper": 0.20},
                "sen_slope_m_per_year": None,
                "p_value": None,
                "sen_slope_ci_95": None,
                "rationale": f"Insufficient data: {years_count} seasonal observations available (requires >= {MIN_DECADAL_TREND_YEARS} years).",
            }

        return years_count, trend_decline, slope, p_val, trend_str, annual_records, ols_diagnostic, mmk_result, sensitivity_res

    # Pre-monsoon: Months 4 and 5 (April-May)
    pre_years, pre_decline, pre_slope, pre_pval, pre_trend_str, pre_coverage, pre_ols, pre_mmk, pre_sens = _process_season([4, 5])

    # Post-monsoon: Months 10 and 11 (October-November)
    post_years, post_decline, post_slope, post_pval, post_trend_str, post_coverage, post_ols, post_mmk, post_sens = _process_season([10, 11])

    if pre_sens["outcome"] == "insufficient_data" or post_sens["outcome"] == "insufficient_data":
        overall_sens = "insufficient_data"
        overall_sens_rationale = "Decadal seasonal records are insufficient (< 10 years in one or both seasons)."
    elif pre_sens["outcome"] == "not_evaluated" or post_sens["outcome"] == "not_evaluated":
        overall_sens = "not_evaluated"
        overall_sens_rationale = "Seasonal trend criteria were not evaluated in one or both seasons."
    elif pre_sens["outcome"] == "significant_across_guideline_range" and post_sens["outcome"] == "significant_across_guideline_range":
        overall_sens = "significant_across_guideline_range"
        overall_sens_rationale = "Water table decline meets or exceeds the entire CGWB guideline range (>= 0.20 m/yr) in both pre-monsoon and post-monsoon seasons."
    elif pre_sens["outcome"] == "below_guideline_range" and post_sens["outcome"] == "below_guideline_range":
        overall_sens = "below_guideline_range"
        overall_sens_rationale = "Water table decline is demonstrably below the CGWB guideline range (< 0.10 m/yr) or not declining in both seasons."
    else:
        overall_sens = "threshold_sensitive"
        overall_sens_rationale = "Seasonal water table trends fall within or overlap the CGWB guideline range (0.10–0.20 m/yr); significance is sensitive to local formation storativity."

    coverage_sufficient = bool(pre_years >= MIN_DECADAL_TREND_YEARS and post_years >= MIN_DECADAL_TREND_YEARS)
    coverage_rationale = (
        f"Decadal coverage: pre-monsoon={pre_years} spatially representative years, post-monsoon={post_years} "
        f"spatially representative years (statutory threshold = {MIN_DECADAL_TREND_YEARS} years each, "
        f"with >= {min_stations_per_year} stations per representative year under hydrogeological network principles)."
    )

    return {
        "assessment_unit": target_block,
        "district": block_district,
        "state": block_state,
        "station_count": len(station_ids),
        "station_ids": station_ids,
        "weighting_method": "equal_station_year_weighting",
        "weighting_rationale": "Station-year seasonal averaging prevents high-frequency telemetry from overwhelming low-frequency seasonal observation wells.",
        "pre_monsoon_years_count": pre_years,
        "post_monsoon_years_count": post_years,
        "pre_monsoon_trend": pre_trend_str,
        "post_monsoon_trend": post_trend_str,
        "pre_monsoon_threshold_sensitivity": pre_sens["outcome"],
        "post_monsoon_threshold_sensitivity": post_sens["outcome"],
        "overall_trend_sensitivity": overall_sens,
        "pre_monsoon_threshold_sensitivity_rationale": pre_sens["rationale"],
        "post_monsoon_threshold_sensitivity_rationale": post_sens["rationale"],
        "overall_trend_sensitivity_rationale": overall_sens_rationale,
        "pre_monsoon_sen_slope_ci_95": pre_mmk.get("sen_slope_ci_95") if pre_mmk else None,
        "post_monsoon_sen_slope_ci_95": post_mmk.get("sen_slope_ci_95") if post_mmk else None,
        "pre_monsoon_trend_decline": pre_decline,
        "post_monsoon_trend_decline": post_decline,
        "pre_monsoon_slope_m_per_year": round(pre_slope, 4) if pre_slope is not None else None,
        "post_monsoon_slope_m_per_year": round(post_slope, 4) if post_slope is not None else None,
        "pre_monsoon_p_value": round(pre_pval, 4) if pre_pval is not None else None,
        "post_monsoon_p_value": round(post_pval, 4) if post_pval is not None else None,
        "pre_monsoon_exploratory_ols": pre_ols,
        "post_monsoon_exploratory_ols": post_ols,
        "pre_monsoon_modified_mann_kendall": pre_mmk,
        "post_monsoon_modified_mann_kendall": post_mmk,
        "significant_decline_threshold_m_per_year": threshold,
        "threshold_record": threshold_dict,
        "threshold_source_publication": thresh_rec.source_publication_title if thresh_rec else None,
        "threshold_source_url": thresh_rec.source_url if thresh_rec else None,
        "threshold_page_table_reference": thresh_rec.page_table_reference if thresh_rec else None,
        "threshold_hydrogeological_formation": thresh_rec.hydrogeological_formation if thresh_rec else None,
        "threshold_justification": thresh_rec.justification if thresh_rec else None,
        "statistical_limitations": OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
        "pre_monsoon_annual_coverage": pre_coverage,
        "post_monsoon_annual_coverage": post_coverage,
        "coverage_sufficient": coverage_sufficient,
        "spatial_representativeness_met": True,
        "min_stations_per_year": min_stations_per_year,
        "coverage_rationale": coverage_rationale,
        "data_quality_screening": screening_audit,
    }


def evaluate_assessment_unit(
    block_name: str,
    stage_of_extraction_pct: Optional[float],
    readings_df: Optional[pd.DataFrame] = None,
    stations_df: Optional[pd.DataFrame] = None,
    pre_monsoon_trend_decline: Optional[bool] = None,
    post_monsoon_trend_decline: Optional[bool] = None,
    pre_monsoon_years_count: Optional[int] = None,
    post_monsoon_years_count: Optional[int] = None,
    soe_source: Optional[str] = None,
    assessment_year: Optional[int | str] = None,
    require_authoritative_metadata: bool = False,
    min_stations_per_year: int = DEFAULT_MIN_STATIONS_PER_YEAR,
    district: Optional[str] = None,
    state: Optional[str] = None,
    pre_monsoon_trend: Optional[str] = None,
    post_monsoon_trend: Optional[str] = None,
    significant_decline_threshold_m_per_year: Optional[float] = None,
    fallback_to_documented_threshold: bool = True,
) -> Dict[str, Any]:
    """
    Perform statutory GEC-2015 assessment at the administrative assessment-unit level (block/taluk).
    Aggregates representative station observations across the unit if readings_df and stations_df are supplied.
    """
    agg_details = None
    if readings_df is not None and stations_df is not None:
        agg = aggregate_block_seasonal_trends(
            readings_df,
            stations_df,
            block_name,
            district=district,
            state=state,
            min_stations_per_year=min_stations_per_year,
            significant_decline_threshold_m_per_year=significant_decline_threshold_m_per_year,
            fallback_to_documented_threshold=fallback_to_documented_threshold,
        )
        agg_details = agg
        pre_monsoon_trend_decline = agg["pre_monsoon_trend_decline"]
        post_monsoon_trend_decline = agg["post_monsoon_trend_decline"]
        pre_monsoon_years_count = agg["pre_monsoon_years_count"]
        post_monsoon_years_count = agg["post_monsoon_years_count"]
        pre_monsoon_trend = agg.get("pre_monsoon_trend")
        post_monsoon_trend = agg.get("post_monsoon_trend")

    res = classify_gec2015_assessment_unit(
        stage_of_extraction_pct=stage_of_extraction_pct,
        pre_monsoon_trend_decline=pre_monsoon_trend_decline,
        post_monsoon_trend_decline=post_monsoon_trend_decline,
        assessment_unit=block_name,
        pre_monsoon_years_count=pre_monsoon_years_count,
        post_monsoon_years_count=post_monsoon_years_count,
        soe_source=soe_source,
        assessment_year=assessment_year,
        require_authoritative_metadata=require_authoritative_metadata,
        pre_monsoon_trend=pre_monsoon_trend,
        post_monsoon_trend=post_monsoon_trend,
        significant_decline_threshold_m_per_year=significant_decline_threshold_m_per_year if significant_decline_threshold_m_per_year is not None else (agg_details.get("significant_decline_threshold_m_per_year") if agg_details else None),
        fallback_to_documented_threshold=fallback_to_documented_threshold,
        pre_monsoon_threshold_sensitivity=agg_details.get("pre_monsoon_threshold_sensitivity") if agg_details else None,
        post_monsoon_threshold_sensitivity=agg_details.get("post_monsoon_threshold_sensitivity") if agg_details else None,
        overall_trend_sensitivity=agg_details.get("overall_trend_sensitivity") if agg_details else None,
        pre_monsoon_sen_slope_ci_95=agg_details.get("pre_monsoon_sen_slope_ci_95") if agg_details else None,
        post_monsoon_sen_slope_ci_95=agg_details.get("post_monsoon_sen_slope_ci_95") if agg_details else None,
    )

    if agg_details:
        res["aggregation_details"] = agg_details
        res["weighting_method"] = agg_details.get("weighting_method")
        res["pre_monsoon_annual_coverage"] = agg_details.get("pre_monsoon_annual_coverage", [])
        res["post_monsoon_annual_coverage"] = agg_details.get("post_monsoon_annual_coverage", [])
        res["pre_monsoon_threshold_sensitivity"] = agg_details.get("pre_monsoon_threshold_sensitivity")
        res["post_monsoon_threshold_sensitivity"] = agg_details.get("post_monsoon_threshold_sensitivity")
        res["overall_trend_sensitivity"] = agg_details.get("overall_trend_sensitivity")
        res["pre_monsoon_threshold_sensitivity_rationale"] = agg_details.get("pre_monsoon_threshold_sensitivity_rationale")
        res["post_monsoon_threshold_sensitivity_rationale"] = agg_details.get("post_monsoon_threshold_sensitivity_rationale")
        res["overall_trend_sensitivity_rationale"] = agg_details.get("overall_trend_sensitivity_rationale")
        res["pre_monsoon_sen_slope_ci_95"] = agg_details.get("pre_monsoon_sen_slope_ci_95")
        res["post_monsoon_sen_slope_ci_95"] = agg_details.get("post_monsoon_sen_slope_ci_95")
        res["pre_monsoon_slope_m_per_year"] = agg_details.get("pre_monsoon_slope_m_per_year")
        res["post_monsoon_slope_m_per_year"] = agg_details.get("post_monsoon_slope_m_per_year")
        res["pre_monsoon_p_value"] = agg_details.get("pre_monsoon_p_value")
        res["post_monsoon_p_value"] = agg_details.get("post_monsoon_p_value")
        res["pre_monsoon_exploratory_ols"] = agg_details.get("pre_monsoon_exploratory_ols")
        res["post_monsoon_exploratory_ols"] = agg_details.get("post_monsoon_exploratory_ols")
        res["pre_monsoon_modified_mann_kendall"] = agg_details.get("pre_monsoon_modified_mann_kendall")
        res["post_monsoon_modified_mann_kendall"] = agg_details.get("post_monsoon_modified_mann_kendall")
        res["significant_decline_threshold_m_per_year"] = agg_details.get("significant_decline_threshold_m_per_year")
        res["threshold_record"] = agg_details.get("threshold_record", res.get("threshold_record"))
        res["threshold_source_publication"] = agg_details.get("threshold_source_publication", res.get("threshold_source_publication"))
        res["threshold_source_url"] = agg_details.get("threshold_source_url", res.get("threshold_source_url"))
        res["threshold_page_table_reference"] = agg_details.get("threshold_page_table_reference", res.get("threshold_page_table_reference"))
        res["threshold_hydrogeological_formation"] = agg_details.get("threshold_hydrogeological_formation", res.get("threshold_hydrogeological_formation"))
        res["threshold_justification"] = agg_details.get("threshold_justification", res.get("threshold_justification"))
        res["statistical_limitations"] = agg_details.get("statistical_limitations", OLS_AUTOCORRELATION_LIMITATIONS_NOTE)
        res["station_count"] = agg_details.get("station_count", 0)
        res["station_ids"] = agg_details.get("station_ids", [])
        res["data_quality_screening"] = agg_details.get("data_quality_screening")
        res["spatial_representativeness_met"] = agg_details.get("spatial_representativeness_met", False)
        res["coverage_sufficient"] = agg_details.get("coverage_sufficient", False)
        if not agg_details.get("coverage_sufficient", False):
            # When seasonal coverage is insufficient, retain verified official category
            # and report trend validation status as insufficient_data.
            res["trend_validation_status"] = "insufficient_data"
            res["trend_validation_reason"] = agg_details.get("coverage_rationale", res.get("trend_validation_reason"))

    return res


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
        "pre_monsoon_years_count":    pre_years,
        "post_monsoon_years_count":   post_years,
        "pre_monsoon_trend_decline":  pre_decline,
        "post_monsoon_trend_decline": post_decline,
        "is_point_level_well_trend":  True,
        "note": "Point-level observation well trend. Cannot be substituted for administrative assessment-unit trend evidence.",
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
    # Remove district fallback: assessment unit must be the administrative block/taluk
    raw_block = station_meta.get("block")
    assessment_unit_name = (
        str(raw_block).strip()
        if raw_block and str(raw_block).strip().lower() not in ("unknown", "none", "unassigned", "")
        else None
    )

    # Never derive official block assessment from an individual station's historical trends.
    # Official block trends must be provided from administrative assessment-unit records or block aggregation.
    block_pre_dec = station_meta.get("block_pre_monsoon_trend_decline")
    block_post_dec = station_meta.get("block_post_monsoon_trend_decline")
    block_pre_yrs = station_meta.get("block_pre_monsoon_years")
    block_post_yrs = station_meta.get("block_post_monsoon_years")

    gec_assessment    = classify_gec2015_assessment_unit(
        stage_of_extraction_pct=stage_of_dev,
        pre_monsoon_trend_decline=block_pre_dec,
        post_monsoon_trend_decline=block_post_dec,
        assessment_unit=assessment_unit_name,
        pre_monsoon_years_count=block_pre_yrs,
        post_monsoon_years_count=block_post_yrs,
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
        "alert_type":                 "exploratory_depth_screening_alert" if alert_required else None,
        "is_official_cgwb_classification": False,
        "statutory_disclaimer": (
            "Exploratory point-level depth screening alert based on local well water depth (<8m Safe, 8–15m Semi-Critical, "
            "15–25m Critical, >25m Over-Exploited). Does not constitute an official statutory CGWB GEC-2015 administrative block assessment."
        ),
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
        "alert_type":                  None,
        "is_official_cgwb_classification": False,
        "statutory_disclaimer":        "Exploratory point-level depth screening indicator. Does not constitute an official statutory CGWB GEC-2015 administrative block assessment.",
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
