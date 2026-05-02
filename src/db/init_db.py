"""
init_db.py — Create schema and seed all static tables.
Run once before any parsers:  python src/db/init_db.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.utils.db_connect import get_connection

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# ── Static seed data ───────────────────────────────────────────────────────────

BED_DAY_RATES = [
    ("routine_ward",   2300, "HBP_2022"),
    ("hdu",            3630, "HBP_2022"),
    ("icu",            9350, "HBP_2022"),
    ("icu_ventilator", 9900, "HBP_2022"),
]

HOSPITAL_TYPE_MULTIPLIERS = [
    ("government", 1.0, 1.0,
     "HBP rate IS the govt rate (CHSI study baseline)"),
    ("mid_private", 1.5, 2.0,
     "Derived from CHSI private/public IPD cost ratio"),
    ("corporate",   2.5, 3.5,
     "Super-specialty corporate hospitals; CHSI adjusted ratio"),
]

# Tier 1 = 8 NPC metros. Tier 2 = state capitals + large cities. Tier 3 = default (everything else).
CITY_TIER_MAP = [
    # ── Tier 1 metros ──
    ("Delhi",      "Delhi",         1, 1),
    ("Mumbai",     "Maharashtra",   1, 1),
    ("Kolkata",    "West Bengal",   1, 1),
    ("Chennai",    "Tamil Nadu",    1, 1),
    ("Bengaluru",  "Karnataka",     1, 1),
    ("Ahmedabad",  "Gujarat",       1, 1),
    ("Hyderabad",  "Telangana",     1, 1),
    ("Pune",       "Maharashtra",   1, 1),

    # ── Tier 2 — state capitals ──
    ("Jaipur",           "Rajasthan",          2, 0),
    ("Lucknow",          "Uttar Pradesh",      2, 0),
    ("Bhopal",           "Madhya Pradesh",     2, 0),
    ("Patna",            "Bihar",              2, 0),
    ("Raipur",           "Chhattisgarh",       2, 0),
    ("Ranchi",           "Jharkhand",          2, 0),
    ("Bhubaneswar",      "Odisha",             2, 0),
    ("Chandigarh",       "Chandigarh",         2, 0),
    ("Shimla",           "Himachal Pradesh",   2, 0),
    ("Dehradun",         "Uttarakhand",        2, 0),
    ("Srinagar",         "Jammu & Kashmir",    2, 0),
    ("Jammu",            "Jammu & Kashmir",    2, 0),
    ("Gandhinagar",      "Gujarat",            2, 0),
    ("Panaji",           "Goa",                2, 0),
    ("Thiruvananthapuram","Kerala",            2, 0),
    ("Guwahati",         "Assam",              2, 0),
    ("Shillong",         "Meghalaya",          2, 0),
    ("Aizawl",           "Mizoram",            2, 0),
    ("Kohima",           "Nagaland",           2, 0),
    ("Imphal",           "Manipur",            2, 0),
    ("Agartala",         "Tripura",            2, 0),
    ("Itanagar",         "Arunachal Pradesh",  2, 0),
    ("Gangtok",          "Sikkim",             2, 0),
    ("Amaravati",        "Andhra Pradesh",     2, 0),

    # ── Tier 2 — large non-capital cities ──
    ("Nagpur",          "Maharashtra",    2, 0),
    ("Nashik",          "Maharashtra",    2, 0),
    ("Aurangabad",      "Maharashtra",    2, 0),
    ("Surat",           "Gujarat",        2, 0),
    ("Vadodara",        "Gujarat",        2, 0),
    ("Kanpur",          "Uttar Pradesh",  2, 0),
    ("Varanasi",        "Uttar Pradesh",  2, 0),
    ("Agra",            "Uttar Pradesh",  2, 0),
    ("Meerut",          "Uttar Pradesh",  2, 0),
    ("Allahabad",       "Uttar Pradesh",  2, 0),
    ("Coimbatore",      "Tamil Nadu",     2, 0),
    ("Madurai",         "Tamil Nadu",     2, 0),
    ("Tiruchirappalli", "Tamil Nadu",     2, 0),
    ("Visakhapatnam",   "Andhra Pradesh", 2, 0),
    ("Vijayawada",      "Andhra Pradesh", 2, 0),
    ("Indore",          "Madhya Pradesh", 2, 0),
    ("Jabalpur",        "Madhya Pradesh", 2, 0),
    ("Kochi",           "Kerala",         2, 0),
    ("Kozhikode",       "Kerala",         2, 0),
    ("Amritsar",        "Punjab",         2, 0),
    ("Ludhiana",        "Punjab",         2, 0),
    ("Jodhpur",         "Rajasthan",      2, 0),
    ("Kota",            "Rajasthan",      2, 0),
    ("Ghaziabad",       "Uttar Pradesh",  2, 0),
    ("Noida",           "Uttar Pradesh",  2, 0),
    ("Faridabad",       "Haryana",        2, 0),
    ("Gurugram",        "Haryana",        2, 0),
    ("Mysuru",          "Karnataka",      2, 0),
    ("Mangaluru",       "Karnataka",      2, 0),
    ("Hubli",           "Karnataka",      2, 0),
    ("Bhubaneswar",     "Odisha",         2, 0),
    ("Cuttack",         "Odisha",         2, 0),
]


def run_schema(conn):
    with open(SCHEMA_PATH, "r") as f:
        sql = f.read()

    cursor = conn.cursor()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            cursor.execute(stmt)
    conn.commit()
    print("[schema] Tables created.")


def seed_bed_day_rates(conn):
    cursor = conn.cursor()
    for category, rate, version in BED_DAY_RATES:
        cursor.execute(
            "IF NOT EXISTS (SELECT 1 FROM dbo.bed_day_rates WHERE bed_category = ?) "
            "INSERT INTO dbo.bed_day_rates (bed_category, rate_per_day, hbp_version) VALUES (?, ?, ?)",
            category, category, rate, version,
        )
    conn.commit()
    print(f"[seed] bed_day_rates — {len(BED_DAY_RATES)} rows.")


def seed_hospital_type_multipliers(conn):
    cursor = conn.cursor()
    for htype, low, high, notes in HOSPITAL_TYPE_MULTIPLIERS:
        cursor.execute(
            "IF NOT EXISTS (SELECT 1 FROM dbo.hospital_type_multipliers WHERE hospital_type = ?) "
            "INSERT INTO dbo.hospital_type_multipliers "
            "(hospital_type, multiplier_low, multiplier_high, notes) VALUES (?, ?, ?, ?)",
            htype, htype, low, high, notes,
        )
    conn.commit()
    print(f"[seed] hospital_type_multipliers — {len(HOSPITAL_TYPE_MULTIPLIERS)} rows.")


def seed_city_tier_map(conn):
    cursor = conn.cursor()
    inserted = 0
    for city, state, tier, is_metro in CITY_TIER_MAP:
        cursor.execute(
            "IF NOT EXISTS (SELECT 1 FROM dbo.city_tier_map WHERE city_name = ?) "
            "INSERT INTO dbo.city_tier_map (city_name, state, tier, is_metro) VALUES (?, ?, ?, ?)",
            city, city, state, tier, is_metro,
        )
        inserted += 1
    conn.commit()
    print(f"[seed] city_tier_map — {inserted} rows.")


def main():
    print("Connecting to Azure SQL...")
    conn = get_connection()
    print("Connected.\n")

    run_schema(conn)
    seed_bed_day_rates(conn)
    seed_hospital_type_multipliers(conn)
    seed_city_tier_map(conn)

    conn.close()
    print("\nDone. Database is ready for parsers.")


if __name__ == "__main__":
    main()
