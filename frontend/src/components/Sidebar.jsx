import { useState } from 'react'
import { MapPin, ChevronDown, ChevronUp, Shield, AlertCircle, Edit2 } from 'lucide-react'

function ConfidenceRing({ value }) {
  const r = 38
  const circ = 2 * Math.PI * r
  const dash = (value / 100) * circ
  const color = value >= 75 ? '#16A34A' : value >= 60 ? '#D97706' : '#DC2626'
  return (
    <div className="relative flex items-center justify-center w-[88px] h-[88px] shrink-0">
      <svg width="88" height="88" className="-rotate-90">
        <circle cx="44" cy="44" r={r} fill="none" stroke="#1E2D45" strokeWidth="7" />
        <circle cx="44" cy="44" r={r} fill="none" stroke={color} strokeWidth="7"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      </svg>
      <div className="absolute flex flex-col items-center leading-none">
        <span className="text-[20px] font-bold text-white">{value}%</span>
        <span className="text-[10px] text-slate-500 mt-0.5">match</span>
      </div>
    </div>
  )
}

function SeverityBadge({ severity }) {
  const cfg = {
    mild:     { dot: 'bg-green-500',  bg: 'bg-green-950',  text: 'text-green-300',  border: 'border-green-800' },
    moderate: { dot: 'bg-amber-400',  bg: 'bg-amber-950',  text: 'text-amber-300',  border: 'border-amber-800' },
    severe:   { dot: 'bg-red-500',    bg: 'bg-red-950',    text: 'text-red-300',    border: 'border-red-800' },
  }
  const c = cfg[severity] || cfg.moderate
  return (
    <span className={`inline-flex items-center gap-1.5 ${c.bg} border ${c.border} ${c.text} text-[11px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {severity}
    </span>
  )
}

function fmt(n) { return `₹${n.toLocaleString('en-IN')}` }

const SEGMENT_COLORS = ['bg-blue-500', 'bg-violet-500', 'bg-teal-500', 'bg-slate-600']
const SEGMENT_LABELS = ['Procedure', 'Stay', 'Meds', 'Contingency']

function EligibilityBanner({ income }) {
  if (!income || income === 'Above ₹10 lakh') return null
  const eligible = income !== 'Above ₹10 lakh'
  return (
    <div className="rounded-2xl p-4" style={{ background: '#052E16', border: '1px solid #166534' }}>
      <p className="text-[10px] text-green-400 uppercase tracking-widest font-semibold mb-2">AB-PMJAY Eligibility</p>
      <p className="text-green-300 text-[13px] font-semibold mb-1">Likely eligible for free treatment</p>
      <p className="text-green-600 text-[12px] leading-relaxed">
        Annual income {income} may qualify for Ayushman Bharat PMJAY — ₹5 lakh/year cashless cover at empanelled hospitals.
      </p>
      <a href="https://pmjay.gov.in" target="_blank" rel="noreferrer"
        className="inline-flex items-center gap-1 mt-2 text-[11px] text-green-400 hover:text-green-300 transition-colors">
        Check eligibility on pmjay.gov.in →
      </a>
    </div>
  )
}

export default function Sidebar({ result, onReset, income }) {
  const [expanded, setExpanded] = useState(false)
  const [selectedTier, setSelectedTier] = useState(result.city_tier)
  const { condition, icd10, confidence, severity, city, state, city_tier, other_conditions, query, budget } = result

  const tierCost = result.tier_costs?.[selectedTier] || result.cost
  const cost = tierCost

  const segments = [cost.procedure[1], cost.stay[1], cost.medication[1], cost.contingency[1]]
  const total = segments.reduce((a, b) => a + b, 0)

  return (
    <aside className="w-full md:w-[400px] shrink-0 md:h-[calc(100vh-60px)] md:sticky md:top-[60px] overflow-y-auto flex flex-col border-r border-[#1E2D45]"
      style={{ background: '#070B14' }}>
      <div className="flex-1 p-4 space-y-3">

        {/* Query Summary */}
        <div className="rounded-2xl p-4" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-2">Your Query</p>
          <p className="text-slate-300 text-sm italic leading-relaxed line-clamp-2">"{query}"</p>
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <span className="flex items-center gap-1 text-[11px] bg-[#111C30] border border-[#1E2D45] text-slate-400 px-2.5 py-1 rounded-full">
              <MapPin size={10} /> {city}
            </span>
            <span className="flex items-center gap-1 text-[11px] bg-[#111C30] border border-[#1E2D45] text-slate-400 px-2.5 py-1 rounded-full">
              💰 {budget}
            </span>
            <button onClick={onReset} className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 transition-colors ml-auto">
              <Edit2 size={10} /> Edit
            </button>
          </div>
        </div>

        {/* Condition Match */}
        <div className="rounded-2xl p-4" style={{ background: '#0D1525', borderLeft: '4px solid #2563EB', border: '1px solid #1E2D45', borderLeftWidth: '4px' }}>
          <div className="flex items-start gap-3 mb-3">
            <div className="flex-1 min-w-0">
              <span className="font-mono text-[11px] text-slate-500 mb-1 block">{icd10}</span>
              <h2 className="text-[17px] font-bold text-white leading-tight mb-2">{condition}</h2>
              <SeverityBadge severity={severity} />
            </div>
            <ConfidenceRing value={confidence} />
          </div>
          <p className="text-[11px] text-slate-500 mb-3">Top match from {other_conditions.length + 1} condition candidates</p>

          {/* Other possibilities */}
          <button
            onClick={() => setExpanded(e => !e)}
            className="flex items-center gap-1.5 text-[12px] text-slate-400 hover:text-slate-200 transition-colors w-full">
            Other possibilities {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {expanded && (
            <div className="mt-3 space-y-2">
              {other_conditions.map((c, i) => (
                <div key={i}>
                  <div className="flex justify-between text-[12px] mb-1">
                    <span className="text-slate-400">{c.name}</span>
                    <span className="text-slate-500 font-mono">{c.confidence}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[#111C30] overflow-hidden">
                    <div className="h-full rounded-full bg-slate-600" style={{ width: `${c.confidence}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Cost Summary */}
        <div className="rounded-2xl p-4" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-3">Total Estimate</p>
          <p className="text-[26px] font-bold text-white leading-none mb-1">
            {fmt(cost.total[0])} <span className="text-slate-500 text-[18px]">–</span> {fmt(cost.total[1])}
          </p>
          <p className="text-[11px] text-slate-500 mb-4">at Government hospital rates · Tier {selectedTier} pricing</p>

          {/* Stacked segment bar */}
          <div className="flex h-2 rounded-full overflow-hidden mb-3 gap-px">
            {segments.map((seg, i) => (
              <div key={i} className={`h-full ${SEGMENT_COLORS[i]}`} style={{ width: `${(seg / total) * 100}%` }} title={`${SEGMENT_LABELS[i]}: ₹${seg.toLocaleString('en-IN')}`} />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 mb-4">
            {SEGMENT_LABELS.map((l, i) => (
              <span key={i} className="flex items-center gap-1 text-[11px] text-slate-500">
                <span className={`w-2 h-2 rounded-sm ${SEGMENT_COLORS[i]}`} />{l}
              </span>
            ))}
          </div>

          {/* Line items */}
          <div className="space-y-2 border-t border-[#1E2D45] pt-3">
            {[
              ['Procedure base', cost.procedure],
              ['Hospital stay (3–5d)', cost.stay],
              ['Medications (15d)', cost.medication],
              ['Contingency', cost.contingency],
            ].map(([label, range], i) => (
              <div key={i} className="flex justify-between text-[12px]">
                <span className="text-slate-500">{label}</span>
                <span className="text-slate-300 font-medium">{fmt(range[0])} – {fmt(range[1])}</span>
              </div>
            ))}
          </div>
        </div>

        {/* City & Tier */}
        <div className="rounded-2xl p-4" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
          <div className="flex items-center gap-2 mb-3">
            <MapPin size={13} className="text-slate-500" />
            <span className="text-slate-300 text-sm font-medium">{city}{state ? ` · ${state}` : ''}</span>
          </div>
          <div className="flex justify-between text-[12px] mb-3">
            <span className="text-slate-500">Tier Classification</span>
            <span className="text-slate-300 font-semibold">Tier {selectedTier} ({['', 'X', 'Y', 'Z'][selectedTier]})</span>
          </div>
          <div className="flex gap-1.5 mb-2">
            {[1, 2, 3].map(t => (
              <button key={t} onClick={() => setSelectedTier(t)}
                className={`flex-1 rounded-lg py-1.5 text-center text-[11px] font-bold transition-all ${t === selectedTier ? 'bg-blue-600 text-white' : 'bg-[#111C30] text-slate-600 hover:text-slate-400'}`}>
                T{t}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-600">HBP rate column: tier{selectedTier}_inr</p>
        </div>
      </div>

        <EligibilityBanner income={income} />
      </div>

      {/* Disclaimer sticky bottom */}
      <div className="p-4 border-t border-[#1E2D45]">
        <div className="flex items-start gap-2">
          <AlertCircle size={12} className="text-slate-600 shrink-0 mt-0.5" />
          <p className="text-[10px] text-slate-600 italic leading-relaxed">
            Estimate only. Not medical advice. Costs vary by hospital and case. Consult a qualified physician before making any decisions.
          </p>
        </div>
      </div>
    </aside>
  )
}
