"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";
import "./globals.css";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "⊞" },
  { href: "/agents", label: "Agentes", icon: "◈" },
  { href: "/produtos", label: "Produtos", icon: "◇" },
  { href: "/workflows", label: "Workflows", icon: "⇄" },
  { href: "/metrics", label: "Métricas", icon: "▤" },
  { href: "/business", label: "Operações", icon: "⚙" },
  { href: "/integracoes", label: "Integrações", icon: "↔" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [user, setUser] = useState<{ name: string; role: string } | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  const checked = useRef(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token && pathname !== "/login") {
      router.push("/login");
      return;
    }
    if (token && !checked.current) {
      checked.current = true;
      api.me()
        .then((d) => setUser(d))
        .catch(() => { localStorage.removeItem("token"); router.push("/login"); });
    }
  }, [pathname]);

  // Close mobile drawer on navigation
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 640) {
      setSidebarOpen(false);
    }
  }, [pathname]);

  const logout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  if (pathname === "/login") {
    return (
      <html lang="pt-BR">
        <head>
          <title>Hermes — Login</title>
          <meta name="viewport" content="width=device-width, initial-scale=1" />
        </head>
        <body className="bg-neutral-950 text-neutral-100 min-h-screen">{children}</body>
      </html>
    );
  }

  return (
    <html lang="pt-BR">
      <head>
        <title>Hermes — Athena</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className="bg-neutral-950 text-neutral-100 min-h-screen flex">

        {/* Mobile backdrop */}
        {sidebarOpen && (
          <div
            className="sm:hidden fixed inset-0 bg-black/60 z-40"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Sidebar */}
        <aside
          aria-label="Navegação principal"
          className={[
            "bg-neutral-900 border-r border-neutral-800 flex flex-col",
            "transition-all duration-200",
            // Mobile: fixed overlay drawer, always full width
            "fixed inset-y-0 left-0 z-50 w-56",
            sidebarOpen ? "translate-x-0" : "-translate-x-full",
            // Desktop: in-flow, collapsible width
            "sm:relative sm:z-auto sm:inset-auto sm:translate-x-0 sm:shrink-0",
            sidebarOpen ? "sm:w-56" : "sm:w-14",
          ].join(" ")}
        >
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
                  <span className="text-base w-5 text-center shrink-0" aria-hidden="true">
                    {item.icon}
                  </span>
                  {sidebarOpen
                    ? <span>{item.label}</span>
                    : <span className="sr-only">{item.label}</span>
                  }
                </Link>
              );
            })}
          </nav>

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

      </body>
    </html>
  );
}
