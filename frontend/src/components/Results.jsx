import { useState } from 'react'
import { Activity, Download, AlertTriangle, ArrowRight } from 'lucide-react'
import Sidebar from './Sidebar'
import TabPathway from './TabPathway'
import TabCost from './TabCost'
import TabHospitals from './TabHospitals'
import ChatDrawer from './ChatDrawer'

const TABS = ['Clinical Pathway', 'Cost Breakdown', 'Matched Hospitals']
const TAB_ICONS = ['🧬', '💰', '🏥']

function OPDCard({ result, onReset }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16"
      style={{ background: '#070B14' }}>
      <div className="max-w-lg w-full">
        <div className="rounded-2xl p-6 mb-4" style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
          <div className="flex items-start gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-amber-950 border border-amber-800 flex items-center justify-center shrink-0">
              <AlertTriangle size={18} className="text-amber-400" />
            </div>
            <div>
              <p className="text-[11px] text-amber-400 font-semibold uppercase tracking-widest mb-1">OPD-Only Condition</p>
              <h2 className="text-white font-bold text-xl">{result.condition}</h2>
              <p className="text-slate-500 text-sm mt-1">{result.city} · {result.severity} severity</p>
            </div>
          </div>
          <p className="text-slate-400 text-[14px] leading-relaxed mb-5">
            This condition is typically managed on an outpatient basis and is <strong className="text-amber-300">not covered under AB-PMJAY hospitalization packages</strong>. HBP only covers inpatient admissions.
          </p>
          <div className="rounded-xl p-4 mb-4" style={{ background: '#111C30', border: '1px solid #1E2D45' }}>
            <p className="text-[11px] text-slate-500 uppercase tracking-widest font-semibold mb-3">Typical OPD Cost (self-pay estimate)</p>
            <div className="space-y-2">
              {[
                ['Doctor consultation', '₹300 – ₹800'],
                ['Diagnostic tests (if needed)', '₹500 – ₹2,500'],
                ['Medications (30 days)', '₹500 – ₹2,000'],
                ['Follow-up visits (2–3)', '₹600 – ₹2,000'],
              ].map(([label, range]) => (
                <div key={label} className="flex justify-between text-[13px]">
                  <span className="text-slate-500">{label}</span>
                  <span className="text-slate-300 font-medium">{range}</span>
                </div>
              ))}
              <div className="border-t border-[#1E2D45] pt-2 flex justify-between text-[14px]">
                <span className="text-white font-semibold">Estimated Total</span>
                <span className="text-white font-bold">₹1,900 – ₹7,300</span>
              </div>
            </div>
          </div>
          <div className="rounded-xl p-3.5 flex items-start gap-2.5" style={{ background: '#0A1628', border: '1px solid #1E3A5F' }}>
            <ArrowRight size={13} className="text-blue-400 shrink-0 mt-0.5" />
            <p className="text-blue-300 text-[12px] leading-relaxed">
              If symptoms worsen or you develop fever, chest pain, or difficulty breathing — seek inpatient care immediately. Those cases <em>are</em> covered under HBP.
            </p>
          </div>
        </div>
        <button onClick={onReset}
          className="w-full py-3 rounded-xl border border-[#1E2D45] text-slate-400 hover:border-slate-500 hover:text-slate-200 text-sm font-medium transition-colors">
          ← Try a different query
        </button>
      </div>
    </div>
  )
}

export default function Results({ result, onReset, income }) {
  const [tab, setTab] = useState(0)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  if (result?._opd) return <OPDCard result={result} onReset={onReset} />

  const handlePrint = () => window.print()

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#070B14' }}>
      {/* Navbar */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center px-4 md:px-8 h-[60px] border-b border-[#1E2D45]"
        style={{ background: 'rgba(7,11,20,0.95)', backdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-2.5 mr-4 md:mr-8">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <Activity size={17} className="text-white" />
          </div>
          <span className="text-white font-bold text-[17px] tracking-tight">HealthNav</span>
        </div>

        {/* Mobile: show condition name */}
        <div className="flex-1 min-w-0 md:hidden">
          <p className="text-slate-300 text-[13px] font-medium truncate">{result?.condition}</p>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          {/* Mobile summary toggle */}
          <button onClick={() => setSidebarOpen(o => !o)}
            className="md:hidden text-[12px] text-slate-400 border border-[#1E2D45] px-3 py-1.5 rounded-lg">
            {sidebarOpen ? 'Hide' : 'Summary'}
          </button>
          <button onClick={handlePrint}
            className="hidden sm:flex items-center gap-1.5 text-[12px] text-slate-400 border border-[#1E2D45] hover:border-slate-500 px-3 py-1.5 rounded-lg transition-colors no-print">
            <Download size={13} /> Export PDF
          </button>
          <button onClick={onReset} className="text-sm text-slate-400 hover:text-slate-200 transition-colors hidden md:block">
            ← New search
          </button>
        </div>
      </nav>

      {/* Body: sidebar + main */}
      <div className="flex pt-[60px] min-h-screen">

        {/* Desktop sidebar */}
        <div className="hidden md:block print-sidebar">
          <Sidebar result={result} onReset={onReset} income={income} />
        </div>

        {/* Mobile sidebar drawer */}
        {sidebarOpen && (
          <div className="md:hidden fixed inset-0 z-40 bg-black/60" onClick={() => setSidebarOpen(false)}>
            <div className="absolute top-[60px] left-0 right-0 max-h-[70vh] overflow-y-auto"
              style={{ background: '#070B14', borderBottom: '1px solid #1E2D45' }}
              onClick={e => e.stopPropagation()}>
              <Sidebar result={result} onReset={onReset} income={income} />
            </div>
          </div>
        )}

        {/* Main content */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Tab bar — desktop horizontal, mobile scrollable */}
          <div className="sticky top-[60px] z-30 border-b border-[#1E2D45] px-2 md:px-6 no-print"
            style={{ background: 'rgba(7,11,20,0.95)', backdropFilter: 'blur(12px)' }}>
            <div className="flex gap-0 overflow-x-auto scrollbar-hide">
              {TABS.map((t, i) => (
                <button key={i} onClick={() => setTab(i)}
                  className={`flex items-center gap-1.5 px-3 md:px-5 py-4 text-[13px] font-semibold border-b-2 transition-all -mb-px whitespace-nowrap shrink-0 ${
                    i === tab
                      ? 'text-white border-blue-500'
                      : 'text-slate-500 border-transparent hover:text-slate-300'
                  }`}>
                  <span className="md:hidden">{TAB_ICONS[i]}</span>
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto print-content">
            {tab === 0 && <TabPathway pathway={result.pathway} condition={result.condition} severity={result.severity} approxOnly={!!result.approximate_only} />}
            {tab === 1 && <TabCost result={result} />}
            {tab === 2 && <TabHospitals hospitals={result.hospitals} baseCost={result.cost} city={result.city} />}
          </div>
        </div>
      </div>

      <ChatDrawer result={result} />
    </div>
  )
}
