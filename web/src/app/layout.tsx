"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { JetBrains_Mono } from "next/font/google";
import { api } from "@/lib/api";
import Icon from "./_components/Icon";
import NotificationBell from "./_components/NotificationBell";
import { AuthProvider, useAuth } from "@/lib/auth";
import { StoreProvider, useStore, type LojaInfo } from "@/lib/store-context";
import { ThemeProvider, useTheme } from "@/lib/theme-context";
import "./globals.css";

// Roda antes da hidratacao (bloqueante no <head>) pra decidir o tema sem
// flash: le localStorage e ja carimba data-theme no <html> antes da 1a pintura.
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("theme");document.documentElement.setAttribute("data-theme",t==="light"?"light":"dark");}catch(e){}})();`;

const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400", "500", "600"] });

const NAV_PERMS: Record<string, string> = {
  "/dashboard": "dashboard:view",
  "/cadastros": "registrations:view",
  "/produtos": "products:view",
  "/estoque": "inventory:view",
  "/compras": "purchasing:view",
  "/vendas": "orders:view",
  "/pdv": "pdv:view",
  "/financeiro": "financial:view",
  "/fiscal": "fiscal.ver",
  "/crm": "crm:view",
  "/atendimento": "services:view",
  // Abas desativadas temporariamente (não usadas no momento) — ver NAV_ITEMS abaixo
  // "/producao": "manufacturing:view",
  // "/manutencao": "manufacturing:view",
  // "/qualidade": "manufacturing:view",
  // "/moldes": "manufacturing:view",
  // "/memory": "agents:view",
  "/rh": "hr:view",
  "/bi": "bi:view",
  "/documentos": "documents:view",
  "/automacoes": "automations:view",
  "/relatorios": "reports:view",
  "/agents": "agents:view",
  "/integracoes/bling": "integrations:view",
  "/bling": "integrations:view",
  "/hermes": "agents:view",
  "/roles": "roles:view",
  "/lojas": "cadastros:view",
  "/seguranca": "security:view",
};

// store: "fisica" | "virtual" marca um item (ou child) como exclusivo desse
// tipo de loja — some do menu quando uma loja do OUTRO tipo esta selecionada.
// Sem "store" = universal, sempre visivel independente da loja selecionada.
type NavChild = { href: string; label: string; store?: "fisica" | "virtual" };
type NavItem = { href: string; label: string; icon: string; store?: "fisica" | "virtual"; children?: NavChild[] };
// group: zona do painel — puramente de apresentação (agrupa visualmente),
// nunca muda href/rota/comportamento de nenhum item.
type NavGroup = { label: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Operação",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
    ],
  },
  {
    label: "Vendas",
    items: [
      {
        href: "/pdv", label: "PDV", icon: "pdv", store: "fisica",
        children: [
          { href: "/pdv", label: "Caixa (Terminal)" },
          { href: "/pdv/aprovacoes", label: "Aprovações de Sangria" },
          { href: "/pdv/quebra-caixa", label: "Quebra de Caixa" },
          { href: "/pdv/operadores", label: "Operadores" },
        ],
      },
      { href: "/vendas", label: "Vendas", icon: "vendas" },
      {
        href: "/integracoes", label: "Shopee", icon: "bling", store: "virtual",
        children: [
          { href: "/integracoes/shopee", label: "Config & Lojas" },
          { href: "/integracoes/shopee/dashboard", label: "Dashboard" },
          { href: "/integracoes/shopee/produtos", label: "Produtos" },
          { href: "/integracoes/shopee/pedidos", label: "Pedidos" },
          { href: "/shopee/regras", label: "Regras de Preco" },
          { href: "/shopee/kits", label: "Kits & Consistência de Preço" },
          { href: "/relatorios/dre-lojas", label: "DRE por Loja" },
          { href: "/integracoes/shopee-ads", label: "Shopee Ads" },
        ],
      },
      { href: "/crm", label: "CRM", icon: "crm" },
      { href: "/chat", label: "Chat", icon: "atendimento" },
    ],
  },
  {
    label: "Catálogo & Estoque",
    items: [
      { href: "/produtos", label: "Produtos", icon: "produtos", store: "fisica" },
      { href: "/cadastros", label: "Cadastros", icon: "cadastros" },
      { href: "/lojas", label: "Lojas", icon: "pdv" },
      {
        href: "/estoque", label: "Estoque", icon: "estoque",
        children: [
          { href: "/estoque", label: "Visão Geral" },
          { href: "/estoque/rapido", label: "Estoque Rápido", store: "virtual" },
          { href: "/estoque/entrada", label: "Entrada (Scanner)", store: "fisica" },
          { href: "/estoque/saida", label: "Saída", store: "fisica" },
          { href: "/estoque/transferencias", label: "Transferências", store: "fisica" },
          { href: "/estoque/aprovacoes", label: "Aprovações", store: "fisica" },
          { href: "/estoque/contagem", label: "Contagem Cíclica", store: "fisica" },
          { href: "/estoque/discrepancias", label: "Discrepâncias" },
          { href: "/estoque/rotacao", label: "Rotação", store: "fisica" },
        ],
      },
      { href: "/compras", label: "Compras", icon: "compras" },
    ],
  },
  {
    label: "Financeiro & Fiscal",
    items: [
      { href: "/financeiro", label: "Financeiro", icon: "financeiro" },
      { href: "/fiscal", label: "Fiscal", icon: "fiscal" },
      { href: "/rh", label: "RH", icon: "rh" },
    ],
  },
  {
    label: "Inteligência",
    items: [
      { href: "/bi", label: "BI", icon: "bi" },
      { href: "/relatorios", label: "Relatórios", icon: "relatorios" },
      { href: "/documentos", label: "Documentos", icon: "documentos" },
      { href: "/automacoes", label: "Automações", icon: "automacoes" },
      { href: "/agents", label: "Agentes", icon: "agents" },
      { href: "/hermes", label: "Hermes", icon: "agents" },
      {
        href: "/bling", label: "Bling", icon: "bling",
        children: [
          { href: "/bling", label: "Dashboard" },
          { href: "/bling/produtos", label: "Produtos" },
          { href: "/bling/pedidos-venda", label: "Pedidos de Venda" },
          { href: "/bling/pedidos-compra", label: "Pedidos de Compra" },
          { href: "/bling/situacoes", label: "Situações" },
          { href: "/bling/canais", label: "Lojas/Canais" },
          { href: "/bling/financeiro", label: "Financeiro" },
          { href: "/bling/notas", label: "Notas Fiscais" },
          { href: "/bling/plano-contas", label: "Contas Contábeis" },
          { href: "/bling/config", label: "Configurações" },
        ],
      },
    ],
  },
  {
    label: "Administração",
    items: [
      { href: "/roles", label: "Cargos", icon: "cadastros" },
      {
        href: "/seguranca", label: "Segurança", icon: "cadastros",
        children: [
          { href: "/seguranca/auditoria", label: "Auditoria" },
          { href: "/seguranca/logs", label: "Logs" },
          { href: "/seguranca/historico", label: "Histórico" },
          { href: "/seguranca/rbac", label: "RBAC" },
        ],
      },
      { href: "/config", label: "Configurações", icon: "cadastros" },
    ],
  },
];
// Abas desativadas temporariamente (não usadas no momento, fora dos grupos):
// producao, manutencao, qualidade, moldes, memory

// null (loja "todas", ou sem tipo definido) mostra tudo. Fisica esconde itens
// marcados "virtual"; Virtual esconde itens marcados "fisica".
function filtrarNavPorTipoLoja(groups: NavGroup[], tipo: "fisica" | "virtual" | null): NavGroup[] {
  if (!tipo) return groups;
  return groups
    .map(group => ({
      label: group.label,
      items: group.items
        .filter(item => !item.store || item.store === tipo)
        .map(item => item.children
          ? { ...item, children: item.children.filter(c => !c.store || c.store === tipo) }
          : item)
        .filter(item => !item.children || item.children.length > 0),
    }))
    .filter(group => group.items.length > 0);
}

function Sidebar({ sidebarOpen, setSidebarOpen }: { sidebarOpen: boolean; setSidebarOpen: (v: boolean) => void }) {
  const { user, logout } = useAuth();
  const { lojaId, lojas, setLojaId, tipoLojaSelecionada } = useStore();
  const { theme, toggleTheme } = useTheme();
  const [expandedMenu, setExpandedMenu] = useState<string | null>(null);
  const pathname = usePathname();
  const navGroups = filtrarNavPorTipoLoja(NAV_GROUPS, tipoLojaSelecionada);
  const lojaAtual = lojas.find(l => String(l.id) === lojaId);
  const lojaIcon = lojaId === "todas" ? "building2" : lojaAtual?.tipo === "virtual" ? "globe" : "building2";

  return (
    <aside aria-label="Navegação principal" className={[
      "flex flex-col transition-[width] duration-200 border-r",
      "fixed inset-y-0 left-0 z-50 w-60",
      sidebarOpen ? "translate-x-0" : "-translate-x-full",
      "sm:relative sm:z-auto sm:inset-auto sm:translate-x-0 sm:shrink-0",
      sidebarOpen ? "sm:w-60" : "sm:w-14",
    ].join(" ")} style={{ background: "var(--panel-900)", borderColor: "var(--panel-border)" }}>
      <div className="flex items-center justify-between px-3 h-12 shrink-0" style={{ borderBottom: "1px solid var(--panel-border)" }}>
        {sidebarOpen && (
          <span className="flex items-center gap-2 select-none">
            <span aria-hidden className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent-400)", boxShadow: "0 0 6px var(--accent-400)" }} />
            <span className="font-semibold text-[13px] tracking-[0.14em]" style={{ color: "var(--ink-100)" }}>ATHENA</span>
          </span>
        )}
        <div className="flex items-center gap-0.5">
          {sidebarOpen && (
            <button
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro"}
              title={theme === "dark" ? "Tema claro" : "Tema escuro"}
              className="p-1.5 rounded transition-colors hover-surface"
              style={{ color: "var(--ink-500)" }}
            >
              <Icon name={theme === "dark" ? "sun" : "moon"} size={15} />
            </button>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? "Recolher menu" : "Expandir menu"}
            aria-expanded={sidebarOpen}
            className="p-1.5 rounded transition-colors hover-surface"
            style={{ color: "var(--ink-500)" }}
          >
            <Icon name={sidebarOpen ? "chevronLeft" : "chevronRight"} size={15} />
          </button>
        </div>
      </div>

      {sidebarOpen ? (
        <div className="px-3 pt-3 pb-3" style={{ borderBottom: "1px solid var(--panel-border)" }}>
          <label className="text-[9px] uppercase tracking-[0.12em] mb-1.5 flex items-center gap-1.5" style={{ color: "var(--ink-700)" }}>
            <Icon name={lojaIcon} size={11} />
            Loja em operação
          </label>
          <select
            value={lojaId}
            onChange={(e) => setLojaId(e.target.value)}
            className="w-full rounded px-2.5 py-1.5 text-xs focus:outline-none transition-colors"
            style={{ background: "var(--panel-800)", border: "1px solid var(--panel-700)", color: "var(--ink-100)" }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "var(--accent-500)")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "var(--panel-700)")}
          >
            <option value="todas">Todas as Lojas</option>
            {lojas.map((l) => (
              <option key={l.id} value={String(l.id)}>{l.tipo === "virtual" ? "Virtual — " : "Física — "}{l.nome}</option>
            ))}
          </select>
        </div>
      ) : (
        <div className="py-2.5 flex justify-center" style={{ borderBottom: "1px solid var(--panel-border)" }} title={`Loja: ${lojaAtual?.nome ?? "Todas"}`}>
          <Icon name={lojaIcon} size={15} className="shrink-0" style={{ color: "var(--ink-500)" }} />
        </div>
      )}

      <nav className="flex-1 px-2 pt-2 pb-2 space-y-3 overflow-y-auto" role="navigation">
        {navGroups.map((group) => (
          <div key={group.label}>
            {sidebarOpen && (
              <div className="px-2 pb-1 text-[9px] uppercase tracking-[0.12em] select-none" style={{ color: "var(--ink-700)" }}>
                {group.label}
              </div>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = pathname?.startsWith(item.href);
                const hasChildren = item.children && item.children.length > 0;
                const isExpanded = expandedMenu === item.href;

                if (hasChildren) {
                  return (
                    <div key={item.href}>
                      <button
                        onClick={() => setExpandedMenu(isExpanded ? null : item.href)}
                        className="flex items-center gap-3 px-2.5 py-1.5 rounded text-[13px] transition-colors w-full text-left"
                        style={active || isExpanded
                          ? { background: "var(--accent-glow)", color: "var(--accent-400)" }
                          : { color: "var(--ink-300)" }}
                      >
                        <Icon name={item.icon} size={16} className="shrink-0" />
                        {sidebarOpen && (
                          <>
                            <span className="flex-1">{item.label}</span>
                            <Icon name="chevronDown" size={11} className={"transition-transform shrink-0 " + (isExpanded ? "rotate-180" : "")} />
                          </>
                        )}
                      </button>
                      {sidebarOpen && isExpanded && item.children && (
                        <div className="ml-[19px] mt-0.5 space-y-0.5 pl-2.5" style={{ borderLeft: "1px solid var(--panel-border)" }}>
                          {item.children.map((child) => {
                            const childActive = pathname === child.href;
                            return (
                              <Link
                                key={child.href}
                                href={child.href}
                                className="block px-2.5 py-1 rounded text-xs transition-colors"
                                style={childActive
                                  ? { background: "var(--accent-glow)", color: "var(--accent-400)" }
                                  : { color: "var(--ink-500)" }}
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
                    className="flex items-center gap-3 px-2.5 py-1.5 rounded text-[13px] transition-colors"
                    style={active
                      ? { background: "var(--accent-glow)", color: "var(--accent-400)" }
                      : { color: "var(--ink-300)" }}
                  >
                    <Icon name={item.icon} size={16} className="shrink-0" />
                    {sidebarOpen
                      ? <span>{item.label}</span>
                      : <span className="sr-only">{item.label}</span>
                    }
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {user && (
        <div className="px-3 py-2.5 shrink-0" style={{ borderTop: "1px solid var(--panel-border)" }}>
          {sidebarOpen ? (
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="text-xs font-medium truncate" style={{ color: "var(--ink-300)" }}>{user.name}</div>
                <div className="text-[9px] uppercase tracking-wide" style={{ color: "var(--ink-700)" }}>{user.role}</div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <NotificationBell />
                <button
                  onClick={logout}
                  aria-label="Sair"
                  className="p-1.5 rounded shrink-0 transition-colors hover-surface"
                  style={{ color: "var(--ink-700)" }}
                >
                  <Icon name="power" size={14} />
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={logout}
              aria-label="Sair"
              className="w-full flex justify-center p-1.5 rounded transition-colors hover-surface"
              style={{ color: "var(--ink-700)" }}
            >
              <Icon name="power" size={14} />
            </button>
          )}
        </div>
      )}
    </aside>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Aberto por padrao em desktop, fechado em mobile — o valor inicial so'
  // e' conhecido no cliente (matchMedia), entao comeca fechado (seguro em
  // mobile) e o effect ajusta pra aberto se a tela ja' for >= sm (640px)
  // antes da 1a pintura relevante, sem popular a tela com o menu por cima
  // do conteudo no primeiro load mobile.
  const [sidebarOpen, setSidebarOpen] = useState(false);
  useEffect(() => {
    if (window.matchMedia("(min-width: 640px)").matches) setSidebarOpen(true);
  }, []);
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  return (
    <html lang="pt-BR" className={mono.variable} suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Athena</title>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className={`min-h-screen ${!isLogin ? "flex" : ""}`}>
        <ThemeProvider>
        {isLogin ? (
          children
        ) : (
          <AuthProvider>
            <StoreProvider>
            <>
              {/*
                THESIS: an ERP shell reads like an instrument panel, not a SaaS dashboard —
                every module is a dedicated readout, not a decorative card.
                OWN-WORLD: near-black cooled ground (panel-9xx tokens), bordered "instrument"
                faces, tabular-mono numerals, color spent only as status (ok/warn/crit), a
                single signature cyan accent for navigation and identity.
                STORY: an operator scans one screen and trusts the number without re-reading
                it; navigation groups into panel zones (Vendas, Estoque, Financeiro...).
                FIRST VIEWPORT: fixed instrument-panel sidebar (zoned nav) plus a dashboard
                grid of differently-weighted instruments, cash position reading largest.
                FORM: cockpit instrument panel, direction 7 of 7 (assigned), seed 8363d831.
                FINISH: unreviewed and undocumented is unfinished; this build ends with the
                finish review, the verdict, and DESIGN.md.
              */}
              {sidebarOpen && (
                <div className="sm:hidden fixed inset-0 bg-black/60 z-40" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
              )}
              <Sidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
              <main className="flex-1 overflow-auto min-w-0">
                <div className="sm:hidden flex items-center gap-3 px-4 h-12 sticky top-0 z-30" style={{ background: "var(--panel-900)", borderBottom: "1px solid var(--panel-border)" }}>
                  <button
                    onClick={() => setSidebarOpen(true)}
                    aria-label="Abrir menu"
                    className="p-1 -ml-1 rounded"
                    style={{ color: "var(--ink-300)" }}
                  >
                    <Icon name="menu" size={19} />
                  </button>
                  <span className="flex items-center gap-2 select-none">
                    <span aria-hidden className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent-400)", boxShadow: "0 0 6px var(--accent-400)" }} />
                    <span className="font-semibold text-[13px] tracking-[0.14em]" style={{ color: "var(--ink-100)" }}>ATHENA</span>
                  </span>
                </div>
                {(() => {
                  const parts = pathname?.split("/").filter(Boolean) || [];
                  if (parts.length < 2) return null;
                  const parentPath = "/" + parts.slice(0, -1).join("/");
                  const parentLabel = parts[parts.length - 2]?.replace(/-/g, " ").replace(/\w/g, c => c.toUpperCase()) || "Voltar";
                  return (
                    <div className="px-4 pt-3 pb-1">
                      <Link href={parentPath} className="inline-flex items-center gap-1 text-xs transition-colors" style={{ color: "var(--ink-500)" }}>
                        <Icon name="chevronLeft" size={13} />
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
        </ThemeProvider>
      </body>
    </html>
  );
}
