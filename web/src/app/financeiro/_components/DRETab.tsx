"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";
import SidebarLayout from "../../cadastros/_components/SidebarLayout";

const SUB_ITEMS = [
  { key: "lucro", label: "Lucro" },
  { key: "prejuizo", label: "Prejuízo" },
  { key: "rateio", label: "Rateio" },
];

interface DreItem { id: number; mes: string; descricao: string; valor: number; tipo: string; categoria: string; }

export default function DRETab() {
  const [dre, setDre] = useState<{ receitas: number; despesas: number; resultado: number; lucro: boolean; items: DreItem[] }>({ receitas: 0, despesas: 0, resultado: 0, lucro: false, items: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.finDREResumo().then((r) => setDre(r as typeof dre)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  function renderContent(key: string) {
    if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;
    const receitas = dre.items.filter((i) => i.tipo === "receita");
    const despesas = dre.items.filter((i) => i.tipo === "despesa");

    switch (key) {
      case "lucro": {
        const total = receitas.reduce((s, i) => s + i.valor, 0);
        return (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-neutral-200">Demonstração de Lucro</h3>
            <div className="grid grid-cols-2 gap-3"><div className="bg-neutral-700/30 rounded-lg p-3"><p className="text-[10px] text-neutral-500">Receita Total</p><p className="text-sm font-semibold text-emerald-400">{fmt(total)}</p></div><div className="bg-neutral-700/30 rounded-lg p-3"><p className="text-[10px] text-neutral-500">Margem</p><p className="text-sm font-semibold text-blue-400">{dre.receitas > 0 ? Math.round((dre.resultado / dre.receitas) * 100) : 0}%</p></div></div>
            <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-3 py-2 font-medium">Categoria</th><th className="px-3 py-2 font-medium">Valor</th></tr></thead>
              <tbody>{receitas.map((i) => (
                <tr key={i.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-3 py-2">{i.categoria}</td><td className="px-3 py-2 text-emerald-400">{fmt(i.valor)}</td></tr>
              ))}</tbody></table>
          </div>
        );
      }
      case "prejuizo": {
        const totalD = despesas.reduce((s, i) => s + Math.abs(i.valor), 0);
        return (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-neutral-200">Demonstração de Prejuízo</h3>
            <div className="grid grid-cols-2 gap-3"><div className="bg-neutral-700/30 rounded-lg p-3"><p className="text-[10px] text-neutral-500">Despesa Total</p><p className="text-sm font-semibold text-red-400">{fmt(totalD)}</p></div><div className="bg-neutral-700/30 rounded-lg p-3"><p className="text-[10px] text-neutral-500">% sobre Receita</p><p className="text-sm font-semibold text-amber-400">{dre.receitas > 0 ? Math.round((totalD / dre.receitas) * 100) : 0}%</p></div></div>
            <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-3 py-2 font-medium">Categoria</th><th className="px-3 py-2 font-medium">Valor</th></tr></thead>
              <tbody>{despesas.map((i) => (
                <tr key={i.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-3 py-2">{i.categoria}</td><td className="px-3 py-2 text-red-400">{fmt(Math.abs(i.valor))}</td></tr>
              ))}</tbody></table>
          </div>
        );
      }
      case "rateio":
        const total = dre.receitas + dre.despesas;
        return (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-neutral-200">Rateio por Categoria</h3>
            <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-3 py-2 font-medium">Categoria</th><th className="px-3 py-2 font-medium">Tipo</th><th className="px-3 py-2 font-medium">Valor</th><th className="px-3 py-2 font-medium">% do Total</th></tr></thead>
              <tbody>{dre.items.map((i) => {
                const pct = total > 0 ? Math.round((Math.abs(i.valor) / total) * 100) : 0;
                return <tr key={i.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-3 py-2">{i.categoria}</td><td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-[10px] ${i.tipo === "receita" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{i.tipo}</span></td><td className="px-3 py-2">{fmt(Math.abs(i.valor))}</td><td className="px-3 py-2">{pct}%</td></tr>;
              })}</tbody></table>
          </div>
        );
      default: return <p className="text-xs text-neutral-500">Selecione um item</p>;
    }
  }

  return <SidebarLayout subItems={SUB_ITEMS} renderContent={renderContent} />;
}
