"""
hbp_2022_parser.py — Parse HBP-2022.pdf into specialties, packages, procedures tables.

Splits the full PDF text into N_CALLS chunks and makes N_CALLS API requests.

Requires: GOOGLE_API_KEY in .env
Run:      python src/parsers/hbp_2022_parser.py
"""
from pdfminer.high_level import extract_text
from dotenv import load_dotenv
import os
import sys
import json
import re
import time
from typing import Optional
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


load_dotenv()

PDF_PATH = os.path.join("raw", "HBP-2022.pdf")
DUMP_PATH = os.path.join("raw", "hbp_2022_raw_response.txt")
MODEL = "gemini-3.1-flash"
N_CALLS = 5

EXTRACTION_PROMPT = """\
Extract every HBP 2022 procedure row from the PDF table text below.
The table columns are:
  Specialty | Specialty Code | Package Code | Package Name | Procedure Code | Procedure Name | Tier3(Z) INR | Tier2(Y) INR | Tier1(X) INR | Implant Mapped | Implant Cost | Stratification Remarks

Rules:
- procedure_code pattern: exactly 2 uppercase letters + 3 digits + 1 uppercase letter (e.g. BM001A)
- tier prices are plain integers — strip commas, strip currency symbols; use null if value is NA or missing
- implant_mapped is true only when implant_cost_inr is a real number (not NA)
- procedure_name: short human-readable label derived from package name and stratification criteria
- stratification_text: the full eligibility/criteria description text
- The specialty and specialty_code repeat across consecutive rows in the same specialty group
- Extract ALL rows present — do not stop early
"""


# ── Pydantic schema ────────────────────────────────────────────────────────────

class Procedure(BaseModel):
    specialty: str
    specialty_code: str
    package_code: str
    package_name: str
    procedure_code: str
    procedure_name: Optional[str] = None
    tier3_inr: Optional[int] = None
    tier2_inr: Optional[int] = None
    tier1_inr: Optional[int] = None
    implant_mapped: bool = False
    implant_cost_inr: Optional[int] = None
    stratification_text: Optional[str] = None


class ProcedureList(BaseModel):
    procedures: list[Procedure]


# ── Chunking ───────────────────────────────────────────────────────────────────

def split_into_chunks(text: str, n: int) -> list[str]:
    """Split text into n roughly equal chunks at page boundaries (\x0c)."""
    pages = text.split("\x0c")
    pages_per_chunk = max(1, len(pages) // n)
    chunks = []
    for i in range(0, len(pages), pages_per_chunk):
        chunk = "\x0c".join(pages[i: i + pages_per_chunk])
        if chunk.strip():
            chunks.append(chunk)
    while len(chunks) > n:
        chunks[-2] += "\x0c" + chunks[-1]
        chunks.pop()
    return chunks


# ── JSON helpers ───────────────────────────────────────────────────────────────

def try_parse_json(raw: str, chunk_idx: int) -> dict | None:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    for text in (cleaned, raw):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    dump = DUMP_PATH.replace(".txt", f"_{chunk_idx}.txt")
    with open(dump, "w", encoding="utf-8") as f:
        f.write(raw)
    print(f"\n  JSON parse failed. Raw response dumped to {dump}")
    return None


# ── Gemini call ────────────────────────────────────────────────────────────────

def call_gemini(client, chunk: str, idx: int, total: int) -> list[Procedure]:
    from google.genai import types

    print(f"[{idx}/{total}] Sending {len(chunk):,} chars...",
          end=" ", flush=True)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=chunk,
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_PROMPT,
                    temperature=1,
                    response_mime_type="application/json",
                    response_schema=ProcedureList,
                ),
            )
            raw = response.text
            data = try_parse_json(raw, idx)
            if data is None:
                return []
            return [Procedure(**p) for p in data.get("procedures", [])]

        except json.JSONDecodeError:
            return []
        except Exception as e:
            err_str = str(e)
            if attempt < 2:
                m = re.search(r"retryDelay.*?(\d+)s", err_str)
                wait = int(m.group(1)) + 5 if m else 60
                print(f"\n  Attempt {attempt+1} API error: {err_str[:200]}")
                print(f"  Retrying in {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise


# ── DB helpers ─────────────────────────────────────────────────────────────────

def upsert_specialty(cursor, code: str, name: str):
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


def upsert_procedure(cursor, p: Procedure):
    cursor.execute(
        "IF NOT EXISTS (SELECT 1 FROM dbo.procedures WHERE procedure_code = ?) "
        "INSERT INTO dbo.procedures "
        "(procedure_code, procedure_name, package_code, tier1_inr, tier2_inr, tier3_inr, "
        "implant_mapped, implant_cost_inr, stratification_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        p.procedure_code,
        p.procedure_code, p.procedure_name, p.package_code,
        p.tier1_inr, p.tier2_inr, p.tier3_inr,
        1 if p.implant_mapped else 0,
        p.implant_cost_inr, p.stratification_text,
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set in .env")
        sys.exit(1)

    from google import genai
    from src.utils.db_connect import get_connection

    client = genai.Client(api_key=api_key)
    conn = get_connection()
    cursor = conn.cursor()

    print(f"Extracting text from {PDF_PATH}...")
    text = extract_text(PDF_PATH)
    chunks = split_into_chunks(text, N_CALLS)
    print(f"Split into {len(chunks)} chunks.\n")

    total_procedures = 0
    total_errors = 0

    for i, chunk in enumerate(chunks, 1):
        try:
            procedures = call_gemini(client, chunk, i, len(chunks))
        except Exception as e:
            print(f"ERROR — {e}")
            total_errors += 1
            continue

        inserted = 0
        for p in procedures:
            if not re.match(r"^[A-Z]{2}\d{3}[A-Z]$", p.procedure_code):
                continue
            try:
                upsert_specialty(cursor, p.specialty_code, p.specialty)
                upsert_package(cursor, p.package_code,
                               p.package_name, p.specialty_code)
                upsert_procedure(cursor, p)
                inserted += 1
                total_procedures += 1
            except Exception as e:
                print(f"\n  Row error ({p.procedure_code}): {e}")
                total_errors += 1

        conn.commit()
        print(f"{inserted} procedures.")

    conn.close()
    print(f"\nDone. {total_procedures} inserted, {total_errors} errors.")


if __name__ == "__main__":
    main()
