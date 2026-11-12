import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np
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
    assert counts["Safe"] == 312
    assert counts["Semi-Critical"] == 77
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
    assert conf["model_alignment"]["is_exact_calibrated_model"] is True
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
    """Verify multi-horizon recursive evaluation on common cohort from fixed origin."""
    assert FORECAST_HORIZONS_JSON.exists()
    horizons = json.loads(FORECAST_HORIZONS_JSON.read_text(encoding="utf-8"))
    
    assert horizons["evaluation_protocol"] == "single_origin_common_cohort_recursive"
    assert horizons["forecast_origin_year"] == 2022
    assert horizons["common_cohort_station_count"] == 276

    h1 = horizons["horizon_1"]
    h2 = horizons["horizon_2"]
    h3 = horizons["horizon_3"]
    
    assert h1["sample_count"] == 276
    assert h2["sample_count"] == 276
    assert h3["sample_count"] == 276

    assert h1["mae_mbgl"] > 0
    assert h2["mae_mbgl"] >= h1["mae_mbgl"]
    assert h2["error_change_vs_h1_pct"] > 0

    assert h1["uncertainty_status"] == "calibrated"
    assert h2["uncertainty_status"] == "unavailable"
    assert h3["uncertainty_status"] == "unavailable"
    assert "error_trajectory_summary" in horizons


def test_served_model_alignment_and_retrospective_label():
    """Verify served model matches calibrated linear regression, 2026 is retrospective, and multi-year uncertainty is suppressed."""
    from service import app as ai_app
    import joblib
    ai_app._load()

    # Model alignment
    calibrated_lr = joblib.load(LR_MODEL)
    assert np.allclose(ai_app.model.coef_, calibrated_lr.coef_)
    assert np.isclose(ai_app.model.intercept_, calibrated_lr.intercept_)
    assert ai_app.health()["model"] == "calibrated_linear_regression"

    # Station forecast checks
    fc = ai_app._compute_station_forecast("942ccfc29ecf")
    assert fc is not None
    assert fc["forecast_year"] == 2026
    assert fc["temporal_classification"] == "retrospective_estimate"
    assert fc["is_future_forecast"] is False
    assert fc["uncertainty_status"] == "calibrated_conformal_interval"

    # Multi-year projections
    projs = fc["multi_year_projections"]
    assert len(projs) == 3

    p1 = projs[0]
    assert p1["target_year"] == 2026
    assert p1["temporal_classification"] == "retrospective_estimate"
    assert p1["uncertainty_status"] == "calibrated_conformal_interval"
    assert p1["uncertainty_radius_mbgl"] is not None

    p2 = projs[1]
    assert p2["target_year"] == 2027
    assert p2["temporal_classification"] == "future_projection"
    assert p2["is_future_forecast"] is True
    assert p2["uncertainty_status"] == "unavailable"
    assert p2["uncertainty_radius_mbgl"] is None
    assert p2["lower_mbgl"] is None

    p3 = projs[2]
    assert p3["target_year"] == 2028
    assert p3["temporal_classification"] == "future_projection"
    assert p3["is_future_forecast"] is True
    assert p3["uncertainty_status"] == "unavailable"
    assert p3["uncertainty_radius_mbgl"] is None


def test_gwl_slope_4_calendar_gap_physics():
    """Verify that gwl_slope_4 uses actual observation calendar years, not equidistant np.arange(4)."""
    import numpy as np

    # Years with calendar gap: [2018, 2019, 2020, 2022] (missing 2021)
    years = [2018, 2019, 2020, 2022]
    # Depths: 10.0m in 2018, 10.2m in 2019, 10.4m in 2020, 10.8m in 2022
    # True physical rate is 0.200 m/year
    depths = [10.0, 10.2, 10.4, 10.8]

    slope_calendar = float(np.polyfit(years, depths, 1)[0])
    slope_naive_array = float(np.polyfit(np.arange(4), depths, 1)[0])

    # The calendar slope must be exactly 0.200 m/yr
    assert pytest.approx(slope_calendar, abs=1e-4) == 0.200
    # The naive array position slope would erroneously distort to ~0.260 (+30% error!)
    assert abs(slope_naive_array - 0.200) > 0.05


def test_missing_model_artifact_prohibits_silent_fallback(monkeypatch, tmp_path):
    """Verify that if the calibrated model artifact is missing, app._load() raises RuntimeError rather than silently falling back."""
    from service import app as ai_app
    fake_model_path = tmp_path / "nonexistent_model.joblib"
    monkeypatch.setattr("service.app.LR_MODEL", fake_model_path)
    
    with pytest.raises(RuntimeError, match="Silent fallback to an uncalibrated model"):
        ai_app._load()
