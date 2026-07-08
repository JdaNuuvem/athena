import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import type { ReactNode } from 'react'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '◉' },
  { to: '/produtos', label: 'Produtos', icon: '📦' },
  { to: '/agents', label: 'Agents', icon: '⚡' },
  { to: '/workflows', label: 'Workflows', icon: '▸' },
  { to: '/metrics', label: 'Metrics', icon: '◈' },
  { to: '/business', label: 'Business', icon: '◆' },
  { to: '/integrations', label: 'Integrações', icon: '🔌' },
  { to: '/bling', label: 'Bling ERP', icon: '💎' },
  { to: '/shopee', label: 'Shopee', icon: '🛒' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const { token, role, name, logout } = useAuth()
  const loc = useLocation()

  return (
    <div className="flex h-screen">
      <nav className="w-56 bg-athena-800 border-r border-athena-700 flex flex-col shrink-0">
        <div className="p-4 border-b border-athena-700">
          <h1 className="text-athena-accent text-lg font-bold tracking-wide">⚡ ATHENA OS</h1>
          <p className="text-athena-600 text-xs mt-1">v0.1.0 · {role}</p>
        </div>
        <div className="flex-1 py-2">
          {NAV.map(n => (
            <Link key={n.to} to={n.to} className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${loc.pathname === n.to ? 'bg-athena-700 text-white border-r-2 border-athena-accent' : 'text-athena-400 hover:text-white hover:bg-athena-700/50'}`}>
              <span>{n.icon}</span><span>{n.label}</span>
            </Link>
          ))}
        </div>
        <div className="p-3 border-t border-athena-700">
          <p className="text-athena-400 text-xs truncate">{name}</p>
          <button onClick={logout} className="text-athena-error text-xs hover:underline mt-1">Logout</button>
        </div>
      </nav>
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  )
}
