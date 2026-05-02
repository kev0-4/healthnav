import { useState } from 'react'
import { Activity } from 'lucide-react'

export default function Clarification({ question, onSubmit, onReset }) {
  const [answer, setAnswer] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (answer.trim()) onSubmit(answer.trim())
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#070B14' }}>
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center px-8 h-[60px] border-b border-[#1E2D45]"
        style={{ background: 'rgba(7,11,20,0.95)', backdropFilter: 'blur(12px)' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <Activity size={17} className="text-white" />
          </div>
          <span className="text-white font-bold text-[17px] tracking-tight">HealthNav</span>
        </div>
      </nav>

      <div className="flex-1 flex items-center justify-center pt-[60px] px-6">
        <div className="w-full max-w-lg">
          <div className="rounded-xl border border-[#1E2D45] p-8" style={{ background: '#0D1526' }}>
            <div className="text-xs text-blue-400 font-semibold uppercase tracking-widest mb-3">
              One more thing
            </div>
            <p className="text-white text-lg font-medium mb-6">{question}</p>
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                autoFocus
                type="text"
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                placeholder="Your answer..."
                className="flex-1 bg-[#0A1120] border border-[#1E2D45] rounded-lg px-4 py-2.5 text-white text-sm placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
              />
              <button
                type="submit"
                disabled={!answer.trim()}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
              >
                Continue
              </button>
            </form>
            <button
              onClick={onReset}
              className="mt-4 text-xs text-slate-500 hover:text-slate-400 transition-colors"
            >
              ← Start over
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
