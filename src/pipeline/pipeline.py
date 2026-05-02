import json
import logging
from src.pipeline.nlp_extractor import extract
from src.pipeline.icd_mapper import get_specialty
from src.pipeline.procedure_selector import select_procedures
from src.pipeline.cost_calculator import calculate
from src.pipeline.provider_matcher import match

log = logging.getLogger("pipeline")


def run(query: str, on_progress=None) -> dict:
    def _emit(step: int, status: str):
        if on_progress:
            try:
                on_progress(step, status)
            except Exception:
                pass  # never let progress callbacks break the pipeline

    log.info("▶ query: %s", query)

    # Layer 1 — NLP extraction
    _emit(0, "running")
    nlp = extract(query)
    _emit(0, "done")
    log.info("  NLP → top: %s (%.0f%%) sev=%s city=%s icd=%s",
             nlp.get("top_condition"), (nlp.get("top_confidence") or 0) * 100,
             nlp.get("top_severity"), nlp.get("city"), nlp.get("top_icd10"))

    if nlp.get("needs_clarification"):
        log.info("  → needs_clarification: %s", nlp["clarification_question"])
        return {
            "status": "needs_clarification",
            "question": nlp["clarification_question"],
            "partial": nlp,
        }

    conditions = nlp.get("conditions", [])
    if not conditions:
        return {
            "status": "needs_clarification",
            "question": "Could you describe your main symptom and which city you are in?",
            "partial": nlp,
        }

    city = nlp.get("city") or "unknown"

    # Layer 2 — ICD-10 → specialty routing + RAG procedure selection
    _emit(1, "running")
    # Priority: inpatient + has procedure codes > inpatient no codes > opd-only
    pathway = None
    top = None
    fallback_inpatient = None
    fallback_opd = None

    for cand in conditions:
        icd10 = cand.get("icd10")
        body_system = nlp.get("body_system")
        severity = cand.get("severity", "moderate")

        # Deterministic ICD-10 → specialty (never fails)
        specialty_code, specialty_name = get_specialty(icd10, body_system)
        log.info("  icd_mapper(%s) → %s (%s)", icd10, specialty_code, specialty_name)

        # RAG: specialty + condition → procedure pathway (never fails)
        other_cands = [c for c in conditions if c is not cand]
        pw = select_procedures(
            specialty_code=specialty_code,
            condition_name=cand["name"],
            icd10=icd10,
            severity=severity,
            body_system=body_system,
            query=query,
            other_conditions=other_cands,
        )
        log.info("  pathway(%s/%s) → opd=%s codes=%s bed=%s LOS=%s-%s",
                 cand["name"], severity,
                 pw.get("opd_only"), pw.get("all_procedure_codes"),
                 pw.get("bed_category"), pw.get("los_low"), pw.get("los_high"))

        if not pw.get("opd_only") and pw.get("all_procedure_codes"):
            pathway = pw
            top = cand
            break
        if not pw.get("opd_only") and fallback_inpatient is None:
            fallback_inpatient = (cand, pw)
        if pw.get("opd_only") and fallback_opd is None:
            fallback_opd = (cand, pw)

    # Fall through to best available fallback
    if top is None:
        if fallback_inpatient:
            top, pathway = fallback_inpatient
        elif fallback_opd:
            top, pathway = fallback_opd
        else:
            top = conditions[0]
            icd10 = top.get("icd10")
            body_system = nlp.get("body_system")
            specialty_code, _ = get_specialty(icd10, body_system)
            pathway = select_procedures(
                specialty_code=specialty_code,
                condition_name=top["name"],
                icd10=icd10,
                severity=top.get("severity", "moderate"),
                body_system=body_system,
            )

    _emit(1, "done")

    if pathway.get("opd_only"):
        return {
            "status": "opd_only",
            "condition": top["name"],
            "confidence": int((top.get("confidence") or 0) * 100),
            "severity": top.get("severity", "mild"),
            "city": city,
            "message": "This condition is typically treated outpatient (OPD) and is not covered under AB-PMJAY hospitalization packages.",
            "disclaimer": "This is an estimate for planning purposes only. Not medical advice.",
        }

    # Layer 3 — Cost estimation
    _emit(2, "running")
    comorbidities = nlp.get("comorbidities") or []
    cost = calculate(pathway, city, comorbidities=comorbidities)
    _emit(2, "done")

    if cost.get("error"):
        # Should never happen after the cost_calculator fix, but handle defensively
        log.warning("  → cost error: %s", cost["error"])
        return {
            "status": "pricing_error",
            "error": cost["error"],
            "condition": top["name"],
        }

    # Layer 4 — Provider matching
    _emit(3, "running")
    providers = match(city, pathway.get("specialty_code") or "", cost)
    _emit(3, "done")

    # Estimated timeline (pre + hospital + recovery)
    estimated_timeline = {
        "hospital_stay_days": [pathway["los_low"], pathway["los_high"]],
        "recovery_days": [14, 21],  # HBP bundle includes 15 days post-discharge meds
        "total_episode_days": [pathway["los_low"] + 14, pathway["los_high"] + 21],
    }

    return {
        "status": "ok",
        "query": query,
        "condition": top["name"],
        "icd10": top.get("icd10"),
        "confidence": int((top.get("confidence") or 0) * 100),
        "severity": top.get("severity", "moderate"),
        "city": city,
        "city_tier": cost["city_tier"],
        "pathway": pathway["steps"],
        "cost": {
            "procedure": cost["procedure_base"],
            "stay": cost["hospital_stay_cost"],
            "medication": cost["medication_post_discharge"],
            "contingency": cost["contingency"],
            "total": cost["total_range"],
        },
        "per_procedure_costs": cost.get("per_procedure_costs", []),
        "estimated_timeline": estimated_timeline,
        "tier_costs": cost.get("tier_costs", {}),
        "assumptions": cost.get("assumptions", {}),
        "approximate_only": cost.get("approximate_only", False),
        "hospitals": providers["hospitals"],
        "other_conditions": [
            {
                "name": c["name"],
                "icd10": c.get("icd10"),
                "confidence": int((c.get("confidence") or 0) * 100),
            }
            for c in conditions[1:]
            if c.get("icd10") != top.get("icd10") and c.get("name") != top["name"]
        ],
        "comorbidities": comorbidities,
        "disclaimer": "This is an estimate for planning purposes only. Actual costs vary by hospital and individual case. This is not medical advice.",
    }


if __name__ == "__main__":
    tests = [
        "knee pain for 3 months, age 58, Nagpur, budget 2.5 lakhs",
        "chest pain sometimes, age 55, Mumbai",
        "fever and cold for 2 days",
        "knee pain and internal bleeding, Mumbai, budget 10 lakhs",
        "stroke symptoms, Hyderabad",
        # Edge cases
        "severe depression, suicidal thoughts, Kolkata",          # psychiatric — no HBP codes
        "diabetic foot ulcer, age 60, Lucknow, budget 80000",    # multi-comorbidity, urology/surgery
        "routine eye checkup, age 45, Jaipur",                   # OPD exclusion
        "kidney stones with severe pain, age 35, Bhopal",        # urology inpatient
        "dizziness and blurred vision sometimes, age 70",        # vague, no city → clarification
    ]
    for q in tests:
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        print("="*60)
        result = run(q)
        print(json.dumps(result, indent=2, default=str))
