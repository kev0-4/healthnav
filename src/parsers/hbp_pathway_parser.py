"""
hbp_pathway_parser.py — Parse HBP.pdf Section 3 (pre-auth requirements)
into the clinical_pathways table.

Splits Section 3 text into N_CALLS chunks and makes N_CALLS API requests.
Strictly document-derived: only what HBP.pdf explicitly states.

Requires: GOOGLE_API_KEY in .env
Run:      python src/parsers/hbp_pathway_parser.py
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

PDF_PATH = os.path.join("raw", "HBP.pdf")
DUMP_PATH = os.path.join("raw", "hbp_pathway_raw_response.txt")
MODEL = "gemini-3.1-flash"
N_CALLS = 5

PATHWAY_PROMPT = """\
Extract clinical pathway steps from the HBP 2.2 pre-authorization requirements text below.
The text covers one or more medical specialties.
Extract ONLY what is explicitly stated — no inference, no additions.

For each specialty found, produce one entry in the "specialties" list.

step_type: consultation | investigation | procedure | documentation | stay | followup
severity:  all | mild | moderate | severe | critical  (use "all" unless text explicitly differentiates)
condition_name: use the specialty name if no specific condition is named
procedure_code: always null
hbp_covered: true unless the text explicitly says otherwise
"""


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class PathwayStep(BaseModel):
    condition_name: str
    severity: str
    step_order: int
    step_type: str
    step_description: str
    procedure_code: Optional[str] = None
    bed_category: Optional[str] = None
    los_days_low: Optional[int] = None
    los_days_high: Optional[int] = None
    hbp_covered: bool = True
    notes: Optional[str] = None


class SpecialtyPathway(BaseModel):
    specialty_name: str
    pathways: list[PathwayStep]


class MultiSpecialtyPathway(BaseModel):
    specialties: list[SpecialtyPathway]


# ── Text extraction ────────────────────────────────────────────────────────────

def find_section_3(text: str) -> str:
    m = re.search(
        r"Section 3\.\s*Key features by Specialty\s*\nThe final picture",
        text, re.IGNORECASE
    )
    start = m.start() if m else -1

    if start == -1:
        half = len(text) // 2
        m2 = re.search(r"Section 3\.", text[half:], re.IGNORECASE)
        start = half + m2.start() if m2 else -1

    if start == -1:
        return ""

    end = len(text)
    for pat in [r"SECTION 4\.", r"Section 4\."]:
        m = re.search(pat, text[start:], re.IGNORECASE)
        if m:
            end = start + m.start()
            break

    return text[start:end]


def split_into_chunks(text: str, n: int) -> list[str]:
    """Split text into n roughly equal chunks at page boundaries (\x0c)."""
    pages = text.split("\x0c")
    if len(pages) < n:
        # Fewer pages than chunks — split by character instead
        size = max(1, len(text) // n)
        chunks = [text[i: i + size] for i in range(0, len(text), size)]
        while len(chunks) > n:
            chunks[-2] += chunks[-1]
            chunks.pop()
        return [c for c in chunks if c.strip()]

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

def call_gemini(client, chunk: str, idx: int, total: int) -> MultiSpecialtyPathway:
    from google.genai import types

    print(f"[{idx}/{total}] Sending {len(chunk):,} chars...",
          end=" ", flush=True)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=chunk,
                config=types.GenerateContentConfig(
                    system_instruction=PATHWAY_PROMPT,
                    temperature=1,
                    response_mime_type="application/json",
                    response_schema=MultiSpecialtyPathway,
                ),
            )
            raw = response.text
            data = try_parse_json(raw, idx)
            if data is None:
                return MultiSpecialtyPathway(specialties=[])
            return MultiSpecialtyPathway(**data)

        except json.JSONDecodeError:
            return MultiSpecialtyPathway(specialties=[])
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

def get_specialty_code(cursor, name: str) -> str | None:
    cursor.execute(
        "SELECT specialty_code FROM dbo.specialties WHERE LOWER(specialty_name) LIKE LOWER(?)",
        f"%{name[:20]}%",
    )
    row = cursor.fetchone()
    return row[0] if row else None


def insert_steps(cursor, steps: list[PathwayStep], specialty_code: str | None):
    for step in steps:
        cursor.execute(
            "INSERT INTO dbo.clinical_pathways "
            "(condition_name, specialty_code, severity, step_order, step_type, "
            "step_description, procedure_code, bed_category, los_days_low, los_days_high, "
            "hbp_covered, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            step.condition_name, specialty_code, step.severity, step.step_order,
            step.step_type, step.step_description, step.procedure_code,
            step.bed_category, step.los_days_low, step.los_days_high,
            1 if step.hbp_covered else 0, step.notes,
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

    section3 = find_section_3(text)
    if not section3:
        print("ERROR: Section 3 not found.")
        conn.close()
        sys.exit(1)

    chunks = split_into_chunks(section3, N_CALLS)
    print(f"Section 3: {len(section3):,} chars → {len(chunks)} chunks.\n")

    total_steps = 0
    total_errors = 0

    for i, chunk in enumerate(chunks, 1):
        try:
            result = call_gemini(client, chunk, i, len(chunks))
        except Exception as e:
            print(f"ERROR — {e}")
            total_errors += 1
            continue

        batch_steps = 0
        for sp in result.specialties:
            spec_code = get_specialty_code(cursor, sp.specialty_name)
            if sp.pathways:
                insert_steps(cursor, sp.pathways, spec_code)
                batch_steps += len(sp.pathways)
                total_steps += len(sp.pathways)

        conn.commit()
        print(f"{batch_steps} steps.")

    conn.close()
    print(
        f"\nDone. {total_steps} pathway steps inserted, {total_errors} errors.")


if __name__ == "__main__":
    main()
