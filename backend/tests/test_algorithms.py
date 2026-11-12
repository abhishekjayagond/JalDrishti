"""
backend/tests/test_algorithms.py — JalDrishti Analytical Algorithm Unit Tests
Tests Task 1 Fluctuation, Task 2 Recharge, and Task 3 CGWB Resource Evaluation.
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
from algorithms.task3_evaluation import evaluate_station, SAFE_MAX, SEMI_CRITICAL_MAX, CRITICAL_MAX


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


def test_task3_cgwb_evaluation():
    """Test Task 3 CGWB resource evaluation and status classification."""
    meta = {
        "station_id": "STN_TEST_01",
        "state": "Karnataka",
        "district": "Bangalore Rural",
        "well_depth_m": 60.0,
        "aquifer_type": "Granite",
    }

    # Safe: level 6.0m (< 8m)
    base_time = pd.Timestamp("2025-06-01 00:00:00", tz="Asia/Kolkata")
    safe_rows = [
        {"station_id": "STN_TEST_01", "timestamp": base_time + pd.Timedelta(days=i), "water_level_m": 6.0}
        for i in range(40)
    ]
    res_safe = evaluate_station(pd.DataFrame(safe_rows), meta, stage_of_dev=55.0)
    assert res_safe["status"] == "safe"

    # Semi-critical: level 12.0m (8m - 15m)
    semi_rows = [
        {"station_id": "STN_TEST_01", "timestamp": base_time + pd.Timedelta(days=i), "water_level_m": 12.0}
        for i in range(40)
    ]
    res_semi = evaluate_station(pd.DataFrame(semi_rows), meta, stage_of_dev=80.0)
    assert res_semi["status"] == "semi_critical"

    # Critical: level 20.0m (15m - 25m)
    crit_rows = [
        {"station_id": "STN_TEST_01", "timestamp": base_time + pd.Timedelta(days=i), "water_level_m": 20.0}
        for i in range(40)
    ]
    res_crit = evaluate_station(pd.DataFrame(crit_rows), meta, stage_of_dev=95.0)
    assert res_crit["status"] == "critical"

    # Over-exploited: level 32.0m (> 25m)
    over_rows = [
        {"station_id": "STN_TEST_01", "timestamp": base_time + pd.Timedelta(days=i), "water_level_m": 32.0}
        for i in range(40)
    ]
    res_over = evaluate_station(pd.DataFrame(over_rows), meta, stage_of_dev=115.0)
    assert res_over["status"] == "over_exploited"


def test_task3_boundary_conditions():
    """Verify exact CGWB project boundary thresholds: Safe <8m; Semi-Critical 8–<15m; Critical 15–25m; Over-Exploited >25m."""
    from algorithms.task3_evaluation import _classify_status

    # Safe: < 8.0m
    assert _classify_status(0.0, None) == "safe"
    assert _classify_status(7.99, None) == "safe"

    # Semi-Critical: 8.0m to < 15.0m (8.0 must NOT be Safe!)
    assert _classify_status(8.0, None) == "semi_critical"
    assert _classify_status(8.001, None) == "semi_critical"
    assert _classify_status(14.99, None) == "semi_critical"

    # Critical: 15.0m to <= 25.0m (15.0 must NOT be Semi-Critical!)
    assert _classify_status(15.0, None) == "critical"
    assert _classify_status(20.0, None) == "critical"
    assert _classify_status(25.0, None) == "critical"

    # Over-Exploited: > 25.0m (25.01 must be Over-Exploited)
    assert _classify_status(25.01, None) == "over_exploited"
    assert _classify_status(50.0, None) == "over_exploited"

    # Missing / Invalid / Non-finite values must NEVER be Safe -> must be unknown
    assert _classify_status(None, None) == "unknown"
    assert _classify_status(float("nan"), None) == "unknown"
    assert _classify_status(np.nan, None) == "unknown"
    assert _classify_status(float("inf"), None) == "unknown"

