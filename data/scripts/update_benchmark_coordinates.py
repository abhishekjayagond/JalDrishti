"""
data/scripts/update_benchmark_coordinates.py
Audits and updates the 78 nationwide simulated benchmark stations in TimescaleDB with
authentic district-level geographic coordinates.
Labels station positions as approximate district-level placements.
Preserves all 390 verified Karnataka CGWB AI stations completely untouched.
"""

import sys
from pathlib import Path
from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from db.database import SessionLocal

# Reliable geographic references: authoritative district headquarters / centroid coordinates
DISTRICT_COORDINATES = {
    # Andhra Pradesh
    ("Andhra Pradesh", "Guntur"):             {"lat": 16.3067, "lon": 80.4365},
    ("Andhra Pradesh", "Kurnool"):            {"lat": 15.8281, "lon": 78.0373},
    ("Andhra Pradesh", "Visakhapatnam"):      {"lat": 17.6868, "lon": 83.2185},
    # Assam
    ("Assam", "Kamrup"):                      {"lat": 26.1445, "lon": 91.7362},
    ("Assam", "Dibrugarh"):                   {"lat": 27.4728, "lon": 94.9120},
    ("Assam", "Cachar"):                      {"lat": 24.8333, "lon": 92.7789},
    # Bihar
    ("Bihar", "Patna"):                       {"lat": 25.5941, "lon": 85.1376},
    ("Bihar", "Gaya"):                        {"lat": 24.7914, "lon": 85.0002},
    ("Bihar", "Muzaffarpur"):                 {"lat": 26.1209, "lon": 85.3647},
    # Chhattisgarh
    ("Chhattisgarh", "Raipur"):               {"lat": 21.2514, "lon": 81.6296},
    ("Chhattisgarh", "Bilaspur"):             {"lat": 22.0797, "lon": 82.1409},
    ("Chhattisgarh", "Bastar"):               {"lat": 19.0740, "lon": 82.0298},
    # Goa
    ("Goa", "North Goa"):                     {"lat": 15.4909, "lon": 73.8278},
    ("Goa", "South Goa"):                     {"lat": 15.2832, "lon": 73.9862},
    ("Goa", "Tiswadi"):                       {"lat": 15.4600, "lon": 73.8700},
    # Gujarat
    ("Gujarat", "Ahmedabad"):                 {"lat": 23.0225, "lon": 72.5714},
    ("Gujarat", "Rajkot"):                    {"lat": 22.3039, "lon": 70.8022},
    ("Gujarat", "Surat"):                     {"lat": 21.1702, "lon": 72.8311},
    # Haryana
    ("Haryana", "Hisar"):                     {"lat": 29.1492, "lon": 75.7217},
    ("Haryana", "Karnal"):                    {"lat": 29.6857, "lon": 76.9905},
    ("Haryana", "Rohtak"):                    {"lat": 28.8955, "lon": 76.6066},
    # Himachal Pradesh
    ("Himachal Pradesh", "Shimla"):           {"lat": 31.1048, "lon": 77.1734},
    ("Himachal Pradesh", "Kangra"):           {"lat": 32.0998, "lon": 76.2691},
    ("Himachal Pradesh", "Mandi"):            {"lat": 31.7087, "lon": 76.9320},
    # Jharkhand
    ("Jharkhand", "Ranchi"):                  {"lat": 23.3441, "lon": 85.3096},
    ("Jharkhand", "Dhanbad"):                 {"lat": 23.7957, "lon": 86.4304},
    ("Jharkhand", "East Singhbhum"):          {"lat": 22.8046, "lon": 86.2029},
    # Karnataka
    ("Karnataka", "Bengaluru Urban"):         {"lat": 12.9716, "lon": 77.5946},
    ("Karnataka", "Mysuru"):                  {"lat": 12.2958, "lon": 76.6394},
    ("Karnataka", "Belagavi"):                {"lat": 15.8497, "lon": 74.4977},
    # Kerala
    ("Kerala", "Thiruvananthapuram"):         {"lat": 8.5241,  "lon": 76.9366},
    ("Kerala", "Ernakulam"):                  {"lat": 9.9816,  "lon": 76.2999},
    ("Kerala", "Palakkad"):                   {"lat": 10.7867, "lon": 76.6548},
    # Madhya Pradesh
    ("Madhya Pradesh", "Bhopal"):             {"lat": 23.2599, "lon": 77.4126},
    ("Madhya Pradesh", "Indore"):             {"lat": 22.7196, "lon": 75.8577},
    ("Madhya Pradesh", "Jabalpur"):           {"lat": 23.1815, "lon": 79.9864},
    # Maharashtra
    ("Maharashtra", "Pune"):                  {"lat": 18.5204, "lon": 73.8567},
    ("Maharashtra", "Nagpur"):                {"lat": 21.1458, "lon": 79.0882},
    ("Maharashtra", "Nashik"):                {"lat": 19.9975, "lon": 73.7898},
    # Meghalaya
    ("Meghalaya", "East Khasi Hills"):        {"lat": 25.5788, "lon": 91.8933},
    ("Meghalaya", "West Garo Hills"):         {"lat": 25.5141, "lon": 90.2023},
    ("Meghalaya", "Ri-Bhoi"):                 {"lat": 25.9036, "lon": 91.8803},
    # Mizoram
    ("Mizoram", "Aizawl"):                    {"lat": 23.7271, "lon": 92.7176},
    ("Mizoram", "Lunglei"):                   {"lat": 22.8878, "lon": 92.7388},
    ("Mizoram", "Champhai"):                  {"lat": 23.4756, "lon": 93.3283},
    # Nagaland
    ("Nagaland", "Kohima"):                   {"lat": 25.6751, "lon": 94.1086},
    ("Nagaland", "Dimapur"):                  {"lat": 25.9068, "lon": 93.7272},
    ("Nagaland", "Mokokchung"):               {"lat": 26.3248, "lon": 94.5154},
    # Odisha
    ("Odisha", "Khordha"):                    {"lat": 20.2961, "lon": 85.8245},
    ("Odisha", "Cuttack"):                    {"lat": 20.4625, "lon": 85.8828},
    ("Odisha", "Sambalpur"):                  {"lat": 21.4669, "lon": 83.9812},
    # Punjab
    ("Punjab", "Ludhiana"):                   {"lat": 30.9010, "lon": 75.8573},
    ("Punjab", "Amritsar"):                   {"lat": 31.6340, "lon": 74.8723},
    ("Punjab", "Jalandhar"):                  {"lat": 31.3260, "lon": 75.5762},
    # Rajasthan
    ("Rajasthan", "Jaipur"):                  {"lat": 26.9124, "lon": 75.7873},
    ("Rajasthan", "Jodhpur"):                 {"lat": 26.2389, "lon": 73.0243},
    ("Rajasthan", "Bikaner"):                 {"lat": 28.0229, "lon": 73.3119},
    # Sikkim
    ("Sikkim", "East Sikkim"):                {"lat": 27.3389, "lon": 88.6065},
    ("Sikkim", "West Sikkim"):                {"lat": 27.2885, "lon": 88.2355},
    ("Sikkim", "South Sikkim"):               {"lat": 27.1666, "lon": 88.3556},
    # Tamil Nadu
    ("Tamil Nadu", "Chennai"):                {"lat": 13.0827, "lon": 80.2707},
    ("Tamil Nadu", "Madurai"):                {"lat": 9.9252,  "lon": 78.1198},
    ("Tamil Nadu", "Coimbatore"):             {"lat": 11.0168, "lon": 76.9558},
    # Telangana
    ("Telangana", "Hyderabad"):               {"lat": 17.3850, "lon": 78.4867},
    ("Telangana", "Warangal"):                {"lat": 17.9689, "lon": 79.5941},
    ("Telangana", "Nizamabad"):               {"lat": 18.6725, "lon": 78.0941},
    # Tripura
    ("Tripura", "West Tripura"):              {"lat": 23.8315, "lon": 91.2868},
    ("Tripura", "South Tripura"):             {"lat": 23.2505, "lon": 91.4544},
    ("Tripura", "Dhalai"):                    {"lat": 23.9167, "lon": 91.8500},
    # Uttar Pradesh
    ("Uttar Pradesh", "Lucknow"):             {"lat": 26.8467, "lon": 80.9462},
    ("Uttar Pradesh", "Varanasi"):            {"lat": 25.3176, "lon": 82.9739},
    ("Uttar Pradesh", "Kanpur"):              {"lat": 26.4499, "lon": 80.3319},
    # Uttarakhand
    ("Uttarakhand", "Dehradun"):              {"lat": 30.3165, "lon": 78.0322},
    ("Uttarakhand", "Haridwar"):              {"lat": 29.9457, "lon": 78.1642},
    ("Uttarakhand", "Nainital"):              {"lat": 29.3919, "lon": 79.4542},
    # West Bengal
    ("West Bengal", "Kolkata"):               {"lat": 22.5726, "lon": 88.3639},
    ("West Bengal", "Darjeeling"):            {"lat": 27.0410, "lon": 88.2663},
    ("West Bengal", "Howrah"):                {"lat": 22.5958, "lon": 88.2636},
}

def audit_and_update_benchmarks():
    db = SessionLocal()
    try:
        stations = db.execute(text("SELECT station_id, state, district, latitude, longitude FROM stations WHERE station_id LIKE 'CGWB_%' ORDER BY state, station_id")).fetchall()
        print(f"Auditing {len(stations)} benchmark stations in database...")

        corrected = 0
        unresolved = 0

        for stn_id, state, district, old_lat, old_lon in stations:
            key = (state, district)
            target = DISTRICT_COORDINATES.get(key)
            if not target:
                print(f"Unresolved location mapping for station {stn_id}: ({state}, {district})")
                unresolved += 1
                continue

            new_lat = target["lat"]
            new_lon = target["lon"]
            # Station label clearly identifying approximate district-level placement
            station_name = f"{state} Benchmark Well ({district} Approx)"

            # Check if correction needed
            dist_diff = abs(old_lat - new_lat) + abs(old_lon - new_lon)
            if dist_diff > 0.01:
                corrected += 1
                print(f"Correcting {stn_id} [{state} - {district}]: ({old_lat:.4f}, {old_lon:.4f}) -> ({new_lat:.4f}, {new_lon:.4f})")

            db.execute(text("""
                UPDATE stations
                SET latitude = :lat,
                    longitude = :lon,
                    station_name = :name
                WHERE station_id = :stn_id
            """), {
                "lat": new_lat,
                "lon": new_lon,
                "name": station_name,
                "stn_id": stn_id
            })

        db.commit()
        print("\nAudit Summary:")
        print(f"  Total benchmark stations: {len(stations)}")
        print(f"  Mismatches corrected:     {corrected}")
        print(f"  Unresolved mismatches:    {unresolved}")
        return corrected, unresolved
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    audit_and_update_benchmarks()
