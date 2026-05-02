import { useState } from 'react'
import { ChevronDown, ChevronUp, Info } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

function fmt(n) { return `₹${n.toLocaleString('en-IN')}` }

const ROWS = [
  { key: 'procedure',   label: 'Procedure Base',         color: '#3B82F6' },
  { key: 'stay',        label: 'Hospital Stay (3–5 days)', color: '#8B5CF6' },
  { key: 'medication',  label: 'Medications (15 days)',   color: '#0D9488' },
  { key: 'contingency', label: 'Contingency (9%)',        color: '#64748B' },
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl px-4 py-3 text-sm" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
      <p className="text-slate-300 font-semibold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>{p.name}: {fmt(p.value)}</p>
      ))}
    </div>
  )
}

export default function TabCost({ result }) {
  const [tier, setTier] = useState(result.city_tier)
  const [assExpanded, setAssExpanded] = useState(false)

  const cost = result.tier_costs?.[tier] || result.tier_costs?.[result.city_tier] || result.cost

  const chartData = ROWS.map(r => ({
    name: r.label.replace(' (3–5 days)', '').replace(' (15 days)', '').replace(' (9%)', ''),
    low: cost[r.key][0],
    high: cost[r.key][1],
    color: r.color,
  }))

  const pcts = ROWS.map(r => ((cost[r.key][1] / cost.total[1]) * 100).toFixed(1))

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-white font-bold text-lg">Cost Breakdown</h3>
          <p className="text-slate-500 text-sm mt-0.5">Itemized estimate by component</p>
        </div>

        {/* Tier toggle */}
        <div className="flex gap-1 p-1 rounded-xl" style={{ background: '#111C30', border: '1px solid #1E2D45' }}>
          {[1, 2, 3].map(t => (
            <button key={t} onClick={() => setTier(t)}
              className={`px-4 py-1.5 rounded-lg text-[13px] font-semibold transition-all ${t === tier ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-300'}`}>
              T{t}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="rounded-2xl p-5 mb-5" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
        <p className="text-[11px] text-slate-500 uppercase tracking-widest font-semibold mb-4">Low vs High Estimate</p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} layout="vertical" barCategoryGap="30%">
            <CartesianGrid horizontal={false} stroke="#1E2D45" />
            <XAxis type="number" tickFormatter={v => `₹${(v/1000).toFixed(0)}k`}
              tick={{ fill: '#475569', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" width={110}
              tick={{ fill: '#94A3B8', fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#FFFFFF08' }} />
            <Bar dataKey="low" name="Low" radius={[0, 4, 4, 0]} opacity={0.5}>
              {chartData.map((d, i) => <Cell key={i} fill={d.color} />)}
            </Bar>
            <Bar dataKey="high" name="High" radius={[0, 4, 4, 0]}>
              {chartData.map((d, i) => <Cell key={i} fill={d.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Table */}
      <div className="rounded-2xl overflow-hidden mb-5" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid #1E2D45' }}>
              <th className="text-left text-[11px] text-slate-500 uppercase tracking-wider font-semibold py-3 px-5">Component</th>
              <th className="text-right text-[11px] text-slate-500 uppercase tracking-wider font-semibold py-3 px-4">Low</th>
              <th className="text-right text-[11px] text-slate-500 uppercase tracking-wider font-semibold py-3 px-4">High</th>
              <th className="text-right text-[11px] text-slate-500 uppercase tracking-wider font-semibold py-3 px-5">Share</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r, i) => (
              <tr key={r.key} className="hover:bg-[#111C30] transition-colors" style={{ borderBottom: i < ROWS.length - 1 ? '1px solid #1E2D4540' : 'none' }}>
                <td className="py-3 px-5 flex items-center gap-2.5">
                  <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: r.color }} />
                  <span className="text-slate-300">{r.label}</span>
                </td>
                <td className="py-3 px-4 text-right text-slate-400 font-mono text-[13px]">{fmt(cost[r.key][0])}</td>
                <td className="py-3 px-4 text-right text-slate-300 font-mono text-[13px]">{fmt(cost[r.key][1])}</td>
                <td className="py-3 px-5 text-right text-slate-500 text-[12px]">{pcts[i]}%</td>
              </tr>
            ))}
            {/* Total row */}
            <tr style={{ borderTop: '1px solid #1E2D45', background: '#111C30' }}>
              <td className="py-4 px-5 text-white font-bold">Total</td>
              <td className="py-4 px-4 text-right text-white font-bold font-mono">{fmt(cost.total[0])}</td>
              <td className="py-4 px-4 text-right text-white font-bold font-mono">{fmt(cost.total[1])}</td>
              <td className="py-4 px-5 text-right text-slate-500 text-[12px]">100%</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        <div className="rounded-xl p-4" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
          <div className="flex items-center gap-1.5 mb-1">
            <Info size={12} className="text-blue-400" />
            <span className="text-[11px] text-slate-500">Rate source</span>
          </div>
          <p className="text-slate-300 text-[13px] font-medium">HBP 2022 · Tier {tier} (YZX) rates</p>
        </div>
        <div className="rounded-xl p-4" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
          <div className="flex items-center gap-1.5 mb-1">
            <Info size={12} className="text-teal-400" />
            <span className="text-[11px] text-slate-500">Bed rate</span>
          </div>
          <p className="text-slate-300 text-[13px] font-medium">₹2,300/day · Routine Ward</p>
        </div>
      </div>

      {/* Assumptions accordion */}
      <div className="rounded-2xl overflow-hidden" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
        <button onClick={() => setAssExpanded(e => !e)}
          className="w-full flex items-center justify-between px-5 py-4 text-slate-400 hover:text-slate-200 transition-colors text-[13px] font-medium">
          View pricing assumptions
          {assExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
        {assExpanded && (
          <div className="px-5 pb-5 space-y-2 border-t border-[#1E2D45] pt-4">
            {Object.entries(result.assumptions).map(([k, v]) => (
              <div key={k} className="flex gap-3 text-[12px]">
                <span className="w-2 h-2 rounded-full bg-slate-600 shrink-0 mt-1.5" />
                <span className="text-slate-400">{v}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
