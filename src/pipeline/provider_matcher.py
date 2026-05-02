import json
from src.utils.db_connect import get_connection

SPECIALTY_KEYWORDS = {
    "MC":   ["cardiology", "cardiac", "heart", "ctvs"],
    "SB":   ["orthopaedic", "orthopedic", "bone", "joint", "spine"],
    "MG":   ["general medicine", "internal medicine", "medicine"],
    "SU":   ["surgery", "general surgery"],
    "NS":   ["neurology", "neurosurgery", "neuro"],
    "OB":   ["obstetrics", "gynaecology", "gynecology", "maternity"],
    "OP":   ["ophthalmology", "eye"],
    "OT":   ["oncology", "cancer"],
    "PD":   ["paediatrics", "pediatrics", "child"],
    "URO":  ["urology", "kidney", "nephrology"],
}


def _score_hospital(h: dict) -> float:
    score = 0.0
    if h["nabh_accredited"]:
        score += 0.25
    if h["google_rating"]:
        score += (h["google_rating"] / 5.0) * 0.35
    else:
        score += 0.15  # neutral placeholder when no rating
    if h["emergency_services"]:
        score += 0.10
    beds = h["total_beds"] or 0
    score += min(beds / 500, 1.0) * 0.15
    type_scores = {"government": 0.15, "mid_private": 0.15, "corporate": 0.05}
    score += type_scores.get(h["hospital_type"] or "", 0.0)
    return round(score, 3)


def _get_multiplier(hospital_type: str) -> tuple:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT multiplier_low, multiplier_high FROM dbo.hospital_type_multipliers WHERE hospital_type = ?",
        (hospital_type,),
    )
    row = cursor.fetchone()
    conn.close()
    return (row[0], row[1]) if row else (1.0, 1.0)


def match(city: str, specialty_code: str, base_cost: dict, top_n: int = 5) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    keywords = SPECIALTY_KEYWORDS.get(specialty_code, [])
    city_lower = city.lower()

    base_query = """
        SELECT TOP 30
            hospital_id, hospital_name, hospital_type, nabh_accredited,
            google_rating, total_beds, emergency_services, address,
            district, state, specialties, discipline, telephone,
            latitude, longitude, website, mobile, pincode
        FROM dbo.hospitals
        WHERE (LOWER(district) LIKE ? OR LOWER(location) LIKE ? OR LOWER(address) LIKE ?)
          AND hospital_type IS NOT NULL
          AND care_type NOT IN ('Clinic', 'Dispensary')
    """
    params = [f"%{city_lower}%", f"%{city_lower}%", f"%{city_lower}%"]

    if keywords:
        kw_filter = " OR ".join(["LOWER(specialties) LIKE ?" for _ in keywords])
        base_query += f" AND ({kw_filter})"
        params += [f"%{kw}%" for kw in keywords]

    cursor.execute(base_query, params)
    cols = [c[0] for c in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

    # Fallback: no specialty match — return all hospitals in city
    if not rows:
        cursor.execute("""
            SELECT TOP 20
                hospital_id, hospital_name, hospital_type, nabh_accredited,
                google_rating, total_beds, emergency_services, address,
                district, state, specialties, discipline, telephone,
                latitude, longitude, website, mobile, pincode
            FROM dbo.hospitals
            WHERE (LOWER(district) LIKE ? OR LOWER(location) LIKE ? OR LOWER(address) LIKE ?)
              AND hospital_type IS NOT NULL
              AND care_type NOT IN ('Clinic', 'Dispensary')
        """, [f"%{city_lower}%", f"%{city_lower}%", f"%{city_lower}%"])
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

    conn.close()

    if not rows:
        return {"city": city, "hospitals": [], "note": "No hospitals found for this city"}

    # Score and sort
    for h in rows:
        h["score"] = _score_hospital(h)
    rows.sort(key=lambda x: x["score"], reverse=True)
    top = rows[:top_n]

    base_low = base_cost.get("total_range", [0, 0])[0]
    base_high = base_cost.get("total_range", [0, 0])[1]

    for h in top:
        mult_low, mult_high = _get_multiplier(h["hospital_type"])
        h["multiplier_low"] = mult_low
        h["multiplier_high"] = mult_high
        h["adjusted_total_low"] = int(base_low * mult_low)
        h["adjusted_total_high"] = int(base_high * mult_high)
        # Rename for frontend compatibility
        h["name"] = h.pop("hospital_name")
        h["rating_google"] = h.pop("google_rating")
        h["nabh"] = bool(h.pop("nabh_accredited"))
        h["emergency"] = bool(h.pop("emergency_services"))
        h["beds"] = h.pop("total_beds")
        h["range"] = [h["adjusted_total_low"], h["adjusted_total_high"]]

    return {"city": city, "hospitals": top}


if __name__ == "__main__":
    from src.pipeline.pathway_mapper import map_pathway
    from src.pipeline.cost_calculator import calculate
    pathway = map_pathway("Coronary Artery Disease", "moderate")
    cost = calculate(pathway, "Nagpur")
    result = match("Nagpur", "MC", cost)
    print(json.dumps(result, indent=2, default=str))
