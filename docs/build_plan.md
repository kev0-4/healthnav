# HealthNav — Complete Build Plan
# From DB-complete prototype → working end-to-end product

> Read this file fully before writing any code. This is the single source of truth for the build phase.
> Companion to: CLAUDE.md (project context), docs/architecture.md (ERD + system diagram)

---

## 0. Current State (What Is Already Done)

### ✅ Fully complete — do not touch
| Component | Location | Status |
|---|---|---|
| Azure SQL schema (9 tables) | `src/db/schema.sql` | Created + seeded |
| DB connection utility | `src/utils/db_connect.py` | Working |
| HBP 2022 procedures loader | `src/parsers/hbp_2022_json_loader.py` | Run, 87 rows loaded |
| HBP clinical pathways loader | `src/parsers/hbp_pathway_json_loader.py` | Run, 141 rows loaded |
| Hospital CSV loader | `src/parsers/hospital_csv_loader.py` | Run, 30,273 rows loaded |
| Study data loader | `src/parsers/study_data_loader.py` | Run, specialty_priority seeded |
| DB sanity check | `src/db/sanity_check.py` | Passes (NABH is WARN not FAIL) |
| Frontend prototype | `frontend/` | Vite + React + Tailwind, mocked data |
| Architecture docs | `docs/architecture.md` | ERD + system diagram |
| Migration prompt | `docs/migration_prompt.md` | Full project context |

### ⚠️ Known data gaps (fix before pipeline, not blocking for now)
- 5 Burns Management procedures have NULL tier prices: `BM003B, BM003C, BM003D, BM004A, BM004B` — manual UPDATE from HBP-2022.pdf burns section
- `nabh_accredited` is all 0 — scrape nabh.co later (Phase 2)
- `google_rating` and `practo_rating` are all NULL — populate later (Phase 2)

---

## 1. Environment

```
OS: Linux (Ubuntu)
Python venv: /home/kevin/Desktop/fincorp/venv/
Working dir: /home/kevin/Desktop/fincorp/
Run scripts: venv/bin/python src/...
DB: Azure SQL Server via pyodbc + ODBC Driver 18
LLM: Claude API (claude-sonnet-4-6) via anthropic SDK
Frontend: Node.js, npm, Vite — in /frontend/
```

### .env file (already exists at project root)
```
AZURE_SQL_SERVER=...
AZURE_SQL_DATABASE=...
AZURE_SQL_USERNAME=...
AZURE_SQL_PASSWORD=...
ANTHROPIC_API_KEY=...        ← add this if not present
GOOGLE_API_KEY=...           ← Gemini key, keep for parsers
```

### Python packages needed (add to venv)
```bash
venv/bin/pip install anthropic fastapi uvicorn python-dotenv pyodbc
# already installed: pdfminer.six, google-generativeai, python-dotenv, pyodbc
```

---

## 2. Build Order — Strict Sequence

Build in this exact order. Each phase depends on the previous.

```
Phase 1: Pipeline layer-by-layer (Python)
  Step 1 → nlp_extractor.py       (Layer 1 — Claude NLP)
  Step 2 → pathway_mapper.py      (Layer 2 — DB query)
  Step 3 → cost_calculator.py     (Layer 3 — pure math)
  Step 4 → provider_matcher.py    (Layer 4 — DB query)
  Step 5 → pipeline.py            (orchestrator — calls 1→2→3→4)

Phase 2: API
  Step 6 → src/api/main.py        (FastAPI — exposes pipeline as HTTP)

Phase 3: Frontend integration
  Step 7 → wire frontend to real API (replace mock data)
  Step 8 → error states + loading states

Phase 4: Data gaps (non-blocking, do last)
  Step 9  → fix 5 null-pricing procedures
  Step 10 → NABH scraper
  Step 11 → Google Places rating population
```

---

## 3. Phase 1 — Pipeline

### Step 1: `src/pipeline/nlp_extractor.py`

**What it does:** Takes raw user query string → returns structured extraction dict.

**Input:**
```python
query = "chest pain sometimes, age 55, Nagpur, budget 3 lakhs"
```

**Output:**
```python
{
  "symptoms": ["chest pain"],
  "body_system": "cardiovascular",
  "duration_signal": "sometimes",
  "comorbidities": [],
  "city": "Nagpur",
  "budget_inr": 300000,
  "age": 55,
  "conditions": [
    {"name": "Coronary Artery Disease", "icd10": "I25.1", "confidence": 0.72, "severity": "moderate"},
    {"name": "Stable Angina", "icd10": "I20.9", "confidence": 0.18, "severity": "mild"},
    {"name": "Hypertensive Heart Disease", "icd10": "I11.9", "confidence": 0.10, "severity": "mild"},
  ],
  "top_condition": "Coronary Artery Disease",
  "top_icd10": "I25.1",
  "top_confidence": 0.72,
  "top_severity": "moderate",
  "needs_clarification": False,   # True if top_confidence < 0.60
  "clarification_question": None
}
```

**Implementation details:**

```python
# Use anthropic SDK — NOT requests, NOT openai
import anthropic
import json
from dotenv import load_dotenv
import os

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
You are a medical triage assistant for an Indian healthcare cost estimation platform.

Extract structured information from the user's health query. Return ONLY valid JSON.

Rules:
- conditions: list top 3 likely conditions, ranked by probability
- confidence: float 0.0–1.0 (sum of all conditions does NOT need to equal 1.0)
- severity: "mild" | "moderate" | "severe"
- city: extract if mentioned, else null
- budget_inr: convert mentions like "3 lakhs" → 300000, "50k" → 50000, else null
- age: extract integer if mentioned, else null
- needs_clarification: true ONLY if top condition confidence < 0.60
- clarification_question: one short question to ask the user if needs_clarification is true, else null
- Never diagnose. Never recommend specific treatments. This is for cost planning only.
- If query is clearly OPD-only (cold, flu, routine checkup), set severity "mild" and flag in notes.
"""

def extract(query: str) -> dict:
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": query}]
    )
    raw = message.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
```

**Test it standalone:**
```python
# At bottom of file, under if __name__ == "__main__":
result = extract("knee pain for 3 months, age 58, Nagpur, budget 2.5 lakhs")
print(json.dumps(result, indent=2))
```

**Edge cases to handle:**
- JSON parse fails → retry once with explicit "return only JSON, no markdown" instruction
- City not in `city_tier_map` → default to Tier 3
- No city mentioned → prompt user (set needs_clarification=True with city question)
- Confidence < 0.60 → set needs_clarification=True, do not proceed to Layer 2

---

### Step 2: `src/pipeline/pathway_mapper.py`

**What it does:** Takes condition name + severity → queries DB → returns ordered procedure sequence.

**Input:**
```python
condition_name = "Coronary Artery Disease"
severity = "moderate"
```

**Output:**
```python
{
  "condition_name": "Coronary Artery Disease",
  "specialty_code": "MC",
  "severity": "moderate",
  "hbp_covered": True,
  "opd_only": False,
  "steps": [
    {
      "step_order": 1,
      "step_type": "CONSULTATION",
      "step_description": "Cardiologist consultation",
      "procedure_code": "MC022A",
      "bed_category": None,
      "los_days_low": None,
      "los_days_high": None,
      "hbp_covered": True
    },
    ...
  ],
  "primary_procedure_code": "MC017A",  # highest-cost procedure (for stacking rule)
  "bed_category": "routine_ward",
  "los_low": 3,
  "los_high": 5
}
```

**Implementation details:**

```python
from src.utils.db_connect import get_connection

def map_pathway(condition_name: str, severity: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Find matching pathway rows — use LIKE for fuzzy condition match
    cursor.execute("""
        SELECT cp.step_order, cp.step_type, cp.step_description,
               cp.procedure_code, cp.bed_category, cp.los_days_low,
               cp.los_days_high, cp.hbp_covered, cp.specialty_code, cp.notes
        FROM dbo.clinical_pathways cp
        WHERE cp.condition_name LIKE ?
          AND (cp.severity = ? OR cp.severity = 'all')
        ORDER BY cp.step_order
    """, (f"%{condition_name}%", severity))

    rows = cursor.fetchall()

    if not rows:
        # Fallback: try just condition name without severity filter
        cursor.execute("""
            SELECT cp.step_order, cp.step_type, cp.step_description,
                   cp.procedure_code, cp.bed_category, cp.los_days_low,
                   cp.los_days_high, cp.hbp_covered, cp.specialty_code, cp.notes
            FROM dbo.clinical_pathways cp
            WHERE cp.condition_name LIKE ?
            ORDER BY cp.step_order
        """, (f"%{condition_name}%",))
        rows = cursor.fetchall()

    steps = [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

    # 2. Check if any step is hospitalization (hbp_covered=1 + has procedure_code)
    has_inpatient = any(s['procedure_code'] and s['hbp_covered'] for s in steps)

    # 3. Find primary procedure (highest-value step with procedure_code)
    procedure_codes = [s['procedure_code'] for s in steps if s['procedure_code']]
    primary_procedure_code = procedure_codes[0] if procedure_codes else None

    # 4. Get bed_category and LOS from STAY step
    stay_steps = [s for s in steps if s['step_type'] == 'STAY' or s['bed_category']]
    bed_category = stay_steps[0]['bed_category'] if stay_steps else 'routine_ward'
    los_low = stay_steps[0]['los_days_low'] if stay_steps else 3
    los_high = stay_steps[0]['los_days_high'] if stay_steps else 5

    conn.close()
    return {
        "condition_name": condition_name,
        "specialty_code": rows[0][8] if rows else None,
        "severity": severity,
        "hbp_covered": has_inpatient,
        "opd_only": not has_inpatient,
        "steps": steps,
        "primary_procedure_code": primary_procedure_code,
        "all_procedure_codes": procedure_codes,
        "bed_category": bed_category,
        "los_low": los_low,
        "los_high": los_high
    }
```

**Edge cases:**
- No pathway found in DB → return `{"hbp_covered": False, "opd_only": True, "steps": [], "error": "no_pathway"}`
- OPD-only severity (mild general medicine) → set `opd_only: True`, note in response
- Multiple bed_categories in pathway → pick most severe (ICU > HDU > routine_ward)

---

### Step 3: `src/pipeline/cost_calculator.py`

**What it does:** Pure calculation — no DB calls except for price lookup. Takes pathway output → returns itemized cost range dict.

**Input:**
```python
pathway = { ...output from pathway_mapper... }
city = "Nagpur"
hospital_type = "mid_private"  # optional, defaults to "government" for base estimate
nabh = False
```

**Output:**
```python
{
  "city": "Nagpur",
  "city_tier": 2,
  "hospital_type": "government",  # base estimate is always government
  "procedure_base": [43200, 49000],
  "hospital_stay_days": [3, 5],
  "hospital_stay_cost": [10890, 18150],
  "medication_post_discharge": [5000, 9000],
  "contingency": [5910, 7615],
  "total_range": [65000, 83765],
  "tier_column": "tier2_inr",
  "bed_rate_used": 2300,
  "bed_category": "routine_ward",
  "stacking_applied": True,
  "nabh_multiplier": 1.0
}
```

**Implementation details:**

```python
from src.utils.db_connect import get_connection

BED_RATES = {
    "routine_ward": 2300,
    "hdu": 3630,
    "icu": 9350,
    "icu_ventilator": 9900
}

TIER_COLUMNS = {1: "tier1_inr", 2: "tier2_inr", 3: "tier3_inr"}

NABH_MULTIPLIERS = {
    "none": 1.0,
    "entry": 1.10,
    "full": 1.15
}

def get_city_tier(city: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tier FROM dbo.city_tier_map WHERE city_name LIKE ?", (f"%{city}%",))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 3  # default Tier 3

def get_procedure_prices(procedure_codes: list, tier_col: str) -> list:
    """Returns list of prices in descending order (for stacking rule)."""
    if not procedure_codes:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?" for _ in procedure_codes])
    cursor.execute(f"""
        SELECT {tier_col} FROM dbo.procedures
        WHERE procedure_code IN ({placeholders})
          AND {tier_col} IS NOT NULL
        ORDER BY {tier_col} DESC
    """, procedure_codes)
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def apply_stacking(prices: list) -> int:
    """HBP multi-procedure rule: P1=100%, P2=50%, P3+=25%"""
    if not prices:
        return 0
    total = prices[0]
    if len(prices) > 1:
        total += prices[1] * 0.5
    for p in prices[2:]:
        total += p * 0.25
    return int(total)

def calculate(pathway: dict, city: str, nabh_level: str = "none") -> dict:
    tier = get_city_tier(city)
    tier_col = TIER_COLUMNS[tier]

    # Procedure cost with stacking
    prices = get_procedure_prices(pathway["all_procedure_codes"], tier_col)
    proc_low = apply_stacking(prices)
    proc_high = int(proc_low * 1.135)  # ~13.5% high-end buffer

    # Stay cost
    bed_rate = BED_RATES.get(pathway["bed_category"], 2300)
    stay_low = bed_rate * pathway["los_low"]
    stay_high = bed_rate * pathway["los_high"]

    # Medications: 8–12% of procedure base
    med_low = int(proc_low * 0.08)
    med_high = int(proc_high * 0.12)

    # NABH multiplier
    nabh_mult = NABH_MULTIPLIERS.get(nabh_level, 1.0)

    # Apply NABH to procedure base only
    proc_low = int(proc_low * nabh_mult)
    proc_high = int(proc_high * nabh_mult)

    # Subtotal before contingency
    sub_low = proc_low + stay_low + med_low
    sub_high = proc_high + stay_high + med_high

    # Contingency: 9%
    cont_low = int(sub_low * 0.09)
    cont_high = int(sub_high * 0.09)

    return {
        "city": city,
        "city_tier": tier,
        "tier_column": tier_col,
        "procedure_base": [proc_low, proc_high],
        "hospital_stay_days": [pathway["los_low"], pathway["los_high"]],
        "hospital_stay_cost": [stay_low, stay_high],
        "medication_post_discharge": [med_low, med_high],
        "contingency": [cont_low, cont_high],
        "total_range": [sub_low + cont_low, sub_high + cont_high],
        "bed_rate_used": bed_rate,
        "bed_category": pathway["bed_category"],
        "stacking_applied": len(pathway["all_procedure_codes"]) > 1,
        "nabh_multiplier": nabh_mult
    }
```

**Edge cases:**
- All procedure prices NULL → return `{"error": "no_pricing", "opd_only": True}`
- City not in city_tier_map → default Tier 3, log warning
- Pathway is OPD-only → skip procedure cost, only return consultation cost note

---

### Step 4: `src/pipeline/provider_matcher.py`

**What it does:** Queries `hospitals` table for the user's city/district → scores and ranks → returns top 3–5 with per-hospital adjusted cost range.

**Input:**
```python
city = "Nagpur"
specialty_code = "MC"         # from pathway mapper
base_cost = {...}             # output from cost_calculator (government base)
top_n = 5
```

**Output:**
```python
{
  "city": "Nagpur",
  "hospitals": [
    {
      "hospital_id": 12345,
      "hospital_name": "Wockhardt Heart Hospital",
      "hospital_type": "mid_private",
      "nabh_accredited": False,
      "google_rating": None,
      "total_beds": 420,
      "emergency_services": True,
      "address": "Ramdaspeth, Nagpur",
      "distance_km": None,         # null until Google Places integrated
      "score": 0.84,
      "multiplier_low": 1.5,
      "multiplier_high": 2.0,
      "adjusted_total_low": 97500,
      "adjusted_total_high": 167530
    },
    ...
  ]
}
```

**Implementation details:**

```python
from src.utils.db_connect import get_connection

SPECIALTY_KEYWORDS = {
    "MC": ["cardiology", "cardiac", "heart", "ctvs"],
    "SB": ["orthopaedic", "orthopedic", "bone", "joint"],
    "MG": ["general medicine", "internal medicine"],
    "SU": ["surgery", "general surgery"],
    # extend as needed
}

def get_multiplier(hospital_type: str) -> tuple:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT multiplier_low, multiplier_high
        FROM dbo.hospital_type_multipliers
        WHERE hospital_type = ?
    """, (hospital_type,))
    row = cursor.fetchone()
    conn.close()
    return (row[0], row[1]) if row else (1.0, 1.0)

def score_hospital(h: dict) -> float:
    score = 0.0
    if h["nabh_accredited"]: score += 0.25
    if h["google_rating"]:
        score += (h["google_rating"] / 5.0) * 0.35
    else:
        score += 0.15  # neutral if no rating
    if h["emergency_services"]: score += 0.10
    beds = h["total_beds"] or 0
    score += min(beds / 500, 1.0) * 0.15  # cap at 500 beds
    # hospital_type preference: mid_private > government > corporate (for affordability)
    type_scores = {"government": 0.15, "mid_private": 0.15, "corporate": 0.05}
    score += type_scores.get(h["hospital_type"], 0.0)
    return round(score, 3)

def match(city: str, specialty_code: str, base_cost: dict, top_n: int = 5) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    keywords = SPECIALTY_KEYWORDS.get(specialty_code, [])

    # Build specialty filter
    specialty_filter = " OR ".join([f"LOWER(specialties) LIKE ?" for _ in keywords])
    params = [f"%{city}%"] + [f"%{kw}%" for kw in keywords]

    query = f"""
        SELECT TOP 20
            hospital_id, hospital_name, hospital_type, nabh_accredited,
            google_rating, total_beds, emergency_services, address,
            district, state, specialties
        FROM dbo.hospitals
        WHERE (LOWER(district) LIKE ? OR LOWER(location) LIKE ?)
          AND hospital_type IS NOT NULL
          AND care_type NOT IN ('Clinic', 'Dispensary')
    """
    params = [f"%{city.lower()}%", f"%{city.lower()}%"]

    if keywords:
        query += f" AND ({specialty_filter})"
        params += [f"%{kw}%" for kw in keywords]

    cursor.execute(query, params)
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    # Score and sort
    for h in rows:
        h["score"] = score_hospital(h)
    rows.sort(key=lambda x: x["score"], reverse=True)
    top = rows[:top_n]

    # Apply cost multiplier
    base_low = base_cost["total_range"][0]
    base_high = base_cost["total_range"][1]
    for h in top:
        mult_low, mult_high = get_multiplier(h["hospital_type"])
        h["multiplier_low"] = mult_low
        h["multiplier_high"] = mult_high
        h["adjusted_total_low"] = int(base_low * mult_low)
        h["adjusted_total_high"] = int(base_high * mult_high)

    return {"city": city, "hospitals": top}
```

**Edge cases:**
- City not found in hospitals table → try state-level fallback query
- Zero hospitals match specialty → return all hospitals in city without specialty filter, add note
- hospital_type is NULL for some rows → skip those rows (filter `WHERE hospital_type IS NOT NULL`)

---

### Step 5: `src/pipeline/pipeline.py`

**What it does:** Orchestrator. Calls layers 1→2→3→4 in sequence. Returns final combined JSON.

```python
from src.pipeline.nlp_extractor import extract
from src.pipeline.pathway_mapper import map_pathway
from src.pipeline.cost_calculator import calculate
from src.pipeline.provider_matcher import match

def run(query: str) -> dict:
    # Layer 1
    nlp = extract(query)

    if nlp.get("needs_clarification"):
        return {
            "status": "needs_clarification",
            "question": nlp["clarification_question"],
            "partial": nlp
        }

    top = nlp["conditions"][0]

    # Layer 2
    pathway = map_pathway(top["name"], top["severity"])

    if pathway.get("opd_only"):
        return {
            "status": "opd_only",
            "condition": top["name"],
            "message": "This condition is typically treated as outpatient (OPD) and is not covered under HBP hospitalization packages.",
            "confidence": top["confidence"],
            "severity": top["severity"]
        }

    if pathway.get("error") == "no_pathway":
        return {
            "status": "no_pathway",
            "condition": top["name"],
            "message": "Clinical pathway not found for this condition in our database.",
        }

    # Layer 3
    city = nlp.get("city") or "unknown"
    cost = calculate(pathway, city)

    if cost.get("error"):
        return {"status": "pricing_error", "error": cost["error"]}

    # Layer 4
    providers = match(city, pathway["specialty_code"], cost)

    return {
        "status": "ok",
        "condition": top["name"],
        "icd10": top["icd10"],
        "confidence": top["confidence"],
        "severity": top["severity"],
        "city": city,
        "city_tier": cost["city_tier"],
        "pathway": pathway,
        "cost_estimate": cost,
        "hospitals": providers["hospitals"],
        "other_conditions": nlp["conditions"][1:],
        "disclaimer": "This is an estimate for planning purposes only. Not medical advice. Actual costs vary by hospital and individual case."
    }


if __name__ == "__main__":
    import json
    result = run("knee pain for 3 months, age 58, Nagpur, budget 2.5 lakhs")
    print(json.dumps(result, indent=2, default=str))
```

---

## 4. Phase 2 — FastAPI Backend

### Step 6: `src/api/main.py`

**What it does:** Exposes the pipeline as an HTTP API. One main endpoint + health check.

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.pipeline.pipeline import run
import uvicorn

app = FastAPI(title="HealthNav API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    city: str | None = None
    budget_inr: int | None = None
    age: int | None = None

class ClarificationRequest(BaseModel):
    original_query: str
    clarification: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/analyze")
def analyze(req: QueryRequest):
    # If city/budget passed separately, append to query for now
    q = req.query
    if req.city and req.city.lower() not in q.lower():
        q += f", {req.city}"
    if req.budget_inr:
        q += f", budget {req.budget_inr}"
    try:
        result = run(q)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
```

**Run command:**
```bash
venv/bin/python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Test with curl:**
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "knee pain, age 58, Nagpur, budget 2 lakhs"}'
```

---

## 5. Phase 3 — Frontend Integration

### Step 7: Replace mock data with real API calls

**File:** `frontend/src/api.js` (create this file)

```javascript
const BASE_URL = "http://localhost:8000"

export async function analyze(query, city, budget) {
  const res = await fetch(`${BASE_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, city, budget_inr: parseBudget(budget) })
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

function parseBudget(budgetStr) {
  if (!budgetStr) return null
  const map = { "Under 50K": 50000, "50K – 1L": 100000, "1L – 3L": 300000, "3L – 5L": 500000, "5L – 10L": 1000000, "10L+": null }
  return map[budgetStr] || null
}
```

**File:** `frontend/src/App.jsx` changes
- Import `analyze` from `./api.js`
- In `handleSearch`: call `analyze(query, city, budget)`, await result, pass to Results component
- Add error state: if API returns `status: "needs_clarification"`, show clarification prompt screen
- Add error state: if API returns `status: "opd_only"`, show OPD-only message card

**Data shape mapping:**
The API output shape matches the frontend's `MOCK_RESULT` structure closely. Map these fields:
```javascript
// API result → frontend shape
result.cost_estimate → result.cost  (rename)
result.hospitals[].adjusted_total_low → result.hospitals[].range[0]
result.hospitals[].adjusted_total_high → result.hospitals[].range[1]
result.hospitals[].hospital_name → result.hospitals[].name
result.pathway.steps → result.pathway (array)
```

### Step 8: Additional frontend screens needed

**Clarification screen** (new component: `src/components/Clarification.jsx`)
- Show when API returns `status: "needs_clarification"`
- Display the `question` from API response
- Simple input + submit → re-run analyze with original query + clarification appended

**OPD-only screen** (add to Results or as separate state)
- Show when API returns `status: "opd_only"`
- Message: "This condition is treated outpatient — not covered under AB-PMJAY hospitalization"
- Show estimated OPD cost range (hardcoded ₹500–₹2,000 consult range)
- CTA: "Try a different query"

**Error screen** (minimal)
- Network error or 500 → show "Something went wrong. Please try again." with retry button

---

## 6. Phase 4 — Data Gap Fixes

### Step 9: Fix 5 null-pricing procedures

Run these SQL UPDATEs directly on Azure SQL after looking up correct values from HBP-2022.pdf burns section (BM specialty):

```sql
-- BM003B, BM003C, BM003D, BM004A, BM004B
-- Look up correct tier1/tier2/tier3 values from HBP-2022.pdf burns section
-- then run:
UPDATE dbo.procedures SET tier1_inr = ?, tier2_inr = ?, tier3_inr = ?
WHERE procedure_code IN ('BM003B', 'BM003C', 'BM003D', 'BM004A', 'BM004B');
```

### Step 10: NABH scraper (optional, Phase 2)

**File:** `src/scrapers/nabh_scraper.py`
- Scrape nabh.co hospital list
- Match by hospital name + state (fuzzy match)
- UPDATE `hospitals.nabh_accredited = 1` where matched

### Step 11: Google Places ratings (optional, Phase 2)

**File:** `src/scrapers/google_ratings.py`
- For each hospital with NULL google_rating: call Google Places Text Search API
- Match on hospital_name + address
- UPDATE `hospitals.google_rating = <value>`

---

## 7. File Structure After Full Build

```
/home/kevin/Desktop/fincorp/
├── .env                          ← ANTHROPIC_API_KEY must be here
├── CLAUDE.md                     ← project bible
├── docs/
│   ├── architecture.md
│   ├── migration_prompt.md
│   └── build_plan.md             ← THIS FILE
├── raw/                          ← source PDFs/CSVs (already processed)
├── frontend/                     ← Vite React app
│   ├── src/
│   │   ├── api.js                ← NEW: API client
│   │   ├── App.jsx
│   │   ├── data.js               ← mock data (keep for fallback)
│   │   ├── components/
│   │   │   ├── Landing.jsx
│   │   │   ├── Loading.jsx
│   │   │   ├── Results.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   ├── TabPathway.jsx
│   │   │   ├── TabCost.jsx
│   │   │   ├── TabHospitals.jsx
│   │   │   ├── HospitalSheet.jsx
│   │   │   └── Clarification.jsx  ← NEW
│   │   └── index.css
├── src/
│   ├── utils/
│   │   └── db_connect.py         ← done
│   ├── db/
│   │   ├── schema.sql            ← done
│   │   ├── init_db.py            ← done
│   │   └── sanity_check.py       ← done
│   ├── parsers/                  ← done, don't re-run
│   ├── pipeline/                 ← BUILD THIS FIRST
│   │   ├── __init__.py
│   │   ├── nlp_extractor.py      ← Step 1
│   │   ├── pathway_mapper.py     ← Step 2
│   │   ├── cost_calculator.py    ← Step 3
│   │   ├── provider_matcher.py   ← Step 4
│   │   └── pipeline.py           ← Step 5
│   └── api/                      ← BUILD SECOND
│       ├── __init__.py
│       └── main.py               ← Step 6
```

---

## 8. Testing Checklist (Run After Each Step)

### After Step 1 (nlp_extractor):
```bash
venv/bin/python src/pipeline/nlp_extractor.py
# Expect: valid JSON with conditions, confidence scores, city, severity
```

### After Step 2 (pathway_mapper):
```bash
venv/bin/python src/pipeline/pathway_mapper.py
# Expect: steps list with procedure codes, bed_category, los range
```

### After Step 3 (cost_calculator):
```bash
venv/bin/python src/pipeline/cost_calculator.py
# Expect: procedure_base, stay_cost, meds, contingency, total_range — all ranges
```

### After Step 4 (provider_matcher):
```bash
venv/bin/python src/pipeline/provider_matcher.py
# Expect: 3–5 hospitals from Nagpur with adjusted cost ranges
```

### After Step 5 (pipeline):
```bash
venv/bin/python src/pipeline/pipeline.py
# Full end-to-end. Expect complete JSON response.
# Test 3 queries:
# 1. "knee pain in Nagpur under 3 lakhs, age 58"  → orthopedics pathway
# 2. "chest pain sometimes, age 55, Mumbai"       → cardiology pathway, Tier 1 pricing
# 3. "fever and cold for 2 days"                  → OPD-only flag
```

### After Step 6 (FastAPI):
```bash
curl http://localhost:8000/health     # → {"status":"ok"}
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"query":"knee pain Nagpur 3 lakhs age 58"}'
```

---

## 9. Critical Rules — Do Not Violate

1. **Never output a point estimate** — always `[low, high]` tuple
2. **Always show confidence** — if < 0.60, trigger clarification before Layer 2
3. **OPD-only cases must be flagged** — never send them through the cost pipeline
4. **Disclaimer must always appear** in API response and frontend
5. **DB connection** — always use `src/utils/db_connect.py`, never hardcode credentials
6. **Surgical + medical packages** cannot be combined in same admission — if pathway has both, split into separate admissions and note it
7. **NABH multiplier is compounded** — not additive. Entry +10%, Full +15%, Metro +10% each compound on base
8. **Multi-procedure stacking** — P1=100%, P2=50%, P3+=25% — implement exactly, not approximately
9. **City tier lookup** — always query `city_tier_map` table, never hardcode city names
10. **Run command prefix** — always `venv/bin/python`, not just `python`

---

## 10. Quick Reference — DB Tables and What Pipeline Uses Them For

| Table | Used in Layer | Purpose |
|---|---|---|
| `specialties` | 2 | FK resolution, specialty_code lookup |
| `packages` | 2 | FK resolution |
| `procedures` | 3 | tier1/2/3_inr price lookup |
| `clinical_pathways` | 2 | condition → ordered steps |
| `city_tier_map` | 3 | city → tier number |
| `bed_day_rates` | 3 | bed_category → rate_per_day |
| `hospital_type_multipliers` | 3, 4 | hospital_type → multiplier_low/high |
| `hospitals` | 4 | filter + rank providers |
| `specialty_priority` | 1 (optional) | rank conditions by real-world volume |

---

*Last updated: May 2026. Use this document as the build bible in the next Claude Code session.*
