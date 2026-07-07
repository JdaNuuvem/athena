import { useState, useRef, useEffect, type FormEvent } from 'react'
import { Send, MessageSquare } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  text: string
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', text: 'Olá! Sou o assistente Hermes. Como posso ajudar?' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }])
    setLoading(true)
    try {
      const resp = await fetch('/api/hermes/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 'athena-dashboard', mensagem: userMsg, nome: 'Usuário' }),
      })
      const data = await resp.json()
      const reply = data.resposta ?? data.mensagem ?? JSON.stringify(data)
      setMessages(prev => [...prev, { role: 'assistant', text: reply }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', text: 'Erro ao conectar com Hermes.' }])
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare size={20} className="text-sky-400" />
        <h2 className="text-lg font-semibold text-slate-200">Hermes Chat</h2>
      </div>
      <div className="flex-1 overflow-y-auto space-y-3 mb-4 pr-1">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-xl px-4 py-2 text-sm ${
              m.role === 'user'
                ? 'bg-sky-500/20 text-sky-200 border border-sky-500/20'
                : 'bg-slate-800/50 text-slate-300 border border-slate-700/50'
            }`}>
              {m.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-800/50 text-slate-400 rounded-xl px-4 py-2 text-sm border border-slate-700/50">
              pensando...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Digite sua mensagem..."
          className="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500/50"
        />
        <button type="submit" disabled={loading} className="bg-sky-500/20 hover:bg-sky-500/30 text-sky-400 rounded-xl px-4 py-2.5 border border-sky-500/20 transition-colors">
          <Send size={18} />
        </button>
      </form>
    </div>
  )
}
