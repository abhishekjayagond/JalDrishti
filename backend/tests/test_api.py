"""
backend/tests/test_api.py — JalDrishti FastAPI Endpoint Tests
Comprehensive tests for:
  - System root & health endpoints
  - Statutory GEC-2015 administrative assessment-unit endpoints:
      * Complete assessment flow (SOE + 10-year decadal pre/post monsoon trends)
      * Missing SOE returns 'unassessed' with explicit rationale
      * Missing SOE source or assessment year returns 'unassessed'
      * Incomplete seasonal data (<10 years pre/post) returns 'unassessed'
      * Uneven station sampling frequency (station-year normalization anti-dominance guard)
      * Insufficient station coverage (0 stations) returns 'unassessed'
      * Legitimate 0.0% SOE evaluates as Safe
      * Assessment units list endpoint
  - Comprehensive Scientific Integrity Pass Regression Suite:
      * Item 1: One-station insufficiency returning Unassessed (WMO No. 168 / CGWB network principles)
      * Item 2: Fake or unverified SOE provenance returning Unassessed (user estimates, missing volumetric components, mathematical contradictions)
      * Item 3: Invalid and suspect quality flags filtered out with coverage tracked in data_quality_screening
      * Item 4: Duplicate block names across different districts disambiguated (ambiguous without district)
      * Item 5: Correct SOE denominator terminology to Annual Extractable Groundwater Resource
      * Item 7: Verification against live PostgreSQL/TimescaleDB session
  - Exploratory point-level station depth alerts labeling
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app
from db.database import get_db
from app.models.station import Base, Station, DWLRReading
from app.services.assessment_unit import evaluate_block_administrative_unit, list_administrative_assessment_units

# In-memory SQLite database for deterministic API testing
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def populate_test_database():
    """Populate test database with stations and multi-year seasonal readings."""
    db = TestingSessionLocal()
    # Clear tables
    db.query(DWLRReading).delete()
    db.query(Station).delete()
    db.commit()

    # 1. Block "Anekal": 2 stations with 10 years of pre- and post-monsoon data (2011-2020)
    stn_a1 = Station(
        station_id="STN_ANEKAL_01",
        station_name="Anekal West Well",
        latitude=12.71,
        longitude=77.69,
        state="Karnataka",
        district="Bangalore Urban",
        block="Anekal",
        well_depth_m=60.0,
        aquifer_type="Granite",
    )
    stn_a2 = Station(
        station_id="STN_ANEKAL_02",
        station_name="Anekal East Well",
        latitude=12.72,
        longitude=77.71,
        state="Karnataka",
        district="Bangalore Urban",
        block="Anekal",
        well_depth_m=60.0,
        aquifer_type="Granite",
    )

    # 2. Block "Devanahalli": 2 stations with only 8 years of pre-monsoon data (<10 years)
    stn_dev1 = Station(
        station_id="STN_DEV_01",
        station_name="Devanahalli Well 1",
        latitude=13.24,
        longitude=77.71,
        state="Karnataka",
        district="Bangalore Rural",
        block="Devanahalli",
        well_depth_m=50.0,
        aquifer_type="Gneiss",
    )
    stn_dev2 = Station(
        station_id="STN_DEV_02",
        station_name="Devanahalli Well 2",
        latitude=13.25,
        longitude=77.72,
        state="Karnataka",
        district="Bangalore Rural",
        block="Devanahalli",
        well_depth_m=50.0,
        aquifer_type="Gneiss",
    )

    # 3. Block "Hosakote": 2 stations with drastically uneven sampling frequency
    # Telemetry: 100 readings/yr; Manual: 1 reading/yr
    stn_hos_telem = Station(
        station_id="STN_HOS_TELEM",
        station_name="Hosakote Telemetry DWLR",
        latitude=13.07,
        longitude=77.79,
        state="Karnataka",
        district="Bangalore Rural",
        block="Hosakote",
        well_depth_m=80.0,
        aquifer_type="Granite",
    )
    stn_hos_manual = Station(
        station_id="STN_HOS_MANUAL",
        station_name="Hosakote Manual Dug Well",
        latitude=13.08,
        longitude=77.80,
        state="Karnataka",
        district="Bangalore Rural",
        block="Hosakote",
        well_depth_m=30.0,
        aquifer_type="Granite",
    )

    # 4. Block "Karkala": 2 stations with 10 years of stable water level (for zero SOE test)
    stn_kar1 = Station(
        station_id="STN_KAR_01",
        station_name="Karkala Sanctuarial Well 1",
        latitude=13.21,
        longitude=74.99,
        state="Karnataka",
        district="Udupi",
        block="Karkala",
        well_depth_m=40.0,
        aquifer_type="Laterite",
    )
    stn_kar2 = Station(
        station_id="STN_KAR_02",
        station_name="Karkala Sanctuarial Well 2",
        latitude=13.22,
        longitude=75.01,
        state="Karnataka",
        district="Udupi",
        block="Karkala",
        well_depth_m=40.0,
        aquifer_type="Laterite",
    )

    # 5. Block "Kudligi": 1 solitary station (for one-station spatial insufficiency test)
    stn_kud = Station(
        station_id="STN_KUD_01",
        station_name="Kudligi Isolated Well",
        latitude=14.90,
        longitude=76.38,
        state="Karnataka",
        district="Vijayanagara",
        block="Kudligi",
        well_depth_m=45.0,
        aquifer_type="Granite",
    )

    # 6. Duplicate block "Rampur" in two distinct districts (for multi-district ambiguity test)
    stn_ramp_a1 = Station(
        station_id="STN_RAMPUR_A1",
        station_name="Rampur District A Well 1",
        latitude=15.10,
        longitude=75.10,
        state="Karnataka",
        district="DistrictAlpha",
        block="Rampur",
        well_depth_m=50.0,
        aquifer_type="Basalt",
    )
    stn_ramp_a2 = Station(
        station_id="STN_RAMPUR_A2",
        station_name="Rampur District A Well 2",
        latitude=15.12,
        longitude=75.12,
        state="Karnataka",
        district="DistrictAlpha",
        block="Rampur",
        well_depth_m=50.0,
        aquifer_type="Basalt",
    )
    stn_ramp_b1 = Station(
        station_id="STN_RAMPUR_B1",
        station_name="Rampur District B Well 1",
        latitude=16.20,
        longitude=76.20,
        state="Karnataka",
        district="DistrictBeta",
        block="Rampur",
        well_depth_m=50.0,
        aquifer_type="Alluvial",
    )
    stn_ramp_b2 = Station(
        station_id="STN_RAMPUR_B2",
        station_name="Rampur District B Well 2",
        latitude=16.22,
        longitude=76.22,
        state="Karnataka",
        district="DistrictBeta",
        block="Rampur",
        well_depth_m=50.0,
        aquifer_type="Alluvial",
    )

    # 7. Block "Chincholi": 2 stations with invalid/suspect quality flags & anomalies (for data quality screening test)
    stn_chin1 = Station(
        station_id="STN_CHIN_01",
        station_name="Chincholi Test Well 1",
        latitude=17.47,
        longitude=77.42,
        state="Karnataka",
        district="Kalaburagi",
        block="Chincholi",
        well_depth_m=60.0,
        aquifer_type="Basalt",
    )
    stn_chin2 = Station(
        station_id="STN_CHIN_02",
        station_name="Chincholi Test Well 2",
        latitude=17.48,
        longitude=77.44,
        state="Karnataka",
        district="Kalaburagi",
        block="Chincholi",
        well_depth_m=60.0,
        aquifer_type="Basalt",
    )

    # 8. Station for alert testing (deep well > 25m)
    stn_alert = Station(
        station_id="STN_CRIT_DEPTH",
        station_name="Deep Over-Exploited Depth Well",
        latitude=12.98,
        longitude=77.59,
        state="Karnataka",
        district="Bangalore Urban",
        block="Bangalore North",
        well_depth_m=80.0,
        aquifer_type="Granite",
    )

    db.add_all([
        stn_a1, stn_a2, stn_dev1, stn_dev2, stn_hos_telem, stn_hos_manual,
        stn_kar1, stn_kar2, stn_kud, stn_ramp_a1, stn_ramp_a2, stn_ramp_b1,
        stn_ramp_b2, stn_chin1, stn_chin2, stn_alert,
    ])
    db.commit()

    readings = []

    # Populate Anekal (10 years, 2011 to 2020, with deepening trend +0.2 m/yr)
    for yr in range(2011, 2021):
        idx = yr - 2011
        # Pre-monsoon: May 10
        readings.append(DWLRReading(
            station_id="STN_ANEKAL_01",
            timestamp=datetime(yr, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=10.0 + idx * 0.2,
            data_quality_flag="G",
        ))
        readings.append(DWLRReading(
            station_id="STN_ANEKAL_02",
            timestamp=datetime(yr, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=14.0 + idx * 0.2,
            data_quality_flag="G",
        ))
        # Post-monsoon: Nov 10
        readings.append(DWLRReading(
            station_id="STN_ANEKAL_01",
            timestamp=datetime(yr, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=8.0 + idx * 0.2,
            data_quality_flag="G",
        ))
        readings.append(DWLRReading(
            station_id="STN_ANEKAL_02",
            timestamp=datetime(yr, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=12.0 + idx * 0.2,
            data_quality_flag="G",
        ))

    # Populate Devanahalli (only 8 years: 2013-2020) across both stations
    for yr in range(2013, 2021):
        for sid in ["STN_DEV_01", "STN_DEV_02"]:
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=15.0,
                data_quality_flag="G",
            ))
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=14.0,
                data_quality_flag="G",
            ))

    # Populate Hosakote for 10 years (2011-2020)
    for yr in range(2011, 2021):
        idx = yr - 2011
        for i in range(100):
            readings.append(DWLRReading(
                station_id="STN_HOS_TELEM",
                timestamp=datetime(yr, 5, 1, 0, 0, 0, tzinfo=timezone.utc) + timedelta(hours=i),
                water_level_m=20.0 + idx * 0.1,
                data_quality_flag="G",
            ))
        readings.append(DWLRReading(
            station_id="STN_HOS_MANUAL",
            timestamp=datetime(yr, 5, 15, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=4.0 + idx * 0.1,
            data_quality_flag="G",
        ))
        readings.append(DWLRReading(
            station_id="STN_HOS_TELEM",
            timestamp=datetime(yr, 11, 5, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=18.0 + idx * 0.1,
            data_quality_flag="G",
        ))
        readings.append(DWLRReading(
            station_id="STN_HOS_MANUAL",
            timestamp=datetime(yr, 11, 5, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=3.0 + idx * 0.1,
            data_quality_flag="G",
        ))

    # Populate Karkala (10 years, stable water level, 2011-2020) across both stations
    for yr in range(2011, 2021):
        for sid in ["STN_KAR_01", "STN_KAR_02"]:
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=5.0,
                data_quality_flag="G",
            ))
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=4.0,
                data_quality_flag="G",
            ))

    # Populate Kudligi (10 years for solitary station STN_KUD_01)
    for yr in range(2011, 2021):
        readings.append(DWLRReading(
            station_id="STN_KUD_01",
            timestamp=datetime(yr, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=8.0,
            data_quality_flag="G",
        ))
        readings.append(DWLRReading(
            station_id="STN_KUD_01",
            timestamp=datetime(yr, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
            water_level_m=6.0,
            data_quality_flag="G",
        ))

    # Populate Rampur stations in DistrictAlpha and DistrictBeta (10 years each)
    for yr in range(2011, 2021):
        for sid in ["STN_RAMPUR_A1", "STN_RAMPUR_A2", "STN_RAMPUR_B1", "STN_RAMPUR_B2"]:
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=9.0,
                data_quality_flag="G",
            ))
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=7.0,
                data_quality_flag="G",
            ))

    # Populate Chincholi: valid readings for 10 years, PLUS invalid flags, unphysical levels, and anomalies
    for yr in range(2011, 2021):
        for sid in ["STN_CHIN_01", "STN_CHIN_02"]:
            # Valid pre-monsoon reading
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 10, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=7.5,
                data_quality_flag="G",
            ))
            # Valid post-monsoon reading
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=5.5,
                data_quality_flag="G",
            ))
            # Invalid reading: Error flag 'E'
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 12, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=22.0,
                data_quality_flag="E",
            ))
            # Invalid reading: Suspect flag 'S'
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 13, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=35.0,
                data_quality_flag="S",
            ))
            # Invalid reading: Unphysical negative level (-5.0m)
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=-5.0,
                data_quality_flag="G",
            ))
            # Invalid reading: Unphysical depth (>300m)
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 15, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=450.0,
                data_quality_flag="G",
            ))
            # Invalid reading: Marked anomaly
            readings.append(DWLRReading(
                station_id=sid,
                timestamp=datetime(yr, 5, 16, 10, 0, 0, tzinfo=timezone.utc),
                water_level_m=18.0,
                data_quality_flag="G",
                is_anomaly=True,
                anomaly_reason="Spike anomaly test",
            ))

    # Populate Alert station reading (deep level 28.5m)
    now_utc = datetime.now(timezone.utc)
    readings.append(DWLRReading(
        station_id="STN_CRIT_DEPTH",
        timestamp=now_utc - timedelta(hours=2),
        water_level_m=28.5,
        data_quality_flag="G",
    ))
    readings.append(DWLRReading(
        station_id="STN_CRIT_DEPTH",
        timestamp=now_utc - timedelta(hours=1),
        water_level_m=28.6,
        data_quality_flag="G",
    ))

    db.add_all(readings)
    db.commit()
    db.close()


# ── System Endpoints ──────────────────────────────────────────────────────────

def test_root_endpoint():
    """Verify system root endpoint returns JalDrishti service status."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "JalDrishti"
    assert data["status"] == "running"
    assert "CGWB Problem Statement #25068" in data["description"]


def test_health_endpoint():
    """Verify /api/health returns valid service payload."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "JalDrishti API v1"


# ── GEC-2015 Assessment Unit Integration Tests ────────────────────────────────

def test_gec_assessment_unit_complete_flow():
    """
    Test 1: Complete block assessment flow.
    Verifies that with authoritative SOE and 10 years of pre/post-monsoon trend records,
    the block evaluates correctly under the GEC-2015 categorization matrix.
    """
    params = {
        "stage_of_extraction_pct": 85.0,
        "annual_extractable_groundwater_resource_ham": 10000.0,
        "existing_gross_draft_total_ham": 8500.0,
        "soe_source": "CGWB Dynamic Ground Water Resources Assessment of India (2023)",
        "assessment_year": 2023,
    }
    res = client.get("/api/gec/assessment-unit/Anekal", params=params)
    assert res.status_code == 200
    data = res.json()

    assert data["assessment_unit"] == "Anekal"
    assert data["is_official_assessment_unit"] is True
    assert data["administrative_level"] == "block_or_taluk"
    # SOE = 85% -> Semi-Critical
    assert data["category"] == "semi_critical"
    assert data["category_label"] == "Semi-Critical"
    assert data["stage_of_extraction_pct"] == 85.0
    assert data["soe_source"] == "CGWB Dynamic Ground Water Resources Assessment of India (2023)"
    assert data["assessment_year"] == 2023

    # Verification of supporting volumetric resource accounting (Item 2 & 5)
    assert "volumetric_resource" in data
    assert data["volumetric_resource"]["annual_extractable_groundwater_resource_ham"] == 10000.0
    assert data["volumetric_resource"]["existing_gross_draft_total_ham"] == 8500.0
    assert "Annual Extractable Groundwater Resource" in data["volumetric_resource"]["formula"]

    # Verification of multi-station aggregation & spatial representativeness (Item 1)
    assert data["station_count"] == 2
    assert "STN_ANEKAL_01" in data["station_ids"]
    assert "STN_ANEKAL_02" in data["station_ids"]
    assert data["weighting_method"] == "equal_station_year_weighting"
    assert data["spatial_representativeness"]["is_met"] is True
    assert data["pre_monsoon_years_count"] == 10
    assert data["post_monsoon_years_count"] == 10
    assert data["pre_monsoon_trend_decline"] is True
    assert data["post_monsoon_trend_decline"] is True

    # Annual coverage breakdown inspection
    pre_cov = data["pre_monsoon_annual_coverage"]
    assert len(pre_cov) == 10
    assert pre_cov[0]["year"] == 2011
    assert pre_cov[0]["contributing_stations_count"] == 2
    assert pre_cov[0]["total_readings_count"] == 2
    assert pre_cov[0]["is_representative"] is True
    assert pre_cov[0]["mean_water_level_mbgl"] == 12.0

    # Test 95% SOE with trend decline -> Critical
    params_crit = dict(params, stage_of_extraction_pct=95.0, existing_gross_draft_total_ham=9500.0)
    res_crit = client.get("/api/gec/assessment-unit/Anekal", params=params_crit)
    assert res_crit.json()["category"] == "critical"

    # Test >100% SOE -> Over-Exploited
    params_oe = dict(params, stage_of_extraction_pct=112.5, existing_gross_draft_total_ham=11250.0)
    res_oe = client.get("/api/gec/assessment-unit/Anekal", params=params_oe)
    assert res_oe.json()["category"] == "over_exploited"


def test_gec_assessment_unit_missing_soe():
    """
    Test 2: Missing authoritative SOE data.
    Must return 'unassessed' with explicit rationale explaining that SOE cannot
    be derived from local well depth or water table levels.
    """
    res = client.get("/api/gec/assessment-unit/Anekal")
    assert res.status_code == 200
    data = res.json()

    assert data["category"] == "unassessed"
    assert data["stage_of_extraction_pct"] is None
    assert "Missing authoritative Stage of Groundwater Extraction" in data["rationale"]
    assert "SOE cannot be derived or estimated from point-level groundwater depth" in data["rationale"]


def test_gec_assessment_unit_missing_soe_metadata():
    """
    Test 3: Missing SOE source citation or assessment year.
    Must return 'unassessed' with explicit rationale.
    """
    # Provided SOE pct but missing source and year
    res1 = client.get("/api/gec/assessment-unit/Anekal", params={"stage_of_extraction_pct": 80.0})
    assert res1.json()["category"] == "unassessed"
    assert "source citation is required" in res1.json()["rationale"]

    # Provided SOE pct and source, but missing assessment year
    res2 = client.get("/api/gec/assessment-unit/Anekal", params={
        "stage_of_extraction_pct": 80.0,
        "soe_source": "CGWB Dynamic Ground Water Resources",
    })
    assert res2.json()["category"] == "unassessed"
    assert "assessment year must be specified" in res2.json()["rationale"]


def test_gec_assessment_unit_incomplete_seasonal_data():
    """
    Test 4: Incomplete seasonal records (<10 years pre- or post-monsoon).
    Devanahalli has only 8 years of pre-monsoon records.
    Must return 'unassessed' with explicit rationale.
    """
    params = {
        "stage_of_extraction_pct": 75.0,
        "annual_extractable_groundwater_resource_ham": 10000.0,
        "existing_gross_draft_total_ham": 7500.0,
        "soe_source": "CGWB Dynamic Ground Water Resources Assessment of India (2023)",
        "assessment_year": 2023,
    }
    res = client.get("/api/gec/assessment-unit/Devanahalli", params=params)
    assert res.status_code == 200
    data = res.json()

    assert data["category"] == "unassessed"
    assert data["pre_monsoon_years_count"] == 8
    assert "Insufficient statutory seasonal trend evidence" in data["rationale"]
    assert "at least 10 years of actual" in data["rationale"]


def test_gec_assessment_unit_uneven_station_sampling_frequency():
    """
    Test 5: Uneven station sampling frequency anti-dominance guard.
    In block 'Hosakote':
      - STN_HOS_TELEM has 100 high-frequency readings in pre-monsoon averaging ~20.0 mbgl.
      - STN_HOS_MANUAL has 1 annual reading in pre-monsoon of 4.0 mbgl.
    Verify that station-year seasonal averaging gives equal weight to both stations:
      Block seasonal mean = (20.0 + 4.0) / 2 = 12.0 mbgl
      NOT the naive pooled average of ~19.84 mbgl.
    """
    params = {
        "stage_of_extraction_pct": 85.0,
        "annual_extractable_groundwater_resource_ham": 10000.0,
        "existing_gross_draft_total_ham": 8500.0,
        "soe_source": "CGWB Dynamic Ground Water Resources (2023)",
        "assessment_year": 2023,
    }
    res = client.get("/api/gec/assessment-unit/Hosakote", params=params)
    assert res.status_code == 200
    data = res.json()

    # Pre-monsoon annual coverage for 2011 (idx=0)
    cov_2011 = data["pre_monsoon_annual_coverage"][0]
    assert cov_2011["year"] == 2011
    assert cov_2011["contributing_stations_count"] == 2
    assert cov_2011["total_readings_count"] == 101  # 100 telemetry + 1 manual
    # Mathematical proof of anti-dominance: (20.0 + 4.0)/2 = 12.0
    assert abs(cov_2011["mean_water_level_mbgl"] - 12.0) < 0.05
    assert cov_2011["weighting_method"] == "equal_station_year_weighting"


def test_gec_assessment_unit_insufficient_station_coverage():
    """
    Test 6: Insufficient station coverage (0 stations in block).
    Must return 'unassessed' with explicit reason.
    """
    params = {
        "stage_of_extraction_pct": 75.0,
        "annual_extractable_groundwater_resource_ham": 10000.0,
        "existing_gross_draft_total_ham": 7500.0,
        "soe_source": "CGWB 2023",
        "assessment_year": 2023,
    }
    res = client.get("/api/gec/assessment-unit/NonExistentBlockXYZ", params=params)
    assert res.status_code == 200
    data = res.json()

    assert data["category"] == "unassessed"
    assert data["station_count"] == 0
    assert "0 monitoring stations located in administrative block" in data["rationale"]


def test_gec_assessment_unit_zero_soe():
    """
    Test 7: Authoritative 0.0% extraction is valid Safe, not missing or unassessed.
    Karkala has 10 years of stable water level data and 0.0% SOE.
    """
    params = {
        "stage_of_extraction_pct": 0.0,
        "annual_extractable_groundwater_resource_ham": 6800.0,
        "existing_gross_draft_total_ham": 0.0,
        "soe_source": "CGWB Dynamic Ground Water Resources (2023)",
        "assessment_year": 2023,
    }
    res = client.get("/api/gec/assessment-unit/Karkala", params=params)
    assert res.status_code == 200
    data = res.json()

    assert data["category"] == "safe"
    assert data["stage_of_extraction_pct"] == 0.0
    assert data["pre_monsoon_years_count"] == 10
    assert data["post_monsoon_years_count"] == 10


def test_gec_assessment_units_list_endpoint():
    """
    Test 8: List administrative assessment units endpoint.
    Verifies that all blocks in the monitoring network are listed with station counts.
    """
    res = client.get("/api/gec/assessment-units")
    assert res.status_code == 200
    data = res.json()

    assert data["total_units"] >= 4
    blocks = [u["block"] for u in data["assessment_units"]]
    assert "Anekal" in blocks
    assert "Devanahalli" in blocks
    assert "Hosakote" in blocks
    assert "Karkala" in blocks

    # Verify unit properties
    anekal = next(u for u in data["assessment_units"] if u["block"] == "Anekal")
    assert anekal["station_count"] == 2
    assert anekal["district"] == "Bangalore Urban"
    assert anekal["state"] == "Karnataka"
    assert anekal["has_representative_spatial_network"] is True


def test_station_depth_alerts_are_labeled_exploratory():
    """
    Test 9: Verify that individual station alerts are clearly labeled
    as exploratory depth-screening alerts, not official CGWB risk classifications.
    """
    res = client.get("/api/alerts?hours=48")
    assert res.status_code == 200
    data = res.json()

    assert data["alert_type"] == "exploratory_depth_screening_alert"
    assert data["is_official_cgwb_classification"] is False
    assert "exploratory point-level depth screening indicators" in data["methodological_disclaimer"].lower()

    if data["total"] > 0:
        alert = data["alerts"][0]
        assert alert["alert_type"] == "exploratory_depth_screening_alert"
        assert alert["is_official_cgwb_classification"] is False
        assert "statutory_disclaimer" in alert
        assert "Exploratory point-level depth screening alert" in alert["statutory_disclaimer"]


# ═══════════════════════════════════════════════════════════════════════════════
# SCIENTIFIC INTEGRITY PASS REGRESSION SUITE (Items 1, 2, 3, 4, 5, 7)
# ═══════════════════════════════════════════════════════════════════════════════

def test_regression_item1_one_station_insufficiency_returns_unassessed():
    """
    Item 1: Do not consider one station per year sufficient evidence of a representative
    block monitoring network. A block with only 1 station must return Unassessed under
    standard hydrogeological network principles (WMO No. 168 / CGWB Network Design Principles).
    """
    params = {
        "stage_of_extraction_pct": 55.0,
        "annual_extractable_groundwater_resource_ham": 5000.0,
        "existing_gross_draft_total_ham": 2750.0,
        "soe_source": "CGWB Dynamic Ground Water Resources Assessment of India (2023)",
        "assessment_year": 2023,
    }
    # Block "Kudligi" has only 1 station (STN_KUD_01)
    res = client.get("/api/gec/assessment-unit/Kudligi", params=params)
    assert res.status_code == 200
    data = res.json()

    assert data["category"] == "unassessed"
    assert data["category_label"] == "Unassessed"
    assert data["station_count"] == 1
    assert "Insufficient spatial monitoring network representativeness" in data["rationale"]
    assert "At least 2 spatially distinct monitoring stations are required" in data["rationale"]


def test_regression_item2_fake_and_unverified_soe_provenance_returns_unassessed():
    """
    Item 2: Validate SOE provenance.
    Rejects arbitrary query parameters or user-entered source descriptions.
    Requires traceable source records with official CGWB document, assessment year,
    and supporting volumetric values (draft & Annual Extractable Groundwater Resource).
    """
    # Case A: Fake user source description
    fake_params = {
        "stage_of_extraction_pct": 65.0,
        "soe_source": "Personal User Estimate from Local Pumping",
        "assessment_year": 2023,
        "annual_extractable_groundwater_resource_ham": 10000.0,
        "existing_gross_draft_total_ham": 6500.0,
    }
    res_fake = client.get("/api/gec/assessment-unit/Anekal", params=fake_params)
    assert res_fake.status_code == 200
    assert res_fake.json()["category"] == "unassessed"
    assert "Unverified Stage of Groundwater Extraction (SOE) provenance" in res_fake.json()["rationale"]
    assert "is not a recognized statutory CGWB publication" in res_fake.json()["rationale"]

    # Case B: Arbitrary SOE percentage without supporting volumetric accounting
    res_no_vol = client.get("/api/gec/assessment-unit/Anekal", params={
        "stage_of_extraction_pct": 85.0,
        "soe_source": "CGWB Dynamic Ground Water Resources Assessment of India (2023)",
        "assessment_year": 2023,
    })
    assert res_no_vol.status_code == 200
    assert res_no_vol.json()["category"] == "unassessed"
    assert "Missing verified volumetric accounting values" in res_no_vol.json()["rationale"]

    # Case C: Mathematically contradictory draft vs Annual Extractable Groundwater Resource
    contradictory_params = {
        "stage_of_extraction_pct": 50.0,  # Claims 50%, but 9000/10000 = 90%
        "annual_extractable_groundwater_resource_ham": 10000.0,
        "existing_gross_draft_total_ham": 9000.0,
        "soe_source": "CGWB Dynamic Ground Water Resources Assessment of India (2023)",
        "assessment_year": 2023,
    }
    res_contra = client.get("/api/gec/assessment-unit/Anekal", params=contradictory_params)
    assert res_contra.status_code == 200
    assert res_contra.json()["category"] == "unassessed"
    assert "Volumetric SOE mathematical contradiction" in res_contra.json()["rationale"]


def test_regression_item3_data_quality_filtering_and_exclusion_reporting():
    """
    Item 3: Filter invalid and suspect groundwater observations using documented
    data-quality rules before seasonal aggregation. Report exclusions and coverage.
    Block 'Chincholi' contains readings with:
      - Flag 'E' (Error)
      - Flag 'S' (Suspect)
      - Unphysical negative water level (-5.0m)
      - Unphysical depth (>300m: 450.0m)
      - Marked anomaly (is_anomaly=True)
    Verify that all invalid readings are excluded and documented in data_quality_screening.
    """
    params = {
        "stage_of_extraction_pct": 60.0,
        "annual_extractable_groundwater_resource_ham": 10000.0,
        "existing_gross_draft_total_ham": 6000.0,
        "soe_source": "CGWB Dynamic Ground Water Resources Assessment of India (2023)",
        "assessment_year": 2023,
    }
    res = client.get("/api/gec/assessment-unit/Chincholi", params=params)
    assert res.status_code == 200
    data = res.json()

    assert data["category"] == "safe"
    assert "data_quality_screening" in data
    dq = data["data_quality_screening"]

    assert dq["total_readings_screened"] > dq["valid_readings_count"]
    assert dq["excluded_readings_count"] > 0
    # Verification of exclusion breakdown categories
    breakdown = dq["exclusion_breakdown"]
    assert breakdown["quality_flag_suspect_or_error"] > 0
    assert breakdown["unphysical_range"] > 0
    assert breakdown["marked_anomaly"] > 0


def test_regression_item4_duplicate_block_names_across_districts():
    """
    Item 4: Require unambiguous administrative identification using block/taluk
    identity together with state and district.
    Block 'Rampur' exists in both 'DistrictAlpha' and 'DistrictBeta'.
    - Querying 'Rampur' without district must return Unassessed due to ambiguity.
    - Querying 'Rampur' with district must unambiguously resolve to that district's stations.
    """
    params = {
        "stage_of_extraction_pct": 65.0,
        "annual_extractable_groundwater_resource_ham": 10000.0,
        "existing_gross_draft_total_ham": 6500.0,
        "soe_source": "CGWB Dynamic Ground Water Resources Assessment of India (2023)",
        "assessment_year": 2023,
    }
    # Ambiguous query (no district)
    res_ambig = client.get("/api/gec/assessment-unit/Rampur", params=params)
    assert res_ambig.status_code == 200
    assert res_ambig.json()["category"] == "unassessed"
    assert "Ambiguous administrative block 'Rampur'" in res_ambig.json()["rationale"]
    assert "DistrictAlpha" in res_ambig.json()["rationale"]
    assert "DistrictBeta" in res_ambig.json()["rationale"]

    # Disambiguated query (with district)
    params_a = dict(params, district="DistrictAlpha")
    res_a = client.get("/api/gec/assessment-unit/Rampur", params=params_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["category"] == "safe"
    assert data_a["station_count"] == 2
    assert "STN_RAMPUR_A1" in data_a["station_ids"]
    assert "STN_RAMPUR_A2" in data_a["station_ids"]
    assert "STN_RAMPUR_B1" not in data_a["station_ids"]


def test_regression_item7_live_postgres_session():
    """
    Item 7: Verification against PostgreSQL/TimescaleDB session (not only in-memory SQLite).
    Connects to the running PostgreSQL database on port 5432 and verifies the GEC service.
    """
    import psycopg2
    try:
        conn = psycopg2.connect("postgresql://jaldrishti_user:jaldrishti_pass@localhost:5432/jaldrishti")
        conn.close()
    except Exception as e:
        pytest.skip(f"Live PostgreSQL not reachable on port 5432: {e}")

    pg_engine = create_engine("postgresql://jaldrishti_user:jaldrishti_pass@localhost:5432/jaldrishti")
    PgSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)
    pg_db = PgSession()

    try:
        # Test 1: List assessment units against real PostgreSQL database
        units_res = list_administrative_assessment_units(db=pg_db, state="Karnataka")
        assert units_res["total_units"] > 0
        blocks = [u["block"] for u in units_res["assessment_units"]]
        assert "Athni" in blocks

        # Find Athni's station count from real database
        athni_unit = next(u for u in units_res["assessment_units"] if u["block"] == "Athni")
        assert athni_unit["station_count"] >= 2
        assert athni_unit["has_representative_spatial_network"] is True

        # Test 2: Evaluate real PostgreSQL block Athni with verified CGWB volumetric data
        athni_eval = evaluate_block_administrative_unit(
            block_name="Athni",
            stage_of_extraction_pct=85.52,
            annual_extractable_groundwater_resource_ham=14500.0,
            existing_gross_draft_total_ham=12400.0,
            soe_source="CGWB Dynamic Ground Water Resources Assessment of India (2023)",
            assessment_year=2023,
            state="Karnataka",
            district="Belagavi",
            db=pg_db,
        )
        assert athni_eval["assessment_unit"] == "Athni"
        assert athni_eval["station_count"] == athni_unit["station_count"]
        assert "volumetric_resource" in athni_eval
        assert athni_eval["volumetric_resource"]["annual_extractable_groundwater_resource_ham"] == 14500.0
        assert athni_eval["volumetric_resource"]["existing_gross_draft_total_ham"] == 12400.0
        assert "data_quality_screening" in athni_eval
        assert athni_eval["data_quality_screening"]["total_readings_screened"] > 0

    finally:
        pg_db.close()
