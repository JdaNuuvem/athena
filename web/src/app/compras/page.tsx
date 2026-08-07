"use client";

import { useState, useEffect } from "react";
import Icon from "../_components/Icon";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import PedidosTab from "./_components/PedidosTab";
import SolicitacoesTab from "./_components/SolicitacoesTab";
import CotacoesTab from "./_components/CotacoesTab";
import RecebimentosTab from "./_components/RecebimentosTab";
import NotasTab from "./_components/NotasTab";
import FornecedoresTab from "./_components/FornecedoresTab";

const TABS = [
  { key: "pedidos", label: "Pedidos", icon: "compras", Component: PedidosTab },
  { key: "solicitacoes", label: "Solicitações", icon: "alert", Component: SolicitacoesTab },
  { key: "cotacoes", label: "Cotações", icon: "relatorios", Component: CotacoesTab },
  { key: "recebimentos", label: "Recebimentos", icon: "truck", Component: RecebimentosTab },
  { key: "notas", label: "Notas de Entrada", icon: "documentos", Component: NotasTab },
  { key: "fornecedores", label: "Fornecedores", icon: "building2", Component: FornecedoresTab },
];

function KpiCards() {
  const [dash, setDash] = useState<{ pendentes: number; pedidos_abertos: number; total_recebido: number } | null>(null);

  useEffect(() => { api.comprasDashboard().then(setDash).catch(() => {}); }, []);

  const cards = [
    { label: "Solicitações Pendentes", valor: dash ? String(dash.pendentes) : "—" },
    { label: "Pedidos em Aberto", valor: dash ? String(dash.pedidos_abertos) : "—" },
    { label: "Total Recebido", valor: dash ? fmtBRL(dash.total_recebido) : "—" },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {cards.map(c => (
        <div key={c.label} className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
          <p className="text-[10px] text-neutral-500">{c.label}</p>
          <p className="mt-0.5 text-lg font-semibold text-neutral-100">{c.valor}</p>
        </div>
      ))}
    </div>
  );
}

export default function ComprasPage() {
  const [activeTab, setActiveTab] = useState("pedidos");
  const active = TABS.find((t) => t.key === activeTab) ?? TABS[0];

  return (
    <div className="p-6 space-y-5 max-w-[1400px]">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
          <Icon name="compras" size={20} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-neutral-100">Compras</h1>
          <p className="text-xs text-neutral-500">Registro de todas as compras: solicitações, cotações, pedidos, recebimentos e notas de entrada</p>
        </div>
      </div>

      <KpiCards />

      <nav className="flex flex-wrap gap-1 rounded-xl border border-neutral-800 bg-neutral-900/50 p-1.5" aria-label="Categorias de compras">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            aria-current={activeTab === tab.key ? "page" : undefined}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200"
            }`}
          >
            <Icon name={tab.icon} size={15} />
            {tab.label}
          </button>
        ))}
      </nav>

      <active.Component key={active.key} />
    </div>
  );
}
