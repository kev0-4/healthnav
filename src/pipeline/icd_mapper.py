"""
icd_mapper.py — Pure Python ICD-10 prefix → HBP specialty code mapping.
Zero LLM calls, zero DB calls. Cannot fail.
"""

# ICD-10 prefix (2-3 chars) → HBP specialty code
# Ordered from most specific (3-char) to least (1-char) for prefix matching
_ICD10_MAP = {
    # ── Circulatory system (I00–I99) ──────────────────────────────────────
    "I2": "MC",   # Ischemic heart disease (CAD, angina, MI)
    "I1": "MC",   # Hypertensive heart disease
    "I3": "MC",   # Pulmonary heart disease, other forms of heart disease
    "I4": "MC",   # Cardiac arrhythmias, conduction disorders
    "I5": "MC",   # Heart failure
    "I0": "MC",   # Acute rheumatic / chronic rheumatic
    "I7": "MC",   # Diseases of arteries, arterioles, capillaries
    "I8": "MC",   # Diseases of veins, lymphatics
    "I9": "MC",   # Other circulatory
    "I6": "NS",   # Cerebrovascular (stroke → Neurosurgery)
    # ── Musculoskeletal (M00–M99) ──────────────────────────────────────────
    "M0": "SB",   # Infectious arthropathies
    "M1": "SB",   # Inflammatory polyarthropathies, rheumatoid
    "M2": "SB",   # Arthrosis (osteoarthritis)
    "M3": "SB",   # Systemic connective tissue disorders
    "M4": "SB",   # Deforming dorsopathies, spondylopathies
    "M5": "SB",   # Dorsalgia (back pain)
    "M6": "SB",   # Soft tissue disorders
    "M7": "SB",   # Other soft tissue disorders
    "M8": "SB",   # Osteopathies and chondropathies
    "M9": "SB",   # Other disorders of MSK system
    # ── Injury & Trauma (S00–T88) ──────────────────────────────────────────
    "S0": "SB",   # Head injuries
    "S1": "SB",   # Neck injuries
    "S2": "SB",   # Thorax injuries
    "S3": "SB",   # Abdomen/lower back injuries
    "S4": "SB",   # Shoulder/upper arm
    "S5": "SB",   # Elbow/forearm
    "S6": "SB",   # Wrist/hand
    "S7": "SB",   # Hip/thigh
    "S8": "SB",   # Knee/lower leg
    "S9": "SB",   # Ankle/foot
    "T0": "SB",   # Multiple/unspecified injuries
    "T1": "SB",   # Burns
    "T2": "BM",   # Burns (classified to Burns Management)
    "T3": "ER",   # Poisoning / toxic effects
    "T4": "ER",   # Other external causes
    # ── Respiratory (J00–J99) ──────────────────────────────────────────────
    "J0": "MG",   # Acute upper respiratory infections
    "J1": "MG",   # Influenza, pneumonia
    "J2": "MG",   # Other acute lower respiratory
    "J3": "MG",   # Chronic upper respiratory
    "J4": "MG",   # Chronic lower respiratory (COPD, asthma)
    "J6": "MG",   # Lung diseases due to external agents
    "J8": "MG",   # Other respiratory diseases
    "J9": "MG",   # Other respiratory
    # ── Digestive system (K00–K95) ─────────────────────────────────────────
    "K0": "SU",   # Diseases of oral cavity, oesophagus, stomach
    "K1": "SU",   # Diseases of small intestine
    "K2": "SU",   # Diseases of oesophagus/stomach/duodenum
    "K3": "SU",   # Hernia
    "K4": "SU",   # Hernia
    "K5": "SU",   # Non-infective enteritis/colitis
    "K6": "SU",   # Other intestinal
    "K7": "SU",   # Liver/gallbladder
    "K8": "SU",   # Gallbladder, biliary tract, pancreas
    "K9": "SU",   # Other digestive
    # ── Genitourinary (N00–N99) ────────────────────────────────────────────
    "N0": "URO",  # Glomerular diseases
    "N1": "URO",  # Renal tubulo-interstitial diseases
    "N2": "URO",  # Acute kidney injury / CKD
    "N3": "URO",  # Urolithiasis (kidney stones)
    "N4": "URO",  # Other disorders of kidney
    "N5": "URO",  # Disorders of ureter/bladder
    "N6": "URO",  # Urethral disorders
    "N7": "URO",  # Other urinary disorders
    "N8": "OB",   # Non-inflammatory disorders of female genital
    "N9": "OB",   # Other female genital
    # ── Nervous system (G00–G99) ────────────────────────────────────────────
    "G0": "NS",   # Inflammatory diseases of CNS
    "G1": "NS",   # Systemic atrophies
    "G2": "NS",   # Extrapyramidal disorders
    "G3": "NS",   # Other degenerative diseases of CNS
    "G4": "NS",   # Episodic / paroxysmal disorders (epilepsy)
    "G5": "NS",   # Nerve / nerve root disorders
    "G6": "NS",   # Polyneuropathies
    "G7": "NS",   # Neuromuscular junction / muscle diseases
    "G8": "NS",   # Cerebral palsy / other paralytic syndromes
    "G9": "NS",   # Other disorders of nervous system
    # ── Neoplasms (C00–D49) ─────────────────────────────────────────────────
    "C": "OT",    # Malignant neoplasms → Surgical/Medical Oncology
    # ── Endocrine / metabolic (E00–E89) ────────────────────────────────────
    "E": "MG",    # Diabetes, thyroid, obesity, etc.
    # ── Infectious diseases (A00–B99) ─────────────────────────────────────
    "A": "ID",
    "B": "ID",
    # ── Blood diseases (D50–D89) ─────────────────────────────────────────────
    "D": "MG",
    # ── Mental health (F00–F99) ──────────────────────────────────────────────
    "F": "MG",    # Mental disorders
    # ── Eye (H00–H59) ────────────────────────────────────────────────────────
    "H0": "OP",
    "H1": "OP",
    "H2": "OP",
    "H3": "OP",
    "H4": "OP",
    "H5": "OP",
    # ── Ear (H60–H95) ────────────────────────────────────────────────────────
    "H6": "ENT",
    "H7": "ENT",
    "H8": "ENT",
    "H9": "ENT",
    # ── Obstetrics (O00–O9A) ─────────────────────────────────────────────────
    "O": "OB",
    # ── Perinatal (P00–P96) ──────────────────────────────────────────────────
    "P": "MG",
    # ── Symptoms (R00–R99) ───────────────────────────────────────────────────
    "R": "MG",
    # ── Burns (specifically) ─────────────────────────────────────────────────
    "L5": "BM",   # Burns classified under skin chapter
}

# Body-system string → specialty fallback when ICD-10 prefix not found
_BODY_SYSTEM_MAP = {
    "cardiovascular":   "MC",
    "cardiac":          "MC",
    "circulatory":      "MC",
    "musculoskeletal":  "SB",
    "orthopedic":       "SB",
    "orthopaedic":      "SB",
    "bone":             "SB",
    "joint":            "SB",
    "respiratory":      "MG",
    "pulmonary":        "MG",
    "digestive":        "SU",
    "gastrointestinal": "SU",
    "abdominal":        "SU",
    "genitourinary":    "URO",
    "renal":            "URO",
    "urinary":          "URO",
    "neurological":     "NS",
    "nervous":          "NS",
    "brain":            "NS",
    "oncology":         "OT",
    "cancer":           "OT",
    "infectious":       "ID",
    "infection":        "ID",
    "endocrine":        "MG",
    "metabolic":        "MG",
    "eye":              "OP",
    "ophthalm":         "OP",
    "ear":              "ENT",
    "obstetric":        "OB",
    "gynaecol":         "OB",
    "gynecol":          "OB",
}

_SPECIALTY_NAMES = {
    "MC": "Cardiology",
    "SB": "Orthopedics",
    "MG": "General Medicine",
    "SU": "General Surgery",
    "NS": "Neurosurgery",
    "URO": "Urology",
    "ID": "Infectious Diseases",
    "OT": "Medical Oncology",
    "OP": "Ophthalmology",
    "OB": "Obstetrics & Gynecology",
    "BM": "Burns Management",
    "ER": "Emergency",
    "ENT": "ENT",
    "HM": "High-end Medicine",
    "HD": "High-end Diagnostics",
}


def get_specialty(icd10: str | None, body_system: str | None = None) -> tuple[str, str]:
    """
    Returns (specialty_code, specialty_name).
    Tries ICD-10 prefix first (3-char, then 2-char, then 1-char),
    then body_system string, then defaults to "MG".
    Never raises.
    """
    if icd10:
        clean = icd10.strip().upper().replace(".", "")
        # Try 3-char, then 2-char, then 1-char prefix
        for length in (3, 2, 1):
            prefix = clean[:length]
            if prefix in _ICD10_MAP:
                code = _ICD10_MAP[prefix]
                return code, _SPECIALTY_NAMES.get(code, code)

    if body_system:
        bs_lower = body_system.lower()
        for key, code in _BODY_SYSTEM_MAP.items():
            if key in bs_lower:
                return code, _SPECIALTY_NAMES.get(code, code)

    return "MG", "General Medicine"
