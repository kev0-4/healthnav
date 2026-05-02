"""
sanity_check.py — Quick DB health check across all tables.
Run: python src/db/sanity_check.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

def check(label, ok, detail=""):
    status = PASS if ok else FAIL
    mark   = "✓" if ok else "✗"
    line   = f"  [{status}] {mark} {label}"
    if detail:
        line += f"  →  {detail}"
    print(line)
    return ok


def main():
    from src.utils.db_connect import get_connection
    conn   = get_connection()
    cursor = conn.cursor()

    all_ok = True

    def q(sql, *args):
        cursor.execute(sql, *args)
        return cursor.fetchone()

    def qall(sql, *args):
        cursor.execute(sql, *args)
        return cursor.fetchall()

    print("\n═══════════════════════════════════════════════")
    print("  DB SANITY CHECK")
    print("═══════════════════════════════════════════════\n")

    # ── Row counts ────────────────────────────────────────────────────────────
    print("── Row counts ──────────────────────────────────")
    tables = [
        ("dbo.specialties",              10,   None),
        ("dbo.packages",                 50,   None),
        ("dbo.procedures",               50,   None),
        ("dbo.bed_day_rates",             4,      4),
        ("dbo.city_tier_map",            50,   None),
        ("dbo.hospital_type_multipliers", 3,      3),
        ("dbo.clinical_pathways",        10,   None),
        ("dbo.hospitals",             10000,   None),
        ("dbo.specialty_priority",        5,   None),
    ]

    for table, min_rows, exact_rows in tables:
        row = q(f"SELECT COUNT(*) FROM {table}")
        count = row[0]
        if exact_rows is not None:
            ok = count == exact_rows
            detail = f"{count} rows (expected exactly {exact_rows})"
        else:
            ok = count >= min_rows
            detail = f"{count} rows (min {min_rows})"
        if not check(table, ok, detail):
            all_ok = False

    # ── Referential integrity ─────────────────────────────────────────────────
    print("\n── Referential integrity ───────────────────────")

    row = q("""
        SELECT COUNT(*) FROM dbo.packages p
        WHERE NOT EXISTS (SELECT 1 FROM dbo.specialties s WHERE s.specialty_code = p.specialty_code)
    """)
    orphan_pkgs = row[0]
    if not check("packages → specialties FK", orphan_pkgs == 0, f"{orphan_pkgs} orphaned packages"):
        all_ok = False

    row = q("""
        SELECT COUNT(*) FROM dbo.procedures pr
        WHERE NOT EXISTS (SELECT 1 FROM dbo.packages p WHERE p.package_code = pr.package_code)
    """)
    orphan_procs = row[0]
    if not check("procedures → packages FK", orphan_procs == 0, f"{orphan_procs} orphaned procedures"):
        all_ok = False

    row = q("""
        SELECT COUNT(*) FROM dbo.specialty_priority sp
        WHERE NOT EXISTS (SELECT 1 FROM dbo.specialties s WHERE s.specialty_code = sp.specialty_code)
    """)
    orphan_prio = row[0]
    if not check("specialty_priority → specialties FK", orphan_prio == 0, f"{orphan_prio} orphaned rows"):
        all_ok = False

    # ── Data quality ──────────────────────────────────────────────────────────
    print("\n── Data quality ────────────────────────────────")

    row = q("SELECT COUNT(*) FROM dbo.procedures WHERE tier1_inr IS NULL AND tier2_inr IS NULL AND tier3_inr IS NULL")
    null_tier = row[0]
    check("procedures with at least one tier price", null_tier == 0,
          f"{null_tier} rows with all tiers NULL" if null_tier else "all have pricing")

    row = q("SELECT COUNT(*) FROM dbo.hospitals WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    with_coords = row[0]
    check("hospitals with coordinates", with_coords > 5000, f"{with_coords} hospitals geo-coded")

    row = q("SELECT COUNT(*) FROM dbo.hospitals WHERE nabh_accredited = 1")
    nabh = row[0]
    status = PASS if nabh > 0 else WARN
    print(f"  [{status}] {'✓' if nabh > 0 else '!'} NABH-accredited hospitals  →  {nabh} (source CSV has no NABH data)")

    row = q("SELECT COUNT(DISTINCT city_name) FROM dbo.city_tier_map")
    cities = row[0]
    if not check("city_tier_map populated", cities >= 50, f"{cities} cities mapped"):
        all_ok = False

    row = q("SELECT COUNT(*) FROM dbo.clinical_pathways WHERE step_description IS NOT NULL")
    steps_ok = row[0]
    check("clinical_pathways have descriptions", steps_ok > 0, f"{steps_ok} steps with descriptions")

    # ── Spot checks ───────────────────────────────────────────────────────────
    print("\n── Spot checks ─────────────────────────────────")

    # Bed day rates
    rows = qall("SELECT bed_category, rate_per_day FROM dbo.bed_day_rates ORDER BY rate_per_day")
    expected = {"routine_ward": 2300, "hdu": 3630, "icu": 9350, "icu_ventilator": 9900}
    for cat, rate in rows:
        exp = expected.get(cat)
        ok  = exp is not None and rate == exp
        check(f"bed_day_rates: {cat}", ok, f"₹{rate}" + (f" (expected ₹{exp})" if not ok else ""))

    # Hospital type multipliers
    rows = qall("SELECT hospital_type, multiplier_low, multiplier_high FROM dbo.hospital_type_multipliers ORDER BY multiplier_low")
    for htype, lo, hi in rows:
        check(f"multiplier: {htype}", lo > 0 and hi >= lo, f"{lo}×–{hi}×")

    # Top specialty priority
    rows = qall("""
        SELECT sp.volume_rank, s.specialty_name, sp.volume_pct
        FROM dbo.specialty_priority sp
        JOIN dbo.specialties s ON s.specialty_code = sp.specialty_code
        ORDER BY sp.volume_rank
    """)
    print(f"\n  Top 5 specialties by volume (from utilisation study):")
    for rank, name, pct in rows[:5]:
        print(f"    #{rank}  {name:<40} {pct}%")

    # Sample procedures
    rows = qall("""
        SELECT TOP 3 pr.procedure_code, pr.procedure_name, pr.tier2_inr, s.specialty_name
        FROM dbo.procedures pr
        JOIN dbo.packages pk ON pk.package_code = pr.package_code
        JOIN dbo.specialties s ON s.specialty_code = pk.specialty_code
        ORDER BY pr.tier2_inr DESC
    """)
    print(f"\n  Top 3 procedures by Tier 2 price:")
    for code, name, t2, spec in rows:
        print(f"    {code}  ₹{t2:,}  {name}  [{spec}]")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n═══════════════════════════════════════════════")
    if all_ok:
        print("  ALL CHECKS PASSED")
    else:
        print("  SOME CHECKS FAILED — review above")
    print("═══════════════════════════════════════════════\n")

    conn.close()


if __name__ == "__main__":
    main()
