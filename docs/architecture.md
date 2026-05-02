# Healthcare Navigator — Architecture & Data Schema

---

## 1. Data Schema

### Entity Relationship

```
┌─────────────────────┐         ┌─────────────────────────┐
│   specialties        │         │   specialty_priority     │
│─────────────────────│         │─────────────────────────│
│ PK specialty_code   │◄────────│ PK specialty_code  (FK) │
│    specialty_name   │    1:1  │    volume_rank           │
└────────┬────────────┘         │    cost_rank             │
         │ 1                    │    volume_pct            │
         │                      └─────────────────────────┘
         │ n
┌────────▼────────────┐
│   packages           │
│─────────────────────│
│ PK package_code     │
│    package_name     │
│ FK specialty_code   │
└────────┬────────────┘
         │ 1
         │ n
┌────────▼────────────┐         ┌─────────────────────────┐
│   procedures         │         │   clinical_pathways      │
│─────────────────────│         │─────────────────────────│
│ PK procedure_code   │◄────────│ FK procedure_code        │
│    procedure_name   │    n:1  │ FK specialty_code        │
│ FK package_code     │         │    condition_name        │
│    tier1_inr        │         │    severity              │
│    tier2_inr        │         │    step_order            │
│    tier3_inr        │         │    step_type             │
│    implant_mapped   │         │    step_description      │
│    implant_cost_inr │         │    bed_category          │
│    stratification.. │         │    los_days_low/high     │
└─────────────────────┘         │    hbp_covered           │
                                └─────────────────────────┘

── Reference / Config ──────────────────────────────────────────

┌──────────────────────┐  ┌───────────────────────────┐  ┌──────────────────────┐
│  bed_day_rates        │  │  hospital_type_multipliers │  │  city_tier_map        │
│──────────────────────│  │───────────────────────────│  │──────────────────────│
│ PK bed_category       │  │ PK hospital_type           │  │ PK city_name          │
│    rate_per_day       │  │    multiplier_low          │  │    state              │
│    hbp_version        │  │    multiplier_high         │  │    tier  (1 / 2 / 3) │
└──────────────────────┘  └───────────────────────────┘  │    is_metro           │
                                                          └──────────────────────┘

── Hospitals ────────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────┐
│  hospitals  (30,273 records — NHP / data.gov.in)             │
│──────────────────────────────────────────────────────────────│
│ PK hospital_id         state / district / pincode            │
│    hospital_name        latitude / longitude                  │
│    hospital_type ──────► joins hospital_type_multipliers      │
│    state ──────────────► joins city_tier_map                  │
│    nabh_accredited      google_rating    practo_rating        │
└──────────────────────────────────────────────────────────────┘
```

### Key Joins Used by the Pipeline

| Join | Purpose |
|---|---|
| `procedures → packages → specialties` | Resolve procedure to specialty |
| `city_tier_map.tier → procedures.tier{N}_inr` | Pick correct city-tier price |
| `hospitals.hospital_type → hospital_type_multipliers` | Apply provider cost markup |
| `clinical_pathways.bed_category → bed_day_rates` | Calculate ward/ICU stay cost |
| `specialty_priority → specialties` | Rank conditions by real-world volume |

---

## 2. System Architecture

```
╔══════════════════════════════════════════════════════════════════╗
║  INPUT                                                           ║
║  "knee pain in Nagpur, budget 3 lakhs, age 58"                  ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║  LAYER 1 — NLP & Disease Extraction                              ║
║                                                                  ║
║  ┌──────────────────────────────────────────────────────────┐   ║
║  │  Claude API  (claude-sonnet)                              │   ║
║  │                                                           │   ║
║  │  • Parse natural language input                           │   ║
║  │  • Extract: symptoms, body system, duration,              │   ║
║  │             comorbidities, city, budget                   │   ║
║  │  • Map to condition candidates + ICD-10 codes             │   ║
║  │  • Rank by probability, assign confidence score           │   ║
║  │  • Classify severity: mild / moderate / severe            │   ║
║  └──────────────────────────────────────────────────────────┘   ║
║                                                                  ║
║  Output: top 3 conditions + confidence score + severity band    ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║  LAYER 2 — Clinical Pathway Mapping                              ║
║                                                                  ║
║  DB: clinical_pathways · procedures · specialty_priority         ║
║                                                                  ║
║  • condition → specialty → ordered pathway steps                 ║
║  • severity branching: mild (OPD flag) / moderate / severe      ║
║  • resolves procedure codes for each step                        ║
║  • flags OPD-only conditions (not HBP-covered)                  ║
║                                                                  ║
║  Output: procedure_codes + bed_category + LOS range             ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║  LAYER 3 — Cost Estimation                                       ║
║                                                                  ║
║  DB: procedures · bed_day_rates · city_tier_map                  ║
║      hospital_type_multipliers                                   ║
║                                                                  ║
║  • City → tier (1/2/3) → tier{N}_inr from procedures            ║
║  • Multi-procedure rule: P1=100%, P2=50%, P3+=25%               ║
║  • Bed cost = rate_per_day × LOS × acuity level                 ║
║  • Medication estimate = 8–12% of procedure cost                 ║
║  • Hospital multiplier: govt 1×, mid-private 1.5–2×, corp 2.5–3.5× ║
║  • NABH add-on: +10% entry / +15% full (compounded)             ║
║                                                                  ║
║  Output: cost range { procedure, stay, meds, contingency, total }║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║  LAYER 4 — Provider Matching                                     ║
║                                                                  ║
║  DB: hospitals · city_tier_map                                   ║
║  APIs: Google Places · Practo                                    ║
║                                                                  ║
║  • Filter by state / district + specialty match                  ║
║  • Score by NABH status + rating + distance + bed count         ║
║  • Apply per-hospital cost multiplier to range                   ║
║                                                                  ║
║  Output: top 3–5 hospitals with adjusted cost range per hospital ║
╚══════════════════════════╦═══════════════════════════════════════╝
                           ║
                           ▼
╔══════════════════════════════════════════════════════════════════╗
║  OUTPUT                                                          ║
║                                                                  ║
║  {                                                               ║
║    condition, confidence, severity, city_tier,                   ║
║    cost_estimate: { procedure, stay, meds, contingency, total }, ║
║    hospitals: [ { name, type, rating, multiplier, adj_cost } ],  ║
║    notes,                                                        ║
║    disclaimer                                                    ║
║  }                                                               ║
╚══════════════════════════════════════════════════════════════════╝

── Serving Layer ────────────────────────────────────────────────

  FastAPI backend  ←──────────────────────────►  Azure SQL DB
       │
       ▼
  React / HTML+JS chat UI
```

---

## 3. Tech Stack

| Component | Technology |
|---|---|
| NLP / LLM | Claude API (claude-sonnet) |
| Ratings & Reviews | Google Places API · Practo |
| HBP Rates Database | Azure SQL (parsed from HBP-2022.pdf) |
| Hospital Directory | data.gov.in NHP — 30,273 records |
| Backend | Python · FastAPI |
| Frontend | React or HTML/JS chatbot |

---

## 4. Data Sources

| Source | What it provides |
|---|---|
| HBP 2.2 (NHA, 2021) | Clinical pathways, pre-auth requirements per specialty |
| HBP 2022 Rates Sheet (NHA) | 1,670 procedures with Tier 1/2/3 pricing |
| CHSI Multi-Site Costing Study (BMC, 2022) | Academic basis for city-tier and provider-type multipliers |
| KGMU Utilisation Study (Annals NAMS, 2026) | Real-world specialty volume & cost rankings |
| NHP Hospital Directory (data.gov.in) | 30,273 hospitals with geo-coordinates and category |
