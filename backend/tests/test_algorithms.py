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
    """Verify statutory GEC-2015 category boundaries & decadal trend rules."""
    # Guard: Missing assessment unit name returns unassessed
    res_no_unit = classify_gec2015_assessment_unit(
        70.0,
        pre_monsoon_trend_decline=False,
        post_monsoon_trend_decline=False,
        assessment_unit=None,
        pre_monsoon_years_count=10,
        post_monsoon_years_count=10,
    )
    assert res_no_unit["category"] == "unassessed"
    assert "administrative assessment unit" in res_no_unit["rationale"]

    # Guard: Missing seasonal trend years count returns unassessed
    res_missing_count = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=None, post_monsoon_years_count=10
    )
    assert res_missing_count["category"] == "unassessed"
    assert "Insufficient statutory seasonal trend evidence" in res_missing_count["rationale"]

    # Guard: Missing SOE (None or negative) returns unassessed
    res_no_soe = classify_gec2015_assessment_unit(
        None, assessment_unit="Anekal", pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_no_soe["category"] == "unassessed"

    # SOE <= 70% with verified 10-year pre/post decadal trends
    # No trend declines -> Safe
    res_safe = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_safe["category"] == "safe"

    # SOE <= 70% with single decline -> Still Safe under GEC-2015
    res_safe_one = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_safe_one["category"] == "safe"

    # SOE <= 70% with dual decline -> Semi-Critical (reassessed)
    res_semi_dual = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=True, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_semi_dual["category"] == "semi_critical"

    # 70% < SOE <= 90% -> Semi-Critical
    res_semi_71 = classify_gec2015_assessment_unit(
        70.01, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_semi_71["category"] == "semi_critical"

    res_semi_90 = classify_gec2015_assessment_unit(
        90.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_semi_90["category"] == "semi_critical"

    # 90% < SOE <= 100%
    # Without trend decline -> Semi-Critical
    res_90_notrend = classify_gec2015_assessment_unit(
        95.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_90_notrend["category"] == "semi_critical"

    # With trend decline -> Critical
    res_90_trend = classify_gec2015_assessment_unit(
        95.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_90_trend["category"] == "critical"

    # SOE > 100% -> Over-Exploited (draft exceeds Annual Extractable Groundwater Resource)
    res_oe_100_1 = classify_gec2015_assessment_unit(
        100.01, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_oe_100_1["category"] == "over_exploited"

    res_oe_135 = classify_gec2015_assessment_unit(
        135.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=True, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_oe_135["category"] == "over_exploited"


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

    # Scenario D: Station with block name but NO administrative assessment-unit trends returns unassessed
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
    # Individual well trends are NEVER used as official block trends
    assert res_d["gec_assessment"]["category"] == "unassessed"
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
        # A3: deep (22m), severe decline (+0.25m/yr)
        readings.append({"station_id": "STN_A3", "timestamp": pd.Timestamp(f"{2010+yr}-05-10"), "water_level_m": 20.0 + yr * 0.25})
        readings.append({"station_id": "STN_A3", "timestamp": pd.Timestamp(f"{2010+yr}-11-10"), "water_level_m": 18.0 + yr * 0.25})

    readings_df = pd.DataFrame(readings)

    # Aggregated block seasonal trends
    agg = aggregate_block_seasonal_trends(readings_df, stations, "Anekal")
    assert agg["assessment_unit"] == "Anekal"
    assert agg["station_count"] == 3
    assert agg["pre_monsoon_years_count"] == 12
    assert agg["post_monsoon_years_count"] == 12
    # Mean of slopes (-0.05 + 0.0 + 0.25)/3 = +0.0667 m/yr -> Net block decline
    assert agg["pre_monsoon_trend_decline"] is True
    assert agg["post_monsoon_trend_decline"] is True

    # Assessment of block with SOE = 68% and dual decline -> Semi-Critical per GEC-2015
    block_eval = evaluate_assessment_unit("Anekal", stage_of_extraction_pct=68.0, readings_df=readings_df, stations_df=stations)
    assert block_eval["category"] == "semi_critical"
    assert block_eval["assessment_unit"] == "Anekal"


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


def test_incomplete_seasonal_records_return_unassessed():
    """Verify that missing or <10 years pre- or post-monsoon trend records return unassessed."""
    # Missing pre-monsoon count
    r1 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=None, post_monsoon_years_count=10
    )
    assert r1["category"] == "unassessed"

    # Missing post-monsoon count
    r2 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=None
    )
    assert r2["category"] == "unassessed"

    # Incomplete pre-monsoon (<10 years)
    r3 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=9, post_monsoon_years_count=10
    )
    assert r3["category"] == "unassessed"

    # Incomplete post-monsoon (<10 years)
    r4 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=8
    )
    assert r4["category"] == "unassessed"

    # Arbitrary annual count without seasonal pre/post counts must NOT pass
    r5 = classify_gec2015_assessment_unit(
        70.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", trend_years_count=20
    )
    assert r5["category"] == "unassessed"


def test_zero_soe_validation():
    """Verify that a legitimate 0.0% extraction is valid and evaluated as Safe, while negative SOE is rejected."""
    # 0.0% extraction with verified decadal trends is valid -> Safe
    res_zero = classify_gec2015_assessment_unit(
        0.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_zero["category"] == "safe"
    assert res_zero["stage_of_extraction_pct"] == 0.0

    # 0.0% extraction with dual trend decline -> Semi-Critical
    res_zero_dual = classify_gec2015_assessment_unit(
        0.0, pre_monsoon_trend_decline=True, post_monsoon_trend_decline=True, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_zero_dual["category"] == "semi_critical"

    # Strictly negative SOE is invalid -> Unassessed
    res_neg = classify_gec2015_assessment_unit(
        -5.0, pre_monsoon_trend_decline=False, post_monsoon_trend_decline=False, assessment_unit="Anekal", pre_monsoon_years_count=10, post_monsoon_years_count=10
    )
    assert res_neg["category"] == "unassessed"


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
