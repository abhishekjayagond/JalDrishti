"""
data/scripts/seed_ai_stations.py — Idempotent Seeder for Karnataka AI Station Registry
Safely synchronizes the 390 validated Karnataka CGWB observation stations and their
historical annual readings (1994–2025) into the main TimescaleDB database.

Preserves data provenance:
- Readings are tagged with data_quality_flag='HISTORICAL_ANNUAL'.
- Original historical observation dates (first_date) are preserved.
- Existing live or benchmark records are never overwritten.
- Fully idempotent: multiple executions produce identical state.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqlalchemy import text

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from db.database import SessionLocal, check_connection

NODES_CSV = BASE_DIR / "ai" / "data" / "processed" / "annual_nodes.csv"
CLEAN_CSV = BASE_DIR / "ai" / "data" / "processed" / "phase1_karnataka_annual_clean.csv"


def seed_stations() -> dict:
    if not check_connection():
        raise RuntimeError("Database unreachable. Ensure TimescaleDB container is running.")

    if not NODES_CSV.exists():
        raise FileNotFoundError(f"Missing {NODES_CSV}")
    if not CLEAN_CSV.exists():
        raise FileNotFoundError(f"Missing {CLEAN_CSV}")

    nodes_df = pd.read_csv(NODES_CSV)
    clean_df = pd.read_csv(CLEAN_CSV)

    # Filter to candidate stations (390 stations with >=25 years of records)
    cand_ids = set(nodes_df["station_id"])
    cand_clean_df = clean_df[clean_df["station_id"].isin(cand_ids)]

    # Compute max observed water level per station for realistic well depth estimates
    max_depths = cand_clean_df.groupby("station_id")["water_level_mbgl"].max().to_dict()

    db = SessionLocal()
    stats = {
        "candidate_stations_target": len(nodes_df),
        "stations_inserted": 0,
        "stations_skipped": 0,
        "statewide_clean_rows_corpus": len(clean_df),
        "candidate_annual_rows": len(cand_clean_df),
        "readings_inserted": 0,
        "readings_skipped": 0,
    }

    try:
        # 1. Fetch existing station IDs
        existing_ids = set(r[0] for r in db.execute(text("SELECT station_id FROM stations")).fetchall())

        # 2. Insert new stations idempotently
        insert_station_sql = text("""
            INSERT INTO stations (
                station_id, station_name, latitude, longitude,
                state, district, block, well_depth_m, aquifer_type, updated_at
            ) VALUES (
                :station_id, :station_name, :latitude, :longitude,
                :state, :district, :block, :well_depth_m, :aquifer_type, :updated_at
            )
            ON CONFLICT (station_id) DO NOTHING
        """)

        for _, row in nodes_df.iterrows():
            st_id = str(row["station_id"]).strip()
            if st_id in existing_ids:
                stats["stations_skipped"] += 1
                continue

            max_wl = float(max_depths.get(st_id, 25.0))
            est_depth = round(max(max_wl * 1.35, 35.0), 1)
            station_name = f"{row['village']} ({row['block']})" if pd.notna(row.get("village")) else f"Karnataka Well {st_id[:6]}"

            db.execute(insert_station_sql, {
                "station_id": st_id,
                "station_name": station_name,
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "state": "Karnataka",
                "district": str(row["district"]),
                "block": str(row["block"]),
                "well_depth_m": est_depth,
                "aquifer_type": "Hard Rock",
                "updated_at": datetime.now(timezone.utc),
            })
            stats["stations_inserted"] += 1

        db.commit()

        # 3. Seed historical annual observation readings (1994–2025)
        # Using batch upsert with ON CONFLICT DO NOTHING
        insert_reading_sql = text("""
            INSERT INTO dwlr_readings (
                station_id, "timestamp", water_level_m, data_quality_flag, is_anomaly, anomaly_reason
            ) VALUES (
                :station_id, :timestamp, :water_level_m, :data_quality_flag, :is_anomaly, :anomaly_reason
            )
            ON CONFLICT (station_id, "timestamp") DO NOTHING
        """)

        batch = []
        batch_size = 2000

        for _, row in cand_clean_df.iterrows():
            st_id = str(row["station_id"]).strip()
            date_str = str(row["first_date"]).strip() if pd.notna(row.get("first_date")) else f"{int(row['year'])}-05-25"
            try:
                ts = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=12, minute=0, second=0)
            except Exception:
                ts = datetime(int(row["year"]), 5, 25, 12, 0, 0, tzinfo=timezone.utc)

            wl = float(row["water_level_mbgl"]) if pd.notna(row.get("water_level_mbgl")) else None
            if wl is None:
                continue

            batch.append({
                "station_id": st_id,
                "timestamp": ts,
                "water_level_m": wl,
                "data_quality_flag": "HISTORICAL_ANNUAL",
                "is_anomaly": False,
                "anomaly_reason": "",
            })

            if len(batch) >= batch_size:
                res = db.execute(insert_reading_sql, batch)
                stats["readings_inserted"] += res.rowcount if hasattr(res, "rowcount") and res.rowcount != -1 else len(batch)
                db.commit()
                batch = []

        if batch:
            res = db.execute(insert_reading_sql, batch)
            stats["readings_inserted"] += res.rowcount if hasattr(res, "rowcount") and res.rowcount != -1 else len(batch)
            db.commit()

        stats["readings_skipped"] = stats["candidate_annual_rows"] - stats["readings_inserted"]
        return stats

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Starting Idempotent Seeding of AI Stations to TimescaleDB ===")
    res = seed_stations()
    print("Seeding finished successfully:")
    for k, v in res.items():
        print(f"  {k}: {v}")
