"""
hospital_csv_loader.py — Load raw/hospital_directory.csv into the hospitals table.

No LLM needed. Derives hospital_type from Hospital_Category and nabh_accredited
from the Accreditation field.

Run: python src/parsers/hospital_csv_loader.py
"""
import os
import sys
import csv
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv

load_dotenv()

CSV_PATH = os.path.join("raw", "hospital_directory.csv")
BATCH_SIZE = 5000  # rows per commit


def parse_coordinates(coord_str: str) -> tuple[float | None, float | None]:
    """Parse '11.6357989, 92.7120575' → (lat, lon)."""
    if not coord_str or coord_str.strip() == "0":
        return None, None
    parts = coord_str.split(",")
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return None, None


def derive_hospital_type(category: str) -> str:
    """Map raw Hospital_Category to one of: government | mid_private | corporate."""
    if not category:
        return "mid_private"
    cat = category.lower()
    if any(k in cat for k in ("government", "public", "govt", "esic", "central", "municipal",
                               "district", "civil", "military", "armed", "railway", "nhm")):
        return "government"
    if any(k in cat for k in ("corporate", "super", "multi speciality", "multispeciality",
                               "specialty", "speciality", "chain", "apollo", "fortis",
                               "max ", "manipal", "medanta", "narayana", "aster")):
        return "corporate"
    return "mid_private"


def is_nabh(accreditation: str) -> bool:
    if not accreditation:
        return False
    return "nabh" in accreditation.lower()


INT_MAX = 2_147_483_647


def parse_int(val: str) -> int | None:
    if not val or val.strip() in ("0", ""):
        return None
    cleaned = re.sub(r"[^\d]", "", val)
    if not cleaned:
        return None
    n = int(cleaned)
    return n if n <= INT_MAX else None


def parse_bool_field(val: str) -> bool:
    if not val or val.strip() in ("0", "No", "no", ""):
        return False
    return True


INSERT_SQL = """
INSERT INTO dbo.hospitals (
    source_id, hospital_name, hospital_category, hospital_type,
    care_type, discipline, address, location, state, district,
    pincode, latitude, longitude, telephone, mobile, website,
    specialties, accreditation, nabh_accredited, total_beds,
    emergency_services, tariff_range, state_id, district_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def build_row(row: dict) -> tuple | None:
    name = row.get("Hospital_Name", "").strip()
    if not name:
        return None
    lat, lon = parse_coordinates(row.get("Location_Coordinates", ""))
    return (
        parse_int(row.get("Sr_No")),
        name,
        row.get("Hospital_Category") or None,
        derive_hospital_type(row.get("Hospital_Category", "")),
        row.get("Hospital_Care_Type") or None,
        row.get("Discipline_Systems_of_Medicine") or None,
        row.get("Address_Original_First_Line") or None,
        row.get("Location") or None,
        row.get("State") or None,
        row.get("District") or None,
        row.get("Pincode") or None,
        lat,
        lon,
        row.get("Telephone") or None,
        row.get("Mobile_Number") or None,
        row.get("Website") or None,
        row.get("Specialties") or None,
        row.get("Accreditation") or None,
        1 if is_nabh(row.get("Accreditation", "")) else 0,
        parse_int(row.get("Total_Num_Beds")),
        1 if parse_bool_field(row.get("Emergency_Services", "")) else 0,
        row.get("Tariff_Range") or None,
        parse_int(row.get("State_ID")),
        parse_int(row.get("District_ID")),
    )


def load_hospitals(conn):
    cursor = conn.cursor()
    cursor.fast_executemany = True  # array binding — much faster than row-by-row

    cursor.execute("TRUNCATE TABLE dbo.hospitals")
    conn.commit()
    print("Existing hospitals table cleared.")

    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    print(f"Loaded {len(raw_rows)} rows from {CSV_PATH}. Building batch...")

    batch = []
    skipped = 0
    inserted = 0

    for raw in raw_rows:
        row = build_row(raw)
        if row is None:
            skipped += 1
            continue
        batch.append(row)

        if len(batch) >= BATCH_SIZE:
            cursor.executemany(INSERT_SQL, batch)
            conn.commit()
            inserted += len(batch)
            print(f"  {inserted} rows inserted...", flush=True)
            batch = []

    if batch:
        cursor.executemany(INSERT_SQL, batch)
        conn.commit()
        inserted += len(batch)

    print(f"\nDone. {inserted} inserted, {skipped} skipped.")


def main():
    from src.utils.db_connect import get_connection

    conn = get_connection()
    load_hospitals(conn)
    conn.close()


if __name__ == "__main__":
    main()
