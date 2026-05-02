"""
hbp_2022_json_loader.py — Load raw/HBP_2022_formatted.txt into specialties,
packages, and procedures tables.

No LLM needed. Direct JSON → DB loader.
Run: python src/parsers/hbp_2022_json_loader.py
"""
import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv

load_dotenv()

JSON_PATH = os.path.join("raw", "HBP_2022_formatted.txt")


def upsert_specialty(cursor, code: str, name: str):
    # Use shortest/simplest name if code already exists
    cursor.execute(
        "IF NOT EXISTS (SELECT 1 FROM dbo.specialties WHERE specialty_code = ?) "
        "INSERT INTO dbo.specialties (specialty_code, specialty_name) VALUES (?, ?)",
        code, code, name,
    )


def upsert_package(cursor, pkg_code: str, pkg_name: str, spec_code: str):
    cursor.execute(
        "IF NOT EXISTS (SELECT 1 FROM dbo.packages WHERE package_code = ?) "
        "INSERT INTO dbo.packages (package_code, package_name, specialty_code) VALUES (?, ?, ?)",
        pkg_code, pkg_code, pkg_name, spec_code,
    )


def upsert_procedure(cursor, p: dict):
    cursor.execute(
        "IF NOT EXISTS (SELECT 1 FROM dbo.procedures WHERE procedure_code = ?) "
        "INSERT INTO dbo.procedures "
        "(procedure_code, procedure_name, package_code, tier1_inr, tier2_inr, tier3_inr, "
        "implant_mapped, implant_cost_inr, stratification_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        p["procedure_code"],
        p["procedure_code"], p.get("procedure_name"), p["package_code"],
        p.get("tier1_inr"), p.get("tier2_inr"), p.get("tier3_inr"),
        1 if p.get("implant_mapped") else 0,
        p.get("implant_cost_inr"),
        p.get("stratification_text") or p.get("stratification_remarks"),
    )


def main():
    from src.utils.db_connect import get_connection

    print(f"Loading {JSON_PATH}...")
    with open(JSON_PATH, encoding="utf-8") as f:
        records = json.load(f)

    print(f"  {len(records)} procedure records found.\n")

    conn   = get_connection()
    cursor = conn.cursor()

    inserted = 0
    skipped  = 0

    for p in records:
        code = p.get("procedure_code", "")
        if not re.match(r"^[A-Z]{2}\d{3}[A-Z]$", code):
            skipped += 1
            continue
        try:
            upsert_specialty(cursor, p["specialty_code"], p["specialty"])
            upsert_package(cursor, p["package_code"], p["package_name"], p["specialty_code"])
            upsert_procedure(cursor, p)
            inserted += 1
        except Exception as e:
            print(f"  Row error ({code}): {e}")
            skipped += 1

    conn.commit()
    conn.close()
    print(f"Done. {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    main()
