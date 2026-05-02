"""
mht_parser.py — Parse utilisation_pattern_PMJAY.mht to populate specialty_priority table.

No LLM needed — extracts HTML tables directly with BeautifulSoup.
Run: python src/parsers/mht_parser.py
"""
import os
import sys
import email
import re
from email import policy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

MHT_PATH = os.path.join("raw", "utilisation_pattern_PMJAY.mht")
SOURCE = "KGMU_utilisation_2023"


def extract_html_from_mht(mht_path: str) -> str:
    """Extract the primary HTML body from a MIME HTML (.mht) file."""
    with open(mht_path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="ignore")

    return ""


def parse_tables(html: str) -> list[list[list[str]]]:
    """Return all tables from the HTML as a list of rows × cells."""
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(separator=" ", strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def is_specialty_table(rows: list[list[str]]) -> bool:
    """Heuristic: does this table contain specialty/volume/cost data?"""
    if not rows:
        return False
    header = " ".join(rows[0]).lower()
    keywords = ["specialty", "package", "volume", "percent", "cost", "rank", "utilisation", "cardio"]
    return sum(1 for kw in keywords if kw in header) >= 2


def parse_specialty_priority(rows: list[list[str]]) -> list[dict]:
    """
    Try to extract specialty → volume_rank, cost_rank, volume_pct rows.
    Handles varied column orderings by inspecting the header row.
    """
    if len(rows) < 2:
        return []

    header = [c.lower() for c in rows[0]]

    def find_col(*keywords):
        for kw in keywords:
            for i, h in enumerate(header):
                if kw in h:
                    return i
        return None

    specialty_col = find_col("specialty", "department", "speciality")
    pct_col       = find_col("percent", "pct", "%", "proportion")
    rank_col      = find_col("rank", "order")

    if specialty_col is None:
        return []

    results = []
    for row in rows[1:]:
        if len(row) <= specialty_col:
            continue

        specialty_name = row[specialty_col].strip()
        if not specialty_name or specialty_name.lower() in ("total", "grand total", ""):
            continue

        volume_pct = None
        if pct_col and pct_col < len(row):
            raw = re.sub(r"[^\d.]", "", row[pct_col])
            try:
                volume_pct = float(raw)
            except ValueError:
                pass

        results.append({
            "specialty_name": specialty_name,
            "volume_pct": volume_pct,
        })

    return results


def assign_ranks(entries: list[dict]) -> list[dict]:
    """Assign volume_rank based on volume_pct descending."""
    sorted_entries = sorted(
        [e for e in entries if e.get("volume_pct") is not None],
        key=lambda x: x["volume_pct"],
        reverse=True,
    )
    for i, entry in enumerate(sorted_entries, 1):
        entry["volume_rank"] = i

    # Entries without volume_pct get no rank
    for entry in entries:
        if "volume_rank" not in entry:
            entry["volume_rank"] = None

    return entries


def get_specialty_code(cursor, name: str) -> str | None:
    cursor.execute(
        "SELECT specialty_code FROM dbo.specialties "
        "WHERE LOWER(specialty_name) LIKE LOWER(?)",
        f"%{name[:20]}%",
    )
    row = cursor.fetchone()
    return row[0] if row else None


def insert_priority(cursor, code: str, entry: dict):
    cursor.execute(
        "IF NOT EXISTS (SELECT 1 FROM dbo.specialty_priority WHERE specialty_code = ?) "
        "INSERT INTO dbo.specialty_priority "
        "(specialty_code, volume_rank, cost_rank, volume_pct, source) "
        "VALUES (?, ?, ?, ?, ?)",
        code,
        code,
        entry.get("volume_rank"),
        entry.get("cost_rank"),
        entry.get("volume_pct"),
        SOURCE,
    )


def main():
    from src.utils.db_connect import get_connection

    print(f"Parsing {MHT_PATH}...")
    html = extract_html_from_mht(MHT_PATH)
    if not html:
        print("ERROR: Could not extract HTML from MHT file.")
        sys.exit(1)

    tables = parse_tables(html)
    print(f"Found {len(tables)} tables in HTML.")

    specialty_tables = [t for t in tables if is_specialty_table(t)]
    print(f"  {len(specialty_tables)} look like specialty/volume tables.")

    if not specialty_tables:
        print("No matching tables found. Review the MHT manually.")
        # Print all table headers for debugging
        for i, t in enumerate(tables[:10]):
            print(f"  Table {i} header: {t[0] if t else '(empty)'}")
        sys.exit(0)

    all_entries = []
    for table in specialty_tables:
        all_entries.extend(parse_specialty_priority(table))

    all_entries = assign_ranks(all_entries)
    print(f"Extracted {len(all_entries)} specialty entries.")

    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0
    skipped = 0
    for entry in all_entries:
        code = get_specialty_code(cursor, entry["specialty_name"])
        if not code:
            print(f"  No specialty code match for: {entry['specialty_name']}")
            skipped += 1
            continue
        insert_priority(cursor, code, entry)
        inserted += 1

    conn.commit()
    conn.close()
    print(f"\nDone. {inserted} inserted, {skipped} skipped (no specialty code match).")


if __name__ == "__main__":
    main()
