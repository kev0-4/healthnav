const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

export async function fetchOsrmDistances(userLat, userLng, hospitals) {
  const valid = hospitals
    .map((h, i) => ({
      id: h.hospital_id ?? i,
      lat: parseFloat(h.latitude),
      lng: parseFloat(h.longitude),
    }))
    .filter(x => !isNaN(x.lat) && !isNaN(x.lng) && x.lat !== 0 && x.lng !== 0)

  if (!valid.length) return {}

  const coords = [
    `${userLng},${userLat}`,
    ...valid.map(x => `${x.lng},${x.lat}`),
  ].join(';')

  const url =
    `https://router.project-osrm.org/table/v1/driving/${coords}` +
    `?sources=0&annotations=duration,distance`

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 8000)

  try {
    const res = await fetch(url, { signal: controller.signal })
    clearTimeout(timer)
    if (!res.ok) return {}
    const data = await res.json()
    if (data.code !== 'Ok') return {}

    const durations = data.durations?.[0] ?? []
    const distances = data.distances?.[0] ?? []

    const out = {}
    valid.forEach((x, j) => {
      const secs   = durations[j + 1]   // +1 because index 0 = user→user = 0
      const meters = distances[j + 1]
      out[x.id] = {
        dist_km:     meters != null ? parseFloat((meters / 1000).toFixed(1)) : null,
        travel_mins: secs   != null ? Math.round(secs / 60)                  : null,
      }
    })
    return out
  } catch {
    clearTimeout(timer)
    return {}
  }
}

export async function fetchHospitalReviews(hospitalId, name, address) {
  const params = new URLSearchParams({ name: name || '', address: address || '' })
  try {
    const res = await fetch(`${BASE_URL}/hospital/${encodeURIComponent(hospitalId)}/reviews?${params}`)
    if (!res.ok) return { reviews: [], rating: null, total_ratings: null }
    return res.json()
  } catch {
    return { reviews: [], rating: null, total_ratings: null }
  }
}

export async function chat(question, result) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      result_context: {
        condition:            result.condition,
        icd10:                result.icd10,
        confidence:           result.confidence,
        severity:             result.severity,
        city:                 result.city,
        city_tier:            result.city_tier,
        cost:                 result.cost,
        per_procedure_costs:  result.per_procedure_costs || [],
        pathway:              (result.pathway || []).map(s => ({
          step:           s.step,
          type:           s.type,
          title:          s.title,
          procedure_code: s.procedure_code,
          cost:           s.cost,
        })),
      },
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Chat error: ${res.status}`)
  }
  const data = await res.json()
  return data.answer
}

export async function analyzeStream(query, city, budget, onProgress) {
  const res = await fetch(`${BASE_URL}/analyze-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      city: city || null,
      budget_inr: parseBudget(budget),
    }),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split("\n\n")
    buffer = parts.pop() ?? ""

    for (const part of parts) {
      if (!part.startsWith("data: ")) continue
      let event
      try { event = JSON.parse(part.slice(6)) } catch { continue }

      if (event.error) throw new Error(event.error)
      onProgress(event)
      if (event.done && event.result) {
        reader.cancel()
        return normalizeResult(event.result)
      }
    }
  }
  throw new Error("Stream ended without a result")
}

// Keep non-streaming version for fallback / direct use
export async function analyze(query, city, budget) {
  const res = await fetch(`${BASE_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      city: city || null,
      budget_inr: parseBudget(budget),
    }),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  const data = await res.json()
  return normalizeResult(data)
}

function parseBudget(budgetStr) {
  if (!budgetStr) return null
  const map = {
    "Under 50K": 50000,
    "50K – 1L": 100000,
    "1L – 3L": 300000,
    "3L – 5L": 500000,
    "5L – 10L": 1000000,
    "10L+": null,
  }
  return map[budgetStr] || null
}

const TYPE_MAP = {
  consultation: "CONSULTATION",
  diagnostic:   "INVESTIGATION",
  procedure:    "PROCEDURE",
  medication:   "FOLLOW-UP",
  followup:     "FOLLOW-UP",
  stay:         "STAY",
}

// Map API response shape → frontend component shape
function normalizeResult(data) {
  if (data.status !== "ok") return data

  // Build code → per_procedure_cost entry for step cost lookup
  const ppcByCode = Object.fromEntries(
    (data.per_procedure_costs || []).map(p => [p.code, p])
  )

  return {
    ...data,
    pathway: (data.pathway || []).map((s, i) => {
      const hbp = s.procedure_code ? ppcByCode[s.procedure_code] : null
      return {
        step:                s.step_order ?? i + 1,
        type:                TYPE_MAP[s.step_type?.toLowerCase()] || "PROCEDURE",
        title:               s.step_description || s.step_type || "Step",
        desc:                s.notes || "",
        covered:             !!s.hbp_covered,
        // Procedure steps get the real HBP cost range; others are bundled (shown as 0,0)
        cost:                hbp ? [hbp.applied_cost, Math.round(hbp.applied_cost * 1.135)] : [0, 0],
        note:                null,
        procedure_code:      s.procedure_code || null,
        stacking_multiplier: hbp?.stacking_multiplier ?? null,
      }
    }),
    cost: data.cost,
    tier_costs: data.tier_costs
      ? Object.fromEntries(
          Object.entries(data.tier_costs).map(([k, v]) => [parseInt(k), v])
        )
      : {},
    hospitals: (data.hospitals || []).map(h => ({
      ...h,
      rating_google: h.rating_google || null,
      rating_practo: h.practo_rating || null,
      mult: h.multiplier_low || 1.0,
      dist: h.distance_km || null,
      nabh_level: h.nabh ? "Entry Level" : null,
    })),
    other_conditions: data.other_conditions || [],
    assumptions: data.assumptions || {},
    state: null,
    budget: null,
  }
}
