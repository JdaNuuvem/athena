"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";
import SidebarLayout from "../../_components/SidebarLayout";
import ExportButtons from "@/app/_components/ExportButtons";

const SUB_ITEMS = [
  { key: "lucro", label: "Lucro" },
  { key: "prejuizo", label: "Prejuízo" },
  { key: "rateio", label: "Rateio" },
];

const TIPOS = ["receita", "despesa"];

interface DreItem { id: number; mes: string; descricao: string; valor: number; tipo: string; categoria: string; }

export default function DRETab() {
  const [mes, setMes] = useState(new Date().toISOString().slice(0, 7));
  const [dre, setDre] = useState<{ receitas: number; despesas: number; resultado: number; lucro: boolean; items: DreItem[] }>({ receitas: 0, despesas: 0, resultado: 0, lucro: false, items: [] });
  const [loading, setLoading] = useState(true);
  const [criando, setCriando] = useState(false);
  const [novo, setNovo] = useState({ descricao: "", valor: "", tipo: "receita", categoria: "" });
  const [erro, setErro] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api.finDREResumo(mes).then((r) => setDre(r as typeof dre)).catch(() => {}).finally(() => setLoading(false));
  }, [mes]);

  useEffect(() => { load(); }, [load]);

  const abrirCriar = () => {
    setNovo({ descricao: "", valor: "", tipo: "receita", categoria: "" });
    setErro("");
    setCriando(true);
  };

  const confirmarCriar = async () => {
    if (!novo.descricao.trim() || !novo.valor || !novo.categoria.trim()) { setErro("Descrição, categoria e valor são obrigatórios"); return; }
    try {
      const r = await api.finCreate("dre", {
        mes,
        descricao: novo.descricao.trim(),
        valor: Number(novo.valor),
        tipo: novo.tipo,
        categoria: novo.categoria.trim(),
      });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(false);
      load();
    } catch {
      setErro("Erro ao criar lançamento de DRE");
    }
  };

  function renderContent(key: string) {
    if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;
    const receitas = dre.items.filter((i) => i.tipo === "receita");
    const despesas = dre.items.filter((i) => i.tipo === "despesa");

    const header = (titulo: string, exportButtons: React.ReactNode) => (
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-neutral-200">{titulo}</h3>
        <div className="flex items-center gap-2">
          {exportButtons}
          <button onClick={abrirCriar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo Lançamento</button>
        </div>
      </div>
    );

    switch (key) {
      case "lucro": {
        const total = receitas.reduce((s, i) => s + i.valor, 0);
        return (
          <div className="space-y-3">
            {header("Demonstração de Lucro", <ExportButtons columns={["Categoria", "Valor"]} rows={receitas.map(i => [i.categoria, fmt(i.valor)])} filename="dre-lucro" title="Demonstração de Lucro" />)}
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
            {header("Demonstração de Prejuízo", <ExportButtons columns={["Categoria", "Valor"]} rows={despesas.map(i => [i.categoria, fmt(Math.abs(i.valor))])} filename="dre-prejuizo" title="Demonstração de Prejuízo" />)}
            <div className="grid grid-cols-2 gap-3"><div className="bg-neutral-700/30 rounded-lg p-3"><p className="text-[10px] text-neutral-500">Despesa Total</p><p className="text-sm font-semibold text-red-400">{fmt(totalD)}</p></div><div className="bg-neutral-700/30 rounded-lg p-3"><p className="text-[10px] text-neutral-500">% sobre Receita</p><p className="text-sm font-semibold text-amber-400">{dre.receitas > 0 ? Math.round((totalD / dre.receitas) * 100) : 0}%</p></div></div>
            <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-3 py-2 font-medium">Categoria</th><th className="px-3 py-2 font-medium">Valor</th></tr></thead>
              <tbody>{despesas.map((i) => (
                <tr key={i.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-3 py-2">{i.categoria}</td><td className="px-3 py-2 text-red-400">{fmt(Math.abs(i.valor))}</td></tr>
              ))}</tbody></table>
          </div>
        );
      }
      case "rateio": {
        const total = dre.receitas + dre.despesas;
        return (
          <div className="space-y-3">
            {header("Rateio por Categoria", (
              <ExportButtons
                columns={["Categoria", "Tipo", "Valor", "% do Total"]}
                rows={dre.items.map(i => [i.categoria, i.tipo, fmt(Math.abs(i.valor)), `${total > 0 ? Math.round((Math.abs(i.valor) / total) * 100) : 0}%`])}
                filename="dre-rateio" title="Rateio por Categoria"
              />
            ))}
            <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-3 py-2 font-medium">Categoria</th><th className="px-3 py-2 font-medium">Tipo</th><th className="px-3 py-2 font-medium">Valor</th><th className="px-3 py-2 font-medium">% do Total</th></tr></thead>
              <tbody>{dre.items.map((i) => {
                const pct = total > 0 ? Math.round((Math.abs(i.valor) / total) * 100) : 0;
                return <tr key={i.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-3 py-2">{i.categoria}</td><td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-[10px] ${i.tipo === "receita" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{i.tipo}</span></td><td className="px-3 py-2">{fmt(Math.abs(i.valor))}</td><td className="px-3 py-2">{pct}%</td></tr>;
              })}</tbody></table>
          </div>
        );
      }
      default: return <p className="text-xs text-neutral-500">Selecione um item</p>;
    }
  }

  return (
    <>
      <div className="flex items-center justify-end px-1 pb-2">
        <input type="month" value={mes} onChange={e => setMes(e.target.value)}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
      </div>
      <SidebarLayout subItems={SUB_ITEMS} renderContent={renderContent} />

      {criando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(false)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-1">Novo Lançamento de DRE</h3>
            <p className="text-xs text-neutral-500 mb-3">Mês: {mes}</p>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <select value={novo.tipo} onChange={e => setNovo({ ...novo, tipo: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <input value={novo.categoria} onChange={e => setNovo({ ...novo, categoria: e.target.value })}
                placeholder="Categoria (ex: Aluguel, Vendas)" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novo.descricao} onChange={e => setNovo({ ...novo, descricao: e.target.value })}
                placeholder="Descrição" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novo.valor} onChange={e => setNovo({ ...novo, valor: e.target.value })}
                placeholder="Valor" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setCriando(false)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarCriar} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Criar</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
