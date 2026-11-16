"""
backend/tests/test_algorithms.py — JalDrishti Analytical Algorithm Unit Tests
Tests:
  - Task 1 Fluctuation
  - Task 2 Recharge
  - Task 3 Depth Indicator Tiers & Boundary Conditions
  - Task 3 GEC-2015 Official Assessment-Unit Categorization & Boundary Tests
  - Task 3 Conflicting Indicators (Point Depth vs GEC-2015)
  - Task 3 Cadence-Aware Depletion Rate (Annual Historical vs Sub-Daily Telemetry)
  - Task 3 Illustrative Depletion Horizon & Scientific Disclaimers
"""

import sys
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from algorithms.task1_fluctuation import analyze_fluctuations
from algorithms.task2_recharge import estimate_recharge
from algorithms.task3_evaluation import (
    evaluate_station,
    classify_depth_tier,
    classify_gec2015_assessment_unit,
    aggregate_block_seasonal_trends,
    evaluate_assessment_unit,
    compute_modified_mann_kendall,
    lookup_trusted_hydrogeological_threshold,
    register_trusted_hydrogeological_threshold,
    clear_trusted_hydrogeological_thresholds,
    HydrogeologicalThresholdRecord,
    OLS_AUTOCORRELATION_LIMITATIONS_NOTE,
    _compute_depletion_rate,
    _compute_years_to_depletion,
    SAFE_MAX,
    SEMI_CRITICAL_MAX,
    CRITICAL_MAX,
)


@pytest.fixture
def mock_station_readings():
    """Generates synthetic hourly DWLR readings for 14 days."""
    base_time = pd.Timestamp("2025-06-01 00:00:00", tz="Asia/Kolkata")
    records = []
    # 14 days * 24 hours = 336 readings
    for i in range(336):
        records.append({
            "station_id": "STN_TEST_01",
            "timestamp": base_time + pd.Timedelta(hours=i),
            # Slowly dropping water level (increasing depth) from 7.0m to 7.8m
            "water_level_m": 7.0 + (i * 0.0024),
            "data_quality_flag": "G",
            "is_anomaly": False,
        })
    return pd.DataFrame(records)


@pytest.fixture
def mock_rainfall():
    """Generates synthetic daily rainfall for the period."""
    return pd.DataFrame({
        "state": ["Karnataka", "Karnataka", "Karnataka"],
        "district": ["Bangalore Rural", "Bangalore Rural", "Bangalore Rural"],
        "date": [
            pd.Timestamp("2025-06-03").date(),
            pd.Timestamp("2025-06-04").date(),
            pd.Timestamp("2025-06-05").date(),
        ],
        "rainfall_mm": [0.0, 45.0, 20.0],
    })


def test_task1_fluctuation(mock_station_readings):
    """Test Task 1 water level fluctuation analytics."""
    res = analyze_fluctuations(mock_station_readings, "STN_TEST_01")
    assert res["station_id"] == "STN_TEST_01"
    assert "rate_per_hour" in res
    assert "rate_per_day" in res
    assert "trend_direction" in res
    assert "current_level_m" in res
    assert res["current_level_m"] > 7.0


def test_task2_recharge(mock_station_readings, mock_rainfall):
    """Test Task 2 dynamic recharge estimation."""
    meta = {
        "station_id": "STN_TEST_01",
        "state": "Karnataka",
        "district": "Bangalore Rural",
        "aquifer_type": "Granite",
        "well_depth_m": 80.0,
    }
    res = estimate_recharge(mock_station_readings, mock_rainfall, meta)
    assert res["station_id"] == "STN_TEST_01"
    assert res["aquifer_type"] == "Granite"
    assert "recharge_rate_m_per_day" in res
    assert "zone_status" in res


def test_task3_depth_indicator_boundaries():
    """Verify point-level depth indicator boundaries (<8m, 8–<15m, 15–25m, >25m)."""
    # Safe Depth: < 8.0m
    safe_0 = classify_depth_tier(0.0)
    assert safe_0["tier"] == "safe"
    assert "Safe Depth" in safe_0["tier_label"]

    safe_edge = classify_depth_tier(7.999)
    assert safe_edge["tier"] == "safe"

    # Semi-Critical Depth: 8.0m to < 15.0m (8.0m must NOT be safe!)
    semi_8 = classify_depth_tier(8.0)
    assert semi_8["tier"] == "semi_critical"
    assert "Semi-Critical" in semi_8["tier_label"]

    semi_14 = classify_depth_tier(14.99)
    assert semi_14["tier"] == "semi_critical"

    # Critical Depth: 15.0m to <= 25.0m (15.0m must NOT be semi-critical!)
    crit_15 = classify_depth_tier(15.0)
    assert crit_15["tier"] == "critical"
    assert "Critical" in crit_15["tier_label"]

    crit_25 = classify_depth_tier(25.0)
    assert crit_25["tier"] == "critical"

    # Over-Exploited Depth: > 25.0m
    over_25 = classify_depth_tier(25.01)
    assert over_25["tier"] == "over_exploited"
    assert "Over-Exploited" in over_25["tier_label"]

    # Non-finite / Missing
    assert classify_depth_tier(None)["tier"] == "unknown"
    assert classify_depth_tier(float("nan"))["tier"] == "unknown"


def test_gec2015_boundary_conditions():
    """Verify statutory GEC-2015 category boundaries & independent decadal trend validation."""
    # Guard: Missing assessment unit name returns unassessed
    res_no_unit = classify_gec2015_assessment_unit(
        70.0,
        pre_monsoon_trend_decline=False,
        post_monsoon_trend_decline=False,
        assessment_unit=None,
        pre_monsoon_years_count=10,
        post_monsoon_years_count=10,
    )
    assert res_no_unit["official_category"] == "unassessed"
    assert res_no_unit["category"] == "unassessed"
    assert "administrative assessment unit" in res_no_unit["rationale"]

    # Incomplete seasonal trend years count retains official category and sets insufficient_data
    res_missing_count = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=None, post_monsoon_years_count=10
    )
    assert res_missing_count["official_category"] == "safe"
    assert res_missing_count["category"] == "safe"
    assert res_missing_count["trend_validation_status"] == "insufficient_data"
    assert "Insufficient statutory seasonal trend records" in res_missing_count["trend_validation_reason"]

    # Guard: Missing SOE (None or negative) returns unassessed
    res_no_soe = classify_gec2015_assessment_unit(
        None, assessment_unit="Anekal", pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_no_soe["official_category"] == "unassessed"
    assert res_no_soe["category"] == "unassessed"

    # SOE <= 70% with verified 10-year pre/post decadal trends
    # No trend declines -> Safe, consistent
    res_safe = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_safe["official_category"] == "safe"
    assert res_safe["category"] == "safe"
    assert res_safe["trend_validation_status"] == "consistent"

    # SOE <= 70% with single decline -> Still Safe and consistent under GEC-2015
    res_safe_one = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_safe_one["official_category"] == "safe"
    assert res_safe_one["category"] == "safe"
    assert res_safe_one["trend_validation_status"] == "consistent"

    # SOE <= 70% with dual decline -> Safe official category, advisory needs_reassessment warning
    res_semi_dual = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=True, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_semi_dual["official_category"] == "safe"
    assert res_semi_dual["category"] == "safe"
    assert res_semi_dual["trend_validation_status"] == "needs_reassessment"

    # 70% < SOE <= 90% -> Semi-Critical
    res_semi_71 = classify_gec2015_assessment_unit(
        70.01, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_semi_71["official_category"] == "semi_critical"
    assert res_semi_71["category"] == "semi_critical"
    assert res_semi_71["trend_validation_status"] == "consistent"

    res_semi_90 = classify_gec2015_assessment_unit(
        90.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_semi_90["official_category"] == "semi_critical"
    assert res_semi_90["category"] == "semi_critical"
    assert res_semi_90["trend_validation_status"] == "consistent"

    # 90% < SOE <= 100% -> Critical strictly based on quantity threshold
    res_90_notrend = classify_gec2015_assessment_unit(
        95.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_90_notrend["official_category"] == "critical"
    assert res_90_notrend["category"] == "critical"
    assert res_90_notrend["trend_validation_status"] == "consistent"

    res_90_trend = classify_gec2015_assessment_unit(
        95.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_90_trend["official_category"] == "critical"
    assert res_90_trend["category"] == "critical"
    assert res_90_trend["trend_validation_status"] == "consistent"

    # SOE > 100% -> Over-Exploited strictly based on quantity threshold
    # If neither trend exhibits decline -> advisory needs_reassessment warning
    res_oe_100_1 = classify_gec2015_assessment_unit(
        100.01, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_oe_100_1["official_category"] == "over_exploited"
    assert res_oe_100_1["category"] == "over_exploited"
    assert res_oe_100_1["trend_validation_status"] == "needs_reassessment"

    res_oe_135 = classify_gec2015_assessment_unit(
        135.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=True, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_oe_135["official_category"] == "over_exploited"
    assert res_oe_135["category"] == "over_exploited"
    assert res_oe_135["trend_validation_status"] == "consistent"


def test_conflicting_depth_and_gec_indicators():
    """
    Verify complete separation of point depth indicator and statutory GEC-2015 category.
    Never blend them into a single misleading status.
    """
    # Scenario A: Shallow well (4.5m, Safe Depth) in an Over-Exploited block (SOE = 115%)
    base_time = pd.Timestamp("2010-01-01 00:00:00")
    shallow_readings = pd.DataFrame([
        {"station_id": "STN_SHALLOW_OE", "timestamp": base_time + pd.DateOffset(years=i), "water_level_m": 4.5}
        for i in range(12)
    ])
    meta_a = {
        "station_id": "STN_SHALLOW_OE",
        "district": "Bangalore Urban",
        "block": "Anekal",
        "well_depth_m": 40.0,
        "block_pre_monsoon_trend_decline": True,
        "block_post_monsoon_trend_decline": True,
        "block_pre_monsoon_years": 12,
        "block_post_monsoon_years": 12,
    }
    res_a = evaluate_station(shallow_readings, meta_a, stage_of_dev=115.0)

    # Point depth indicator is Safe Depth (<8m)
    assert res_a["depth_indicator"]["tier"] == "safe"
    assert res_a["depth_indicator"]["current_level_m"] == 4.5
    # GEC-2015 block categorization is Over-Exploited (>100% SOE)
    assert res_a["gec_assessment"]["category"] == "over_exploited"
    assert res_a["gec_assessment"]["stage_of_extraction_pct"] == 115.0
    # Both indicators are independently preserved in output
    assert res_a["depth_indicator"]["tier"] != res_a["gec_assessment"]["category"]
    assert res_a["is_station_official_assessment"] is False

    # Scenario B: Deep well (27.5m, Over-Exploited Depth) in a Safe block (SOE = 52%)
    records_b = []
    for yr in range(12):
        records_b.append({"station_id": "STN_DEEP_SAFE", "timestamp": pd.Timestamp(f"{2010+yr}-05-15"), "water_level_m": 27.5})
        records_b.append({"station_id": "STN_DEEP_SAFE", "timestamp": pd.Timestamp(f"{2010+yr}-11-15"), "water_level_m": 26.0})
    deep_readings = pd.DataFrame(records_b)
    meta_b = {
        "station_id": "STN_DEEP_SAFE",
        "district": "Udupi",
        "block": "Karkala",
        "well_depth_m": 60.0,
        "block_pre_monsoon_trend_decline": False,
        "block_post_monsoon_trend_decline": False,
        "block_pre_monsoon_years": 12,
        "block_post_monsoon_years": 12,
    }
    res_b = evaluate_station(deep_readings, meta_b, stage_of_dev=52.0)

    assert res_b["depth_indicator"]["tier"] == "over_exploited"
    assert res_b["gec_assessment"]["category"] == "safe"
    assert res_b["depth_indicator"]["tier"] != res_b["gec_assessment"]["category"]

    # Scenario C: Station with unmapped block returns unassessed for GEC-2015
    records_c = []
    for yr in range(12):
        records_c.append({"station_id": "STN_UNMAPPED", "timestamp": pd.Timestamp(f"{2010+yr}-05-15"), "water_level_m": 27.5})
    unmapped_readings = pd.DataFrame(records_c)
    meta_c = {
        "station_id": "STN_UNMAPPED",
        "district": "Unknown",
        "block": "",
        "well_depth_m": 30.0,
    }
    res_c = evaluate_station(unmapped_readings, meta_c, stage_of_dev=52.0)
    assert res_c["gec_assessment"]["category"] == "unassessed"
    assert res_c["depth_indicator"]["tier"] == "over_exploited"

    # Scenario D: Station with block name but NO administrative assessment-unit trends
    records_d = []
    for yr in range(12):
        records_d.append({"station_id": "STN_NO_BLOCK_TRENDS", "timestamp": pd.Timestamp(f"{2010+yr}-05-15"), "water_level_m": 4.5})
    shallow_readings_d = pd.DataFrame(records_d)
    meta_d = {
        "station_id": "STN_NO_BLOCK_TRENDS",
        "district": "Bangalore Urban",
        "block": "Anekal",
        "well_depth_m": 40.0,
    }
    res_d = evaluate_station(shallow_readings_d, meta_d, stage_of_dev=65.0)
    # Individual well trends are NEVER used as official block trends.
    # The official category is Safe (derived from SOE 65.0%), and trend validation reports not_evaluated / insufficient_data.
    assert res_d["gec_assessment"]["official_category"] == "safe"
    assert res_d["gec_assessment"]["category"] == "safe"
    assert res_d["gec_assessment"]["trend_validation_status"] in ("not_evaluated", "insufficient_data")
    assert res_d["depth_indicator"]["tier"] == "safe"


def test_station_versus_block_aggregation():
    """
    Verify that multiple stations in an administrative assessment unit are aggregated
    across the block network and individual station trends do NOT override block classification.
    """
    # 3 stations in block "Anekal"
    stations = pd.DataFrame([
        {"station_id": "STN_A1", "block": "Anekal", "district": "Bangalore Urban"},
        {"station_id": "STN_A2", "block": "Anekal", "district": "Bangalore Urban"},
        {"station_id": "STN_A3", "block": "Anekal", "district": "Bangalore Urban"},
        {"station_id": "STN_OTHER", "block": "Nelamangala", "district": "Bangalore Rural"},
    ])

    readings = []
    for yr in range(12):
        # A1: shallow (4m), recovering slope (-0.05m/yr)
        readings.append({"station_id": "STN_A1", "timestamp": pd.Timestamp(f"{2010+yr}-05-10"), "water_level_m": 4.5 - yr * 0.05})
        readings.append({"station_id": "STN_A1", "timestamp": pd.Timestamp(f"{2010+yr}-11-10"), "water_level_m": 3.5 - yr * 0.05})
        # A2: moderate (12m), flat slope (0.00m/yr)
        readings.append({"station_id": "STN_A2", "timestamp": pd.Timestamp(f"{2010+yr}-05-10"), "water_level_m": 12.0})
        readings.append({"station_id": "STN_A2", "timestamp": pd.Timestamp(f"{2010+yr}-11-10"), "water_level_m": 11.0})
        # A3: deep (22m), severe decline (+0.55m/yr)
        readings.append({"station_id": "STN_A3", "timestamp": pd.Timestamp(f"{2010+yr}-05-10"), "water_level_m": 20.0 + yr * 0.55})
        readings.append({"station_id": "STN_A3", "timestamp": pd.Timestamp(f"{2010+yr}-11-10"), "water_level_m": 18.0 + yr * 0.55})

    readings_df = pd.DataFrame(readings)

    # Aggregated block seasonal trends (evaluated with configured decline threshold = 0.15 m/yr)
    agg = aggregate_block_seasonal_trends(
        readings_df, stations, "Anekal", significant_decline_threshold_m_per_year=0.15
    )
    assert agg["assessment_unit"] == "Anekal"
    assert agg["station_count"] == 3
    assert agg["pre_monsoon_years_count"] == 12
    assert agg["post_monsoon_years_count"] == 12
    # Mean of slopes (-0.05 + 0.0 + 0.55)/3 = +0.1667 m/yr -> Net block decline exceeding threshold (0.15 m/yr)
    assert agg["pre_monsoon_slope_m_per_year"] == pytest.approx(0.1667, abs=0.001)
    assert agg["pre_monsoon_trend_decline"] is True
    assert agg["post_monsoon_trend_decline"] is True

    # Assessment of block with SOE = 68% and dual decline:
    # Official category is Safe (SOE <= 70%), advisory trend validation warning is needs_reassessment.
    # The trend warning NEVER overwrites the official category.
    block_eval = evaluate_assessment_unit(
        "Anekal", stage_of_extraction_pct=68.0, readings_df=readings_df, stations_df=stations,
        significant_decline_threshold_m_per_year=0.15
    )
    assert block_eval["official_category"] == "safe"
    assert block_eval["category"] == "safe"
    assert block_eval["trend_validation_status"] == "needs_reassessment"
    assert block_eval["assessment_unit"] == "Anekal"

    # When no threshold is configured, unconfigured block evaluates to not_evaluated
    block_eval_not_eval = evaluate_assessment_unit(
        "Anekal", stage_of_extraction_pct=68.0, readings_df=readings_df, stations_df=stations,
        significant_decline_threshold_m_per_year=None, fallback_to_documented_threshold=False
    )
    assert block_eval_not_eval["official_category"] == "safe"
    assert block_eval_not_eval["trend_validation_status"] == "not_evaluated"


def test_missing_assessment_units_and_district_fallback_prohibited():
    """Verify that missing assessment units return unassessed and district fallback is strictly prohibited."""
    # Direct function calls with missing assessment unit
    assert classify_gec2015_assessment_unit(70.0, assessment_unit=None)["category"] == "unassessed"
    assert classify_gec2015_assessment_unit(70.0, assessment_unit="")["category"] == "unassessed"
    assert classify_gec2015_assessment_unit(70.0, assessment_unit="   ")["category"] == "unassessed"
    assert classify_gec2015_assessment_unit(70.0, assessment_unit="Unknown")["category"] == "unassessed"

    # evaluate_station with district present but block missing must NOT fall back to district
    readings = pd.DataFrame([
        {"station_id": "STN_NO_BLOCK", "timestamp": pd.Timestamp(f"{2010+yr}-05-10"), "water_level_m": 10.0}
        for yr in range(12)
    ])
    meta_no_block = {
        "station_id": "STN_NO_BLOCK",
        "district": "Bangalore Urban",
        "block": None,  # Missing block
    }
    res = evaluate_station(readings, meta_no_block, stage_of_dev=65.0)
    assert res["gec_assessment"]["assessment_unit"] is None
    assert res["gec_assessment"]["category"] == "unassessed"
    assert "No valid administrative assessment unit was specified" in res["gec_assessment"]["rationale"]


def test_incomplete_seasonal_records_retain_category_and_report_insufficient_data():
    """Verify that missing or <10 years pre- or post-monsoon trend records retain official category and report insufficient_data."""
    # Missing pre-monsoon count with verified SOE (70.0%)
    r1 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=None, post_monsoon_years_count=10
    )
    assert r1["official_category"] == "safe"
    assert r1["category"] == "safe"
    assert r1["trend_validation_status"] == "insufficient_data"
    assert r1["pre_monsoon_trend"] == "insufficient_data"

    # Missing post-monsoon count with verified SOE (70.0%)
    r2 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=None
    )
    assert r2["official_category"] == "safe"
    assert r2["category"] == "safe"
    assert r2["trend_validation_status"] == "insufficient_data"
    assert r2["post_monsoon_trend"] == "insufficient_data"

    # Incomplete pre-monsoon (<10 years)
    r3 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=9, post_monsoon_years_count=10
    )
    assert r3["official_category"] == "safe"
    assert r3["trend_validation_status"] == "insufficient_data"
    assert r3["pre_monsoon_trend"] == "insufficient_data"

    # Incomplete post-monsoon (<10 years)
    r4 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=8
    )
    assert r4["official_category"] == "safe"
    assert r4["trend_validation_status"] == "insufficient_data"
    assert r4["post_monsoon_trend"] == "insufficient_data"

    # Missing SOE always returns unassessed
    r_no_soe = classify_gec2015_assessment_unit(
        None, assessment_unit="Anekal", pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert r_no_soe["official_category"] == "unassessed"
    assert r_no_soe["category"] == "unassessed"
    assert r_no_soe["trend_validation_status"] == "not_evaluated"


def test_zero_soe_validation():
    """Verify that a legitimate 0.0% extraction is valid and evaluated as Safe, while negative SOE is rejected."""
    # 0.0% extraction with verified decadal trends is valid -> Safe, consistent
    res_zero = classify_gec2015_assessment_unit(
        0.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_zero["official_category"] == "safe"
    assert res_zero["category"] == "safe"
    assert res_zero["trend_validation_status"] == "consistent"
    assert res_zero["stage_of_extraction_pct"] == 0.0

    # 0.0% extraction with dual trend decline -> Safe official category, needs_reassessment trend validation status
    res_zero_dual = classify_gec2015_assessment_unit(
        0.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=True, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_zero_dual["official_category"] == "safe"
    assert res_zero_dual["category"] == "safe"
    assert res_zero_dual["trend_validation_status"] == "needs_reassessment"

    # Strictly negative SOE is invalid -> Unassessed
    res_neg = classify_gec2015_assessment_unit(
        -5.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_neg["official_category"] == "unassessed"
    assert res_neg["category"] == "unassessed"


def test_part1_comprehensive_gec2015_regression_suite():
    """
    Comprehensive regression suite for JalDrishti Part 1:
      1. All 4 SOE category boundaries (<=70%, 70-90%, 90-100%, >100%).
      2. Zero, negative, NaN, infinite, and None SOE values.
      3. Both seasonal trends declining at SOE <= 70% (needs_reassessment, official Safe retained).
      4. Neither seasonal trend declining at SOE > 100% (needs_reassessment, official Over-Exploited retained).
      5. Missing pre-monsoon or post-monsoon trends (insufficient_data, official category retained).
      6. Insufficient trend history (< 10 years, no invented trend result).
      7. Verified SOE with no local station history (not_evaluated / insufficient_data, official category retained).
      8. Trend warnings NEVER overwriting official categories.
    """
    # ── 1. All 4 SOE Category Boundaries ───────────────────────────────────────
    # Boundary 1: SOE = 70.0% -> Safe
    r_safe = classify_gec2015_assessment_unit(70.0, assessment_unit="BlockA", pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, pre_monsoon_years_count=10, post_monsoon_years_count=10)
    assert r_safe["official_category"] == "safe"
    assert r_safe["category"] == "safe"

    # Boundary 2: SOE = 70.01% -> Semi-Critical
    r_semi = classify_gec2015_assessment_unit(70.01, assessment_unit="BlockA", pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, pre_monsoon_years_count=10, post_monsoon_years_count=10)
    assert r_semi["official_category"] == "semi_critical"
    assert r_semi["category"] == "semi_critical"

    # Boundary 2b: SOE = 90.0% -> Semi-Critical
    r_semi_90 = classify_gec2015_assessment_unit(90.0, assessment_unit="BlockA", pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, pre_monsoon_years_count=10, post_monsoon_years_count=10)
    assert r_semi_90["official_category"] == "semi_critical"

    # Boundary 3: SOE = 90.01% -> Critical
    r_crit = classify_gec2015_assessment_unit(90.01, assessment_unit="BlockA", pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, pre_monsoon_years_count=10, post_monsoon_years_count=10)
    assert r_crit["official_category"] == "critical"
    assert r_crit["category"] == "critical"

    # Boundary 3b: SOE = 100.0% -> Critical
    r_crit_100 = classify_gec2015_assessment_unit(100.0, assessment_unit="BlockA", pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, pre_monsoon_years_count=10, post_monsoon_years_count=10)
    assert r_crit_100["official_category"] == "critical"

    # Boundary 4: SOE = 100.01% -> Over-Exploited
    r_oe = classify_gec2015_assessment_unit(100.01, assessment_unit="BlockA", pre_monsoon_trend_decline=True, post_monsoon_trend_decline=True, pre_monsoon_years_count=10, post_monsoon_years_count=10)
    assert r_oe["official_category"] == "over_exploited"
    assert r_oe["category"] == "over_exploited"

    # ── 2. Zero, Negative, NaN, Infinite, and None SOE ─────────────────────────
    # Zero SOE -> Safe
    r_zero = classify_gec2015_assessment_unit(0.0, assessment_unit="BlockA")
    assert r_zero["official_category"] == "safe"
    assert r_zero["stage_of_extraction_pct"] == 0.0

    # Negative SOE -> Unassessed
    r_neg = classify_gec2015_assessment_unit(-10.0, assessment_unit="BlockA")
    assert r_neg["official_category"] == "unassessed"
    assert r_neg["stage_of_extraction_pct"] is None

    # NaN SOE -> Unassessed
    r_nan = classify_gec2015_assessment_unit(float("nan"), assessment_unit="BlockA")
    assert r_nan["official_category"] == "unassessed"

    # Infinite SOE -> Unassessed
    r_inf = classify_gec2015_assessment_unit(float("inf"), assessment_unit="BlockA")
    assert r_inf["official_category"] == "unassessed"

    # None SOE -> Unassessed
    r_none = classify_gec2015_assessment_unit(None, assessment_unit="BlockA")
    assert r_none["official_category"] == "unassessed"

    # ── 3. Dual Seasonal Trend Decline at SOE <= 70% ───────────────────────────
    # Safe official category is NEVER overwritten; trend status reports needs_reassessment
    r_reassess_safe = classify_gec2015_assessment_unit(
        65.0,
        pre_monsoon_trend="declining",
        post_monsoon_trend="declining",
        assessment_unit="BlockA",
        pre_monsoon_years_count=12,
        post_monsoon_years_count=12,
    )
    assert r_reassess_safe["official_category"] == "safe"
    assert r_reassess_safe["category"] == "safe"
    assert r_reassess_safe["trend_validation_status"] == "needs_reassessment"
    assert r_reassess_safe["pre_monsoon_trend"] == "declining"
    assert r_reassess_safe["post_monsoon_trend"] == "declining"
    assert "reassessment per GEC-2015" in r_reassess_safe["trend_validation_reason"]

    # ── 4. Neither Seasonal Trend Declining at SOE > 100% ──────────────────────
    # Over-Exploited official category is NEVER overwritten; trend status reports needs_reassessment
    r_reassess_oe = classify_gec2015_assessment_unit(
        125.0,
        pre_monsoon_trend="no_decline",
        post_monsoon_trend="no_decline",
        assessment_unit="BlockA",
        pre_monsoon_years_count=15,
        post_monsoon_years_count=15,
    )
    assert r_reassess_oe["official_category"] == "over_exploited"
    assert r_reassess_oe["category"] == "over_exploited"
    assert r_reassess_oe["trend_validation_status"] == "needs_reassessment"
    assert r_reassess_oe["pre_monsoon_trend"] == "no_decline"
    assert r_reassess_oe["post_monsoon_trend"] == "no_decline"
    assert "potential localized recharge buffer" in r_reassess_oe["trend_validation_reason"]

    # ── 5. Missing Pre-Monsoon or Post-Monsoon Trends ─────────────────────────
    # Missing pre-monsoon trend -> insufficient_data, official category retained
    r_missing_pre = classify_gec2015_assessment_unit(
        80.0,
        pre_monsoon_trend=None,
        post_monsoon_trend="no_decline",
        assessment_unit="BlockA",
        pre_monsoon_years_count=None,
        post_monsoon_years_count=10,
    )
    assert r_missing_pre["official_category"] == "semi_critical"
    assert r_missing_pre["category"] == "semi_critical"
    assert r_missing_pre["trend_validation_status"] == "insufficient_data"
    assert r_missing_pre["pre_monsoon_trend"] == "insufficient_data"

    # Missing post-monsoon trend -> insufficient_data, official category retained
    r_missing_post = classify_gec2015_assessment_unit(
        80.0,
        pre_monsoon_trend="no_decline",
        post_monsoon_trend=None,
        assessment_unit="BlockA",
        pre_monsoon_years_count=10,
        post_monsoon_years_count=None,
    )
    assert r_missing_post["official_category"] == "semi_critical"
    assert r_missing_post["category"] == "semi_critical"
    assert r_missing_post["trend_validation_status"] == "insufficient_data"
    assert r_missing_post["post_monsoon_trend"] == "insufficient_data"

    # ── 6. Insufficient Trend History (<10 years) ─────────────────────────────
    # Does not invent a trend result
    r_insufficient = classify_gec2015_assessment_unit(
        92.0,
        pre_monsoon_trend="declining",
        post_monsoon_trend="declining",
        assessment_unit="BlockA",
        pre_monsoon_years_count=7,
        post_monsoon_years_count=8,
    )
    assert r_insufficient["official_category"] == "critical"
    assert r_insufficient["category"] == "critical"
    assert r_insufficient["trend_validation_status"] == "insufficient_data"
    assert r_insufficient["pre_monsoon_trend"] == "insufficient_data"
    assert r_insufficient["post_monsoon_trend"] == "insufficient_data"

    # ── 7. Verified SOE with No Local Station History ─────────────────────────
    r_no_history = classify_gec2015_assessment_unit(
        75.0,
        assessment_unit="BlockRemote",
        soe_source="CGWB Dynamic Ground Water Resources Assessment of India (2023)",
        assessment_year=2023,
    )
    assert r_no_history["official_category"] == "semi_critical"
    assert r_no_history["category"] == "semi_critical"
    assert r_no_history["trend_validation_status"] == "not_evaluated"
    assert r_no_history["pre_monsoon_trend"] is None
    assert r_no_history["post_monsoon_trend"] is None

    # ── 8. Trend Warnings NEVER Overwriting Official Categories ───────────────
    # Safe with dual decline remains Safe
    assert r_reassess_safe["official_category"] == "safe"
    assert r_reassess_safe["category"] == "safe"
    # Over-Exploited with no decline remains Over-Exploited
    assert r_reassess_oe["official_category"] == "over_exploited"
    assert r_reassess_oe["category"] == "over_exploited"


def test_cadence_aware_depletion_rate_annual():
    """
    Test depletion-rate calculation on 30-year annual CGWB historical data.
    Water level drops from 10.0m to 13.0m over 30 years -> 0.100 m/year.
    MUST NOT multiply by 365*96 (which would erroneously yield 3,504 m/year).
    """
    base_time = pd.Timestamp("1995-05-01 00:00:00")
    # 30 annual readings with steady 0.1 m/yr drop
    records = []
    for yr in range(30):
        records.append({
            "station_id": "STN_ANNUAL_30",
            "timestamp": base_time + pd.DateOffset(years=yr),
            "water_level_m": 10.0 + (yr * 0.1),
        })
    df_annual = pd.DataFrame(records)

    depletion = _compute_depletion_rate(df_annual)
    assert depletion["cadence"] == "annual_historical"
    assert depletion["reading_count"] == 30
    # Annual rate must be approximately 0.100 m/year
    assert pytest.approx(depletion["annual_rate_m"], abs=0.01) == 0.100
    assert depletion["annual_rate_m"] < 1.0  # Guard against 3,504 m/yr multiplier bug!
    assert depletion["trend_direction"] == "depleting"
    assert depletion["confidence"] == "high"


def test_cadence_aware_depletion_rate_telemetry():
    """
    Test depletion-rate calculation on 15-minute DWLR telemetry.
    Detects sub_daily_telemetry cadence and scales via fractional years.
    Guards against short duration and seasonal bias.
    """
    base_time = pd.Timestamp("2025-01-01 00:00:00")
    # 48 readings spaced 15 minutes apart (12 hours) with 0.05m drop
    records = []
    for i in range(48):
        records.append({
            "station_id": "STN_TELEMETRY",
            "timestamp": base_time + pd.Timedelta(minutes=15 * i),
            "water_level_m": 8.0 + (i * 0.001),
        })
    df_telem = pd.DataFrame(records)

    depletion = _compute_depletion_rate(df_telem)
    assert depletion["cadence"] == "sub_daily_telemetry"
    assert depletion["reading_count"] == 48
    # Short duration (<90 days) must have low confidence and unadjusted sub-seasonal bias
    assert depletion["confidence"] == "low"
    assert depletion["seasonal_bias"] == "unadjusted_sub_seasonal_transient"
    assert "autocorrelation_lag1" in depletion


def test_years_to_depletion_suppressed_when_unverified():
    """
    Verify years-to-depletion is suppressed from primary results
    unless verified drilled well depth and hydrogeology are present.
    """
    # Unverified well depth -> suppressed
    res_unverified = _compute_years_to_depletion(
        current_level_m=12.0, well_depth_m=50.0, annual_depletion=0.5, well_depth_verified=False
    )
    assert res_unverified["status"] == "suppressed_unverified_well_depth"
    assert res_unverified["is_dependable_prediction"] is False
    assert res_unverified["years"] is None
    assert "suppressed" in res_unverified["disclaimer"].lower()

    # Missing well depth -> suppressed
    res_none = _compute_years_to_depletion(
        current_level_m=12.0, well_depth_m=None, annual_depletion=0.5
    )
    assert res_none["status"] == "suppressed_unverified_well_depth"
    assert res_none["years"] is None

    # Verified drilled well depth and verified hydrogeology -> verified estimate
    res_verified = _compute_years_to_depletion(
        current_level_m=12.0, well_depth_m=50.0, annual_depletion=0.5, well_depth_verified=True, hydrogeology_verified=True
    )
    assert res_verified["status"] == "verified_hydrogeological_estimate"
    assert res_verified["is_dependable_prediction"] is True
    assert res_verified["years"] == round((50.0 - 12.0) / 0.5, 1)

    # Recovering water level -> None years
    rec = _compute_years_to_depletion(
        current_level_m=12.0, well_depth_m=50.0, annual_depletion=-0.2, well_depth_verified=True, hydrogeology_verified=True
    )
    assert rec["years"] is None
    assert rec["status"] == "stable_or_recovering"


def test_resource_availability_index_heuristic_meta():
    """Verify that RAI is documented as an exploratory unvalidated heuristic."""
    base_time = pd.Timestamp("2010-01-01 00:00:00")
    readings = pd.DataFrame([
        {"station_id": "STN_RAI", "timestamp": base_time + pd.DateOffset(years=i), "water_level_m": 6.5}
        for i in range(12)
    ])
    meta = {
        "station_id": "STN_RAI",
        "district": "Bangalore Urban",
        "block": "Bangalore North",
        "well_depth_m": 40.0,
    }
    res = evaluate_station(readings, meta, stage_of_dev=65.0)
    assert "resource_availability_index_meta" in res
    rai_meta = res["resource_availability_index_meta"]
    assert rai_meta["scientific_status"] == "exploratory_unvalidated_heuristic"
    assert rai_meta["is_statutory_cgwb_index"] is False
    assert "NOT an official CGWB metric" in rai_meta["disclaimer"]


def test_hydrogeological_trend_significance_and_thresholds():
    """
    Regression tests for Hydrogeological vs Statistical Significance in GEC-2015 Trend Validation:
      1. Statistically significant but hydrogeologically small positive slope:
         e.g. 0.02 m/yr deepening with p < 0.05, threshold = 0.15 m/yr -> not a significant decline.
      2. Decline meeting configured magnitude threshold:
         e.g. 0.20 m/yr >= 0.15 m/yr with p < 0.05 -> significant decline.
      3. Different configured thresholds:
         0.14 m/yr tested against 0.10 m/yr (declining) vs 0.20 m/yr (no decline).
      4. Missing threshold:
         When no defensible threshold is available -> trend_validation_status == 'not_evaluated'.
      5. Insufficient observations:
         < 10 years of decadal records -> trend_validation_status == 'insufficient_data'.
      6. Missing calendar years:
         e.g. 2011..2021 with 2015 missing (10 observations over 11-year span),
         verifies linear regression calculates rate on actual observation year coordinates in m/year.
    """
    # 2 stations in block "TestBlock" for spatial representativeness (>=2 stations per year)
    stations_df = pd.DataFrame([
        {"station_id": "STN_T1", "block": "TestBlock", "district": "TestDistrict", "state": "TestState"},
        {"station_id": "STN_T2", "block": "TestBlock", "district": "TestDistrict", "state": "TestState"},
    ])

    # ── 1. Statistically significant but hydrogeologically small positive slope ───────────
    # Deepening at exactly 0.02 m/yr over 12 years (p < 0.001), threshold = 0.15 m/yr
    readings_small = []
    for yr in range(2010, 2022):
        idx = yr - 2010
        # Pre-monsoon: May
        readings_small.append({"station_id": "STN_T1", "timestamp": pd.Timestamp(f"{yr}-05-10"), "water_level_m": 10.0 + idx * 0.02})
        readings_small.append({"station_id": "STN_T2", "timestamp": pd.Timestamp(f"{yr}-05-10"), "water_level_m": 12.0 + idx * 0.02})
        # Post-monsoon: Nov
        readings_small.append({"station_id": "STN_T1", "timestamp": pd.Timestamp(f"{yr}-11-10"), "water_level_m": 8.0 + idx * 0.02})
        readings_small.append({"station_id": "STN_T2", "timestamp": pd.Timestamp(f"{yr}-11-10"), "water_level_m": 10.0 + idx * 0.02})
    df_small = pd.DataFrame(readings_small)

    agg_small = aggregate_block_seasonal_trends(
        df_small, stations_df, "TestBlock", significant_decline_threshold_m_per_year=0.15
    )
    assert agg_small["pre_monsoon_slope_m_per_year"] == pytest.approx(0.02, abs=0.001)
    assert agg_small["pre_monsoon_p_value"] < 0.05  # Statistically significant
    assert agg_small["pre_monsoon_slope_m_per_year"] < 0.15  # Hydrogeologically small (< 0.15 m/yr)
    assert agg_small["pre_monsoon_trend"] == "no_decline"
    assert agg_small["pre_monsoon_trend_decline"] is False
    assert agg_small["post_monsoon_trend"] == "no_decline"
    assert agg_small["post_monsoon_trend_decline"] is False

    eval_small = evaluate_assessment_unit(
        "TestBlock", stage_of_extraction_pct=65.0, readings_df=df_small, stations_df=stations_df,
        significant_decline_threshold_m_per_year=0.15
    )
    assert eval_small["official_category"] == "safe"
    assert eval_small["trend_validation_status"] == "consistent"

    # ── 2. Decline meeting configured magnitude threshold ────────────────────────────────
    # Deepening at 0.20 m/yr over 12 years (>= 0.15 m/yr, p < 0.001)
    readings_decline = []
    for yr in range(2010, 2022):
        idx = yr - 2010
        readings_decline.append({"station_id": "STN_T1", "timestamp": pd.Timestamp(f"{yr}-05-10"), "water_level_m": 10.0 + idx * 0.20})
        readings_decline.append({"station_id": "STN_T2", "timestamp": pd.Timestamp(f"{yr}-05-10"), "water_level_m": 12.0 + idx * 0.20})
        readings_decline.append({"station_id": "STN_T1", "timestamp": pd.Timestamp(f"{yr}-11-10"), "water_level_m": 8.0 + idx * 0.20})
        readings_decline.append({"station_id": "STN_T2", "timestamp": pd.Timestamp(f"{yr}-11-10"), "water_level_m": 10.0 + idx * 0.20})
    df_decline = pd.DataFrame(readings_decline)

    agg_decline = aggregate_block_seasonal_trends(
        df_decline, stations_df, "TestBlock", significant_decline_threshold_m_per_year=0.15
    )
    assert agg_decline["pre_monsoon_slope_m_per_year"] == pytest.approx(0.20, abs=0.001)
    assert agg_decline["pre_monsoon_p_value"] < 0.05
    assert agg_decline["pre_monsoon_trend"] == "declining"
    assert agg_decline["pre_monsoon_trend_decline"] is True
    assert agg_decline["post_monsoon_trend"] == "declining"
    assert agg_decline["post_monsoon_trend_decline"] is True

    # At SOE 65% (Safe) with dual decline -> needs_reassessment advisory, official category remains Safe
    eval_decline = evaluate_assessment_unit(
        "TestBlock", stage_of_extraction_pct=65.0, readings_df=df_decline, stations_df=stations_df,
        significant_decline_threshold_m_per_year=0.15
    )
    assert eval_decline["official_category"] == "safe"
    assert eval_decline["trend_validation_status"] == "needs_reassessment"

    # ── 3. Different configured thresholds (0.10 m/yr vs 0.20 m/yr) ──────────────────────
    # Deepening at 0.14 m/yr
    readings_mid = []
    for yr in range(2010, 2022):
        idx = yr - 2010
        readings_mid.append({"station_id": "STN_T1", "timestamp": pd.Timestamp(f"{yr}-05-10"), "water_level_m": 10.0 + idx * 0.14})
        readings_mid.append({"station_id": "STN_T2", "timestamp": pd.Timestamp(f"{yr}-05-10"), "water_level_m": 12.0 + idx * 0.14})
        readings_mid.append({"station_id": "STN_T1", "timestamp": pd.Timestamp(f"{yr}-11-10"), "water_level_m": 8.0 + idx * 0.14})
        readings_mid.append({"station_id": "STN_T2", "timestamp": pd.Timestamp(f"{yr}-11-10"), "water_level_m": 10.0 + idx * 0.14})
    df_mid = pd.DataFrame(readings_mid)

    # Threshold 0.10 m/yr: 0.14 >= 0.10 -> Declining
    agg_thresh_10 = aggregate_block_seasonal_trends(
        df_mid, stations_df, "TestBlock", significant_decline_threshold_m_per_year=0.10
    )
    assert agg_thresh_10["pre_monsoon_trend"] == "declining"
    assert agg_thresh_10["pre_monsoon_trend_decline"] is True

    # Threshold 0.20 m/yr: 0.14 < 0.20 -> No Decline
    agg_thresh_20 = aggregate_block_seasonal_trends(
        df_mid, stations_df, "TestBlock", significant_decline_threshold_m_per_year=0.20
    )
    assert agg_thresh_20["pre_monsoon_trend"] == "no_decline"
    assert agg_thresh_20["pre_monsoon_trend_decline"] is False

    # ── 4. Missing threshold -> trend_validation_status == 'not_evaluated' ────────────────
    # Block "TestBlock" has no documented threshold in dictionary, and threshold is None
    agg_no_thresh = aggregate_block_seasonal_trends(
        df_decline, stations_df, "TestBlock", significant_decline_threshold_m_per_year=None,
        fallback_to_documented_threshold=False
    )
    assert agg_no_thresh["significant_decline_threshold_m_per_year"] is None
    assert agg_no_thresh["pre_monsoon_trend"] == "not_evaluated"
    assert agg_no_thresh["post_monsoon_trend"] == "not_evaluated"
    assert agg_no_thresh["pre_monsoon_trend_decline"] is None
    assert agg_no_thresh["post_monsoon_trend_decline"] is None

    eval_no_thresh = evaluate_assessment_unit(
        "TestBlock", stage_of_extraction_pct=65.0, readings_df=df_decline, stations_df=stations_df,
        significant_decline_threshold_m_per_year=None, fallback_to_documented_threshold=False
    )
    assert eval_no_thresh["official_category"] == "safe"
    assert eval_no_thresh["trend_validation_status"] == "not_evaluated"
    assert eval_no_thresh["pre_monsoon_trend"] == "not_evaluated"
    assert eval_no_thresh["post_monsoon_trend"] == "not_evaluated"
    assert "no defensible hydrogeological" in eval_no_thresh["trend_validation_reason"].lower()

    # ── 5. Insufficient observations (< 10 years) ─────────────────────────────────────────
    # Only 7 years of data (2015 to 2021)
    readings_7yrs = [r for r in readings_decline if r["timestamp"].year >= 2015]
    df_7yrs = pd.DataFrame(readings_7yrs)

    agg_7yrs = aggregate_block_seasonal_trends(
        df_7yrs, stations_df, "TestBlock", significant_decline_threshold_m_per_year=0.15
    )
    assert agg_7yrs["coverage_sufficient"] is False
    assert agg_7yrs["pre_monsoon_years_count"] == 7
    assert agg_7yrs["post_monsoon_years_count"] == 7
    assert agg_7yrs["pre_monsoon_trend"] == "insufficient_data"
    assert agg_7yrs["post_monsoon_trend"] == "insufficient_data"
    assert agg_7yrs["pre_monsoon_trend_decline"] is None

    eval_7yrs = evaluate_assessment_unit(
        "TestBlock", stage_of_extraction_pct=65.0, readings_df=df_7yrs, stations_df=stations_df,
        significant_decline_threshold_m_per_year=0.15
    )
    assert eval_7yrs["official_category"] == "safe"
    assert eval_7yrs["trend_validation_status"] == "insufficient_data"
    assert eval_7yrs["pre_monsoon_trend"] == "insufficient_data"
    assert eval_7yrs["post_monsoon_trend"] == "insufficient_data"

    # ── 6. Missing calendar years (e.g. 2011..2021 with 2015 missing) ────────────────────
    # 10 observation years across an 11-year span: [2011, 2012, 2013, 2014, 2016, 2017, 2018, 2019, 2020, 2021]
    years_with_gap = [2011, 2012, 2013, 2014, 2016, 2017, 2018, 2019, 2020, 2021]
    readings_gap = []
    for yr in years_with_gap:
        # Physical water table deepens by exactly 0.18 m per calendar year from base year 2011
        dt_yr = yr - 2011
        readings_gap.append({"station_id": "STN_T1", "timestamp": pd.Timestamp(f"{yr}-05-10"), "water_level_m": 10.0 + dt_yr * 0.18})
        readings_gap.append({"station_id": "STN_T2", "timestamp": pd.Timestamp(f"{yr}-05-10"), "water_level_m": 12.0 + dt_yr * 0.18})
        readings_gap.append({"station_id": "STN_T1", "timestamp": pd.Timestamp(f"{yr}-11-10"), "water_level_m": 8.0 + dt_yr * 0.18})
        readings_gap.append({"station_id": "STN_T2", "timestamp": pd.Timestamp(f"{yr}-11-10"), "water_level_m": 10.0 + dt_yr * 0.18})
    df_gap = pd.DataFrame(readings_gap)

    agg_gap = aggregate_block_seasonal_trends(
        df_gap, stations_df, "TestBlock", significant_decline_threshold_m_per_year=0.15
    )
    assert agg_gap["pre_monsoon_years_count"] == 10
    # Because actual observation year coordinates are used in linear regression (not array index positions):
    # The calculated slope is exactly 0.18 m/yr regardless of the 2015 calendar gap!
    assert agg_gap["pre_monsoon_slope_m_per_year"] == pytest.approx(0.18, abs=0.001)
    assert agg_gap["post_monsoon_slope_m_per_year"] == pytest.approx(0.18, abs=0.001)
    # However, because of the calendar gap (2015 missing), Modified Mann-Kendall detects non-equidistant spacing.
    # Hamed & Rao (1998) variance correction cannot assume adjacent array positions are equal 1-year lags without justification.
    # Therefore, Modified Mann-Kendall reports is_equidistant=False, and trend is marked 'not_evaluated' (never falsely declining or no_decline).
    assert agg_gap["pre_monsoon_modified_mann_kendall"]["is_equidistant"] is False
    assert agg_gap["pre_monsoon_modified_mann_kendall"]["trend_direction"] == "not_evaluated"
    assert agg_gap["pre_monsoon_trend"] == "not_evaluated"
    assert agg_gap["pre_monsoon_trend_decline"] is None


def test_modified_mann_kendall_serial_correlation():
    """
    Test Modified Mann-Kendall Trend Test for Autocorrelated Data (Hamed & Rao, 1998).
    Verifies:
      1. Correct identification of positive (deepening) linear trend.
      2. Correct identification of negative (rising/recovering) linear trend.
      3. Variance correction factor >= 1.0 on autocorrelated series.
      4. Numerical robustness on constant series (zero variance).
      5. Graceful handling of insufficient observations (n < 3).
      6. Tied values handling in baseline variance.
      7. Irregular annual observations & missing calendar years (non-equidistant spacing).
      8. Non-finite values filtering (NaN / Inf).
    """
    # 1. Linear deepening trend over 12 years (0.25 m/yr)
    t12 = np.arange(2010, 2022, dtype=float)
    y_deep = 10.0 + 0.25 * (t12 - 2010.0)
    res_deep = compute_modified_mann_kendall(y_deep, t12)
    assert res_deep["s_statistic"] == 66  # 12 * 11 / 2 = 66
    assert res_deep["kendall_tau"] == 1.0
    assert res_deep["sen_slope_m_per_year"] == pytest.approx(0.25, abs=0.001)
    assert res_deep["p_value"] < 0.001
    assert res_deep["is_statistically_significant"] is True
    assert res_deep["trend_direction"] == "declining"
    assert res_deep["variance_correction_factor"] >= 1.0
    assert res_deep["is_equidistant"] is True

    # 2. Linear rising trend (recovering water table, negative slope in m bgl)
    y_rise = 20.0 - 0.30 * (t12 - 2010.0)
    res_rise = compute_modified_mann_kendall(y_rise, t12)
    assert res_rise["s_statistic"] == -66
    assert res_rise["kendall_tau"] == -1.0
    assert res_rise["sen_slope_m_per_year"] == pytest.approx(-0.30, abs=0.001)
    assert res_rise["p_value"] < 0.001
    assert res_rise["is_statistically_significant"] is True
    assert res_rise["trend_direction"] == "rising"

    # 3. Series with strong positive autocorrelation in residuals
    t20 = np.arange(20, dtype=float)
    y_autocorr = 0.10 * t20 + np.sin(np.linspace(0, np.pi, 20))
    res_autocorr = compute_modified_mann_kendall(y_autocorr, t20)
    assert res_autocorr["variance_correction_factor"] > 1.0
    assert res_autocorr["modified_variance_s"] >= res_autocorr["variance_s"]
    assert res_autocorr["sen_slope_m_per_year"] == pytest.approx(0.10, abs=0.01)

    # 4. Perfectly constant series (zero variance edge case)
    y_const = np.full(12, 12.5)
    res_const = compute_modified_mann_kendall(y_const, t12)
    assert res_const["s_statistic"] == 0
    assert res_const["sen_slope_m_per_year"] == 0.0
    assert res_const["variance_correction_factor"] == 1.0
    assert res_const["is_statistically_significant"] is False
    assert res_const["trend_direction"] == "stable"

    # 5. Insufficient data (n < 3)
    res_few = compute_modified_mann_kendall(np.array([10.0, 11.0]))
    assert res_few["trend_direction"] == "insufficient_data"
    assert res_few["is_statistically_significant"] is False

    # 6. Tied values in observations
    # 10 values with consecutive ties: [10, 10, 11, 11, 12, 12, 13, 13, 14, 14]
    t10 = np.arange(2010, 2020, dtype=float)
    y_tied = np.array([10.0, 10.0, 11.0, 11.0, 12.0, 12.0, 13.0, 13.0, 14.0, 14.0])
    res_tied = compute_modified_mann_kendall(y_tied, t10)
    assert res_tied["is_equidistant"] is True
    assert res_tied["sen_slope_m_per_year"] == pytest.approx(0.50, abs=0.05)
    assert res_tied["is_statistically_significant"] is True
    assert res_tied["trend_direction"] == "declining"
    # Tied variance v0 must be strictly less than untied variance n(n-1)(2n+5)/18 = 10*9*25/18 = 125
    assert res_tied["variance_s"] < 125.0

    # 7. Irregular annual observations & missing calendar years (non-equidistant)
    # Missing year 2015: [2010, 2011, 2012, 2013, 2014, 2016, 2017, 2018, 2019, 2020]
    t_gapped = np.array([2010, 2011, 2012, 2013, 2014, 2016, 2017, 2018, 2019, 2020], dtype=float)
    y_gapped = 10.0 + 0.20 * (t_gapped - 2010.0)
    res_gapped = compute_modified_mann_kendall(y_gapped, t_gapped)
    assert res_gapped["is_equidistant"] is False
    assert res_gapped["trend_direction"] == "not_evaluated"
    assert res_gapped["variance_correction_factor"] is None
    assert res_gapped["p_value"] is None
    assert "Missing calendar years" in res_gapped["limitation_note"]

    # 8. Non-finite values (NaN / Inf) filtering
    y_nonfinite = np.array([10.0, np.nan, 12.0, np.inf, 14.0, 16.0, 18.0])
    t_nonfinite = np.array([2010.0, 2011.0, 2012.0, 2013.0, 2014.0, 2015.0, 2016.0])
    res_nf = compute_modified_mann_kendall(y_nonfinite, t_nonfinite)
    # After filtering NaN and Inf, remaining years are [2010, 2012, 2014, 2015, 2016] (gapped)
    assert res_nf["n_observations"] == 5
    assert res_nf["is_equidistant"] is False


def test_trend_significance_exploratory_ols_and_provenance():
    """
    Test separation of exploratory OLS diagnostics from serial-correlation robust MMK
    and authoritative threshold provenance reporting.
    """
    stations_df = pd.DataFrame([
        {"station_id": "STN_A1", "block": "Anekal", "district": "Bengaluru Urban", "state": "Karnataka"},
        {"station_id": "STN_A2", "block": "Anekal", "district": "Bengaluru Urban", "state": "Karnataka"},
    ])

    # 12 years of deepening data (0.22 m/yr)
    readings = []
    for yr in range(2010, 2022):
        dt = yr - 2010
        readings.append({"station_id": "STN_A1", "timestamp": pd.Timestamp(f"{yr}-05-15"), "water_level_m": 15.0 + dt * 0.22})
        readings.append({"station_id": "STN_A2", "timestamp": pd.Timestamp(f"{yr}-05-15"), "water_level_m": 16.0 + dt * 0.22})
        readings.append({"station_id": "STN_A1", "timestamp": pd.Timestamp(f"{yr}-11-15"), "water_level_m": 12.0 + dt * 0.22})
        readings.append({"station_id": "STN_A2", "timestamp": pd.Timestamp(f"{yr}-11-15"), "water_level_m": 13.0 + dt * 0.22})
    df = pd.DataFrame(readings)

    # 1. By default, unconfigured blocks have no threshold -> returns not_evaluated
    clear_trusted_hydrogeological_thresholds()
    agg_unconfigured = aggregate_block_seasonal_trends(df, stations_df, "Anekal")
    assert agg_unconfigured["significant_decline_threshold_m_per_year"] is None
    assert agg_unconfigured["threshold_record"] is None
    assert agg_unconfigured["threshold_source_publication"] is None
    assert agg_unconfigured["pre_monsoon_trend"] == "not_evaluated"
    assert agg_unconfigured["post_monsoon_trend"] == "not_evaluated"
    assert agg_unconfigured["pre_monsoon_trend_decline"] is None
    assert agg_unconfigured["post_monsoon_trend_decline"] is None

    # Exploratory OLS diagnostic is still calculated and explicitly labeled
    ols = agg_unconfigured["pre_monsoon_exploratory_ols"]
    assert ols is not None
    assert ols["status"] == "exploratory_diagnostic_only"
    assert ols["slope_m_per_year"] == pytest.approx(0.22, abs=0.001)
    assert ols["p_value"] < 0.01
    assert "Ordinary least-squares" in ols["caveat"]

    # Modified Mann-Kendall is present
    mmk = agg_unconfigured["pre_monsoon_modified_mann_kendall"]
    assert mmk is not None
    assert mmk["method"] == "Modified Mann-Kendall (Hamed & Rao, 1998)"
    assert mmk["sen_slope_m_per_year"] == pytest.approx(0.22, abs=0.001)
    assert mmk["is_statistically_significant"] is True

    # 2. When an authoritative threshold record is registered, it evaluates with full provenance
    test_rec = HydrogeologicalThresholdRecord(
        block="Anekal",
        state="Karnataka",
        district="Bengaluru Urban",
        threshold_m_per_year=0.15,
        source_publication_title="Test Groundwater Publication (CGWB)",
        source_url="https://cgwb.gov.in/sites/default/files/test.pdf",
        page_table_reference="Table 1, Page 10",
        hydrogeological_formation="Crystalline hard-rock granite/gneiss",
        justification="Verified test hard-rock threshold.",
    )
    register_trusted_hydrogeological_threshold(test_rec)
    try:
        agg_registered = aggregate_block_seasonal_trends(df, stations_df, "Anekal")
        assert agg_registered["significant_decline_threshold_m_per_year"] == 0.15
        assert agg_registered["threshold_record"] is not None
        assert agg_registered["threshold_record"]["block"] == "Anekal"
        assert agg_registered["threshold_source_url"] == "https://cgwb.gov.in/sites/default/files/test.pdf"
        assert agg_registered["pre_monsoon_trend"] == "declining"
        assert agg_registered["pre_monsoon_trend_decline"] is True
    finally:
        clear_trusted_hydrogeological_thresholds()

    # 3. Block with 12 years of representative stations but NO registered threshold -> returns not_evaluated
    stations_unsupported = pd.DataFrame([
        {"station_id": "STN_A1", "block": "UnsupportedBlockXYZ", "district": "Bengaluru Urban", "state": "Karnataka"},
        {"station_id": "STN_A2", "block": "UnsupportedBlockXYZ", "district": "Bengaluru Urban", "state": "Karnataka"},
    ])
    agg_unsupported = aggregate_block_seasonal_trends(df, stations_unsupported, "UnsupportedBlockXYZ")
    assert agg_unsupported["significant_decline_threshold_m_per_year"] is None
    assert agg_unsupported["threshold_record"] is None
    assert agg_unsupported["threshold_source_publication"] is None
    assert agg_unsupported["pre_monsoon_trend"] == "not_evaluated"
    assert agg_unsupported["post_monsoon_trend"] == "not_evaluated"


def test_threshold_sensitivity_exact_diagnostic_outcomes():
    """
    Item 2: Verify the 5 exact threshold-sensitivity diagnostic outcomes:
      - 'significant_across_guideline_range'
      - 'below_guideline_range'
      - 'threshold_sensitive'
      - 'insufficient_data'
      - 'not_evaluated'
    """
    from algorithms.task3_evaluation import evaluate_trend_threshold_sensitivity

    # 1. significant_across_guideline_range: slope >= 0.20, p < 0.05, CI lower >= 0.10
    r1 = evaluate_trend_threshold_sensitivity(
        sen_slope_m_per_year=0.25,
        p_value=0.001,
        ci_lower=0.18,
        ci_upper=0.32,
        years_count=12,
        min_years=10,
    )
    assert r1["outcome"] == "significant_across_guideline_range"
    assert r1["status"] == "significant_across_guideline_range"
    assert "meets or exceeds the entire CGWB guideline range" in r1["rationale"]

    # 2. threshold_sensitive (two sub-cases):
    # Sub-case A: 0.10 <= slope < 0.20, p < 0.05
    r2a = evaluate_trend_threshold_sensitivity(
        sen_slope_m_per_year=0.15,
        p_value=0.01,
        ci_lower=0.11,
        ci_upper=0.19,
        years_count=12,
    )
    assert r2a["outcome"] == "threshold_sensitive"
    assert "falls within CGWB guideline range" in r2a["rationale"]

    # Sub-case B: slope >= 0.20, p < 0.05, but CI lower extends below 0.10 m/yr
    r2b = evaluate_trend_threshold_sensitivity(
        sen_slope_m_per_year=0.22,
        p_value=0.02,
        ci_lower=0.05,
        ci_upper=0.39,
        years_count=12,
    )
    assert r2b["outcome"] == "threshold_sensitive"
    assert "interpretation is sensitive to local formation storativity" in r2b["rationale"]

    # 3. below_guideline_range (three sub-cases):
    # Sub-case A: slope < 0.10
    r3a = evaluate_trend_threshold_sensitivity(
        sen_slope_m_per_year=0.06,
        p_value=0.01,
        ci_lower=0.02,
        ci_upper=0.09,
        years_count=12,
    )
    assert r3a["outcome"] == "below_guideline_range"
    assert "below CGWB guideline range" in r3a["rationale"]

    # Sub-case B: non-significant (p >= 0.05)
    r3b = evaluate_trend_threshold_sensitivity(
        sen_slope_m_per_year=0.25,
        p_value=0.18,
        ci_lower=-0.05,
        ci_upper=0.55,
        years_count=12,
    )
    assert r3b["outcome"] == "below_guideline_range"
    assert "not statistically significant" in r3b["rationale"]

    # Sub-case C: recovering water table (slope <= 0.0)
    r3c = evaluate_trend_threshold_sensitivity(
        sen_slope_m_per_year=-0.12,
        p_value=0.001,
        ci_lower=-0.18,
        ci_upper=-0.06,
        years_count=12,
    )
    assert r3c["outcome"] == "below_guideline_range"
    assert "stable or recovering water table" in r3c["rationale"]

    # 4. insufficient_data: years_count < 10
    r4 = evaluate_trend_threshold_sensitivity(
        sen_slope_m_per_year=0.25,
        p_value=0.001,
        years_count=7,
        min_years=10,
    )
    assert r4["outcome"] == "insufficient_data"
    assert "requires >= 10 representative decadal years" in r4["rationale"]

    # 5. not_evaluated: missing inputs
    r5 = evaluate_trend_threshold_sensitivity(
        sen_slope_m_per_year=None,
        p_value=None,
        years_count=12,
    )
    assert r5["outcome"] == "not_evaluated"


def test_sens_slope_confidence_interval_properties():
    """
    Item 3: Verify non-parametric Sen's slope confidence interval (Sen 1968, Gilbert 1987).
    """
    from algorithms.task3_evaluation import compute_sens_slope_confidence_interval

    # Create synthetic pairwise slopes centered around 0.20 m/yr
    slopes = [0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.32]
    var_s = 20.0

    ci_low_95, ci_high_95 = compute_sens_slope_confidence_interval(slopes, var_s, confidence_level=0.95)
    assert ci_low_95 is not None and ci_high_95 is not None
    assert ci_low_95 <= ci_high_95
    assert ci_low_95 >= min(slopes)
    assert ci_high_95 <= max(slopes)

    # Higher confidence level (99%) produces wider interval than 90%
    ci_low_99, ci_high_99 = compute_sens_slope_confidence_interval(slopes, var_s, confidence_level=0.99)
    ci_low_90, ci_high_90 = compute_sens_slope_confidence_interval(slopes, var_s, confidence_level=0.90)

    width_99 = ci_high_99 - ci_low_99
    width_90 = ci_high_90 - ci_low_90
    assert width_99 >= width_90


def test_authoritative_registry_multi_year_cycles_and_summary_stats():
    """
    Item 4: Verify multi-year Karnataka assessment cycles (2023, 2024, 2025)
    and summary statistics cross-checked against official CGWB publications.
    """
    from app.services.assessment_unit_registry import (
        get_authoritative_summary_statistics,
        lookup_authoritative_record,
    )

    stats = get_authoritative_summary_statistics()
    assert stats["state"] == "Karnataka"
    assert stats["total_records_count"] >= 684
    assert stats["unique_assessment_units_count"] == 228

    cycles = stats["assessment_cycles"]
    assert 2023 in cycles
    assert 2024 in cycles
    assert 2025 in cycles

    # Verify 2025 official totals and publication URLs
    c2025 = cycles[2025]
    assert c2025["statewide_total_recharge_bcm"] == 19.28
    assert c2025["statewide_extractable_resource_bcm"] == 17.41
    assert c2025["statewide_gross_draft_bcm"] == 11.58
    assert c2025["statewide_stage_of_extraction_pct"] == 66.49
    assert "cgwb.gov.in" in c2025["publication_url"]
    assert "jalshakti-dowr.gov.in" in c2025["national_compilation_url"]

    # Verify 2024 official totals
    c2024 = cycles[2024]
    assert c2024["statewide_total_recharge_bcm"] == 18.09
    assert c2024["statewide_extractable_resource_bcm"] == 16.34
    assert c2024["statewide_gross_draft_bcm"] == 11.18
    assert c2024["statewide_stage_of_extraction_pct"] == 68.44

    # Verify multi-year lookups for Athni
    rec_2025 = lookup_authoritative_record("Athni", assessment_year=2025)
    assert rec_2025 is not None
    assert rec_2025.assessment_year == 2025
    assert rec_2025.stage_of_extraction_pct == 82.31

    rec_2024 = lookup_authoritative_record("Athni", assessment_year=2024)
    assert rec_2024 is not None
    assert rec_2024.assessment_year == 2024
    assert rec_2024.stage_of_extraction_pct == 83.90

    rec_2023 = lookup_authoritative_record("Athni", assessment_year=2023)
    assert rec_2023 is not None
    assert rec_2023.assessment_year == 2023
    assert rec_2023.stage_of_extraction_pct == 85.52

