"""
procedure_selector.py — Function-calling RAG procedure pathway builder.

Flow:
  1. LLM calls search_hbp_procedures(keywords) tool to find relevant procedures
  2. Manual tool-call loop handles the back-and-forth
  3. LLM returns pathway JSON using only found procedures
     — if nothing relevant found, returns empty codes (correct for psych/OPD/novel conditions)

Fallback chain (never raises):
  LLM OK       → structured pathway from LLM with correctly matched codes
  LLM fails    → deterministic per-specialty fallback (hardcoded codes)
  Fallback empty   → bed-day-only stub (always succeeds, always inpatient)
"""
import json
import logging
import os
import openai
from dotenv import load_dotenv
from src.utils.db_connect import get_connection

load_dotenv()
log = logging.getLogger("procedure_selector")

_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_MODELS = ["gpt-4o-mini"]

_TOOL_SCHEMA = [{
    "type": "function",
    "function": {
        "name": "search_hbp_procedures",
        "description": (
            "Search the HBP 2022 procedure database for procedures matching clinical keywords. "
            "Returns a JSON array of matching procedures with code, name, and tier2 price."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": (
                        "Space or comma-separated clinical terms to search for. "
                        "Examples: 'PTCA angioplasty coronary' or 'nephrostomy kidney stone calculi'"
                    ),
                }
            },
            "required": ["keywords"],
        },
    },
}]

def _chat_create(**kwargs):
    """Wrapper that retries with max_completion_tokens if model rejects max_tokens."""
    create = _client.chat.completions.create
    try:
        return create(**kwargs)
    except openai.BadRequestError as e:
        if "max_tokens" in str(e) and "max_completion_tokens" in str(e):
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            return create(**kwargs)
        raise


_SEVERITY_DEFAULTS = {
    "mild":     {"bed": "routine_ward", "los": (1, 3)},
    "moderate": {"bed": "routine_ward", "los": (3, 5)},
    "severe":   {"bed": "icu",          "los": (5, 10)},
}

# Hardcoded fallback codes when LLM/AFC fails entirely
_SPECIALTY_FALLBACK = {
    "MC":  {"mild": ["MC001A"],   "moderate": ["MC011A", "MC017A"],       "severe": ["MC011A", "MC017A", "MC020A"]},
    "SB":  {"mild": ["SB036A"],   "moderate": ["SB036A"],                 "severe": ["SB039A"]},
    "MG":  {"mild": None,         "moderate": [],                          "severe": []},
    "SU":  {"mild": [],           "moderate": [],                          "severe": []},
    "NS":  {"mild": [],           "moderate": [],                          "severe": []},
    "URO": {"mild": [],           "moderate": [],                          "severe": []},
    "ID":  {"mild": None,         "moderate": [],                          "severe": []},
    "OT":  {"mild": [],           "moderate": [],                          "severe": []},
    "OB":  {"mild": [],           "moderate": [],                          "severe": []},
    "OP":  {"mild": [],           "moderate": [],                          "severe": []},
    "ENT": {"mild": [],           "moderate": [],                          "severe": []},
    "BM":  {"mild": [],           "moderate": [],                          "severe": []},
    "ER":  {"mild": [],           "moderate": [],                          "severe": []},
}

_SELECTOR_SYSTEM = """
You are a clinical pathway planner for India's AB-PMJAY (Ayushman Bharat) healthcare scheme.

You have the search_hbp_procedures tool to search the HBP 2022 procedure database.

## Workflow
1. Call search_hbp_procedures 2–4 times using different clinical keywords for the condition
   (e.g., "PTCA angioplasty stent" then "coronary bypass graft" then "cardiac catheter")
2. From all search results combined, select ONLY procedures directly relevant to this condition
3. Return the pathway JSON

## Critical selection rules
- A procedure is relevant ONLY if it would realistically be performed for this exact condition
- Do NOT select a procedure just because it appeared in results or has a high price
- If no relevant procedures found after 2–4 searches: return selected_procedure_codes: []
- Mental health / psychiatric conditions (depression, anxiety, schizophrenia): almost certainly no HBP procedure codes — return []
- Mild infections, cold, flu, OPD conditions: return opd_only: true, selected_procedure_codes: []

## Output format
Return ONLY valid JSON after all searches — no markdown, no code fences, no explanation.

{
  "selected_procedure_codes": [<string>, ...],
  "bed_category": <"routine_ward"|"hdu"|"icu"|"icu_ventilator">,
  "los_low": <integer, hospitalization days minimum>,
  "los_high": <integer, hospitalization days maximum>,
  "opd_only": <boolean>,
  "steps": [
    {
      "step_order": <integer 1-N>,
      "step_type": <"consultation"|"diagnostic"|"procedure"|"medication"|"followup">,
      "step_description": <string, concise clinical description>,
      "procedure_code": <string matching a selected code, or null>,
      "estimated_days": <integer>,
      "notes": <string or null>
    }
  ],
  "rationale": <string, 1 sentence>
}

## Additional rules
- selected_procedure_codes: order highest-to-lowest price (HBP stacking: P1=100%, P2=50%, P3+=25%)
- steps: 3–6 steps covering consultation → diagnostics → procedure → recovery → followup
- los_low/los_high: 0 if opd_only; mild: 1–3 days, moderate: 3–5 days, severe: 5–10 days
- bed_category: routine_ward for elective/mild, hdu for moderate, icu for severe/critical
""".strip()


def search_hbp_procedures(keywords: str) -> str:
    """Search the HBP 2022 procedure database for procedures matching clinical keywords.

    Args:
        keywords: Space or comma-separated clinical terms to search for.
                  Examples: "PTCA angioplasty coronary" or "nephrostomy kidney stone calculi"

    Returns:
        JSON array of matching procedures with code, name, and tier2 price.
    """
    terms = [k.strip() for k in keywords.replace(",", " ").split() if len(k.strip()) >= 3]
    if not terms:
        return "[]"

    results: dict[str, dict] = {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for term in terms[:6]:
            cursor.execute("""
                SELECT TOP 15
                    procedure_code, procedure_name,
                    tier1_inr, tier2_inr, tier3_inr
                FROM dbo.procedures
                WHERE procedure_name LIKE ?
                  AND tier2_inr IS NOT NULL
                ORDER BY tier2_inr DESC
            """, (f"%{term}%",))
            for row in cursor.fetchall():
                code = row[0]
                if code and code not in results:
                    results[code] = {
                        "code": code,
                        "name": row[1] or code,
                        "tier2_inr": row[3],
                    }
        conn.close()
    except Exception as e:
        log.warning("[selector] keyword search error: %s", e)
        return "[]"

    sorted_r = sorted(results.values(), key=lambda x: x.get("tier2_inr") or 0, reverse=True)
    log.info("[selector] search(%r) → %d results", keywords[:60], len(sorted_r))
    return json.dumps(sorted_r[:20])


def _get_procedure_details(codes: list[str]) -> list[dict]:
    """Fetch full price details for specific procedure codes, sorted by tier2 DESC."""
    if not codes:
        return []
    try:
        conn = get_connection()
        cursor = conn.cursor()
        placeholders = ",".join(["?" for _ in codes])
        cursor.execute(
            f"SELECT procedure_code, procedure_name, tier1_inr, tier2_inr, tier3_inr "
            f"FROM dbo.procedures "
            f"WHERE procedure_code IN ({placeholders}) "
            f"ORDER BY COALESCE(tier2_inr, 0) DESC",
            codes,
        )
        rows = cursor.fetchall()
        conn.close()
        found = {r[0]: {"code": r[0], "name": r[1] or r[0],
                        "tier1_inr": r[2], "tier2_inr": r[3], "tier3_inr": r[4]}
                 for r in rows}
        # Preserve price-sorted order; append any codes not found in DB
        result = [found[c] for c in codes if c in found]
        result += [{"code": c, "name": c, "tier1_inr": None, "tier2_inr": None, "tier3_inr": None}
                   for c in codes if c not in found]
        result.sort(key=lambda x: x.get("tier2_inr") or 0, reverse=True)
        return result
    except Exception as e:
        log.warning("[selector] procedure detail fetch failed: %s", e)
        return [{"code": c, "name": c, "tier1_inr": None, "tier2_inr": None, "tier3_inr": None}
                for c in codes]


def _call_llm_afc(condition_name: str, icd10: str | None,
                  severity: str, specialty_code: str,
                  query: str | None = None,
                  other_conditions: list | None = None) -> dict | None:
    """Call OpenAI with manual tool-call loop. Returns parsed pathway dict or None on failure."""
    context_parts = [
        f"Primary condition: {condition_name}",
        f"ICD-10: {icd10 or 'unknown'}",
        f"Severity: {severity}",
        f"Specialty: {specialty_code}",
    ]
    if query:
        context_parts.insert(0, f"Original query: {query}")
    if other_conditions:
        others = ", ".join(
            f"{c.get('name')} ({c.get('icd10', '?')})"
            for c in other_conditions[:3]
        )
        context_parts.append(f"Other identified conditions: {others}")
        context_parts.append(
            "If any of these co-conditions require inpatient procedures, "
            "include relevant procedure codes for them too."
        )
    context_parts.append("\nSearch for relevant HBP procedures using the tool, then return the pathway JSON.")
    context = "\n".join(context_parts)
    last_err = None
    for model in _MODELS:
        try:
            messages = [
                {"role": "system", "content": _SELECTOR_SYSTEM},
                {"role": "user",   "content": context},
            ]
            for _turn in range(6):  # max 5 tool turns + 1 final answer turn
                resp = _chat_create(
                    model=model,
                    messages=messages,
                    tools=_TOOL_SCHEMA,
                    tool_choice="auto",
                    temperature=1,
                    max_tokens=2048,
                )
                msg = resp.choices[0].message

                if not msg.tool_calls:
                    # Final answer turn
                    raw = (msg.content or "").strip()
                    if not raw:
                        log.info("[selector] %s: empty final response — no relevant procedures", model)
                        break  # try next model
                    if raw.startswith("```"):
                        lines = raw.split("\n")
                        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                    try:
                        result = json.loads(raw)
                    except json.JSONDecodeError:
                        log.info("[selector] %s: non-JSON final response", model)
                        break  # try next model
                    log.info("[selector] OpenAI (%s) → %d codes opd=%s",
                             model, len(result.get("selected_procedure_codes", [])),
                             result.get("opd_only"))
                    return result

                # Tool call turn — execute each tool and append results
                messages.append(msg)
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    tool_result = search_hbp_procedures(args.get("keywords", ""))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    })

            log.warning("[selector] %s: exceeded max tool turns", model)
            continue  # try next model

        except openai.RateLimitError as e:
            last_err = e
            log.warning("[selector] %s rate limited, trying next model", model)
            continue
        except openai.NotFoundError:
            log.info("[selector] %s not found, trying next model", model)
            continue
        except json.JSONDecodeError:
            log.info("[selector] %s: non-JSON tool args — trying next model", model)
            continue
        except Exception as e:
            last_err = e
            log.warning("[selector] %s unexpected error: %s", model, e)
            continue

    log.warning("[selector] all models exhausted: %s", last_err)
    return None


def _deterministic_pathway(specialty_code: str, severity: str) -> dict:
    """Hardcoded fallback when AFC fails — uses known-good procedure codes."""
    sev_cfg = _SEVERITY_DEFAULTS.get(severity, _SEVERITY_DEFAULTS["moderate"])
    procs = _SPECIALTY_FALLBACK.get(specialty_code, {})
    codes = procs.get(severity, procs.get("moderate", []))

    if codes is None:
        return {
            "selected_procedure_codes": [],
            "bed_category": "routine_ward",
            "los_low": 0, "los_high": 0,
            "opd_only": True,
            "steps": [{"step_order": 1, "step_type": "consultation",
                       "step_description": "OPD consultation and treatment",
                       "procedure_code": None, "estimated_days": 1, "notes": "Outpatient management"}],
            "rationale": "Mild condition — outpatient management.",
        }

    return {
        "selected_procedure_codes": codes or [],
        "bed_category": sev_cfg["bed"],
        "los_low": sev_cfg["los"][0], "los_high": sev_cfg["los"][1],
        "opd_only": False,
        "steps": [
            {"step_order": 1, "step_type": "consultation",
             "step_description": "Specialist consultation and clinical assessment",
             "procedure_code": None, "estimated_days": 1, "notes": None},
            {"step_order": 2, "step_type": "diagnostic",
             "step_description": "Pre-procedure investigations (blood tests, imaging)",
             "procedure_code": None, "estimated_days": 1, "notes": None},
            {"step_order": 3, "step_type": "procedure",
             "step_description": "Primary procedure / intervention",
             "procedure_code": codes[0] if codes else None,
             "estimated_days": sev_cfg["los"][0], "notes": None},
            {"step_order": 4, "step_type": "followup",
             "step_description": "Post-procedure monitoring and discharge planning",
             "procedure_code": None, "estimated_days": 1,
             "notes": "15-day post-discharge medicines included per HBP bundle"},
        ],
        "rationale": f"Deterministic fallback for {specialty_code}/{severity}.",
    }


def _stub_pathway(condition_name: str, severity: str) -> dict:
    """Final fallback: bed-day cost estimate with generic clinical steps."""
    sev_cfg = _SEVERITY_DEFAULTS.get(severity, _SEVERITY_DEFAULTS["moderate"])
    opd = sev_cfg["los"][0] == 0
    return {
        "selected_procedure_codes": [],
        "bed_category": sev_cfg["bed"],
        "los_low": sev_cfg["los"][0], "los_high": sev_cfg["los"][1],
        "opd_only": opd,
        "steps": [
            {"step_order": 1, "step_type": "consultation",
             "step_description": "Specialist consultation and assessment",
             "procedure_code": None, "estimated_days": 1, "notes": None},
            {"step_order": 2, "step_type": "diagnostic",
             "step_description": "Diagnostic investigations and monitoring",
             "procedure_code": None, "estimated_days": 1, "notes": None},
            {"step_order": 3, "step_type": "procedure",
             "step_description": f"Clinical management and treatment of {condition_name}",
             "procedure_code": None,
             "estimated_days": max(sev_cfg["los"][0], 1),
             "notes": "Cost estimated from bed-day rates — no specific HBP package mapped"},
            {"step_order": 4, "step_type": "followup",
             "step_description": "Discharge planning and outpatient follow-up",
             "procedure_code": None, "estimated_days": 1, "notes": None},
        ],
        "rationale": "No HBP procedure mapped — bed-day cost estimate only.",
    }


def select_procedures(
    specialty_code: str,
    condition_name: str,
    icd10: str | None,
    severity: str,
    body_system: str | None = None,
    query: str | None = None,
    other_conditions: list | None = None,
) -> dict:
    """
    Main entry point. Always returns a valid pathway dict — never raises.

    Returns dict compatible with cost_calculator.calculate():
      condition_name, specialty_code, severity,
      all_procedure_codes, primary_procedure_code,
      procedure_details (list with tier prices),
      bed_category, los_low, los_high, opd_only,
      steps, hbp_covered, approximate_only, llm_rationale
    """
    if severity not in ("mild", "moderate", "severe"):
        severity = "moderate"

    log.info("[selector] %s / %s / %s", condition_name, specialty_code, severity)

    # 1 — AFC: LLM searches DB and selects procedures
    raw = _call_llm_afc(condition_name, icd10, severity, specialty_code,
                        query=query, other_conditions=other_conditions)

    # 2 — Fallback chain
    if raw is None:
        raw = _deterministic_pathway(specialty_code, severity)
        log.info("[selector] deterministic fallback: %s", raw["selected_procedure_codes"])

    # If LLM ran but returned no codes, check if the condition warrants an inpatient stub
    # (e.g., stroke/urology — real inpatient but no DB codes)
    if not raw.get("selected_procedure_codes") and not raw.get("opd_only"):
        det = _deterministic_pathway(specialty_code, severity)
        if det.get("selected_procedure_codes"):
            # Deterministic has codes the LLM couldn't find via search — use them
            raw["selected_procedure_codes"] = det["selected_procedure_codes"]
            log.info("[selector] supplemented with deterministic codes: %s",
                     raw["selected_procedure_codes"])

    # 3 — Derive billing codes from pathway steps (ground truth)
    # selected_procedure_codes is discarded for billing — it's the LLM's scratch list
    # and may include codes not in any step (wrong) or miss step codes (also wrong).
    # Step codes are what the patient actually receives, so they drive cost.
    step_codes: list[str] = []
    seen_codes: set[str] = set()
    for s in raw.get("steps", []):
        c = s.get("procedure_code")
        if c and c not in seen_codes:
            step_codes.append(c)
            seen_codes.add(c)

    # Fallback: if LLM assigned no codes to steps (e.g. deterministic supplement),
    # use selected_procedure_codes so we don't silently drop the fallback codes.
    codes = step_codes or raw.get("selected_procedure_codes") or []
    proc_details = _get_procedure_details(codes) if codes else []

    # Sort by tier2 price DESC (stacking rule: P1=100%, P2=50%, P3+=25%)
    sorted_codes = [d["code"] for d in proc_details]
    for c in codes:
        if c not in sorted_codes:
            sorted_codes.append(c)

    has_real_codes = bool(sorted_codes)
    opd_only = raw.get("opd_only", False)

    # 4 — Normalize steps
    norm_steps = []
    for s in raw.get("steps", []):
        norm_steps.append({
            "step_order":       s.get("step_order", 0),
            "step_type":        s.get("step_type", "procedure"),
            "step_description": s.get("step_description", ""),
            "procedure_code":   s.get("procedure_code"),
            "bed_category":     raw.get("bed_category", "routine_ward"),
            "los_days_low":     raw.get("los_low", 3),
            "los_days_high":    raw.get("los_high", 5),
            "hbp_covered":      has_real_codes,
            "specialty_code":   specialty_code,
            "notes":            s.get("notes"),
            "estimated_days":   s.get("estimated_days"),
        })

    # Ensure we always have at least a stub if steps came back empty
    if not norm_steps:
        stub = _stub_pathway(condition_name, severity)
        for s in stub["steps"]:
            norm_steps.append({
                "step_order":       s["step_order"],
                "step_type":        s["step_type"],
                "step_description": s["step_description"],
                "procedure_code":   s.get("procedure_code"),
                "bed_category":     stub.get("bed_category", "routine_ward"),
                "los_days_low":     stub.get("los_low", 3),
                "los_days_high":    stub.get("los_high", 5),
                "hbp_covered":      has_real_codes,
                "specialty_code":   specialty_code,
                "notes":            s.get("notes"),
                "estimated_days":   s.get("estimated_days"),
            })

    return {
        "condition_name":         condition_name,
        "specialty_code":         specialty_code,
        "severity":               severity,
        "hbp_covered":            has_real_codes or (not opd_only and bool(norm_steps)),
        "opd_only":               opd_only,
        "steps":                  norm_steps,
        "primary_procedure_code": sorted_codes[0] if sorted_codes else None,
        "all_procedure_codes":    sorted_codes,
        "procedure_details":      proc_details,
        "bed_category":           raw.get("bed_category", "routine_ward"),
        "los_low":                raw.get("los_low", 3),
        "los_high":               raw.get("los_high", 5),
        "approximate_only":       not has_real_codes,
        "llm_rationale":          raw.get("rationale"),
    }


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(name)s — %(message)s")
    tests = [
        ("MC",  "Coronary Artery Disease",    "I25.1", "moderate"),
        ("SB",  "Osteoarthritis of knee",     "M17.1", "severe"),
        ("MG",  "Major Depressive Disorder",  "F32.2", "severe"),
        ("URO", "Kidney Stones",              "N20.0", "moderate"),
        ("NS",  "Ischemic stroke",            "I63.9", "severe"),
        ("MG",  "Fever",                      "R50.9", "mild"),
    ]
    for spec, cond, icd, sev in tests:
        print(f"\n{'─'*55}")
        print(f"{cond} / {spec} / {sev}")
        result = select_procedures(spec, cond, icd, sev)
        print(f"  codes={result['all_procedure_codes']}")
        print(f"  opd={result['opd_only']}  approx={result['approximate_only']}")
        print(f"  bed={result['bed_category']}  LOS={result['los_low']}–{result['los_high']}")
        print(f"  steps={len(result['steps'])}")
        if result.get("llm_rationale"):
            print(f"  rationale: {result['llm_rationale']}")
