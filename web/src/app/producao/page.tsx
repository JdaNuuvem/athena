"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import HelpTooltip from "@/app/_components/HelpTooltip";

const MODULOS = [
  { href: "/producao/ops", label: "OPs" title="Ordens de Producao — planejamento e execucao de fabricacao", color: "bg-blue-600", help: "Ordens de Producao — planejamento e execucao de fabricacao" },
  { href: "/producao/bom", label: "BOM" title="Bill of Materials — lista de materiais e componentes necessarios", color: "bg-purple-600", help: "Bill of Materials — lista de materiais e componentes necessarios" },
  { href: "/producao/maquinas", label: "Maquinas" title="Cadastro e status de maquinas do parque fabril", color: "bg-teal-600", help: "Cadastro e status de maquinas do parque fabril" },
  { href: "/producao/apontamentos", label: "Apontamentos" title="Registro de producao — quantidade boa, refugo e horas trabalhadas", color: "bg-amber-600", help: "Registro de producao — quantidade boa, refugo e horas trabalhadas" },
  { href: "/producao/consumo", label: "Consumo" title="Consumo real de materias-primas vs previsto", color: "bg-pink-600", help: "Consumo real de materias-primas vs previsto" },
  { href: "/producao/perdas", label: "Perdas" title="Registro de perdas e refugos por motivo", color: "bg-red-600", help: "Registro de perdas e refugos por motivo" },
  { href: "/producao/custos", label: "Custos" title="Custos de producao por OP", color: "bg-indigo-600", help: "Custos de producao por OP — materia-prima, mao de obra, energia" },
];

export default function ProducaoPage() {
  const [dash, setDash] = useState<any>(null);
  useEffect(() => { fetch("/api/producao/dashboard").then(r=>r.json()).then(setDash).catch(()=>{}); }, []);
  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">Producao</h1><p className="text-xs text-neutral-500 mt-1">OPs, BOM, Maquinas, Apontamentos, Custos e Perdas</p></div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4" title="Ordens de Producao ativas no momento"><p className="text-xs text-neutral-500">OPs Ativas <HelpTooltip text="Ordens de Producao em andamento" /></p><p className="text-xl font-bold text-blue-400">{dash?.ops_ativas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4" title="OPs iniciadas hoje"><p className="text-xs text-neutral-500">OPs Hoje <HelpTooltip text="Ordens iniciadas na data de hoje" /></p><p className="text-xl font-bold text-amber-400">{dash?.ops_hoje??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Maquinas Ativas</p><p className="text-xl font-bold text-emerald-400">{dash?.maquinas_ativas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Maquinas Paradas</p><p className="text-xl font-bold text-red-400">{dash?.maquinas_paradas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Perdas</p><p className="text-xl font-bold text-orange-400">{dash?.total_perdas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4" title="Rendimento = (pecas boas / total) * 100"><p className="text-xs text-neutral-500">Rendimento <HelpTooltip text="Percentual de pecas boas sobre o total produzido" /></p><p className="text-xl font-bold text-emerald-400">{dash?.rendimento_pct??0}%</p></div>
      </div>
      <div><h2 className="text-sm font-semibold text-neutral-300 mb-3">Modulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {MODULOS.map(m => (
            <Link key={m.href} href={m.href} title={m.help} className={m.color + " hover:opacity-90 text-white rounded-lg p-4 transition-opacity group"}>
              <div className="flex items-center gap-1.5">
                <p className="text-sm font-semibold">{m.label}</p>
                <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[9px] bg-white/20 rounded-full w-4 h-4 flex items-center justify-center">?</span>
              </div>
            </Link>
          ))}</div>
      </div>
    </div>
  );
}
