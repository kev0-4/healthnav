import { CheckCircle, AlertTriangle } from 'lucide-react'

const TYPE_CFG = {
  CONSULTATION: { color: 'bg-blue-600',   text: 'text-blue-300',   dot: 'bg-blue-500' },
  INVESTIGATION: { color: 'bg-teal-700',  text: 'text-teal-300',   dot: 'bg-teal-500' },
  PROCEDURE:    { color: 'bg-violet-700', text: 'text-violet-300', dot: 'bg-violet-500' },
  STAY:         { color: 'bg-slate-700',  text: 'text-slate-300',  dot: 'bg-slate-400' },
  'FOLLOW-UP':  { color: 'bg-green-800',  text: 'text-green-300',  dot: 'bg-green-500' },
}

const STEP_ICONS = {
  CONSULTATION: '🩺',
  INVESTIGATION: '🔬',
  PROCEDURE: '⚕️',
  STAY: '🛏️',
  'FOLLOW-UP': '💊',
}

function fmt(n) { return `₹${n.toLocaleString('en-IN')}` }

export default function TabPathway({ pathway, condition, severity, approxOnly }) {
  return (
    <div className="p-6 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-white font-bold text-lg">Clinical Pathway</h3>
          <p className="text-slate-500 text-sm mt-0.5">{condition || 'Condition'} · {severity ? severity.charAt(0).toUpperCase() + severity.slice(1) : ''} severity</p>
        </div>
        <button className="text-[12px] text-blue-400 hover:text-blue-300 border border-blue-900 rounded-lg px-3 py-1.5 transition-colors">
          What is HBP? ⓘ
        </button>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical connector line */}
        <div className="absolute left-[19px] top-10 bottom-10 w-px bg-[#1E2D45]" style={{ background: 'linear-gradient(to bottom, #2563EB55, #1E2D45)' }} />

        <div className="space-y-3">
          {pathway.map((step, i) => {
            const cfg = TYPE_CFG[step.type] || TYPE_CFG.CONSULTATION
            const isLast = i === pathway.length - 1
            const costText = step.cost[0] === 0 && step.cost[1] === 0
              ? step.note || 'Bundled'
              : `${fmt(step.cost[0])} – ${fmt(step.cost[1])}`
            return (
              <div key={step.step} className="flex gap-4">
                {/* Step number circle */}
                <div className="relative flex flex-col items-center" style={{ width: 40, flexShrink: 0 }}>
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center z-10 ${cfg.color} shrink-0`}
                    style={{ boxShadow: '0 0 0 4px #070B14' }}>
                    <span className="text-lg">{STEP_ICONS[step.type]}</span>
                  </div>
                </div>

                {/* Card */}
                <div className="flex-1 mb-1 rounded-2xl p-4 transition-all hover:border-slate-600"
                  style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <span className={`inline-block text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full mb-2 ${cfg.color} ${cfg.text}`}>
                        {step.type}
                      </span>
                      <h4 className="text-white font-semibold text-[15px] leading-tight">{step.title}</h4>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-[11px] text-slate-500 mb-1">Estimated</p>
                      <p className="text-[13px] font-semibold text-slate-200">{costText}</p>
                    </div>
                  </div>
                  <p className="text-slate-500 text-[13px] leading-relaxed mb-3">{step.desc}</p>
                  {step.procedure_code && (
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                      <span className="text-[11px] font-mono text-slate-500 bg-[#111C30] border border-[#1E2D45] px-2 py-0.5 rounded">
                        {step.procedure_code}
                      </span>
                      {step.stacking_multiplier != null && step.stacking_multiplier < 1 && (
                        <span className="text-[11px] text-amber-400">
                          ×{Math.round(step.stacking_multiplier * 100)}% stacked
                        </span>
                      )}
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    {step.covered
                      ? <span className="flex items-center gap-1.5 text-[11px] text-green-400 bg-green-950 border border-green-900 px-2.5 py-1 rounded-full">
                          <CheckCircle size={10} /> HBP Covered
                        </span>
                      : approxOnly
                        ? <span className="flex items-center gap-1.5 text-[11px] text-slate-400 bg-slate-900 border border-slate-700 px-2.5 py-1 rounded-full">
                            Est. only
                          </span>
                        : <span className="flex items-center gap-1.5 text-[11px] text-amber-400 bg-amber-950 border border-amber-900 px-2.5 py-1 rounded-full">
                            <AlertTriangle size={10} /> OPD Only
                          </span>
                    }
                    <span className="text-[11px] text-slate-600">Step {step.step} of {pathway.length}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Multi-procedure note — only when real stacked codes exist */}
      {!approxOnly && pathway.filter(s => s.procedure_code).length > 1 && (
        <div className="mt-5 rounded-xl p-4 flex items-start gap-3" style={{ background: '#1A1200', border: '1px solid #78350F55' }}>
          <AlertTriangle size={15} className="text-amber-400 shrink-0 mt-0.5" />
          <p className="text-amber-300 text-[12px] leading-relaxed">
            <strong>Multi-procedure rule applied:</strong> Primary procedure (100%) + additional procedures (50% / 25%). Total adjusted per HBP Section 1.3.
          </p>
        </div>
      )}
    </div>
  )
}
