import json
from src.utils.db_connect import get_connection

# Maps NLP-extracted condition names (substrings, case-insensitive) → DB condition_name (specialty level)
# and specialty_code + primary procedure codes per severity
_CONDITION_MAP = [
    # Cardiology
    {
        "keywords": ["coronary artery", "angina", "ischemic heart", "ischaemic heart", "myocardial infarction", "heart attack", "mi ", "cad"],
        "db_condition": "Cardiology",
        "specialty_code": "MC",
        "procedures": {
            "mild":     ["MC001A"],                           # Right Heart Cath (diagnostic)
            "moderate": ["MC011A", "MC017A"],                 # PTCA + Angioplasty
            "severe":   ["MC011A", "MC017A", "MC020A"],       # PTCA + Angio + Thrombolysis
        },
        "bed_category": {"mild": "routine_ward", "moderate": "routine_ward", "severe": "icu"},
        "los": {"mild": (2, 3), "moderate": (3, 5), "severe": (5, 7)},
    },
    {
        "keywords": ["chest pain", "chest tightness", "pericarditis", "pericardiocentesis"],
        "db_condition": "Cardiology",
        "specialty_code": "MC",
        "procedures": {
            "mild":     ["MC001A"],
            "moderate": ["MC019A", "MC011A"],
            "severe":   ["MC019A", "MC011A", "MC020A"],
        },
        "bed_category": {"mild": "routine_ward", "moderate": "routine_ward", "severe": "icu"},
        "los": {"mild": (2, 3), "moderate": (3, 5), "severe": (5, 7)},
    },
    # Orthopedics
    {
        "keywords": ["osteoarthritis", "knee", "joint pain", "knee pain", "knee osteo", "knee replacement",
                     "knee injury", "knee trauma", "meniscus", "meniscal", "total knee", "tkr", "knee degenerat",
                     "patella", "ligament tear", "acl", "pcl"],
        "db_condition": "Orthopedics",
        "specialty_code": "SB",
        "procedures": {
            "mild":     ["SB036A"],                  # Arthroscopy
            "moderate": ["SB036A"],                  # Arthroscopy
            "severe":   ["SB039A"],                  # Primary TKR
        },
        "bed_category": {"mild": "routine_ward", "moderate": "routine_ward", "severe": "routine_ward"},
        "los": {"mild": (1, 2), "moderate": (2, 3), "severe": (5, 7)},
    },
    {
        "keywords": ["hip pain", "hip replacement", "total hip", "hip fracture", "hip osteo"],
        "db_condition": "Orthopedics",
        "specialty_code": "SB",
        "procedures": {
            "mild":     ["SB036A"],
            "moderate": ["SB038B"],                  # THR Cementless
            "severe":   ["SB038A"],                  # THR Cemented
        },
        "bed_category": {"mild": "routine_ward", "moderate": "routine_ward", "severe": "routine_ward"},
        "los": {"mild": (1, 2), "moderate": (4, 6), "severe": (5, 7)},
    },
    {
        "keywords": ["fracture", "bone fracture", "broken bone", "limb fracture"],
        "db_condition": "Orthopedics",
        "specialty_code": "SB",
        "procedures": {
            "mild":     ["SB036A"],
            "moderate": ["SB036A"],
            "severe":   ["SB039A"],
        },
        "bed_category": {"mild": "routine_ward", "moderate": "routine_ward", "severe": "routine_ward"},
        "los": {"mild": (2, 3), "moderate": (3, 5), "severe": (5, 7)},
    },
    # General Medicine
    {
        "keywords": ["fever", "cold", "flu", "infection", "pneumonia", "typhoid", "dengue", "malaria", "sepsis"],
        "db_condition": "General Medicine",
        "specialty_code": "MG",
        "procedures": {
            "mild":     None,                         # OPD only
            "moderate": [],                           # Medical management, no procedure
            "severe":   [],
        },
        "bed_category": {"mild": None, "moderate": "routine_ward", "severe": "icu"},
        "los": {"mild": (0, 0), "moderate": (3, 5), "severe": (5, 10)},
    },
    # Infectious Diseases
    {
        "keywords": ["tuberculosis", "tb", "covid", "hiv", "hepatitis"],
        "db_condition": "Infectious Diseases",
        "specialty_code": "ID",
        "procedures": {
            "mild":     None,
            "moderate": [],
            "severe":   [],
        },
        "bed_category": {"mild": None, "moderate": "routine_ward", "severe": "hdu"},
        "los": {"mild": (0, 0), "moderate": (5, 10), "severe": (10, 21)},
    },
    # General Surgery
    {
        "keywords": ["internal bleeding", "gi bleed", "gastrointestinal bleed", "gastrointestinal hemorrhage",
                     "appendicitis", "appendix", "gallstone", "gall bladder", "cholecystitis",
                     "hernia", "bowel obstruction", "peritonitis", "abdominal abscess",
                     "gastrointestinal perforation", "rectal bleed"],
        "db_condition": "General Surgery",
        "specialty_code": "SU",
        "procedures": {
            "mild":     [],
            "moderate": [],
            "severe":   [],
        },
        "bed_category": {"mild": "routine_ward", "moderate": "routine_ward", "severe": "icu"},
        "los": {"mild": (2, 4), "moderate": (3, 5), "severe": (5, 10)},
    },
    # Urology
    {
        "keywords": ["kidney stone", "renal calculi", "urinary stone", "nephrolithiasis", "nephrostomy"],
        "db_condition": "Urology",
        "specialty_code": "URO",
        "procedures": {
            "mild":     [],
            "moderate": [],
            "severe":   [],
        },
        "bed_category": {"mild": "routine_ward", "moderate": "routine_ward", "severe": "hdu"},
        "los": {"mild": (1, 2), "moderate": (2, 4), "severe": (4, 7)},
    },
    # Neurology
    {
        "keywords": ["stroke", "brain stroke", "cerebrovascular", "tia", "seizure", "epilepsy", "brain"],
        "db_condition": "Neurosurgery",
        "specialty_code": "NS",
        "procedures": {
            "mild":     [],
            "moderate": [],
            "severe":   [],
        },
        "bed_category": {"mild": "routine_ward", "moderate": "hdu", "severe": "icu"},
        "los": {"mild": (2, 4), "moderate": (5, 10), "severe": (10, 21)},
    },
]


def _match_condition(condition_name: str) -> dict | None:
    name_lower = condition_name.lower()
    for entry in _CONDITION_MAP:
        if any(kw in name_lower for kw in entry["keywords"]):
            return entry
    return None


def map_pathway(condition_name: str, severity: str) -> dict:
    # Normalize severity
    if severity not in ("mild", "moderate", "severe"):
        severity = "moderate"

    entry = _match_condition(condition_name)
    db_condition = entry["db_condition"] if entry else condition_name

    # Query DB for pathway steps
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cp.step_order, cp.step_type, cp.step_description,
               cp.procedure_code, cp.bed_category, cp.los_days_low,
               cp.los_days_high, cp.hbp_covered, cp.specialty_code, cp.notes
        FROM dbo.clinical_pathways cp
        WHERE cp.condition_name LIKE ?
          AND (cp.severity = ? OR cp.severity = 'all')
        ORDER BY cp.step_order
    """, (f"%{db_condition}%", severity))
    rows = cursor.fetchall()

    if not rows:
        cursor.execute("""
            SELECT cp.step_order, cp.step_type, cp.step_description,
                   cp.procedure_code, cp.bed_category, cp.los_days_low,
                   cp.los_days_high, cp.hbp_covered, cp.specialty_code, cp.notes
            FROM dbo.clinical_pathways cp
            WHERE cp.condition_name LIKE ?
            ORDER BY cp.step_order
        """, (f"%{db_condition}%",))
        rows = cursor.fetchall()
    conn.close()

    cols = ["step_order", "step_type", "step_description", "procedure_code",
            "bed_category", "los_days_low", "los_days_high", "hbp_covered",
            "specialty_code", "notes"]
    # Deduplicate steps by step_order (DB has tripled rows from multi-load)
    seen_steps = set()
    steps = []
    for row in rows:
        d = dict(zip(cols, row))
        if d["step_order"] not in seen_steps:
            seen_steps.add(d["step_order"])
            steps.append(d)

    # Resolve procedure codes from condition map (DB pathways don't have codes attached)
    procedure_codes = []
    bed_category = "routine_ward"
    los_low, los_high = 3, 5
    specialty_code = None
    opd_only = False

    if entry:
        specialty_code = entry["specialty_code"]
        raw_procs = entry["procedures"].get(severity, entry["procedures"].get("moderate", []))
        if raw_procs is None:
            # Explicitly OPD-only (e.g., mild fever)
            opd_only = True
        else:
            procedure_codes = raw_procs
        bed_category = entry["bed_category"].get(severity, "routine_ward") or "routine_ward"
        los_low, los_high = entry["los"].get(severity, (3, 5))
        if los_low == 0:
            opd_only = True
    elif rows:
        # Fallback: use whatever came from DB
        specialty_code = rows[0][8]
        for s in steps:
            if s["bed_category"]:
                bed_category = s["bed_category"]
            if s["los_days_low"]:
                los_low = s["los_days_low"]
            if s["los_days_high"]:
                los_high = s["los_days_high"]
    else:
        return {
            "hbp_covered": False,
            "opd_only": True,
            "steps": [],
            "error": "no_pathway",
            "condition_name": condition_name,
            "severity": severity,
        }

    has_inpatient = bool(procedure_codes) or (not opd_only and bool(steps))

    return {
        "condition_name": condition_name,
        "db_condition": db_condition,
        "specialty_code": specialty_code,
        "severity": severity,
        "hbp_covered": has_inpatient,
        "opd_only": opd_only,
        "steps": steps,
        "primary_procedure_code": procedure_codes[0] if procedure_codes else None,
        "all_procedure_codes": procedure_codes,
        "bed_category": bed_category,
        "los_low": los_low,
        "los_high": los_high,
    }


if __name__ == "__main__":
    tests = [
        ("Coronary Artery Disease", "moderate"),
        ("Angina Pectoris", "moderate"),
        ("Osteoarthritis of knee", "severe"),
        ("Fever", "mild"),
        ("Fever", "severe"),
    ]
    for condition, sev in tests:
        print(f"\n{condition} / {sev}")
        result = map_pathway(condition, sev)
        print(f"  specialty: {result['specialty_code']} | opd_only: {result['opd_only']} | procedures: {result['all_procedure_codes']} | bed: {result['bed_category']} | LOS: {result['los_low']}-{result['los_high']}")
        print(f"  steps: {len(result['steps'])}")
