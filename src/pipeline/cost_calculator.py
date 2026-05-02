import json
from src.utils.db_connect import get_connection

BED_RATES = {
    "routine_ward": 2300,
    "hdu": 3630,
    "icu": 9350,
    "icu_ventilator": 9900,
}

TIER_COLUMNS = {1: "tier1_inr", 2: "tier2_inr", 3: "tier3_inr"}

NABH_MULTIPLIERS = {"none": 1.0, "entry": 1.10, "full": 1.15}

HOSPITAL_TYPE_MULTIPLIERS = {
    "government":  (1.0, 1.0),
    "mid_private": (1.5, 2.0),
    "corporate":   (2.5, 3.5),
}


def get_city_tier(city: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT tier FROM dbo.city_tier_map WHERE LOWER(city_name) LIKE ?",
        (f"%{city.lower()}%",),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 3  # default Tier 3


def _get_procedure_prices(procedure_codes: list, tier_col: str) -> list:
    """Returns prices in descending order (highest first, for stacking rule)."""
    if not procedure_codes:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["?" for _ in procedure_codes])
    cursor.execute(
        f"SELECT {tier_col} FROM dbo.procedures "
        f"WHERE procedure_code IN ({placeholders}) AND {tier_col} IS NOT NULL "
        f"ORDER BY {tier_col} DESC",
        procedure_codes,
    )
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def _apply_stacking(prices: list) -> int:
    """HBP multi-procedure rule: P1=100%, P2=50%, P3+=25%"""
    if not prices:
        return 0
    total = prices[0]
    if len(prices) > 1:
        total += prices[1] * 0.5
    for p in prices[2:]:
        total += p * 0.25
    return int(total)


_COMORBIDITY_CONTINGENCY = {
    "diabetes":       0.05,
    "diabetic":       0.05,
    "hypertension":   0.03,
    "heart disease":  0.08,
    "cardiac":        0.08,
    "kidney disease": 0.05,
    "renal":          0.05,
    "copd":           0.04,
    "asthma":         0.03,
    "cancer":         0.07,
    "obesity":        0.03,
}


def _comorbidity_bump(comorbidities: list) -> tuple[float, list]:
    """Returns (total_extra_contingency_rate, list_of_reasons)."""
    if not comorbidities:
        return 0.0, []
    bump = 0.0
    reasons = []
    for c in comorbidities:
        c_lower = c.lower()
        for keyword, rate in _COMORBIDITY_CONTINGENCY.items():
            if keyword in c_lower:
                bump += rate
                reasons.append(f"{c} (+{int(rate*100)}% contingency)")
                break
    return min(bump, 0.20), reasons  # cap at 20% extra


def calculate(pathway: dict, city: str, nabh_level: str = "none", comorbidities: list = None) -> dict:
    if pathway.get("opd_only"):
        return {"error": "no_pricing", "opd_only": True, "city": city}

    tier = get_city_tier(city)
    tier_col = TIER_COLUMNS[tier]

    # Procedure cost (government base, stacking applied)
    prices = _get_procedure_prices(pathway["all_procedure_codes"], tier_col)
    if not prices:
        # No procedure codes available — estimate from bed-day cost only (medical management)
        # Use specialty average as a rough proxy: ~₹15,000 base for surgical, ₹5,000 for medical
        specialty = pathway.get("specialty_code", "MG")
        _default_proc = 15000 if specialty in ("SU", "NS", "URO", "SB", "MC") else 5000
        proc_low = int(_default_proc * NABH_MULTIPLIERS.get(nabh_level, 1.0))
        proc_high = int(proc_low * 1.135)
        _no_procedure_data = True
    else:
        proc_base = _apply_stacking(prices)
        proc_low = int(proc_base * NABH_MULTIPLIERS.get(nabh_level, 1.0))
        proc_high = int(proc_low * 1.135)  # ~13.5% high-end buffer
        _no_procedure_data = False

    # Stay cost
    bed_rate = BED_RATES.get(pathway["bed_category"], 2300)
    stay_low = bed_rate * pathway["los_low"]
    stay_high = bed_rate * pathway["los_high"]

    # Medications: 8–12% of procedure base (IRDAI benchmark)
    med_low = int(proc_low * 0.08)
    med_high = int(proc_high * 0.12)

    # Subtotal → contingency at 9% + comorbidity bump
    co_bump, co_reasons = _comorbidity_bump(comorbidities or [])
    cont_rate = 0.09 + co_bump
    sub_low = proc_low + stay_low + med_low
    sub_high = proc_high + stay_high + med_high
    cont_low = int(sub_low * cont_rate)
    cont_high = int(sub_high * cont_rate)

    # Per-procedure cost breakdown (uses procedure_details from procedure_selector if available)
    per_procedure_costs = []
    stacking_mults = [1.0, 0.5]  # P1=100%, P2=50%, P3+=25%
    proc_details = pathway.get("procedure_details", [])
    for i, code in enumerate(pathway.get("all_procedure_codes", [])):
        mult = stacking_mults[i] if i < len(stacking_mults) else 0.25
        detail = next((d for d in proc_details if d.get("code") == code), None)
        base_price = (detail.get(tier_col) if detail else None) or 0
        per_procedure_costs.append({
            "code": code,
            "name": detail.get("name", code) if detail else code,
            "base_price": base_price,
            "stacking_multiplier": mult,
            "applied_cost": int(base_price * mult),
        })

    # tier_costs: compute all three tiers for the frontend comparison view
    tier_costs = {}
    for t in [1, 2, 3]:
        t_col = TIER_COLUMNS[t]
        t_prices = _get_procedure_prices(pathway["all_procedure_codes"], t_col)
        t_proc = int(_apply_stacking(t_prices) * NABH_MULTIPLIERS.get(nabh_level, 1.0)) if t_prices else proc_low
        t_proc_h = int(t_proc * 1.135)
        t_stay_l = bed_rate * pathway["los_low"]
        t_stay_h = bed_rate * pathway["los_high"]
        t_med_l = int(t_proc * 0.08)
        t_med_h = int(t_proc_h * 0.12)
        t_sub_l = t_proc + t_stay_l + t_med_l
        t_sub_h = t_proc_h + t_stay_h + t_med_h
        t_cont_l = int(t_sub_l * 0.09)
        t_cont_h = int(t_sub_h * 0.09)
        tier_costs[t] = {
            "procedure": [t_proc, t_proc_h],
            "stay": [t_stay_l, t_stay_h],
            "medication": [t_med_l, t_med_h],
            "contingency": [t_cont_l, t_cont_h],
            "total": [t_sub_l + t_cont_l, t_sub_h + t_cont_h],
        }

    return {
        "city": city,
        "city_tier": tier,
        "tier_column": tier_col,
        "procedure_base": [proc_low, proc_high],
        "per_procedure_costs": per_procedure_costs,
        "hospital_stay_days": [pathway["los_low"], pathway["los_high"]],
        "hospital_stay_cost": [stay_low, stay_high],
        "medication_post_discharge": [med_low, med_high],
        "contingency": [cont_low, cont_high],
        "total_range": [sub_low + cont_low, sub_high + cont_high],
        "bed_rate_used": bed_rate,
        "bed_category": pathway["bed_category"],
        "stacking_applied": len(pathway.get("all_procedure_codes", [])) > 1,
        "nabh_multiplier": NABH_MULTIPLIERS.get(nabh_level, 1.0),
        "approximate_only": _no_procedure_data,
        "tier_costs": tier_costs,
        "assumptions": {
            "stacking": "Multi-procedure rule: P1=100%, P2=50%, P3+=25%" if len(pathway.get("all_procedure_codes", [])) > 1 else ("Specialty average — no specific HBP procedure code available" if _no_procedure_data else "Single procedure"),
            "hospital_type": "Government (1.0× multiplier — base estimate)",
            "nabh": f"{nabh_level} ({NABH_MULTIPLIERS.get(nabh_level, 1.0)}×)",
            "los": f"{pathway['los_low']}–{pathway['los_high']} days, {pathway['bed_category'].replace('_', ' ').title()}",
            "meds": "8–12% of procedure base (IRDAI benchmark)",
            "contingency": f"{int(cont_rate*100)}% of subtotal" + (f" — raised for: {', '.join(co_reasons)}" if co_reasons else ""),
            "bed_rate": f"₹{bed_rate:,}/day · {pathway['bed_category'].replace('_', ' ').title()} (HBP 2022)",
        },
    }


if __name__ == "__main__":
    from src.pipeline.pathway_mapper import map_pathway
    pathway = map_pathway("Coronary Artery Disease", "moderate")
    result = calculate(pathway, "Nagpur")
    print(json.dumps(result, indent=2, default=str))
