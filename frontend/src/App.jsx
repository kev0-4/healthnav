import { useState } from 'react'
import Landing from './components/Landing'
import Loading from './components/Loading'
import Results from './components/Results'
import Clarification from './components/Clarification'
import { analyzeStream } from './api'

export default function App() {
  const [screen, setScreen] = useState('landing')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [clarification, setClarification] = useState(null)

  // Real-time pipeline progress
  const [activeStep, setActiveStep] = useState(-1)
  const [completedSteps, setCompletedSteps] = useState(new Set())

  const handleSearch = async (query, city, budget) => {
    setScreen('loading')
    setError(null)
    setActiveStep(0)
    setCompletedSteps(new Set())

    try {
      const data = await analyzeStream(query, city, budget, (event) => {
        if (event.step === undefined) return
        if (event.status === 'running') {
          setActiveStep(event.step)
        } else if (event.status === 'done') {
          setCompletedSteps(prev => new Set([...prev, event.step]))
        }
      })

      if (data.status === 'needs_clarification') {
        setClarification({ question: data.question, originalQuery: query, city, budget })
        setScreen('clarification')
      } else if (data.status === 'opd_only') {
        setResult({ ...data, _opd: true })
        setScreen('results')
      } else if (data.status === 'ok') {
        setResult(data)
        setScreen('results')
      } else {
        setError(data.message || 'An unexpected error occurred.')
        setScreen('error')
      }
    } catch (err) {
      setError(err.message || 'Network error. Please try again.')
      setScreen('error')
    }
  }

  const handleClarify = async (answer) => {
    const combined = `${clarification.originalQuery}, ${answer}`
    await handleSearch(combined, clarification.city, clarification.budget)
  }

  const handleReset = () => {
    setScreen('landing')
    setResult(null)
    setError(null)
    setClarification(null)
    setActiveStep(-1)
    setCompletedSteps(new Set())
  }

  return (
    <>
      {screen === 'landing' && <Landing onSearch={handleSearch} />}
      {screen === 'loading' && <Loading activeStep={activeStep} completedSteps={completedSteps} />}
      {screen === 'results' && <Results result={result} onReset={handleReset} />}
      {screen === 'clarification' && (
        <Clarification
          question={clarification?.question}
          onSubmit={handleClarify}
          onReset={handleReset}
        />
      )}
      {screen === 'error' && (
        <div className="min-h-screen flex items-center justify-center" style={{ background: '#070B14' }}>
          <div className="text-center max-w-md px-6">
            <div className="text-red-400 text-lg font-semibold mb-3">Something went wrong</div>
            <div className="text-slate-400 text-sm mb-6">{error}</div>
            <button onClick={handleReset}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-lg transition-colors">
              Try again
            </button>
          </div>
        </div>
      )}
    </>
  )
}
