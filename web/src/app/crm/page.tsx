"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import HelpTooltip from "@/app/_components/HelpTooltip";

interface FunilData { categorias: string[]; series: {name:string;total:number;valor:number}[]; total_leads: number; total_negociacoes: number; total_propostas: number; etapas: string[]; }

const SUBMENU = [
  { href: "/crm/leads", label: "Leads", color: "bg-blue-600" },
  { href: "/crm/contatos", label: "Contatos", color: "bg-emerald-600" },
  { href: "/crm/empresas", label: "Empresas", color: "bg-purple-600" },
  { href: "/crm/negociacoes", label: "Negociacoes", color: "bg-amber-600" },
  { href: "/crm/agenda", label: "Agenda", color: "bg-pink-600" },
  { href: "/crm/propostas", label: "Propostas", color: "bg-indigo-600" },
  { href: "/crm/contratos", label: "Contratos", color: "bg-teal-600" },
];

const ETAPA_COLORS: Record<string, string> = {
  captacao: "bg-blue-600", qualificacao: "bg-cyan-600",
  prospeccao: "bg-yellow-600", proposta: "bg-orange-600",
  negociacao: "bg-pink-600", fechamento: "bg-emerald-600",
};

export default function CRMPage() {
  const [funil, setFunil] = useState<FunilData | null>(null);
  const [loading, setLoading] = useState(true);
  const [blingStatus, setBlingStatus] = useState<string | null>(null);
  const [blingCounts, setBlingCounts] = useState<{ empresas: number; contatos: number; leads: number; total: number } | null>(null);

  const importarBling = useCallback(async () => {
    setBlingStatus("Importando contatos do Bling...");
    setBlingCounts(null);
    try {
      const r = await fetch("/api/crm/importar-bling", { method: "POST" });
      const d = await r.json();
      if (d.error) {
        setBlingStatus("Erro: " + d.error);
        if (d.auth_url) setBlingStatus(status => status + " — Autorize em /integracoes/bling");
      } else {
        setBlingCounts(d);
        setBlingStatus("Importacao concluida!");
        fetch("/api/crm/funil").then(r => r.json()).then(d => setFunil(d)).catch(() => {});
      }
    } catch {
      setBlingStatus("Erro de conexao ao importar.");
    }
  }, []);

  useEffect(() => {
    fetch("/api/crm/funil")
      .then(r => r.json())
      .then(d => setFunil(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const maxValor = Math.max(1, ...(funil?.series.map(s => s.valor) || [1]));

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">CRM</h1>
        <p className="text-xs text-neutral-500 mt-1">Gestao de relacionamento com o cliente</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Leads</p>
          <p className="text-xl font-bold text-blue-400">{funil?.total_leads ?? 0}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Negociacoes</p>
          <p className="text-xl font-bold text-amber-400">{funil?.total_negociacoes ?? 0}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Propostas</p>
          <p className="text-xl font-bold text-indigo-400">{funil?.total_propostas ?? 0}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Conversao</p>
          <p className="text-xl font-bold text-emerald-400">{funil && funil.total_leads > 0 ? Math.round((funil.total_propostas / funil.total_leads) * 100) : 0}%</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={importarBling}
          disabled={blingStatus?.startsWith("Importando")}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg transition-colors"
        >
          {blingStatus?.startsWith("Importando") ? "⏳ Importando..." : "📥 Importar do Bling"}
        </button>
        {blingStatus && !blingStatus.startsWith("Importando") && blingCounts && (
          <span className="text-xs text-emerald-400">
            {blingStatus} ({blingCounts.empresas} empresas, {blingCounts.leads} leads, {blingCounts.contatos} contatos)
          </span>
        )}
        {blingStatus && !blingStatus.startsWith("Importando") && !blingCounts && (
          <span className="text-xs text-red-400">{blingStatus}</span>
        )}
      </div>
      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Funil de Vendas</h2>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <div className="flex items-end gap-2 h-32">
            {(funil?.etapas || []).map(etapa => {
              const s = funil?.series.find(x => x.name === etapa);
              const altura = s ? Math.max((s.valor / maxValor) * 100, 4) : 4;
              return (
                <div key={etapa} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[10px] text-neutral-300">{s ? s.total : 0}</span>
                  <div className={"w-full rounded-t-sm " + (ETAPA_COLORS[etapa] || "bg-neutral-600")}
                    style={{ height: altura + "%" }} />
                  <span className="text-[9px] text-neutral-500 capitalize">{etapa}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Modulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {SUBMENU.map(m => (
            <Link key={m.href} href={m.href} className={m.color + " hover:opacity-90 text-white rounded-lg p-4 transition-opacity"}>
              <p className="text-sm font-semibold">{m.label}</p>
              <p className="text-[10px] opacity-80 mt-1">Gerenciar {m.label.toLowerCase()}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
