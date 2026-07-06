import { NavLink } from "react-router-dom"
import { LayoutDashboard, Package, Boxes, Factory, Drill, Users, Shield, Sliders, DollarSign, Scale, LogOut } from "lucide-react"

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Overview" },
  { to: "/orders", icon: Package, label: "Pedidos" },
  { to: "/inventory", icon: Boxes, label: "Estoque" },
  { to: "/production", icon: Factory, label: "Producao" },
  { to: "/molds", icon: Drill, label: "Moldes & CNC" },
  { to: "/customers", icon: Users, label: "Clientes" },
  { to: "/finance", icon: DollarSign, label: "Financeiro" },
  { to: "/tax-intelligence", icon: Scale, label: "Tributario" },
  { to: "/admin", icon: Shield, label: "Admin" },
  { to: "/settings", icon: Sliders, label: "Config" },
]

export function Sidebar() {
  const user = (() => { try { return JSON.parse(localStorage.getItem("athena_user") || "") } catch { return null } })()

  return (
    <aside className="w-56 bg-slate-900/95 backdrop-blur border-r border-slate-800 flex flex-col h-screen sticky top-0">
      <div className="p-5 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-500 to-sky-600 flex items-center justify-center">
            <span className="text-white font-black text-sm">A</span>
          </div>
          <div>
            <h1 className="text-sky-400 font-bold text-base tracking-tight leading-none">ATHENA OS</h1>
            <p className="text-slate-600 text-[10px] uppercase tracking-[0.2em] mt-0.5">Dashboard</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-2 px-2">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 mb-0.5 ${
                isActive
                  ? "bg-sky-500/10 text-sky-400 font-medium border border-sky-500/20 shadow-sm shadow-sky-500/5"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`
            }
          >
            <Icon size={16} className="shrink-0" />
            <span className="truncate">{label}</span>
          </NavLink>
        ))}
      </nav>

      {user && (
        <div className="p-3 border-t border-slate-800 mx-2 mb-1">
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg bg-slate-800/50">
            <div className="w-7 h-7 rounded-full bg-sky-500/20 flex items-center justify-center text-xs text-sky-400 font-bold">
              {user.name?.[0]?.toUpperCase() || "A"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-slate-300 truncate">{user.name || "Admin"}</p>
              <p className="text-[10px] text-slate-500 capitalize">{user.role || "admin"}</p>
            </div>
            <button
              onClick={() => { localStorage.clear(); window.location.reload() }}
              className="text-slate-500 hover:text-red-400 transition-colors"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      )}
    </aside>
  )
}