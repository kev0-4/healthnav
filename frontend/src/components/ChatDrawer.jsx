import { useState, useRef, useEffect } from 'react'
import { MessageCircle, X, Send, Bot } from 'lucide-react'
import { chat } from '../api'

export default function ChatDrawer({ result }) {
  const [open, setOpen] = useState(true)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send() {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { q, a: null }])
    try {
      const a = await chat(q, result)
      setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { q, a } : m))
    } catch {
      setMessages(prev => prev.map((m, i) =>
        i === prev.length - 1
          ? { q, a: 'Something went wrong. Please try again.' }
          : m
      ))
    } finally {
      setLoading(false)
    }
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const greeting = `Hi! I can answer questions about your **${result.condition}** estimate and how India's AB-PMJAY scheme works. What would you like to know?`

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(o => !o)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 h-11 rounded-full bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-900/60 transition-all"
        title="Ask AI assistant"
      >
        {open
          ? <X size={16} className="text-white" />
          : <MessageCircle size={16} className="text-white" />
        }
        <span className="text-white text-[13px] font-semibold">{open ? 'Close' : 'Ask AI'}</span>
      </button>

      {/* Drawer */}
      {open && (
        <div
          className="fixed bottom-[76px] right-6 z-50 w-[380px] rounded-2xl flex flex-col overflow-hidden shadow-2xl"
          style={{ background: '#0D1525', border: '1px solid #1E2D45', maxHeight: '520px' }}
        >
          {/* Header */}
          <div className="flex items-center gap-2.5 px-4 py-3 border-b border-[#1E2D45] shrink-0">
            <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
              <Bot size={14} className="text-white" />
            </div>
            <div>
              <p className="text-white text-[13px] font-semibold leading-tight">HealthNav Assistant</p>
              <p className="text-slate-500 text-[11px]">Ask about your result or HBP coverage</p>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 min-h-0">
            {/* Greeting */}
            <div className="flex gap-2.5 items-start">
              <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center shrink-0 mt-0.5">
                <Bot size={12} className="text-white" />
              </div>
              <p className="text-slate-300 text-[13px] leading-relaxed">
                Hi! I can answer questions about your <span className="text-white font-medium">{result.condition}</span> estimate and how India's AB-PMJAY scheme works. What would you like to know?
              </p>
            </div>

            {messages.map((m, i) => (
              <div key={i} className="space-y-2">
                {/* User question */}
                <div className="flex justify-end">
                  <div className="max-w-[75%] rounded-2xl rounded-tr-sm px-3.5 py-2.5 text-[13px] text-white"
                    style={{ background: '#1E3A5F' }}>
                    {m.q}
                  </div>
                </div>
                {/* Answer */}
                {m.a === null
                  ? null
                  : (
                    <div className="flex gap-2.5 items-start">
                      <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center shrink-0 mt-0.5">
                        <Bot size={12} className="text-white" />
                      </div>
                      <p className="text-slate-300 text-[13px] leading-relaxed">{m.a}</p>
                    </div>
                  )
                }
              </div>
            ))}

            {/* Loading dots */}
            {loading && (
              <div className="flex gap-2.5 items-start">
                <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot size={12} className="text-white" />
                </div>
                <div className="flex gap-1 pt-2">
                  {[0, 1, 2].map(n => (
                    <span key={n} className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce"
                      style={{ animationDelay: `${n * 0.15}s` }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="px-3 py-3 border-t border-[#1E2D45] shrink-0">
            <div className="flex items-center gap-2 rounded-xl px-3 py-2"
              style={{ background: '#111C30', border: '1px solid #1E2D45' }}>
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={onKey}
                placeholder="Ask a question…"
                className="flex-1 bg-transparent text-[13px] text-slate-200 placeholder-slate-600 outline-none"
              />
              <button onClick={send} disabled={!input.trim() || loading}
                className="w-7 h-7 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-30 flex items-center justify-center transition-all shrink-0">
                <Send size={13} className="text-white" />
              </button>
            </div>
            <p className="text-[10px] text-slate-600 mt-2 text-center">Not medical advice · AB-PMJAY planning only</p>
          </div>
        </div>
      )}
    </>
  )
}
