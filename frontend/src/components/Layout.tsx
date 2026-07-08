import { useState, useEffect, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth, useApi } from '../hooks/useAuth'
import type { ReactNode } from 'react'

interface Loja {
  id: number; nome: string; tipo: string
}

const NAV_POR_ROLE: Record<string, Array<{ to: string; label: string; icon: string }>> = {
  admin: [
    { to: '/', label: 'Dashboard', icon: '◉' },
    { to: '/produtos', label: 'Produtos', icon: '📦' },
    { to: '/agents', label: 'Agents', icon: '⚡' },
    { to: '/workflows', label: 'Workflows', icon: '▸' },
    { to: '/metrics', label: 'Metrics', icon: '◈' },
    { to: '/business', label: 'Business', icon: '◆' },
    { to: '/integrations', label: 'Integrações', icon: '🔌' },
    { to: '/bling', label: 'Bling ERP', icon: '💎' },
    { to: '/shopee', label: 'Shopee', icon: '🛒' },
  ],
  produto: [
    { to: '/', label: 'Dashboard', icon: '◉' },
    { to: '/produtos', label: 'Produtos', icon: '📦' },
    { to: '/shopee', label: 'Shopee', icon: '🛒' },
  ],
  financeiro: [
    { to: '/', label: 'Dashboard', icon: '◉' },
    { to: '/produtos', label: 'Produtos', icon: '📦' },
    { to: '/metrics', label: 'Métricas', icon: '◈' },
    { to: '/bling', label: 'Bling ERP', icon: '💎' },
  ],
  operador: [
    { to: '/', label: 'Dashboard', icon: '◉' },
    { to: '/produtos', label: 'Produtos', icon: '📦' },
    { to: '/shopee', label: 'Shopee', icon: '🛒' },
    { to: '/integrations', label: 'Integrações', icon: '🔌' },
  ],
}

export default function Layout({ children }: { children: ReactNode }) {
  const { token, role, name, logout } = useAuth()
  const api = useApi()
  const loc = useLocation()
  const [lojas, setLojas] = useState<Loja[]>([])
  const [lojaSelecionada, setLojaSelecionada] = useState<string>(
    () => localStorage.getItem('loja_selecionada') || ''
  )
  const [sidebarOpen, setSidebarOpen] = useState(true)

  useEffect(() => {
    api<Loja[]>('/api/lojas').then(d => { if (d) setLojas(d.filter(l => l.tipo !== 'consolidado')) })
  }, [api])

  const onChangeLoja = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value
    setLojaSelecionada(val)
    localStorage.setItem('loja_selecionada', val)
    window.location.reload()
  }, [])

  const nav = NAV_POR_ROLE[role || ''] || NAV_POR_ROLE.admin
  const userRole = role === 'admin' ? 'Admin' : role === 'produto' ? 'Produtos' : role === 'financeiro' ? 'Financeiro' : role === 'operador' ? 'Operador' : role || ''

  return (
    <div className="flex h-screen bg-athena-900">
      <nav className={`${sidebarOpen ? 'w-56' : 'w-14'} bg-athena-800 border-r border-athena-700 flex flex-col shrink-0 transition-all duration-200`}>
        <div className="p-3 border-b border-athena-700 flex items-center gap-2">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-athena-400 hover:text-white text-lg">☰</button>
          {sidebarOpen && <div><h1 className="text-athena-accent text-sm font-bold tracking-wide truncate">ATHENA OS</h1><p className="text-athena-600 text-[10px]">{userRole}</p></div>}
        </div>
        <div className="flex-1 py-1 overflow-y-auto">
          {nav.map(n => (
            <Link key={n.to} to={`${n.to}${lojaSelecionada ? `?loja=${lojaSelecionada}` : ''}`}
              className={`flex items-center gap-2.5 px-3 py-2 text-xs transition-colors ${loc.pathname === n.to ? 'bg-athena-700 text-white border-r-2 border-athena-accent' : 'text-athena-400 hover:text-white hover:bg-athena-700/50'}`}
              title={!sidebarOpen ? n.label : undefined}>
              <span className="text-base shrink-0">{n.icon}</span>
              {sidebarOpen && <span className="truncate">{n.label}</span>}
            </Link>
          ))}
        </div>
        <div className="p-3 border-t border-athena-700">
          {sidebarOpen && <p className="text-athena-400 text-xs truncate">{name}</p>}
          <button onClick={logout} className="text-athena-error text-xs hover:underline mt-1 w-full text-left">
            {sidebarOpen ? 'Logout' : '🚪'}
          </button>
        </div>
      </nav>
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-athena-800 border-b border-athena-700 px-4 py-2 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-athena-400 text-xs font-medium">📍</span>
            <select value={lojaSelecionada} onChange={onChangeLoja}
              className="bg-athena-900 border border-athena-700 rounded px-2.5 py-1.5 text-sm text-white focus:border-athena-accent focus:outline-none min-w-[160px] cursor-pointer">
              <option value="">🏪 Todas as lojas</option>
              {lojas.filter(l => l.tipo === 'fisica').map(l => (
                <option key={l.id} value={l.nome}>🏪 {l.nome}</option>
              ))}
              <option disabled>──────────</option>
              {lojas.filter(l => l.tipo === 'digital').map(l => (
                <option key={l.id} value={l.nome}>🛒 {l.nome}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-3">
            {lojaSelecionada && (
              <span className="bg-athena-accent/10 text-athena-accent text-[10px] px-2 py-0.5 rounded-full border border-athena-accent/30">
                Filtrando: {lojaSelecionada}
              </span>
            )}
            <span className="text-athena-400 text-xs">{name}</span>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
