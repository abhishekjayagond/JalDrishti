"""
JalDrishti — DWLR Data Scraper
data/scripts/scraper.py

Fetches groundwater level data from:
  Primary  → India-WRIS GeoServer (WFS) + statewise API
  Fallback → data.gov.in open datasets
  Fallback → Local CSV sample data (offline dev mode)

Also fetches:
  Rainfall → IMD AWS API (for Task 2 recharge estimation)

Usage:
  python scraper.py                          # Continuous loop, all states
  python scraper.py --once                   # Run once and exit
  python scraper.py --state Rajasthan        # Fetch one state
  python scraper.py --district Jaipur        # Fetch one district
  python scraper.py --source sample          # Use local sample data (offline)
  python scraper.py --days 30                # Last 30 days of data
  python scraper.py --refresh                # Force full station master refresh
"""

import argparse
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("jaldrishti.scraper")

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent   # data/
RAW_DIR       = BASE_DIR / "raw"
SAMPLE_DIR    = BASE_DIR / "sample"
RAW_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
INDIA_WRIS_BASE  = "https://indiawris.gov.in"
WRIS_GW_API      = f"{INDIA_WRIS_BASE}/api/gwl"
WRIS_STATION_API = f"{INDIA_WRIS_BASE}/api/gwstation"
WRIS_GEOSERVER   = f"{INDIA_WRIS_BASE}/geoserver/wfs"

IMD_BASE         = os.getenv("IMD_BASE_URL", "https://imdaws.imd.gov.in")
DATA_GOV_API     = "https://api.data.gov.in/resource"
CGWB_DATASET_ID  = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"

FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_SEC", "900"))  # 15 minutes

ALL_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
]
SAMPLE_STATIONS_PER_STATE = 3


def _state_code(state: str) -> str:
    """Build a stable short code for synthetic station IDs."""
    parts = [p for p in str(state).split() if p]
    if len(parts) >= 2:
      return (parts[0][0] + parts[1][0]).upper()
    return str(state)[:2].upper()


# ─────────────────────────────────────────────
# HTTP SESSION — retry + browser headers
# ─────────────────────────────────────────────
def make_session() -> requests.Session:
    """
    Create a requests Session with:
    - Automatic retry on 429 / 5xx (3 attempts, exponential backoff)
    - Browser-like headers to avoid blocks
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,                              # waits: 1s, 2s, 4s
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Referer":         INDIA_WRIS_BASE,
    })
    return session


# ═══════════════════════════════════════════════════════════════
# FETCHER 1 — Station Master
# ═══════════════════════════════════════════════════════════════
def fetch_station_master(
    session: requests.Session,
    state: str = None,
) -> pd.DataFrame:
    """
    Fetch DWLR station metadata from India-WRIS GeoServer (WFS).
    Falls back to data.gov.in, then local sample CSV.

    Returns DataFrame with columns:
        station_id, station_name, state, district, block,
        latitude, longitude, aquifer_type, well_depth_m, station_type
    """
    log.info(f"Fetching station master — state: {state or 'ALL'}")

    params = {
        "service":      "WFS",
        "version":      "1.0.0",
        "request":      "GetFeature",
        "typeName":     "india-wris:gwl_station",
        "outputFormat": "application/json",
        "maxFeatures":  6000,
    }
    if state:
        params["CQL_FILTER"] = f"state_name='{state}'"

    try:
        resp = session.get(WRIS_GEOSERVER, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        stations = []
        for feature in data.get("features", []):
            props  = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [None, None])
            stations.append({
                "station_id":   props.get("station_id", ""),
                "station_name": props.get("station_name", ""),
                "state":        props.get("state_name", ""),
                "district":     props.get("district_name", ""),
                "block":        props.get("block_name", ""),
                "latitude":     coords[1] if coords else None,
                "longitude":    coords[0] if coords else None,
                "aquifer_type": props.get("aquifer_type", ""),
                "well_depth_m": props.get("well_depth", None),
                "station_type": props.get("station_type", "DWLR"),
            })

        df = pd.DataFrame(stations)
        log.info(f"  {len(df)} stations from India-WRIS GeoServer.")
        return df

    except requests.exceptions.ConnectionError:
        log.warning("  GeoServer unreachable — trying data.gov.in fallback …")
        return _station_fallback(state)
    except Exception as e:
        log.warning(f"  GeoServer error: {e} — trying fallback …")
        return _station_fallback(state)


def _station_fallback(state: str = None) -> pd.DataFrame:
    """Fallback 1: data.gov.in → Fallback 2: sample CSV → Fallback 3: synthetic."""
    try:
        params = {
            "api-key": os.getenv(
                "DATA_GOV_API_KEY",
                "579b464db66ec23bdd000001cdd3946e44ce4aad38d76835a8bfe6d"
            ),
            "format":         "json",
            "limit":          500,
            "filters[state]": state or "",
        }
        resp = requests.get(
            f"{DATA_GOV_API}/{CGWB_DATASET_ID}", params=params, timeout=15
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        df = pd.DataFrame(records)
        log.info(f"  {len(df)} stations from data.gov.in fallback.")
        return df
    except Exception as e:
        log.warning(f"  data.gov.in also failed: {e}")

    # Fallback: local sample CSV
    sample_file = SAMPLE_DIR / "station_master_sample.csv"
    if sample_file.exists():
        df = pd.read_csv(sample_file)
        if state:
            df = df[df["state"].str.lower() == state.lower()]
        log.info(f"  {len(df)} stations from sample CSV (offline mode).")
        return df

    # Last resort: synthetic data
    log.warning("  Generating synthetic sample stations.")
    return _generate_sample_stations(state)


# ═══════════════════════════════════════════════════════════════
# FETCHER 2 — DWLR Water Level Readings
# ═══════════════════════════════════════════════════════════════
def fetch_water_levels_batch(
    session: requests.Session,
    state: str,
    district: str = None,
    days: int = 30,
    since: datetime = None,
) -> pd.DataFrame:
    """
    Fetch water level time-series for all stations in a state/district.
    Falls back to sample data if API is unreachable.

    Returns DataFrame with columns:
        station_id, station_name, state, district,
        timestamp, water_level_m, data_quality
    """
    log.info(f"Fetching water levels — {state} / {district or 'all districts'}")

    start_date = (since.strftime("%Y-%m-%d") if since
                  else (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"))
    params = {
        "state":    state,
        "district": district or "",
        "from":     start_date,
        "to":       datetime.now().strftime("%Y-%m-%d"),
    }

    try:
        resp = session.get(
            f"{INDIA_WRIS_BASE}/api/gwl/statewise",
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        rows = []
        for station in data.get("stations", []):
            for reading in station.get("readings", []):
                rows.append({
                    "station_id":    station.get("station_id"),
                    "station_name":  station.get("station_name"),
                    "state":         state,
                    "district":      station.get("district"),
                    "timestamp":     pd.to_datetime(reading.get("timestamp")),
                    "water_level_m": float(reading.get("water_level", 0)),
                    "data_quality_flag": reading.get("quality", "G"),
                })

        df = pd.DataFrame(rows)
        log.info(f"  {len(df)} readings from India-WRIS.")
        return df

    except requests.exceptions.ConnectionError:
        log.warning(f"  India-WRIS unreachable for {state} (redirect/offline) — using benchmark telemetry simulation.")
        return _load_sample_readings(state, district, days, since=since)
    except Exception as e:
        log.warning(f"  API error for {state}: {e} — using benchmark telemetry simulation.")
        return _load_sample_readings(state, district, days, since=since)


# ═══════════════════════════════════════════════════════════════
# FETCHER 3 — IMD Rainfall
# ═══════════════════════════════════════════════════════════════
def fetch_rainfall(
    session: requests.Session,
    states: list[str],
    target_date: datetime = None,
) -> pd.DataFrame:
    """
    Fetch daily district-level rainfall from IMD AWS.
    Used by Task 2 recharge estimation.

    Returns DataFrame with columns:
        state, district, date, rainfall_mm
    """
    if target_date is None:
        target_date = datetime.now()

    date_str = target_date.strftime("%Y-%m-%d")
    log.info(f"Fetching IMD rainfall — {len(states)} states on {date_str} …")

    try:
        resp = session.get(
            f"{IMD_BASE}/api/rainfall/district",
            params={
                "states": ",".join(states),
                "date":   date_str,
                "format": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        rows = []
        for record in data.get("data", []):
            rows.append({
                "state":       record.get("stateName"),
                "district":    record.get("distName"),
                "date":        pd.to_datetime(record.get("date")).date(),
                "rainfall_mm": float(record.get("rainfallMm", 0)),
            })

        df = pd.DataFrame(rows)
        log.info(f"  {len(df)} district rainfall records from IMD.")
        return df

    except Exception as e:
        log.warning(f"  IMD API unavailable: {e} — using sample rainfall data.")
        sample_file = SAMPLE_DIR / "rainfall_sample.csv"
        if sample_file.exists():
            return pd.read_csv(sample_file, parse_dates=["date"])
        return pd.DataFrame(columns=["state", "district", "date", "rainfall_mm"])


# ═══════════════════════════════════════════════════════════════
def _snap_to_15min(dt: datetime) -> datetime:
    """Snap datetime to the nearest preceding 15-minute grid mark."""
    dt = dt.replace(second=0, microsecond=0)
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute)


def _load_sample_readings(
    state: str,
    district: str = None,
    days: int = 30,
    since: datetime = None,
) -> pd.DataFrame:
    """Load readings from sample CSV, or generate synthetic incremental benchmark data."""
    sample_file = SAMPLE_DIR / "dwlr_readings_sample.csv"
    if sample_file.exists():
        df = pd.read_csv(sample_file, parse_dates=["timestamp"])
        if state:
            df = df[df.get("state", pd.Series(dtype=str)).str.lower() == state.lower()]
        if district:
            df = df[df.get("district", pd.Series(dtype=str)).str.lower() == district.lower()]
        cutoff = since if since else (datetime.now() - timedelta(days=days))
        df = df[df["timestamp"] >= cutoff]
        log.info(f"  {len(df)} readings from sample CSV.")
        return df

    return _generate_sample_readings(state, district, days=days, since=since)


def _generate_sample_stations(state: str = None) -> pd.DataFrame:
    """Generate realistic synthetic station master data with authentic district coordinates."""
    import random
    district_cfg = {
        ("Andhra Pradesh", "Guntur"):             {"lat": 16.3067, "lon": 80.4365},
        ("Andhra Pradesh", "Kurnool"):            {"lat": 15.8281, "lon": 78.0373},
        ("Andhra Pradesh", "Visakhapatnam"):      {"lat": 17.6868, "lon": 83.2185},
        ("Arunachal Pradesh", "Papum Pare"):      {"lat": 27.1350, "lon": 93.6050},
        ("Arunachal Pradesh", "Changlang"):       {"lat": 27.1264, "lon": 95.7388},
        ("Arunachal Pradesh", "West Kameng"):     {"lat": 27.2644, "lon": 92.4158},
        ("Assam", "Kamrup"):                      {"lat": 26.1445, "lon": 91.7362},
        ("Assam", "Dibrugarh"):                   {"lat": 27.4728, "lon": 94.9120},
        ("Assam", "Cachar"):                      {"lat": 24.8333, "lon": 92.7789},
        ("Bihar", "Patna"):                       {"lat": 25.5941, "lon": 85.1376},
        ("Bihar", "Gaya"):                        {"lat": 24.7914, "lon": 85.0002},
        ("Bihar", "Muzaffarpur"):                 {"lat": 26.1209, "lon": 85.3647},
        ("Chhattisgarh", "Raipur"):               {"lat": 21.2514, "lon": 81.6296},
        ("Chhattisgarh", "Bilaspur"):             {"lat": 22.0797, "lon": 82.1409},
        ("Chhattisgarh", "Bastar"):               {"lat": 19.0740, "lon": 82.0298},
        ("Goa", "North Goa"):                     {"lat": 15.4909, "lon": 73.8278},
        ("Goa", "South Goa"):                     {"lat": 15.2832, "lon": 73.9862},
        ("Goa", "Tiswadi"):                       {"lat": 15.4600, "lon": 73.8700},
        ("Gujarat", "Ahmedabad"):                 {"lat": 23.0225, "lon": 72.5714},
        ("Gujarat", "Rajkot"):                    {"lat": 22.3039, "lon": 70.8022},
        ("Gujarat", "Surat"):                     {"lat": 21.1702, "lon": 72.8311},
        ("Haryana", "Hisar"):                     {"lat": 29.1492, "lon": 75.7217},
        ("Haryana", "Karnal"):                    {"lat": 29.6857, "lon": 76.9905},
        ("Haryana", "Rohtak"):                    {"lat": 28.8955, "lon": 76.6066},
        ("Himachal Pradesh", "Shimla"):           {"lat": 31.1048, "lon": 77.1734},
        ("Himachal Pradesh", "Kangra"):           {"lat": 32.0998, "lon": 76.2691},
        ("Himachal Pradesh", "Mandi"):            {"lat": 31.7087, "lon": 76.9320},
        ("Jharkhand", "Ranchi"):                  {"lat": 23.3441, "lon": 85.3096},
        ("Jharkhand", "Dhanbad"):                 {"lat": 23.7957, "lon": 86.4304},
        ("Jharkhand", "East Singhbhum"):          {"lat": 22.8046, "lon": 86.2029},
        ("Karnataka", "Bengaluru Urban"):         {"lat": 12.9716, "lon": 77.5946},
        ("Karnataka", "Mysuru"):                  {"lat": 12.2958, "lon": 76.6394},
        ("Karnataka", "Belagavi"):                {"lat": 15.8497, "lon": 74.4977},
        ("Kerala", "Thiruvananthapuram"):         {"lat": 8.5241,  "lon": 76.9366},
        ("Kerala", "Ernakulam"):                  {"lat": 9.9816,  "lon": 76.2999},
        ("Kerala", "Palakkad"):                   {"lat": 10.7867, "lon": 76.6548},
        ("Madhya Pradesh", "Bhopal"):             {"lat": 23.2599, "lon": 77.4126},
        ("Madhya Pradesh", "Indore"):             {"lat": 22.7196, "lon": 75.8577},
        ("Madhya Pradesh", "Jabalpur"):           {"lat": 23.1815, "lon": 79.9864},
        ("Maharashtra", "Pune"):                  {"lat": 18.5204, "lon": 73.8567},
        ("Maharashtra", "Nagpur"):                {"lat": 21.1458, "lon": 79.0882},
        ("Maharashtra", "Nashik"):                {"lat": 19.9975, "lon": 73.7898},
        ("Manipur", "Imphal West"):               {"lat": 24.8170, "lon": 93.9368},
        ("Manipur", "Churachandpur"):             {"lat": 24.3333, "lon": 93.6667},
        ("Manipur", "Thoubal"):                   {"lat": 24.6393, "lon": 93.9998},
        ("Meghalaya", "East Khasi Hills"):        {"lat": 25.5788, "lon": 91.8933},
        ("Meghalaya", "West Garo Hills"):         {"lat": 25.5141, "lon": 90.2023},
        ("Meghalaya", "Ri-Bhoi"):                 {"lat": 25.9036, "lon": 91.8803},
        ("Mizoram", "Aizawl"):                    {"lat": 23.7271, "lon": 92.7176},
        ("Mizoram", "Lunglei"):                   {"lat": 22.8878, "lon": 92.7388},
        ("Mizoram", "Champhai"):                  {"lat": 23.4756, "lon": 93.3283},
        ("Nagaland", "Kohima"):                   {"lat": 25.6751, "lon": 94.1086},
        ("Nagaland", "Dimapur"):                  {"lat": 25.9068, "lon": 93.7272},
        ("Nagaland", "Mokokchung"):               {"lat": 26.3248, "lon": 94.5154},
        ("Odisha", "Khordha"):                    {"lat": 20.2961, "lon": 85.8245},
        ("Odisha", "Cuttack"):                    {"lat": 20.4625, "lon": 85.8828},
        ("Odisha", "Sambalpur"):                  {"lat": 21.4669, "lon": 83.9812},
        ("Punjab", "Ludhiana"):                   {"lat": 30.9010, "lon": 75.8573},
        ("Punjab", "Amritsar"):                   {"lat": 31.6340, "lon": 74.8723},
        ("Punjab", "Jalandhar"):                  {"lat": 31.3260, "lon": 75.5762},
        ("Rajasthan", "Jaipur"):                  {"lat": 26.9124, "lon": 75.7873},
        ("Rajasthan", "Jodhpur"):                 {"lat": 26.2389, "lon": 73.0243},
        ("Rajasthan", "Bikaner"):                 {"lat": 28.0229, "lon": 73.3119},
        ("Sikkim", "East Sikkim"):                {"lat": 27.3389, "lon": 88.6065},
        ("Sikkim", "West Sikkim"):                {"lat": 27.2885, "lon": 88.2355},
        ("Sikkim", "South Sikkim"):               {"lat": 27.1666, "lon": 88.3556},
        ("Tamil Nadu", "Chennai"):                {"lat": 13.0827, "lon": 80.2707},
        ("Tamil Nadu", "Madurai"):                {"lat": 9.9252,  "lon": 78.1198},
        ("Tamil Nadu", "Coimbatore"):             {"lat": 11.0168, "lon": 76.9558},
        ("Telangana", "Hyderabad"):               {"lat": 17.3850, "lon": 78.4867},
        ("Telangana", "Warangal"):                {"lat": 17.9689, "lon": 79.5941},
        ("Telangana", "Nizamabad"):               {"lat": 18.6725, "lon": 78.0941},
        ("Tripura", "West Tripura"):              {"lat": 23.8315, "lon": 91.2868},
        ("Tripura", "South Tripura"):             {"lat": 23.2505, "lon": 91.4544},
        ("Tripura", "Dhalai"):                    {"lat": 23.9167, "lon": 91.8500},
        ("Uttar Pradesh", "Lucknow"):             {"lat": 26.8467, "lon": 80.9462},
        ("Uttar Pradesh", "Varanasi"):            {"lat": 25.3176, "lon": 82.9739},
        ("Uttar Pradesh", "Kanpur"):              {"lat": 26.4499, "lon": 80.3319},
        ("Uttarakhand", "Dehradun"):              {"lat": 30.3165, "lon": 78.0322},
        ("Uttarakhand", "Haridwar"):              {"lat": 29.9457, "lon": 78.1642},
        ("Uttarakhand", "Nainital"):              {"lat": 29.3919, "lon": 79.4542},
        ("West Bengal", "Kolkata"):               {"lat": 22.5726, "lon": 88.3639},
        ("West Bengal", "Darjeeling"):            {"lat": 27.0410, "lon": 88.2663},
        ("West Bengal", "Howrah"):                {"lat": 22.5958, "lon": 88.2636},
    }

    state_districts = {}
    for (st, dist) in district_cfg.keys():
        state_districts.setdefault(st, []).append(dist)

    states_to_gen = [state] if state else ALL_STATES
    rows = []
    for s in states_to_gen:
        districts = state_districts.get(s, ["District 1", "District 2", "District 3"])
        code = _state_code(s)
        rng = random.Random(f"stations:{s}")
        for i in range(SAMPLE_STATIONS_PER_STATE):
            dist = districts[i] if i < len(districts) else f"District {i + 1}"
            coord = district_cfg.get((s, dist), {"lat": 22.0, "lon": 78.0})
            rows.append({
                "station_id":   f"CGWB_{code}_{i + 1:04d}",
                "station_name": f"{s} Benchmark Well ({dist} Approx)",
                "state":        s,
                "district":     dist,
                "block":        f"{dist} Block",
                "latitude":     coord["lat"],
                "longitude":    coord["lon"],
                "aquifer_type": rng.choice(["Alluvial", "Hard Rock", "Basalt"]),
                "well_depth_m": round(rng.uniform(25, 80), 1),
                "station_type": "DWLR",
            })
    return pd.DataFrame(rows)


def _generate_sample_readings(
    state: str,
    district: str = None,
    days: int = 30,
    since: datetime = None,
    until: datetime = None,
) -> pd.DataFrame:
    """
    Generate realistic synthetic DWLR readings on a fixed 15-minute grid.
    - If 'since' is provided: generates incremental readings from 'since' up to 'until' (or now).
    - If 'since' is None: generates the initial baseline history of 'days'.
    """
    import random
    import math
    base_wl_map = {
        "Rajasthan": 18.0, "Gujarat": 22.0, "Maharashtra": 8.0,
        "Uttar Pradesh": 6.0, "Punjab": 12.0, "Haryana": 11.0,
    }
    base_wl  = base_wl_map.get(state, 10.0)
    stations = _generate_sample_stations(state)

    ref_now = until or (datetime.now(since.tzinfo) if (since and since.tzinfo) else datetime.now())
    end_ts = _snap_to_15min(ref_now)

    if since:
        start_ts = _snap_to_15min(since)
        if start_ts <= since:
            start_ts += timedelta(minutes=15)
        if start_ts > end_ts:
            # Up to date: no new 15-minute interval has elapsed
            return pd.DataFrame(columns=[
                "station_id", "station_name", "state", "district",
                "timestamp", "water_level_m", "data_quality", "data_quality_flag"
            ])
    else:
        start_ts = end_ts - timedelta(days=days)

    baseline_start = end_ts - timedelta(days=max(days, 30))
    rows     = []

    for _, stn in stations.iterrows():
        rng = random.Random(f"readings:{stn['station_id']}")
        station_bias = rng.uniform(-2.8, 2.8)
        long_term_trend = rng.uniform(-0.015, 0.02) / 24
        seasonal_amp = rng.uniform(0.6, 2.2)
        daily_amp = rng.uniform(0.02, 0.12)
        monsoon_gain = rng.uniform(0.8, 2.4)
        recharge_pulse_remaining = 0.0

        ts = start_ts
        while ts <= end_ts:
            elapsed_days = (ts - baseline_start).total_seconds() / 86400
            day_fraction = (ts.hour * 60 + ts.minute) / 1440
            seasonal_wave = seasonal_amp * math.sin((elapsed_days / max(days, 30)) * 2 * math.pi)
            daily_wave = daily_amp * math.sin(day_fraction * 2 * math.pi)

            # Monsoon months get shallower readings (recharge / recovery).
            monsoon_component = 0.0
            if ts.month in [7, 8, 9]:
                monsoon_component = -monsoon_gain
            elif ts.month in [6, 10]:
                monsoon_component = -(monsoon_gain * 0.45)

            # Occasional recharge pulses in wetter months produce short recoveries.
            if ts.hour == 0 and ts.minute == 0 and ts.month in [6, 7, 8, 9, 10] and rng.random() < 0.22:
                recharge_pulse_remaining = rng.uniform(0.15, 0.6)
            pulse_effect = -recharge_pulse_remaining
            recharge_pulse_remaining = max(0.0, recharge_pulse_remaining * 0.94)

            noise = rng.uniform(-0.025, 0.025)
            wl = base_wl + station_bias + (elapsed_days * long_term_trend) + seasonal_wave + daily_wave + monsoon_component + pulse_effect + noise
            wl = round(max(1.0, wl), 2)
            rows.append({
                "station_id":        stn["station_id"],
                "station_name":      stn["station_name"],
                "state":             state,
                "district":          stn["district"],
                "timestamp":         ts,
                "water_level_m":     wl,
                "data_quality":      "Good",
                "data_quality_flag": "SIMULATED",
            })
            ts += timedelta(minutes=15)   # 15-min interval matches real DWLR

    return pd.DataFrame(rows)

def _generate_sample_rainfall(stations_df, days: int = 365):
    """
    Generate synthetic daily rainfall for Task 2.
    Monsoon months (Jul-Sep) get heavy rain, other months get minimal.
    """
    import random
    from datetime import datetime, timedelta

    if stations_df.empty or "state" not in stations_df.columns:
        return pd.DataFrame(columns=["state", "district", "date", "rainfall_mm"])

    rows = []
    end_date   = datetime.now().date()
    start_date = end_date - timedelta(days=max(days, 30))

    # Get unique state-district pairs
    if "district" in stations_df.columns:
        pairs = stations_df[["state", "district"]].drop_duplicates().to_dict("records")
    else:
        pairs = [{"state": s, "district": "District 1"} for s in stations_df["state"].unique()]

    for pair in pairs:
        rng = random.Random(f"rainfall:{pair['state']}:{pair['district']}:{days}")
        current = start_date
        while current <= end_date:
            month = current.month
            if month in [7, 8, 9]:      # Monsoon
                rainfall = rng.uniform(5, 120)
            elif month in [6, 10]:       # Pre/post monsoon transition
                rainfall = rng.uniform(1, 40)
            elif month in [11, 12, 1]:   # Winter
                rainfall = rng.uniform(0, 8)
            else:                         # Summer / pre-monsoon dry
                rainfall = rng.uniform(0, 3)

            # Occasional heavy events
            if rng.random() < 0.08:
                rainfall *= 3

            rows.append({
                "state":       pair["state"],
                "district":    pair["district"],
                "date":        current,
                "rainfall_mm": round(min(rainfall, 400), 1),
            })
            current += timedelta(days=1)

    log.info(f"Generated {len(rows)} synthetic rainfall records for Task 2.")
    return pd.DataFrame(rows)


def _ensure_rainfall_coverage(
    stations_df: pd.DataFrame,
    rainfall_df: pd.DataFrame,
    days: int,
) -> pd.DataFrame:
    """Backfill rainfall for offline/demo runs when station coverage is missing."""
    if stations_df.empty:
        return rainfall_df

    required_pairs = {
        (str(row["state"]).strip().title(), str(row["district"]).strip().title())
        for _, row in stations_df[["state", "district"]].drop_duplicates().iterrows()
    }
    provided_pairs = set()
    if not rainfall_df.empty and {"state", "district"}.issubset(rainfall_df.columns):
        provided_pairs = {
            (str(row["state"]).strip().title(), str(row["district"]).strip().title())
            for _, row in rainfall_df[["state", "district"]].drop_duplicates().iterrows()
        }

    if not rainfall_df.empty and required_pairs.issubset(provided_pairs):
        return rainfall_df

    log.info("Rainfall coverage incomplete for fallback data — generating synthetic rainfall.")
    return _generate_sample_rainfall(stations_df, days=max(days, 365))


# ═══════════════════════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════════════════════
def save_raw(df: pd.DataFrame, filename: str) -> Path:
    """Save DataFrame to raw/ folder as CSV with timestamp + latest copy."""
    if df.empty:
        log.warning(f"  Nothing to save for {filename}")
        return None
    filepath = RAW_DIR / filename
    df.to_csv(filepath, index=False)
    log.info(f"  Saved {len(df)} rows → {filepath}")
    return filepath


# ═══════════════════════════════════════════════════════════════
# DB WRITE — clean + write to TimescaleDB
# ═══════════════════════════════════════════════════════════════
def write_to_db(
    stations_df: pd.DataFrame,
    readings_df: pd.DataFrame,
    rainfall_df: pd.DataFrame,
):
    """
    Run cleaning pipeline and write all three datasets to TimescaleDB.
    Skips gracefully if DB is unreachable (e.g. running without Docker).
    """
    try:
        from clean_data import run_cleaning_pipeline
        from db_writer import DBWriter

        clean_r, clean_s, clean_rf = run_cleaning_pipeline(
            readings_df, stations_df, rainfall_df
        )

        db = DBWriter()
        db.ensure_schema()
        db.upsert_stations(clean_s)
        if not clean_r.empty:
            db.insert_readings(clean_r)
        else:
            log.info("  No new telemetry readings to insert (telemetry already up to date).")
        if clean_rf.empty:
            from clean_data import clean_rainfall
            clean_rf, _ = clean_rainfall(_generate_sample_rainfall(clean_s))
        if not clean_rf.empty:
            db.upsert_rainfall(clean_rf)
        db.close()
        log.info("  Written to TimescaleDB ✓")

    except ImportError:
        log.warning("  db_writer not available — skipping DB write.")
    except Exception as e:
        log.error(f"  DB write failed: {e} — data saved to raw/ only.")


# ═══════════════════════════════════════════════════════════════
# SINGLE PIPELINE RUN
# ═══════════════════════════════════════════════════════════════
def run_once(
    state: str = None,
    district: str = None,
    days: int = 30,
    source: str = "live",
    refresh: bool = False,
):
    """Execute one full fetch → save → DB write cycle."""
    log.info("=" * 55)
    log.info("  JalDrishti DWLR Scraper — Pipeline Run")
    log.info(f"  State   : {state or 'ALL'}")
    log.info(f"  District: {district or 'ALL'}")
    log.info(f"  Days    : {days}")
    log.info(f"  Source  : {source}")
    log.info("=" * 55)

    start = time.time()

    # Query latest existing benchmark telemetry timestamp in DB to avoid regenerating full 30-day baseline
    since = None
    try:
        from db_writer import DBWriter
        db_chk = DBWriter()
        latest_bm_ts = db_chk.get_latest_benchmark_reading_time()
        db_chk.close()
        if latest_bm_ts:
            since = latest_bm_ts
            log.info(f"  Existing benchmark telemetry high-water mark: {since}")
    except Exception as e:
        log.warning(f"  Could not check existing benchmark timestamp: {e}")

    if source == "sample":
        log.info("Running in SAMPLE mode (offline)")
        stations_df = _generate_sample_stations(state)
        if state:
            readings_df = _generate_sample_readings(state, district, days, since=since)
        else:
            readings_df = pd.concat(
                [_generate_sample_readings(s, district, days, since=since) for s in ALL_STATES],
                ignore_index=True,
            )
        rainfall_df = _generate_sample_rainfall(stations_df, days=max(days, 365))
    else:
        session = make_session()

        # Step 1 — Station Master
        log.info("Step 1/3 — Fetching station master …")
        stations_df = fetch_station_master(session, state)

        # Step 2 — Water Level Readings
        log.info("Step 2/3 — Fetching water level readings …")
        states_to_fetch = [state] if state else ALL_STATES
        all_readings = []
        for s in states_to_fetch:
            df = fetch_water_levels_batch(session, s, district, days, since=since)
            all_readings.append(df)
            time.sleep(0.05)   # polite rate limit

        readings_df = (
            pd.concat(all_readings, ignore_index=True)
            if all_readings else pd.DataFrame()
        )

        # Step 3 — Rainfall
        log.info("Step 3/3 — Fetching IMD rainfall …")
        states_list = [state] if state else ALL_STATES
        rainfall_df = fetch_rainfall(session, states_list)
        rainfall_df = _ensure_rainfall_coverage(stations_df, rainfall_df, days)

    # Save raw files
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_raw(stations_df, f"stations_{ts}.csv")
    save_raw(readings_df, f"readings_{ts}.csv")
    save_raw(rainfall_df, f"rainfall_{ts}.csv")
    save_raw(stations_df, "stations_latest.csv")
    save_raw(readings_df, "readings_latest.csv")
    save_raw(rainfall_df, "rainfall_latest.csv")

    # Write to TimescaleDB
    write_to_db(stations_df, readings_df, rainfall_df)

    elapsed = round(time.time() - start, 2)
    log.info("=" * 55)
    log.info(f"  Done in {elapsed}s")
    log.info(f"  Stations : {len(stations_df)}")
    log.info(f"  Readings : {len(readings_df)}")
    log.info(f"  Rainfall : {len(rainfall_df)}")
    log.info("=" * 55)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="JalDrishti DWLR Scraper — fetches groundwater data from India-WRIS"
    )
    parser.add_argument("--state",    type=str,  default=None,   help="State name (default: all)")
    parser.add_argument("--district", type=str,  default=None,   help="District name (default: all)")
    parser.add_argument("--days",     type=int,  default=30,     help="Days of history (default: 30)")
    parser.add_argument("--source",   type=str,  default="live",
                        choices=["live", "sample"],              help="live = India-WRIS, sample = local")
    parser.add_argument("--once",     action="store_true",       help="Run once and exit")
    parser.add_argument("--refresh",  action="store_true",       help="Force full station master refresh")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)

    if args.once:
        run_once(args.state, args.district, args.days, args.source, args.refresh)
    else:
        log.info(f"Starting continuous scraper (interval: {FETCH_INTERVAL}s) …")
        first_run = True
        while True:
            try:
                run_once(
                    args.state, args.district, args.days,
                    args.source, refresh=first_run,
                )
                first_run = False
            except Exception as e:
                log.error(f"Pipeline error: {e}", exc_info=True)
            log.info(f"Sleeping {FETCH_INTERVAL}s …")
            time.sleep(FETCH_INTERVAL)


if __name__ == "__main__":
    main()
