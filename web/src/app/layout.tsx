"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import Icon from "./_components/Icon";
import { AuthProvider, useAuth } from "@/lib/auth";
import "./globals.css";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { href: "/cadastros", label: "Cadastros", icon: "cadastros" },
  { href: "/produtos", label: "Produtos", icon: "produtos" },
  { href: "/estoque", label: "Estoque", icon: "estoque" },
  { href: "/compras", label: "Compras", icon: "compras" },
  { href: "/vendas", label: "Vendas", icon: "vendas" },
  { href: "/pdv", label: "PDV", icon: "pdv" },
  { href: "/financeiro", label: "Financeiro", icon: "financeiro" },
  { href: "/fiscal", label: "Fiscal", icon: "fiscal" },
  { href: "/crm", label: "CRM", icon: "crm" },
  { href: "/atendimento", label: "Atendimento", icon: "atendimento" },
  { href: "/producao", label: "Produção", icon: "producao" },
  { href: "/rh", label: "RH", icon: "rh" },
  { href: "/bi", label: "BI", icon: "bi" },
  { href: "/documentos", label: "Documentos", icon: "documentos" },
  { href: "/automacoes", label: "Automações", icon: "automacoes" },
  { href: "/relatorios", label: "Relatórios", icon: "relatorios" },
  { href: "/agents", label: "Agentes", icon: "agents" },
  { href: "/integracoes/bling", label: "Bling", icon: "bling" },
  { href: "/hermes", label: "Hermes", icon: "agents" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [user, setUser] = useState<{ name: string; role: string } | null>(null);
  const [lojas, setLojas] = useState<Array<{ id: number; nome: string }>>([]);
  const [loja, setLoja] = useState<string>(() => {
    if (typeof window === "undefined") return "todas";
    return localStorage.getItem("loja") || "todas";
  });
  const pathname = usePathname();

  // Load lojas from API
  useEffect(() => {
    api.lojasManage().then(r => setLojas(r.lojas)).catch(() => {});
  }, []);

  // Auto-login: garante que sempre existe um token
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!localStorage.getItem("token")) {
      localStorage.setItem("token", "athena-token-123456789");
      localStorage.setItem("user", JSON.stringify({ name: "Admin", role: "admin" }));
      setUser({ name: "Admin", role: "admin" });
    } else {
      try {
        const cached = localStorage.getItem("user");
        if (cached) setUser(JSON.parse(cached));
      } catch {}
    }
  }, []);

  const logout = () => {
    fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
    window.location.href = "/login";
  };

  const isLogin = pathname === "/login";

  return (
    <html lang="pt-BR">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Athena</title>
      </head>
      <body className={`bg-neutral-950 text-neutral-100 min-h-screen ${!isLogin ? "flex" : ""}`}>
        {isLogin ? (
          children
        ) : (
          <AuthProvider>
          <>
            {/* Mobile backdrop */}
            {sidebarOpen && (
              <div className="sm:hidden fixed inset-0 bg-black/60 z-40" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
            )}

            {/* Sidebar */}
            <aside aria-label="Navegação principal" className={[
              "bg-neutral-900 border-r border-neutral-800 flex flex-col transition-all duration-200",
              "fixed inset-y-0 left-0 z-50 w-56",
              sidebarOpen ? "translate-x-0" : "-translate-x-full",
              "sm:relative sm:z-auto sm:inset-auto sm:translate-x-0 sm:shrink-0",
              sidebarOpen ? "sm:w-56" : "sm:w-14",
            ].join(" ")}>
          <div className="flex items-center justify-between p-3 border-b border-neutral-800">
            {sidebarOpen && (
              <span className="font-semibold text-sm tracking-wide select-none">ATHENA</span>
            )}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label={sidebarOpen ? "Recolher menu" : "Expandir menu"}
              aria-expanded={sidebarOpen}
              className="text-neutral-500 hover:text-neutral-300 text-lg leading-none p-1 rounded"
            >
              {sidebarOpen ? "◀" : "▶"}
            </button>
          </div>

          <nav className="flex-1 p-2 space-y-1" role="navigation">
            {NAV_ITEMS.map((item) => {
              const active = pathname?.startsWith(item.href);
              const modPerm = item.href.replace(/\//g,".").replace(/^./,"");
                if (modPerm && typeof window !== "undefined") {
                  const token = localStorage.getItem("token");
                  if (!token) return null;
                }
                return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                    active
                      ? "bg-indigo-600/20 text-indigo-300"
                      : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                  }`}
                >
                  <Icon name={item.icon} size={18} className="shrink-0" />
                  {sidebarOpen
                    ? <span>{item.label}</span>
                    : <span className="sr-only">{item.label}</span>
                  }
                </Link>
              );
            })}
          </nav>

          {/* Store selector */}
          {sidebarOpen && (
            <div className="px-3 pb-2">
              <label className="text-[9px] text-neutral-500 uppercase tracking-wider mb-1 block">Loja</label>
              <select
                value={loja}
                onChange={(e) => {
                  setLoja(e.target.value);
                  localStorage.setItem("loja", e.target.value);
                }}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="todas">🏢 Todas as Lojas</option>
                {lojas.map((l) => (
                  <option key={l.id} value={String(l.id)}>📍 {l.nome}</option>
                ))}
              </select>
            </div>
          )}
          {!sidebarOpen && (
            <div className="px-1.5 pb-2 flex justify-center">
              <span className="text-[9px] text-neutral-500 cursor-help" title={`Loja: ${loja}`}>🏢</span>
            </div>
          )}

          {user && (
            <div className="p-3 border-t border-neutral-800">
              {sidebarOpen ? (
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-neutral-300 truncate">{user.name}</div>
                    <div className="text-[10px] text-neutral-500 uppercase">{user.role}</div>
                  </div>
                  <button
                    onClick={logout}
                    className="text-neutral-500 hover:text-red-400 text-xs shrink-0 transition-colors"
                  >
                    sair
                  </button>
                </div>
              ) : (
                <button
                  onClick={logout}
                  aria-label="Sair"
                  className="text-neutral-500 hover:text-red-400 text-xs w-full text-center transition-colors"
                >
                  ⏻
                </button>
              )}
            </div>
          )}
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-auto min-w-0">
          {/* Mobile header — always visible, opens drawer */}
          <div className="sm:hidden flex items-center gap-3 px-4 py-3 border-b border-neutral-800 bg-neutral-900 sticky top-0 z-30">
            <button
              onClick={() => setSidebarOpen(true)}
              aria-label="Abrir menu"
              className="text-neutral-400 hover:text-neutral-200 text-lg leading-none"
            >
              ☰
            </button>
            <span className="font-semibold text-sm tracking-wide text-neutral-200 select-none">ATHENA</span>
          </div>
          {children}
        </main>
          </>
          </AuthProvider>
        )}
      </body>
    </html>
  );
}
