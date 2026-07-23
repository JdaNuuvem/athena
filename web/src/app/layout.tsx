"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import Icon from "./_components/Icon";
import { AuthProvider, useAuth } from "@/lib/auth";
import { StoreProvider, useStore, type LojaInfo } from "@/lib/store-context";
import "./globals.css";

const NAV_PERMS: Record<string, string> = {
  "/dashboard": "dashboard:view",
  "/cadastros": "registrations:view",
  "/produtos": "products:view",
  "/estoque": "inventory:view",
  "/compras": "purchasing:view",
  "/vendas": "orders:view",
  "/pdv": "pdv:view",
  "/financeiro": "financial:view",
  "/fiscal": "fiscal:view",
  "/crm": "crm:view",
  "/atendimento": "services:view",
  "/producao": "manufacturing:view",
  "/rh": "hr:view",
  "/bi": "bi:view",
  "/documentos": "documents:view",
  "/automacoes": "automations:view",
  "/relatorios": "reports:view",
  "/agents": "agents:view",
  "/integracoes/bling": "integrations:view",
  "/hermes": "agents:view",
  "/roles": "roles:view",
  "/lojas": "cadastros:view",
};

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { href: "/cadastros", label: "Cadastros", icon: "cadastros" },
  { href: "/lojas", label: "Lojas", icon: "pdv" },
  { href: "/atendimento/chat", label: "Chat", icon: "atendimento" },
  { href: "/produtos", label: "Produtos", icon: "produtos" },
  { href: "/estoque", label: "Estoque", icon: "estoque" },
  { href: "/estoque/rotacao", label: "Rotação", icon: "estoque" },
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
  {
    href: "/integracoes", label: "Shopee", icon: "bling",
    children: [
      { href: "/integracoes/shopee", label: "Config & Lojas" },
      { href: "/shopee/regras", label: "Regras de Preco" },
      { href: "/shopee/kits", label: "Kits & Consistência de Preço" },
      { href: "/relatorios/dre-lojas", label: "DRE por Loja" },
    ],
  },
  { href: "/integracoes/bling", label: "Bling", icon: "bling" },
  { href: "/hermes", label: "Hermes", icon: "agents" },
  { href: "/roles", label: "Cargos", icon: "cadastros" },
  { href: "/config", label: "Configurações", icon: "cadastros" },
];

function Sidebar() {
  const { user, hasPermission, logout } = useAuth();
  const { lojaId, lojas, setLojaId } = useStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [expandedMenu, setExpandedMenu] = useState<string | null>(null);
  const pathname = usePathname();

  return (
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

      <nav className="flex-1 p-2 space-y-1 overflow-y-auto" role="navigation">
        {NAV_ITEMS.map((item) => {
          const active = pathname?.startsWith(item.href);
          const hasChildren = item.children && item.children.length > 0;
          const isExpanded = expandedMenu === item.href;

          if (hasChildren) {
            return (
              <div key={item.href}>
                <button
                  onClick={() => setExpandedMenu(isExpanded ? null : item.href)}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors w-full text-left ${
                    active || isExpanded
                      ? "bg-indigo-600/20 text-indigo-300"
                      : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                  }`}
                >
                  <Icon name={item.icon} size={18} className="shrink-0" />
                  {sidebarOpen && (
                    <>
                      <span className="flex-1">{item.label}</span>
                      <span className="text-[10px]">{isExpanded ? "▾" : "▸"}</span>
                    </>
                  )}
                </button>
                {sidebarOpen && isExpanded && item.children && (
                  <div className="ml-5 mt-0.5 space-y-0.5 border-l border-neutral-800 pl-2">
                    {item.children.map((child) => {
                      const childActive = pathname === child.href;
                      return (
                        <Link
                          key={child.href}
                          href={child.href}
                          className={`block px-3 py-1.5 rounded-lg text-xs transition-colors ${
                            childActive
                              ? "bg-indigo-600/30 text-indigo-200"
                              : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
                          }`}
                        >
                          {child.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
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

      {sidebarOpen && (
        <div className="px-3 pb-2">
          <label className="text-[9px] text-neutral-500 uppercase tracking-wider mb-1 block">Loja</label>
          <select
            value={lojaId}
            onChange={(e) => setLojaId(e.target.value)}
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
          <span className="text-[9px] text-neutral-500 cursor-help" title={`Loja: ${lojaId}`}>🏢</span>
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
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const pathname = usePathname();
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
            <StoreProvider>
            <>
              {sidebarOpen && (
                <div className="sm:hidden fixed inset-0 bg-black/60 z-40" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
              )}
              <Sidebar />
              <main className="flex-1 overflow-auto min-w-0">
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
                {(() => {
                  const parts = pathname?.split("/").filter(Boolean) || [];
                  if (parts.length < 2) return null;
                  const parentPath = "/" + parts.slice(0, -1).join("/");
                  const parentLabel = parts[parts.length - 2]?.replace(/-/g, " ").replace(/\w/g, c => c.toUpperCase()) || "Voltar";
                  return (
                    <div className="px-4 pt-3 pb-1">
                      <Link href={parentPath} className="inline-flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-300 transition-colors">
                        <span className="text-base leading-none">&larr;</span>
                        <span>{parentLabel}</span>
                      </Link>
                    </div>
                  );
                })()}
                {children}
              </main>
            </>
            </StoreProvider>
          </AuthProvider>
        )}
      </body>
    </html>
  );
}
