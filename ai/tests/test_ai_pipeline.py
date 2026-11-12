import sys
import json
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline import load_clean, candidate_stations
from src.config import MODELS, METRICS_JSON, CALIBRATION_JSON, FORECAST_HORIZONS_JSON, PRODUCTION_MODEL, LR_MODEL
RAW = ROOT / "data/raw/phase1_karnataka_premonsoon_1994_2025.csv"


def test_cleaning_counts():
    df = load_clean(RAW)
    assert len(df) == 28544
    assert df.year.min() == 1994
    assert df.year.max() == 2025
    assert df.station_id.nunique() == 2112


def test_candidates():
    df = load_clean(RAW)
    cand = candidate_stations(df, 25)
    assert len(cand) == 390


def test_classify_gwl_depth_boundaries():
    """Verify CGWB project boundary thresholds: Safe <8m, Semi-Critical 8–<15m, Critical 15–25m, Over-Exploited >25m."""
    from service.app import classify_gwl_depth
    import numpy as np

    # Safe: < 8.0 m
    assert classify_gwl_depth(0.0) == "Safe"
    assert classify_gwl_depth(4.5) == "Safe"
    assert classify_gwl_depth(7.99) == "Safe"

    # Semi-Critical: 8.0 m to < 15.0 m (8.0 must NOT be Safe!)
    assert classify_gwl_depth(8.0) == "Semi-Critical"
    assert classify_gwl_depth(8.001) == "Semi-Critical"
    assert classify_gwl_depth(14.99) == "Semi-Critical"

    # Critical: 15.0 m to <= 25.0 m (15.0 must NOT be Semi-Critical!)
    assert classify_gwl_depth(15.0) == "Critical"
    assert classify_gwl_depth(20.0) == "Critical"
    assert classify_gwl_depth(25.0) == "Critical"

    # Over-Exploited: > 25.0 m (25.01 must be Over-Exploited)
    assert classify_gwl_depth(25.01) == "Over-Exploited"
    assert classify_gwl_depth(35.0) == "Over-Exploited"

    # Missing / Invalid / Non-finite values MUST NEVER be classified as Safe!
    assert classify_gwl_depth(None) == "Unavailable"
    assert classify_gwl_depth(float("nan")) == "Unavailable"
    assert classify_gwl_depth(np.nan) == "Unavailable"
    assert classify_gwl_depth(float("inf")) == "Unavailable"
    assert classify_gwl_depth(float("-inf")) == "Unavailable"
    assert classify_gwl_depth("invalid") == "Unavailable"


def test_forecast_distribution_and_unavailable():
    """Verify that predictions match actual ground truth distribution and unpredicted stations return Unavailable."""
    from service import app as ai_app
    ai_app._load()

    forecasts = ai_app.all_forecasts
    assert len(forecasts) == 390

    counts = {"Safe": 0, "Semi-Critical": 0, "Critical": 0, "Over-Exploited": 0, "Unavailable": 0}
    for stn_id, data in forecasts.items():
        risk = data["risk"]
        counts[risk] += 1

    # Exact honest distribution across 390 candidate stations
    assert counts["Safe"] == 315
    assert counts["Semi-Critical"] == 74
    assert counts["Critical"] == 1
    assert counts["Over-Exploited"] == 0
    assert counts["Unavailable"] == 0

    # Specifically check the Critical station
    assert forecasts["942ccfc29ecf"]["risk"] == "Critical"
    assert 15.0 <= forecasts["942ccfc29ecf"]["predicted_depth_m"] <= 25.0

    # Non-candidate station returns Unavailable
    unknown_risk = ai_app.classify_gwl_depth(forecasts.get("NON_EXISTENT_STATION", {}).get("predicted_depth_m"))
    assert unknown_risk == "Unavailable"


def test_chronological_4way_split_and_conformal():
    """Verify 4-way chronological split, separate calibration holdout, and non-empty exchangeability limitations."""
    assert METRICS_JSON.exists()
    assert CALIBRATION_JSON.exists()
    
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    conf = json.loads(CALIBRATION_JSON.read_text(encoding="utf-8"))
    
    split = metrics["split"]
    assert split["strategy"] == "4_way_chronological_split"
    
    train_years = set(split["train_years"])
    val_years = set(split["validation_years"])
    calib_years = set(split["calibration_years"])
    test_years = set(split["test_years"])
    
    # Strictly disjoint sets
    assert len(train_years.intersection(val_years)) == 0
    assert len(val_years.intersection(calib_years)) == 0
    assert len(calib_years.intersection(test_years)) == 0
    assert len(train_years.intersection(test_years)) == 0
    
    # Chronological ordering
    assert max(train_years) < min(val_years)
    assert max(val_years) < min(calib_years)
    assert max(calib_years) < min(test_years)
    
    # Conformal calibrated on calibration split (not validation!)
    assert conf["calibration_years"] == sorted(list(calib_years))
    assert conf["test_empirical_coverage_overall"] > 0.90
    assert "exchangeability_assumptions_and_limitations" in conf
    assert len(conf["exchangeability_assumptions_and_limitations"]) > 50


def test_model_selection_eligibility_and_production_artifact():
    """Verify model selection follows documented eligibility rules and separate production model exists."""
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    ms = metrics["model_selection"]
    
    assert ms["selected_model"] == "linear_regression"
    framework = ms["eligibility_framework"]
    assert framework["lstm"]["eligible"] is False
    assert "Sequence starvation" in framework["lstm"]["disqualification_reason"]
    assert framework["linear_regression"]["eligible"] is True
    
    # Separate artifacts exist
    assert PRODUCTION_MODEL.exists()
    assert LR_MODEL.exists()


def test_multi_horizon_recursive_evaluation():
    """Verify multi-horizon recursive evaluation quantifies error compounding."""
    assert FORECAST_HORIZONS_JSON.exists()
    horizons = json.loads(FORECAST_HORIZONS_JSON.read_text(encoding="utf-8"))
    
    h1 = horizons["horizon_1_year_rolling"]
    h2 = horizons["horizon_2_year_recursive"]
    h3 = horizons["horizon_3_year_recursive"]
    
    assert h1["mae_mbgl"] > 0
    assert h2["mae_mbgl"] >= h1["mae_mbgl"]  # Error compounds across lead times
    assert "error_compounding_summary" in horizons
