"""
study_data_loader.py — Load data from the two research papers into the DB.

Data hardcoded from:
  1. utilisation_pattern_PMJAY.pdf (KGMU, 2023) → specialty_priority table
  2. CHSI_cost_study.pdf (BMC Health Services Research, 2022) → reference only
     (CHSI multipliers already seeded in hospital_type_multipliers by init_db.py)

No LLM needed. Run AFTER hbp_2022_parser.py (needs specialties table populated).
Run: python src/parsers/study_data_loader.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv

load_dotenv()

SOURCE = "KGMU_utilisation_2023"

# ── Data from Table 1 & Table 3 of utilisation_pattern_PMJAY.pdf ──────────────
# Fields: specialty_name, volume_pct (% of total packages), cost_pct (% of total spend)
# volume_rank and cost_rank are assigned below by sorting.
#
# Total packages: 4,542 | Total spend: ₹32,21,73,036 (2023, KGMU)
#
# Specialty names must loosely match what HBP-2022 parser inserts into specialties table.

SPECIALTY_DATA = [
    # Medical packages
    {"name": "Cardiology",                          "volume_pct": 22.8, "cost_pct": 40.7},
    {"name": "General Medicine",                    "volume_pct":  6.7, "cost_pct":  2.0},
    {"name": "Radiotherapy",                        "volume_pct":  6.0, "cost_pct":  0.2},
    {"name": "Neurology",                           "volume_pct":  3.5, "cost_pct":  1.1},
    {"name": "Pulmonary and Critical Care Medicine","volume_pct":  3.3, "cost_pct":  3.0},
    {"name": "Emergency Medicine",                  "volume_pct":  3.2, "cost_pct":  1.3},
    {"name": "Respiratory Medicine",                "volume_pct":  2.7, "cost_pct":  0.7},
    {"name": "Gastroenterology",                    "volume_pct":  1.8, "cost_pct":  1.5},
    {"name": "Rheumatology",                        "volume_pct":  1.2, "cost_pct":  0.6},
    {"name": "Radiodiagnosis",                      "volume_pct":  0.8, "cost_pct":  1.1},  # from cost table (max pkg ₹4,31,640)
    {"name": "Anesthesiology",                      "volume_pct":  0.5, "cost_pct":  0.5},
    # Surgical packages
    {"name": "Orthopedics",                         "volume_pct": 15.7, "cost_pct": 19.2},
    {"name": "Surgical Oncology",                   "volume_pct":  9.2, "cost_pct":  7.7},
    {"name": "General Surgery",                     "volume_pct":  5.8, "cost_pct":  3.3},
    {"name": "Neurosurgery",                        "volume_pct":  4.5, "cost_pct":  5.6},
    {"name": "Urology",                             "volume_pct":  2.1, "cost_pct":  1.2},
    {"name": "Obstetrics and Gynecology",           "volume_pct":  2.0, "cost_pct":  0.7},
    {"name": "Oral and Maxillofacial Surgery",      "volume_pct":  1.8, "cost_pct":  0.8},
    {"name": "Trauma Surgery",                      "volume_pct":  1.4, "cost_pct":  0.4},
    {"name": "Cardio Thoracic and Vascular Surgery","volume_pct":  0.9, "cost_pct":  2.8},  # costliest surgical pkg ₹3,86,735
    {"name": "Plastic Surgery",                     "volume_pct":  0.3, "cost_pct":  0.6},
]


def assign_ranks(data: list[dict]) -> list[dict]:
    vol_sorted  = sorted(data, key=lambda x: x["volume_pct"], reverse=True)
    cost_sorted = sorted(data, key=lambda x: x["cost_pct"],   reverse=True)
    vol_rank  = {d["name"]: i + 1 for i, d in enumerate(vol_sorted)}
    cost_rank = {d["name"]: i + 1 for i, d in enumerate(cost_sorted)}
    for d in data:
        d["volume_rank"] = vol_rank[d["name"]]
        d["cost_rank"]   = cost_rank[d["name"]]
    return data


def find_or_create_specialty(cursor, name: str) -> str:
    """Look up specialty by name; insert it if not found using a derived code."""
    for prefix_len in (20, 12, 8):
        cursor.execute(
            "SELECT specialty_code FROM dbo.specialties "
            "WHERE LOWER(specialty_name) LIKE LOWER(?)",
            f"%{name[:prefix_len]}%",
        )
        row = cursor.fetchone()
        if row:
            return row[0]

    # Derive a code: initials of each word, max 6 chars, uppercase
    code = "".join(w[0] for w in name.split() if w)[:6].upper()
    # Ensure uniqueness — append digit if collision
    base, suffix = code, 0
    while True:
        cursor.execute("SELECT 1 FROM dbo.specialties WHERE specialty_code = ?", code)
        if not cursor.fetchone():
            break
        suffix += 1
        code = f"{base}{suffix}"

    cursor.execute(
        "INSERT INTO dbo.specialties (specialty_code, specialty_name) VALUES (?, ?)",
        code, name,
    )
    print(f"    → Inserted new specialty: {code} = {name}")
    return code


def main():
    from src.utils.db_connect import get_connection

    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM dbo.specialties")
    count = cursor.fetchone()[0]
    print(f"Specialties table has {count} rows. Loading study data...\n")

    data = assign_ranks(SPECIALTY_DATA)

    inserted = 0

    for d in data:
        code = find_or_create_specialty(cursor, d["name"])

        cursor.execute(
            "IF NOT EXISTS (SELECT 1 FROM dbo.specialty_priority WHERE specialty_code = ?) "
            "INSERT INTO dbo.specialty_priority "
            "(specialty_code, volume_rank, cost_rank, volume_pct, source) "
            "VALUES (?, ?, ?, ?, ?)",
            code,
            code, d["volume_rank"], d["cost_rank"], d["volume_pct"], SOURCE,
        )
        print(f"  [{d['volume_rank']:2d}] {d['name']:<45} vol={d['volume_pct']}%  cost={d['cost_pct']}%  code={code}")
        inserted += 1

    conn.commit()
    conn.close()
    print(f"\nDone. {inserted} inserted.")


if __name__ == "__main__":
    main()
