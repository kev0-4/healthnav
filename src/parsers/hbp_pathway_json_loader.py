"""
hbp_pathway_json_loader.py — Load raw/paathway_Specialities_formatted.txt
into the clinical_pathways table.

No LLM needed. Direct JSON → DB loader.
Run: python src/parsers/hbp_pathway_json_loader.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv

load_dotenv()

JSON_PATH = os.path.join("raw", "paathway_Specialities_formatted.txt")


def get_specialty_code(cursor, name: str) -> str | None:
    for prefix_len in (20, 12, 8):
        cursor.execute(
            "SELECT specialty_code FROM dbo.specialties "
            "WHERE LOWER(specialty_name) LIKE LOWER(?)",
            f"%{name[:prefix_len]}%",
        )
        row = cursor.fetchone()
        if row:
            return row[0]
    return None


def main():
    from src.utils.db_connect import get_connection

    print(f"Loading {JSON_PATH}...")
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    specialties = data.get("specialties", [])
    print(f"  {len(specialties)} specialties found.\n")

    conn   = get_connection()
    cursor = conn.cursor()

    total_steps  = 0
    total_errors = 0

    for sp in specialties:
        condition_name = sp.get("condition_name", "")
        severity       = sp.get("severity", "all")
        steps          = sp.get("pathway_steps", [])
        spec_code      = get_specialty_code(cursor, condition_name)

        for i, step in enumerate(steps, 1):
            try:
                cursor.execute(
                    "INSERT INTO dbo.clinical_pathways "
                    "(condition_name, specialty_code, severity, step_order, step_type, "
                    "step_description, procedure_code, bed_category, los_days_low, "
                    "los_days_high, hbp_covered, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    condition_name,
                    spec_code,
                    severity,
                    i,
                    step.get("step_type"),
                    step.get("description"),
                    step.get("procedure_code"),
                    step.get("bed_category"),
                    step.get("los_days_low"),
                    step.get("los_days_high"),
                    1 if step.get("hbp_covered", True) else 0,
                    step.get("notes"),
                )
                total_steps += 1
            except Exception as e:
                print(f"  Error ({condition_name} step {i}): {e}")
                total_errors += 1

        print(f"  {condition_name}: {len(steps)} steps (code={spec_code})")

    conn.commit()
    conn.close()
    print(f"\nDone. {total_steps} steps inserted, {total_errors} errors.")


if __name__ == "__main__":
    main()
