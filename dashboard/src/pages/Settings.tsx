import { useState, useEffect } from 'react'
import { Save, RefreshCw, Eye, EyeOff, ShieldCheck } from 'lucide-react'

interface SettingGroup {
  [key: string]: Array<{ key: string; value: string; secure: boolean; updatedAt: string }>
}

const GROUP_LABELS: Record<string, string> = {
  shopee: 'Shopee Integração',
  whatsapp: 'WhatsApp (Evolution API)',
  telegram: 'Telegram',
  system: 'Sistema',
}

const GROUP_ICONS: Record<string, string> = {
  shopee: '🛒',
  whatsapp: '💬',
  telegram: '✈️',
  system: '⚙️',
}

export function Settings() {
  const [groups, setGroups] = useState<SettingGroup>({})
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [revealed, setRevealed] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchSettings()
  }, [])

  async function fetchSettings() {
    try {
      const resp = await fetch('/api/settings')
      const data = await resp.json()
      setGroups(data)
      const initial: Record<string, string> = {}
      for (const group of Object.values(data) as any) {
        for (const s of group as Array<{ key: string; value: string }>) {
          initial[s.key] = ''
        }
      }
      setEdits(initial)
    } catch {
      setMessage({ type: 'error', text: 'Falha ao carregar configurações' })
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    setMessage(null)
    const entries = Object.entries(edits).filter(([, v]) => v !== '').map(([key, value]) => ({ key, value }))
    if (entries.length === 0) {
      setMessage({ type: 'error', text: 'Nenhuma alteração para salvar' })
      setSaving(false)
      return
    }
    try {
      const resp = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: entries }),
      })
      if (!resp.ok) throw new Error('Save failed')
      setMessage({ type: 'success', text: `${entries.length} configuração(ões) salva(s)!` })
      setTimeout(() => setMessage(null), 3000)
      await fetchSettings()
    } catch {
      setMessage({ type: 'error', text: 'Erro ao salvar configurações' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">Configurações</h2>
        <div className="animate-pulse space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-32 bg-slate-800 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Configurações</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchSettings}
            className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded-md border border-slate-700 hover:bg-slate-800 transition-colors"
          >
            <RefreshCw size={14} /> Recarregar
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 text-sm bg-sky-500/10 text-sky-400 hover:bg-sky-500/20 px-3 py-1.5 rounded-md border border-sky-500/30 transition-colors disabled:opacity-50"
          >
            <Save size={14} /> {saving ? 'Salvando...' : 'Salvar'}
          </button>
        </div>
      </div>

      {message && (
        <div className={`px-4 py-2 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
          : 'bg-red-500/10 text-red-400 border border-red-500/30'
        }`}>
          {message.text}
        </div>
      )}

      {Object.entries(groups).map(([group, settings]) => (
        <div key={group} className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-700 flex items-center gap-2">
            <span className="text-sm">{GROUP_ICONS[group]}</span>
            <h3 className="text-sm font-medium text-slate-200">{GROUP_LABELS[group] ?? group}</h3>
          </div>
          <div className="divide-y divide-slate-700/50">
            {settings.map((s) => {
              const isDirty = edits[s.key] !== '' && edits[s.key] !== undefined
              return (
                <div key={s.key} className="px-4 py-3 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <label className="block text-xs text-slate-400 uppercase tracking-wider mb-1 font-mono">
                      {s.key}
                      {s.secure && <ShieldCheck size={12} className="inline ml-1 text-amber-400" />}
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type={s.secure && !revealed[s.key] ? 'password' : 'text'}
                        placeholder={s.secure ? '••••••••' : s.value}
                        onChange={e => setEdits(prev => ({ ...prev, [s.key]: e.target.value }))}
                        className={`w-full bg-slate-900 border rounded-md px-3 py-1.5 text-sm text-slate-200 outline-none transition-colors ${
                          isDirty ? 'border-sky-500/50' : 'border-slate-700 focus:border-slate-500'
                        }`}
                      />
                      {s.secure && (
                        <button
                          onClick={() => setRevealed(prev => ({ ...prev, [s.key]: !prev[s.key] }))}
                          className="text-slate-400 hover:text-slate-200 shrink-0"
                        >
                          {revealed[s.key] ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-500 text-right shrink-0 whitespace-nowrap">
                    {new Date(s.updatedAt).toLocaleDateString('pt-BR')}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
