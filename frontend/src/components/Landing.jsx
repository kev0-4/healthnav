import { useState, useMemo } from 'react'
import { ArrowRight, Activity, MapPin, DollarSign, ChevronDown, ChevronUp, Brain, Database, Calculator, Building2 } from 'lucide-react'
import { EXAMPLES, STATS } from '../data'

const CITIES = ["Nagpur", "Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Pune", "Kolkata", "Jaipur", "Lucknow", "Surat", "Bhopal", "Indore", "Patna", "Chandigarh"]
const BUDGETS = ["Under 50K", "50K – 1L", "1L – 3L", "3L – 5L", "5L – 10L", "10L+"]
const SOURCES = ["HBP 2022 (NHA)", "NHP Hospital Directory", "CHSI Costing Study", "KGMU Utilisation Data"]

const HOW_IT_WORKS = [
  {
    icon: Brain,
    color: 'text-blue-400',
    bg: 'bg-blue-950',
    border: 'border-blue-800',
    step: '01',
    title: 'Describe your condition',
    desc: 'Type your symptoms in plain language — no medical jargon needed. Add city and budget if you have them.',
  },
  {
    icon: Database,
    color: 'text-violet-400',
    bg: 'bg-violet-950',
    border: 'border-violet-800',
    step: '02',
    title: 'AI maps to ICD-10 + pathway',
    desc: 'GPT-4o-mini extracts the condition and severity. Our RAG layer searches the HBP 2022 procedure database to build a clinical pathway.',
  },
  {
    icon: Calculator,
    color: 'text-teal-400',
    bg: 'bg-teal-950',
    border: 'border-teal-800',
    step: '03',
    title: 'City-tier cost estimate',
    desc: 'Procedure rates from HBP 2022 are adjusted for your city tier (T1/T2/T3), bed category, length of stay, and post-discharge medications.',
  },
  {
    icon: Building2,
    color: 'text-green-400',
    bg: 'bg-green-950',
    border: 'border-green-800',
    step: '04',
    title: 'Matched hospitals ranked',
    desc: 'Hospitals near you are filtered by specialty and ranked by rating, NABH accreditation, and adjusted cost range.',
  },
]

const COMORBIDITIES = ['Diabetes', 'Hypertension', 'Heart disease', 'Kidney disease', 'Obesity']
const INCOMES = ['Below ₹1 lakh', '₹1–5 lakh', '₹5–10 lakh', 'Above ₹10 lakh']

export default function Landing({ onSearch }) {
  const [query, setQuery]           = useState('')
  const [city, setCity]             = useState('')
  const [budget, setBudget]         = useState('')
  const [comorbidities, setComorbidities] = useState([])
  const [income, setIncome]         = useState('')
  const [moreOpen, setMoreOpen]     = useState(false)

  const displayedExamples = useMemo(() => {
    return [...EXAMPLES].sort(() => Math.random() - 0.5).slice(0, 5)
  }, [])

  const toggleComorbidity = (c) =>
    setComorbidities(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c])

  const submit = (q = query) => {
    if (!q.trim()) return
    // Append comorbidities to query so NLP extractor picks them up naturally
    let fullQuery = q.trim()
    if (comorbidities.length) fullQuery += `. I also have: ${comorbidities.join(', ')}.`
    onSearch(fullQuery, city, budget, income)
  }

  const scrollToHowItWorks = () => {
    document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#070B14' }}>
      {/* Navbar */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 h-[60px] border-b border-[#1E2D45]" style={{ background: 'rgba(7,11,20,0.9)', backdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <Activity size={17} className="text-white" />
          </div>
          <span className="text-white font-bold text-[17px] tracking-tight">HealthNav</span>
          <span className="ml-1 text-[10px] bg-blue-950 text-blue-400 border border-blue-800 px-2 py-0.5 rounded-full font-semibold">Beta</span>
        </div>
        <div className="flex items-center gap-5">
          <button onClick={scrollToHowItWorks} className="text-slate-400 hover:text-slate-200 text-sm transition-colors">How it works</button>
          <button onClick={scrollToHowItWorks} className="text-sm border border-[#1E2D45] text-slate-300 hover:border-slate-500 px-4 py-1.5 rounded-[10px] transition-colors">View Demo</button>
        </div>
      </nav>

      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 pt-24 pb-16">
        <div className="text-center max-w-[680px] w-full">
          {/* Pill badge */}
          <div className="inline-flex items-center gap-2 bg-blue-950 border border-blue-800 text-blue-300 text-[11px] font-semibold px-3.5 py-1.5 rounded-full mb-7">
            <span>⚕</span>
            <span>Powered by HBP 2022 · 30,273 Hospitals</span>
          </div>

          <h1 className="text-[52px] leading-[1.1] font-extrabold text-white mb-5 tracking-tight">
            Find out what your<br />
            treatment will cost —<br />
            <span className="text-blue-400">before you walk in.</span>
          </h1>

          <p className="text-[18px] text-slate-400 max-w-[520px] mx-auto mb-10 leading-relaxed">
            AI-powered cost intelligence for Indian patients. Enter your symptoms, city, and budget. Get a real, itemized estimate in seconds.
          </p>

          {/* Search card */}
          <div className="w-full max-w-[720px] mx-auto rounded-2xl p-5 mb-5"
            style={{ background: '#0D1525', border: '1px solid #1E2D45', boxShadow: '0 0 40px rgba(37,99,235,0.08)' }}>
            <textarea
              rows={3}
              className="w-full bg-transparent text-white placeholder-slate-500 outline-none text-[15px] resize-none leading-relaxed"
              placeholder={`Describe your health concern...\ne.g. "knee pain in Nagpur under 3 lakhs, age 58"`}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
            />
            <div className="border-t border-[#1E2D45] mt-3 pt-3 flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <div className="relative flex items-center gap-1.5 bg-[#111C30] border border-[#1E2D45] rounded-[10px] px-3 py-2 text-sm text-slate-300 cursor-pointer hover:border-slate-500 transition-colors">
                  <MapPin size={13} className="text-slate-500" />
                  <select className="bg-transparent outline-none text-slate-300 text-[13px] cursor-pointer pr-4"
                    value={city} onChange={e => setCity(e.target.value)}>
                    <option value="">City</option>
                    {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <ChevronDown size={12} className="text-slate-600 absolute right-2" />
                </div>
                <div className="relative flex items-center gap-1.5 bg-[#111C30] border border-[#1E2D45] rounded-[10px] px-3 py-2 text-sm text-slate-300 cursor-pointer hover:border-slate-500 transition-colors">
                  <DollarSign size={13} className="text-slate-500" />
                  <select className="bg-transparent outline-none text-slate-300 text-[13px] cursor-pointer pr-4"
                    value={budget} onChange={e => setBudget(e.target.value)}>
                    <option value="">Budget</option>
                    {BUDGETS.map(b => <option key={b} value={b}>{b}</option>)}
                  </select>
                  <ChevronDown size={12} className="text-slate-600 absolute right-2" />
                </div>
              </div>
              <button onClick={() => submit()}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-5 py-2.5 rounded-[10px] text-sm transition-colors">
                Analyze <ArrowRight size={15} />
              </button>
            </div>

            {/* More options toggle */}
            <button onClick={() => setMoreOpen(o => !o)}
              className="flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-slate-300 transition-colors mt-2">
              {moreOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              {moreOpen ? 'Hide details' : 'Add health conditions & income (optional)'}
            </button>

            {moreOpen && (
              <div className="mt-3 pt-3 border-t border-[#1E2D45] space-y-4">
                {/* Comorbidities */}
                <div>
                  <p className="text-[11px] text-slate-500 uppercase tracking-widest font-semibold mb-2">Existing conditions</p>
                  <div className="flex flex-wrap gap-2">
                    {COMORBIDITIES.map(c => (
                      <button key={c} onClick={() => toggleComorbidity(c)}
                        className={`text-[12px] px-3 py-1.5 rounded-full border transition-colors ${
                          comorbidities.includes(c)
                            ? 'bg-blue-600 border-blue-500 text-white'
                            : 'border-[#1E2D45] text-slate-400 hover:border-slate-500'
                        }`}>
                        {c}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Annual income */}
                <div>
                  <p className="text-[11px] text-slate-500 uppercase tracking-widest font-semibold mb-2">Annual family income</p>
                  <div className="flex flex-wrap gap-2">
                    {INCOMES.map(inc => (
                      <button key={inc} onClick={() => setIncome(income === inc ? '' : inc)}
                        className={`text-[12px] px-3 py-1.5 rounded-full border transition-colors ${
                          income === inc
                            ? 'bg-teal-700 border-teal-600 text-white'
                            : 'border-[#1E2D45] text-slate-400 hover:border-slate-500'
                        }`}>
                        {inc}
                      </button>
                    ))}
                  </div>
                  {income && income !== 'Above ₹10 lakh' && (
                    <p className="text-[11px] text-green-400 mt-2 flex items-center gap-1.5">
                      ✓ You may be eligible for AB-PMJAY free treatment — we'll check in results
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Example chips — 5 random ones from pool of 20 */}
          <div className="flex flex-wrap gap-2 justify-center mb-16">
            <span className="text-slate-500 text-sm self-center">Try:</span>
            {displayedExamples.map((ex, i) => (
              <button key={i} onClick={() => submit(ex)}
                className="text-[12px] text-slate-400 hover:text-slate-200 border border-[#1E2D45] hover:border-slate-500 bg-[#0D1525] hover:bg-[#111C30] rounded-full px-3.5 py-1.5 transition-all">
                {ex}
              </button>
            ))}
          </div>

          {/* Stats */}
          <div className="flex justify-center gap-12 mb-12">
            {STATS.map((s, i) => (
              <div key={i} className="text-center">
                <div className="text-[28px] font-bold text-white">{s.value}</div>
                <div className="text-[12px] text-slate-500 mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Trust strip */}
          <div className="border-t border-[#1E2D45] pt-8">
            <p className="text-[11px] text-slate-600 mb-3">Data sources</p>
            <div className="flex flex-wrap justify-center gap-3">
              {SOURCES.map((s, i) => (
                <span key={i} className="text-[11px] text-slate-500 bg-[#0D1525] border border-[#1E2D45] px-3 py-1 rounded-full">{s}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* How It Works section */}
      <div id="how-it-works" className="px-6 py-20 border-t border-[#1E2D45]">
        <div className="max-w-[900px] mx-auto">
          <div className="text-center mb-14">
            <span className="text-[11px] text-blue-400 font-semibold uppercase tracking-widest">Pipeline</span>
            <h2 className="text-[34px] font-extrabold text-white mt-2 mb-3 tracking-tight">How it works</h2>
            <p className="text-slate-400 text-[15px] max-w-[480px] mx-auto">Four AI layers turn a vague symptom description into an itemized cost estimate in under 15 seconds.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {HOW_IT_WORKS.map((item, i) => {
              const Icon = item.icon
              const isLast = i === HOW_IT_WORKS.length - 1
              return (
                <div key={i} className="relative rounded-2xl p-5"
                  style={{ background: '#0D1525', border: '1px solid #1E2D45' }}>
                  {/* Connector arrow for non-last on desktop */}
                  <div className="flex items-start gap-4">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${item.bg} border ${item.border}`}>
                      <Icon size={18} className={item.color} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[10px] font-bold text-slate-600 font-mono">{item.step}</span>
                        <h3 className="text-white font-semibold text-[14px]">{item.title}</h3>
                      </div>
                      <p className="text-slate-500 text-[13px] leading-relaxed">{item.desc}</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="text-center mt-10">
            <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-6 py-3 rounded-xl text-sm transition-colors">
              Try it now <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
