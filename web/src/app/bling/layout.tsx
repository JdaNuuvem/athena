"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Icon from "@/app/_components/Icon";
import { getBlingAmbiente } from "@/lib/api";

// Icon.tsx nao tem engrenagem — a tela antiga ja resolvia isso com SVG inline.
function GearIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

// Ordem espelha a do spec do modulo. Toda entrada aqui precisa ter um
// diretorio com page.tsx em web/src/app/bling/ — link pra rota inexistente
// vira 404 silencioso na navegacao.
const SUBMENU: Array<{ href: string; label: string; icon?: string }> = [
  { href: "/bling", label: "Dashboard", icon: "dashboard" },
  { href: "/bling/produtos", label: "Produtos", icon: "produtos" },
  { href: "/bling/pedidos-venda", label: "Pedidos de Venda", icon: "vendas" },
  { href: "/bling/pedidos-compra", label: "Pedidos de Compra", icon: "compras" },
  { href: "/bling/situacoes", label: "Situações", icon: "check" },
  { href: "/bling/canais", label: "Lojas/Canais", icon: "globe" },
  { href: "/bling/financeiro", label: "Financeiro", icon: "financeiro" },
  { href: "/bling/notas", label: "Notas Fiscais", icon: "fiscal" },
  { href: "/bling/plano-contas", label: "Contas Contábeis", icon: "bi" },
  { href: "/bling/config", label: "Configurações" },
];

export default function BlingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [ambiente, setAmbiente] = useState<string>("");

  useEffect(() => {
    getBlingAmbiente()
      .then((r) => setAmbiente(r.ambiente || ""))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Bling</h1>
          <p className="text-xs text-neutral-500 mt-1">
            Integração ERP — catálogo, vendas, financeiro e fiscal
          </p>
        </div>
        {ambiente === "homologacao" && (
          <span className="shrink-0 px-2 py-1 rounded-md text-[11px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            Homologação
          </span>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <nav className="lg:w-52 shrink-0">
          <ul className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible">
            {SUBMENU.map((item) => {
              const ativo = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs whitespace-nowrap transition-colors ${
                      ativo
                        ? "bg-indigo-600 text-white"
                        : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                    }`}
                  >
                    {item.icon ? <Icon name={item.icon} size={14} /> : <GearIcon />}
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </div>
  );
}
