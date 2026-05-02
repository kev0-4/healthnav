import { useState } from 'react'
import { Activity } from 'lucide-react'
import Sidebar from './Sidebar'
import TabPathway from './TabPathway'
import TabCost from './TabCost'
import TabHospitals from './TabHospitals'
import ChatDrawer from './ChatDrawer'

const TABS = ['Clinical Pathway', 'Cost Breakdown', 'Matched Hospitals']

export default function Results({ result, onReset }) {
  const [tab, setTab] = useState(0)

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#070B14' }}>
      {/* Navbar */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center px-8 h-[60px] border-b border-[#1E2D45]"
        style={{ background: 'rgba(7,11,20,0.95)', backdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-2.5 mr-8">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <Activity size={17} className="text-white" />
          </div>
          <span className="text-white font-bold text-[17px] tracking-tight">HealthNav</span>
        </div>
        <div className="flex-1" />
        <button onClick={onReset} className="text-sm text-slate-400 hover:text-slate-200 transition-colors">
          ← New search
        </button>
      </nav>

      {/* Body: sidebar + main */}
      <div className="flex pt-[60px] min-h-screen">
        <Sidebar result={result} onReset={onReset} />

        {/* Main content */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Tab bar */}
          <div className="sticky top-[60px] z-30 border-b border-[#1E2D45] px-6"
            style={{ background: 'rgba(7,11,20,0.95)', backdropFilter: 'blur(12px)' }}>
            <div className="flex gap-1">
              {TABS.map((t, i) => (
                <button key={i} onClick={() => setTab(i)}
                  className={`px-5 py-4 text-[13px] font-semibold border-b-2 transition-all -mb-px ${
                    i === tab
                      ? 'text-white border-blue-500'
                      : 'text-slate-500 border-transparent hover:text-slate-300'
                  }`}>
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto">
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
