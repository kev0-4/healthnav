# Migration Prompt — Healthcare Navigator Project

Use this as the opening message when starting a new Claude chat session to restore full project context.

---

## PASTE THIS:

I am building an AI-powered healthcare decision-intelligence platform for Indian patients, primarily targeting Tier 2/3 cities. Think "Kayak for Healthcare" — a user types a vague query like "knee pain in Nagpur under 3 lakhs" and gets back: likely condition, itemized cost range, and ranked hospitals. This is Problem Statement 4B from a hackathon.

---

### What the system does

Takes a natural language health query + optional city/age/budget → runs it through 4 layers → returns structured JSON with condition, cost range, and hospital recommendations.

**4 Layers:**

1. **LLM / RAG Layer** — Claude parses the query, extracts symptoms/city/budget/comorbidities, queries a temporary Pinecone vector store of HBP procedure embeddings for context, then outputs: top condition candidates + ICD-10 codes + severity (mild/moderate/severe) + confidence score. If confidence < 60%, asks for clarification.
2. **Clinical Pathway Mapping** — maps condition + severity to an ordered sequence of procedure steps from the DB. Flags OPD-only cases as not HBP-covered. Outputs procedure codes + bed category + LOS range.
3. **Cost Estimation** — city → tier (1/2/3) → picks tier price from procedures table. Applies multi-procedure stacking rule (P1=100%, P2=50%, P3+=25%). Adds bed-day cost (rate × LOS × acuity). Adds medication estimate (8–12% of procedure cost). Applies hospital-type multiplier. Applies NABH add-on if applicable. Outputs cost range (low–high), never a point estimate.
4. **Provider Matching** — filters 30,273-hospital DB by location + specialty. Scores by NABH status, Google rating, distance, bed count. Applies per-hospital cost multiplier. Returns top 3–5 hospitals with adjusted cost range per hospital.

**Output JSON shape:**

```json
{
  "condition": "Coronary Artery Disease",
  "confidence": 0.72,
  "severity": "moderate",
  "city_tier": 2,
  "cost_estimate": {
    "procedure_base": [43200, 49000],
    "hospital_stay_cost": [13500, 18150],
    "medication_post_discharge": [5000, 9000],
    "contingency": [8000, 15000],
    "total_range": [69700, 91150]
  },
  "hospitals": [
    {
      "name": "ABC Heart Institute",
      "type": "mid_private",
      "nabh": true,
      "rating": 4.5,
      "cost_multiplier": 1.8,
      "adjusted_total_range": [125460, 164070]
    }
  ],
  "disclaimer": "This is an estimate for planning purposes only. Not medical advice."
}
```

---

### Tech Stack

| Component    | Technology                                         |
| ------------ | -------------------------------------------------- |
| LLM          | Claude API (claude-sonnet)                         |
| Vector Store | Pinecone (temporary, for HBP procedure embeddings) |
| Database     | Azure SQL Server (pyodbc + ODBC Driver 18)         |
| Backend      | Python · FastAPI                                   |
| Frontend     | React or HTML/JS chat UI                           |
| Ratings      | Google Places API · Practo                         |

---

### Database — 9 Tables (Azure SQL, fully populated)

**HBP Procedure Hierarchy:**

- `specialties` (specialty_code PK, specialty_name) — 25 rows
- `packages` (package_code PK, package_name, specialty_code FK) — 65 rows
- `procedures` (procedure_code PK, procedure_name, package_code FK, tier1_inr, tier2_inr, tier3_inr, implant_mapped, implant_cost_inr, stratification_text) — 87 rows. **Known issue: 5 Burns Management procedures (BM003B, BM003C, BM003D, BM004A, BM004B) have all-NULL tier prices — need manual UPDATE from HBP-2022.pdf.**

**Clinical Logic:**

- `clinical_pathways` (id PK, condition_name, specialty_code FK, severity, step_order, step_type, step_description, procedure_code FK, bed_category, los_days_low, los_days_high, hbp_covered, notes) — 141 rows
- `specialty_priority` (specialty_code PK FK, volume_rank, cost_rank, volume_pct, source) — 19 rows. Source: KGMU utilisation study 2023.

**Reference / Config (seeded, static):**

- `bed_day_rates` (bed_category PK, rate_per_day, hbp_version) — 4 rows:
  - routine_ward: ₹2,300/day
  - hdu: ₹3,630/day
  - icu: ₹9,350/day
  - icu_ventilator: ₹9,900/day
- `city_tier_map` (city_name PK, state, tier 1/2/3, is_metro) — 63 cities
- `hospital_type_multipliers` (hospital_type PK, multiplier_low, multiplier_high) — 3 rows:
  - government: 1.0×–1.0×
  - mid_private: 1.5×–2.0×
  - corporate: 2.5×–3.5×

**Hospitals:**

- `hospitals` (hospital_id PK, source_id, hospital_name, hospital_category, hospital_type, care_type, discipline, address, location, state, district, pincode, latitude, longitude, telephone, mobile, website, specialties, accreditation, nabh_accredited BIT, total_beds, emergency_services BIT, tariff_range, state_id, district_id, google_rating NULL, practo_rating NULL) — 30,273 rows from NHP / data.gov.in. Note: nabh_accredited is all 0 because source CSV has no NABH data — will be scraped from nabh.co later.

**Key joins the pipeline uses:**

- `procedures → packages → specialties` (resolve procedure to specialty)
- `city_tier_map.tier → procedures.tier{N}_inr` (city-tier price)
- `hospitals.hospital_type → hospital_type_multipliers` (provider markup)
- `clinical_pathways.bed_category → bed_day_rates` (stay cost)
- `specialty_priority → specialties` (condition priority routing)

---

### Data Sources & Ingestion

| File                            | Source                   | How Processed                                                                                |
| ------------------------------- | ------------------------ | -------------------------------------------------------------------------------------------- |
| `HBP-2022.pdf`                  | NHA (govt)               | pdfminer extracts text → LLM parses procedure rows → `specialties`, `packages`, `procedures` |
| `HBP.pdf`                       | NHA (govt)               | pdfminer extracts Section 3 → LLM parses pre-auth steps → `clinical_pathways`                |
| `hospital_directory.csv`        | data.gov.in              | CSV loader, derives hospital_type + nabh_accredited from raw fields → bulk loads `hospitals` |
| `utilisation_pattern_PMJAY.pdf` | KGMU / Annals NAMS 2026  | Data hardcoded from published tables → `specialty_priority`                                  |
| `CHSI_cost_study.pdf`           | BMC Health Services 2022 | Multipliers hardcoded → `bed_day_rates`, `city_tier_map`, `hospital_type_multipliers`        |

---

### Key Data Facts (baked into the system)

**HBP Pricing rules:**

- HBP covers hospitalization only — OPD-only cases are NOT covered, must be flagged
- City tiers: Tier 1 = 8 NPC metros (Delhi UA, Mumbai UA, Kolkata UA, Chennai UA, Bengaluru UA, Ahmedabad UA, Hyderabad UA, Pune UA). Tier 2 = state capitals + large cities. Tier 3 = everything else.
- Multi-procedure stacking: primary 100%, 2nd 50%, 3rd+ 25%
- NABH incentive: Entry NABH +10%, Full NABH +15%, Metro +10%, Aspirational district +10% — compounded not additive
- Surgical + medical packages cannot be combined in same admission

**Top specialties by real-world volume (KGMU 2023, N=4,542):**

- #1 Cardiology: 22.8% volume, 40.7% of total spend
- #2 Orthopedics: 15.7% volume, 19.2% of total spend
- #3 Surgical Oncology: 9.2% volume
- Costliest medical package: Radiodiagnosis (max ₹4,31,640)
- Costliest surgical package: CTVS (max ₹3,86,735)

**CHSI study multiplier backing:**

- Private hospitals have ~4× OPD cost vs district after capacity adjustment
- Tier 3 cities significantly cheaper than Tier 1/2 for IPD bed-day costs
- Academic source for all multipliers applied in Layer 3

---

### File Structure

```
/raw/
  HBP.pdf
  HBP-2022.pdf
  HBP_2022_formatted.txt        ← manually generated JSON (LLM output)
  paathway_Specialities_formatted.txt  ← manually generated JSON (LLM output)
  hospital_directory.csv
  utilisation_pattern_PMJAY.pdf
  CHSI_cost_study.pdf

/src/
  utils/
    db_connect.py               ← Azure SQL connection via pyodbc
  db/
    schema.sql                  ← T-SQL DDL for all 9 tables
    init_db.py                  ← creates schema + seeds static tables
    sanity_check.py             ← automated DB health check script
  parsers/
    hbp_2022_json_loader.py     ← loads HBP_2022_formatted.txt → DB
    hbp_pathway_json_loader.py  ← loads paathway_Specialities_formatted.txt → DB
    hospital_csv_loader.py      ← loads hospital_directory.csv → DB
    study_data_loader.py        ← hardcoded data from research papers → DB
    hbp_2022_parser.py          ← LLM parser (Gemini, 5 chunks, backup)
    hbp_pathway_parser.py       ← LLM parser (Gemini, 5 chunks, backup)

/docs/
  architecture.md               ← full schema ERD + system architecture

/.env
  AZURE_SQL_SERVER
  AZURE_SQL_DATABASE
  AZURE_SQL_USERNAME
  AZURE_SQL_PASSWORD
  GOOGLE_API_KEY                ← Gemini API key (gemini-3.1-flash)
```

---

### What Is Built

- Full Azure SQL schema, created and seeded
- All data loaded and verified (sanity check passes)
- `db_connect.py` shared connection utility
- All parser/loader scripts written and run
- `sanity_check.py` — automated test across all 9 tables
- `docs/architecture.md` — full ERD + architecture reference
- Eraser.io diagram code for all 4 layers (for PPT deck)

---

### What Is NOT Built Yet (next steps)

- `src/pipeline/nlp_extractor.py` — Layer 1 (Claude + RAG)
- `src/pipeline/pathway_mapper.py` — Layer 2
- `src/pipeline/cost_calculator.py` — Layer 3
- `src/pipeline/provider_matcher.py` — Layer 4
- `src/api/main.py` — FastAPI endpoints
- Frontend chat UI
- Fix 5 null-pricing procedures (BM003B/C/D, BM004A/B) — manual UPDATE needed
- NABH data — scrape from nabh.co and UPDATE hospitals table
- Google Places / Practo ratings — populate google_rating, practo_rating columns

---

### Environment

- OS: Linux (Ubuntu), Python venv at `/home/kevin/Desktop/fincorp/venv/`
- Run scripts as: `venv/bin/python src/...`
- Working directory: `/home/kevin/Desktop/fincorp/`
- DB: Azure SQL Server, pyodbc, ODBC Driver 18 for SQL Server
- LLM for parsing: `gemini-3.1-flash` (Google GenAI SDK)
- LLM for pipeline: Claude API (claude-sonnet)

---

### Constraints & Rules

- Outputs are always ranges, never point estimates
- Confidence score always shown; < 60% triggers clarification prompt
- Never recommend HBP for: cosmetic, dental, vaccination, fertility, OPD-only
- System is decision-support only — always show disclaimer, never diagnose
- HBP covers: pre-procedure OPD diagnostics + procedure + hospitalization + 15 days post-discharge meds (bundled)
