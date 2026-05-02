# CLAUDE.md — AI-Powered Healthcare Navigator & Cost Estimator for India

> This file is the single source of truth for this project. Read it fully before writing any code.

---

## 1. What We Are Building

A **healthcare decision-intelligence platform** for Indian patients — primarily Tier 2/3 cities — that takes a vague natural language query ("my chest hurts sometimes", "knee replacement in Nagpur under 3 lakhs") and returns:

- Likely condition + severity classification
- Matching hospitals ranked by capability, reputation, and affordability
- Itemized, city-tier-adjusted treatment cost range
- Confidence score + disclaimer

Think **"Kayak for Healthcare"** — not a chatbot that suggests hospitals, but a structured pipeline:

```
User prompt (vague NL) 
  → Disease + severity extraction (LLM + Infermedica API)
  → Clinical pathway mapping (HBP logic layer)
  → Cost estimation (HBP rates × city tier × hospital type multiplier)
  → Provider matching (hospital DB + Google reviews)
  → Output: ranked list + itemized cost range + confidence score
```

**This is Problem Statement 4B** from a hackathon. The PS doc is in context from a previous session — do not re-ask for it.

---

## 2. Raw Data Sources (`/raw` folder)

All files are in the same `/raw` directory. Here is what each is, and how to use it.

---

### 2.1 `HBP.pdf` — HBP 2.2 User Guidelines (NHA, Nov 2021)

**What it is:** The operational manual for India's AB-PMJAY (Ayushman Bharat) scheme. 64 pages. NOT the rates sheet — this is the clinical logic document.

**What it contains that matters:**
- 26 specialties, 919 packages, 1,670 procedures (Section 2.3 table, Page 21)
- Per-specialty pre-authorization requirements (Section 3, Pages 22–33) — these implicitly define clinical pathways
- Medical package bed-day pricing (Section 2.2.3, Page 17):
  - Routine Ward: ₹1,800/day
  - High Dependency Unit: ₹2,700/day
  - ICU (no ventilator): ₹3,600/day
  - ICU (with ventilator): ₹4,500/day
- Multiple-procedure stacking rule (Section 1.3, Page 6): primary = 100%, 2nd = 50%, 3rd+ = 25%
- NABH incentive structure (Page 50): Entry NABH +10%, Full NABH +15%, Metro location +10%, Aspirational district +10% — compounded, not additive
- Metros defined (Page 50): Delhi UA, Mumbai UA, Kolkata UA, Chennai UA, Bengaluru UA, Ahmedabad UA, Hyderabad UA, Pune UA
- Exclusions (Annexure 1, Pages 54–55): OPD, cosmetic, dental, vaccination, infertility

**How to use it:** This is your **clinical logic and pathway layer** — not for ₹ rates. Use the pre-auth requirements per specialty to infer what investigations precede what procedures.

---

### 2.2 `HBP-2022.pdf` — HBP 2022 Rates Sheet (NHA)

**What it is:** The actual procedure-level rates spreadsheet exported as PDF. This is the **cost data core** of the project.

**Structure (columns per row):**
```
Specialty | Specialty Code | Package Code | Package Name | Procedure Code | Procedure Name | Tier3 (Z) ₹ | Tier2 (Y) ₹ | Tier1 (X) ₹ | Implant Mapped | Implant Cost | Stratification Remarks
```

**Key confirmed data points:**
- Burns Thermal <20% TBSA: ₹7,000 / ₹8,200 / ₹8,800 (T3/T2/T1)
- Burns 25–40% TBSA: ₹62,500 / ₹71,000 / ₹75,000
- Peripheral Angioplasty (MC017A): ₹43,200 / ₹49,000 / ₹51,800
- Bronchial Artery Embolisation (MC018A): ₹41,000 / ₹46,600 / ₹49,200
- Pericardiocentesis (MC019A): ₹15,200 / ₹17,200 / ₹18,200
- Systemic Thrombolysis for MI (MC020A): ₹22,400 / ₹25,500 / ₹26,900
- Right Heart Catheterization (MC001A): ₹12,500 / ₹14,200 / ₹15,000
- Left Heart Catheterization (MC001B): ₹12,500 / ₹14,200 / ₹15,000
- Catheter-directed Thrombolysis DVT (MC002A): ₹38,500 / ₹43,800 / ₹46,200
- Nephrostomy percutaneous (SU008A): ₹18,800 / ₹21,300 / ₹22,500
- Bone Marrow Aspiration (MG082A): ₹1,200 / ₹1,600 / ₹1,600
- EBUS (MG097A): ₹15,700 / ₹18,000 / ₹18,000
- COVID-19 PCR (ID001B): ₹3,000 flat all tiers
- Implant costs are listed separately (e.g., Single Chamber Pacemaker ₹45,000, Double Chamber ₹75,000, Peripheral Bare Metal Stent ₹21,000)

**Medical package rates (HBP 2022 update, different from HBP 2.2):**
- Routine Ward: ₹2,300/day
- HDU: ₹3,630/day
- ICU (no ventilator): ₹9,350/day
- ICU (with ventilator): ₹9,900/day

> Note: HBP 2022 has updated bed-day rates vs HBP 2.2. Use HBP 2022 rates as they are newer.

**How to parse:** Extract with `pdfminer.six`. The PDF is ~485KB, text-extractable. Each procedure is a row. Parse into a structured CSV/JSON with columns: `specialty`, `specialty_code`, `package_code`, `package_name`, `procedure_code`, `procedure_name`, `tier3_inr`, `tier2_inr`, `tier1_inr`, `implant_mapped`, `implant_cost_inr`, `stratification`.

**Parser command:**
```python
from pdfminer.high_level import extract_text
text = extract_text('raw/HBP-2022.pdf')
```

---

### 2.3 `Cost_of_hospital_services_in_India...PMC.mht` — CHSI Multi-Site Costing Study

**What it is:** BMC Health Services Research paper (2022). "Cost of Health Services in India" (CHSI) — first large-scale multi-site costing study, 54 hospitals across 11 states. This is the **academic source for city-tier multipliers and provider-type cost differentials**.

**Key findings to use in the cost model:**

*Provider type unit costs (unadjusted):*
- OPD visit: Tertiary ₹304 | District ₹185 | Private ₹1,251
- IPD admission: Tertiary ₹5,690 | Private ₹4,839 | District ₹3,447

*City tier differentials (statistically significant):*
- Significant differences in adjusted bed-day costs between Tier 3 vs Tier 1 and Tier 2
- Significant differences in procedure costs between Tier 2 and Tier 3
- This is the academic backing for applying tier multipliers to HBP base rates

*Capacity utilization matters:*
- Private hospitals: 50% bed occupancy (vs 80% district, 70% tertiary)
- After adjusting to 80% capacity: private and tertiary costs converge on IPD
- Private OPD remains ~4x district even after adjustment

*ALOS (Average Length of Stay):*
- Tertiary: 5.8 days | District: 4.3 days | Private: 2.5 days
- ICU bed occupancy: Private 20% vs District/Tertiary 70–80%

**How to use it:** This paper justifies your tier multiplier framework. Cite it in documentation. The actual numbers back the argument that Tier 1 costs ~1.5–2x Tier 3 for the same procedure.

**Source URL:** https://bmchealthservres.biomedcentral.com/articles/10.1186/s12913-022-08707-7

---

### 2.4 `Utilisation_pattern...Annals_of_National_Academy...mht` — HBP Utilisation Study

**What it is:** Cross-sectional study (2023 data) from KGMU Lucknow analyzing 4,542 HBP packages utilized under AB-PMJAY. Published in Annals of National Academy of Medical Sciences India (2026).

**Key findings to use:**

*Top specialties by volume (surgical + medical combined):*
1. Cardiology — 22.8% of all packages
2. Orthopedics — 15.7%

*Most expensive specialties:*
1. Radiodiagnosis (imaging)
2. Cardio-thoracic & Vascular Surgery (CTVS)

*Cardiology ranked #1 in BOTH volume AND cost* — this validates prioritizing cardiology in your demo/prototype.

*Package cost structure:*
- Each HBP payment includes: pre-procedure OPD diagnostics + procedure + hospitalization + 15 days post-discharge medicines
- This is your "bundled cost" definition

**How to use it:** Use to prioritize which conditions to build clinical pathways for first. Cardiology + Orthopedics = ~38% of all cases. Build those two pathways deeply rather than 10 pathways shallowly.

**Source URL:** https://nams-annals.in/utilisation-pattern-of-health-benefit-packages-under-ayushman-bharat-pradhan-mantri-jan-arogya-yojana/

---

## 3. Additional Data Sources (Not in `/raw` yet — to be added)

### 3.1 Hospital Lists (Already acquired)
- **data.gov.in NHP Hospital Directory** — state-wise hospitals with lat/long, specialization, category, PIN, contact. ~3,000 records. CSV/JSON downloadable. URL: https://data.gov.in/catalog/hospital-directory-national-health-portal

### 3.2 Reviews & Ratings (To be scraped)
- **Practo** — doctor profiles, consultation fees, ratings, experience. Apify scraper: `easyapi/practo-doctor-scraper` and `vasukurji/practo-hospital-review-scrapper`
- **Google Places API** — ratings, reviews, hours, photos, coordinates
- **JustDial** — useful for Tier 2/3 city coverage where Practo is thin

### 3.3 Drug Pricing(will be scraped)
- **NPPA drug price ceiling list** — `nppaindia.nic.in` — scheduled drug ceiling prices
- **Jan Aushadhi price list** — generic drug prices, `janaushadhi.gov.in`

### 3.4 NABH Accreditation (will be scraped)
- **NABH hospital list** — `nabh.co` — scrapeable. Use to flag NABH-accredited hospitals (triggers +10% or +15% rate incentive per HBP)

---

## 4. Core Architecture

### 4.1 Pipeline

```
INPUT: Natural language query + optional (city, age, budget)
  │
  ▼
[Layer 1] NLP / Disease Extraction
  - LLM (Claude API) extracts: symptoms, body system, duration signals, comorbidities
  - Infermedica API for ICD-10 mapping + condition probability ranking
  - Output: top 3 condition candidates + severity band (mild/moderate/severe)
  │
  ▼
[Layer 2] Clinical Pathway Mapping
  - Static pathway map: condition → sequence of procedures (built from HBP pre-auth requirements)
  - Severity determines branch: medication-only vs. diagnostic + procedure vs. surgical
  - Top 30–40 conditions cover ~80% of real cases (Cardiology + Ortho = 38% alone)
  │
  ▼
[Layer 3] Cost Estimation
  - Procedure codes → HBP 2022 base rates (Tier3/Tier2/Tier1)
  - Apply city tier: user's city → tier classification
  - Apply hospital type multiplier: Govt 1.0x | Mid-private 1.5–2.0x | Corporate 2.5–3.5x
  - Apply NABH multiplier if applicable (+10% entry, +15% full, compounded)
  - Medical cases: bed-day rate × estimated LOS × acuity (Routine/HDU/ICU)
  - Add medication estimate: ~8–12% of procedure cost (IRDAI benchmark) or NPPA lookup
  - Output: cost range (low–high), not point estimate
  │
  ▼
[Layer 4] Provider Matching
  - Filter hospital DB by: city, specialty match, hospital type preference
  - Rank by: NABH status, Google rating, Practo reviews, distance
  - Return top 3–5 hospitals with cost estimate per hospital type
  │
  ▼
OUTPUT: Structured response with:
  - Likely condition + confidence
  - Cost range per component (procedure, stay, meds, contingency)
  - Ranked hospitals
  - Confidence score (0–1)
  - Mandatory disclaimer
```

---

### 4.2 City Tier Classification

| Tier | Cities | HBP Column |
|------|--------|------------|
| Tier 1 (X) | Delhi UA, Mumbai UA, Kolkata UA, Chennai UA, Bengaluru UA, Ahmedabad UA, Hyderabad UA, Pune UA | Use `tier1_inr` |
| Tier 2 (Y) | State capitals + large cities (Jaipur, Nagpur, Surat, Lucknow, Kanpur, Bhopal, etc.) | Use `tier2_inr` |
| Tier 3 (Z) | All other cities, towns, rural | Use `tier3_inr` |

Source: National Pay Commission classification. HBP explicitly uses X/Y/Z notation.

---

### 4.3 Hospital Type Multipliers

These are derived from CHSI study private vs. public cost ratios:

| Hospital Type | Multiplier over HBP base |
|---|---|
| Government / Public | 1.0× (HBP rate IS the govt rate) |
| Mid-tier private | 1.5–2.0× |
| Corporate / Super-specialty | 2.5–3.5× |

---

### 4.4 Severity → Bed Category Mapping

| Severity Signal | Bed Category | Rate/day (HBP 2022) |
|---|---|---|
| Mild (outpatient, monitoring) | Routine Ward | ₹2,300 |
| Moderate (close monitoring) | HDU | ₹3,630 |
| Severe (critical, no vent) | ICU | ₹9,350 |
| Critical (ventilated) | ICU + ventilator | ₹9,900 |

---

### 4.5 Multiple Procedure Rule (from HBP, Page 6)

When a patient needs multiple procedures in one OT session:
- Procedure 1 (highest rate): 100%
- Procedure 2: 50%
- Procedure 3+: 25%

Implement this in your cost calculator for complex cases.

---

## 5. Clinical Pathway Templates (Priority Order)

Build these first (covers ~70% of real volume based on utilisation study):

### Cardiology — Coronary Artery Disease (Moderate)
```
Step 1: Consultation (cardiologist)
Step 2: ECG + ECHO + Lipid panel + Blood tests (INR, Hb, Creatinine)
  → Severity branch:
     Mild: Medication only (₹2,300/day ward)
     Moderate: Coronary Angiography (CAG) → Angioplasty (MC017 equivalent)
     Severe: CABG (CTVS specialty)
Step 3: Post-procedure stay (2–5 days depending on branch)
Step 4: 15-day post-discharge meds (included in HBP bundle)
Step 5: Follow-up at 2–4 weeks (MC022A, included in package)
```

### Orthopedics — Knee Pain / Osteoarthritis
```
Step 1: Consultation (orthopedician)
Step 2: X-ray bilateral knees + MRI if needed
  → Severity branch:
     Mild: Physiotherapy + medication
     Moderate: Intra-articular injection / arthroscopy
     Severe: Total Knee Replacement (TKR) — SB specialty
Step 3: Post-op stay (TKR ~5–7 days)
Step 4: Physiotherapy + follow-up
```

### General Medicine — Fever / Infection
```
Step 1: OPD consultation
Step 2: CBC + CRP + culture if needed
  → Severity:
     Mild: OPD treatment (not covered under HBP — flag this)
     Moderate: Inpatient under MG specialty, ward admission
     Severe: HDU/ICU, sepsis protocol
```

---

## 6. Key Constraints & Rules

1. **HBP covers hospitalization only** — OPD-only cases are NOT covered and should be flagged to the user
2. **No diagnosis** — the system is decision-support only. Always show disclaimer
3. **Confidence score** must be shown. If condition match < 60%, prompt user for clarification
4. **Outputs are ranges, not point estimates** — never output a single number
5. **Exclusions to never recommend HBP for:** cosmetic, dental, vaccination, fertility treatments, OPD-only conditions
6. **Pre-existing conditions affect cost** — diabetes → higher ICU probability, prior cardiac history → higher complication risk. Factor into contingency band
7. **Surgical + medical packages cannot be combined** in same admission (HBP rule) — only surgical OR medical per episode

---

## 7. Output Format (Target)

```json
{
  "condition": "Coronary Artery Disease",
  "confidence": 0.72,
  "recommended_procedure": "Coronary Angioplasty",
  "severity": "moderate",
  "city": "Nagpur",
  "city_tier": 2,

  "cost_estimate": {
    "procedure_base": [43200, 49000],
    "hospital_stay_days": [3, 5],
    "hospital_stay_cost": [13500, 18150],
    "medication_post_discharge": [5000, 9000],
    "contingency": [8000, 15000],
    "total_range": [69700, 91150]
  },

  "hospitals": [
    {
      "name": "ABC Heart Institute",
      "rating": 4.5,
      "type": "mid_private",
      "nabh": true,
      "distance_km": 5.2,
      "cost_multiplier": 1.8,
      "adjusted_total_range": [125460, 164070]
    }
  ],

  "notes": [
    "Costs may increase if ICU care is required",
    "Diabetes may increase complication risk and extend stay"
  ],

  "disclaimer": "This is an estimate for planning purposes only. Actual costs vary. This is not medical advice."
}
```

---

## 8. Tech Stack Recommendations

| Component | Recommended |
|---|---|
| LLM for NLP | Claude API (claude-sonnet) |
| Symptom-to-ICD mapping | Infermedica API (free tier available) |
| Hospital data | data.gov.in CSV + ABDM HFR |
| Reviews | Practo scraper (Apify) + Google Places API |
| Drug prices | NPPA ceiling list (CSV download) |
| HBP rates | Parse HBP-2022.pdf → structured DB |
| Backend | Python (FastAPI) |
| Frontend | React or simple HTML/JS chatbot |
| DB | SQLite or Postgres for hospital + procedure data |

---

## 9. Files to Create

```
/raw/
  HBP.pdf                          ← HBP 2.2 User Guidelines (clinical logic)
  HBP-2022.pdf                     ← HBP 2022 Rates Sheet (cost data)
  CHSI_cost_study.mht              ← BMC paper on hospital costs (tier multiplier source)
  utilisation_pattern_PMJAY.mht    ← KGMU utilisation study (priority conditions)

/data/
  hbp_procedures.csv               ← parsed from HBP-2022.pdf
  hospitals.csv                    ← from data.gov.in NHP
  city_tier_map.csv                ← city → tier 1/2/3

/src/
  pipeline/
    nlp_extractor.py               ← LLM + Infermedica → condition + severity
    pathway_mapper.py              ← condition + severity → procedure sequence
    cost_calculator.py             ← procedure codes + city + hospital type → range
    provider_matcher.py            ← hospital DB query + ranking
  api/
    main.py                        ← FastAPI endpoints
  parsers/
    hbp_pdf_parser.py              ← extract HBP-2022.pdf → CSV
```

---

## 10. What We Are NOT Building

- Not a diagnosis engine
- Not a booking system
- Not a telemedicine app
- Not a claims processor
- Not a real-time appointment scheduler

We are building a **pre-decision cost intelligence tool** that helps users understand what a treatment will likely cost before they commit to a hospital.

---

## 11. Conversation History Summary

This project was developed through an extended research and planning session. Key decisions made:

- Chose Problem Statement 4B (Healthcare Navigator) over 4A/4C/4D
- Hospital data: data.gov.in NHP directory (already sourced)
- Cost data: HBP 2022 rates sheet (the core `/raw` file)
- City-tier multipliers: sourced from CHSI study (academic backing)
- Clinical pathways: derived from HBP pre-auth requirements per specialty
- Disease extraction: Infermedica API for ICD-10 mapping (not synthetic)
- Medication costs: NPPA ceiling list + 8–12% of procedure cost as fallback
- Reviews: Practo scraper + Google Places API (to be added later)
- Priority conditions to build: Cardiology first (22.8% of all PMJAY usage), then Orthopedics (15.7%)
- Output format: always ranges, never point estimates; always show confidence score; always show disclaimer

---

*Last updated: April 2026. Migrate this file into Claude Code as CLAUDE.md at project root.*
