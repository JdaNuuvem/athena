import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Package, Boxes, Factory, Drill, Users, Shield, Sliders } from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/orders', icon: Package, label: 'Pedidos' },
  { to: '/inventory', icon: Boxes, label: 'Estoque' },
  { to: '/production', icon: Factory, label: 'Produção' },
  { to: '/molds', icon: Drill, label: 'Moldes & CNC' },
  { to: '/customers', icon: Users, label: 'Clientes' },
  { to: '/admin', icon: Shield, label: 'Admin' },
  { to: '/settings', icon: Sliders, label: 'Config' },
]

export function Sidebar() {
  return (
    <aside className="w-56 bg-slate-900 border-r border-slate-700 flex flex-col h-screen sticky top-0">
      <div className="p-4 border-b border-slate-700">
        <h1 className="text-sky-400 font-bold text-lg tracking-tight">ATHENA OS</h1>
        <p className="text-slate-500 text-[10px] uppercase tracking-widest mt-0.5">Dashboard</p>
      </div>
      <nav className="flex-1 p-2 space-y-0.5">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? 'bg-sky-500/10 text-sky-400 font-medium'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-slate-700 text-[10px] text-slate-600 text-center">
        v0.1.0 — ATHENA OS
      </div>
    </aside>
  )
}
