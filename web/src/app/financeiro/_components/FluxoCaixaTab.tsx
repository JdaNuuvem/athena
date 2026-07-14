"use client";

import { useState, ReactNode, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";

export default function FluxoCaixaTab() {
  const [data, setData] = useState<Array<{ id: number; data: string; descricao: string; tipo: string; valor: number; categoria: string }>>([]);
  const [resumo, setResumo] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.finFluxoResumo().then((r: any) => { setData(r.diario || []); setResumo(r.resumo || {}); }).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><button className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo Lançamento</button></div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[{ label: "Entradas", v: Number(resumo.total_entradas) || 0, c: "text-emerald-400" }, { label: "Saídas", v: Number(resumo.total_saidas) || 0, c: "text-red-400" }, { label: "Saldo", v: (Number(resumo.total_entradas) || 0) - (Number(resumo.total_saidas) || 0), c: "text-blue-400" }, { label: "Lançamentos", v: data.length, c: "text-neutral-200" }].map((c) => (
          <div key={c.label} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3"><p className="text-[10px] text-neutral-500">{c.label}</p><p className={`text-sm font-semibold mt-0.5 ${c.c}`}>{c.label === "Lançamentos" ? c.v : fmt(c.v)}</p></div>
        ))}</div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden"><table className="w-full text-xs">
          <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-4 py-2 font-medium">Data</th><th className="px-4 py-2 font-medium">Descrição</th><th className="px-4 py-2 font-medium">Categoria</th><th className="px-4 py-2 font-medium">Valor</th><th className="px-4 py-2 font-medium">Tipo</th></tr></thead>
          <tbody>{data.map((f: any) => (
            <tr key={f.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-4 py-2.5">{f.data ? new Date(f.data + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td><td className="px-4 py-2.5">{f.descricao}</td><td className="px-4 py-2.5">{f.categoria}</td><td className={`px-4 py-2.5 font-medium ${f.tipo === "entrada" ? "text-emerald-400" : "text-red-400"}`}>{f.tipo === "entrada" ? "+" : "-"}{fmt(f.valor)}</td><td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${f.tipo === "entrada" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{f.tipo}</span></td></tr>
          ))}</tbody></table></div>
      )}</div>
  );
}

interface SubItem { key: string; label: string; children?: SubItem[]; }

export function SidebarLayout({ subItems, renderContent }: { subItems: SubItem[]; renderContent: (activeKey: string) => ReactNode }) {
  const [active, setActive] = useState(subItems[0]?.key ?? "");
  return (
    <div className="flex gap-0 min-h-[60vh]">
      <nav className="w-48 shrink-0 bg-neutral-800/50 border-r border-neutral-700/50 rounded-l-lg">
        <div className="p-2 space-y-0.5">
          {subItems.map((item) => (
            <div key={item.key}>
              <button onClick={() => setActive(item.key)}
                className={`w-full text-left px-3 py-1.5 rounded text-xs transition-colors ${active === item.key ? "bg-indigo-600/20 text-indigo-300 font-medium" : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-700/50"} ${item.children ? "font-semibold" : ""}`}>{item.label}</button>
              {item.children && (
                <div className="ml-3 space-y-0.5 mt-0.5">
                  {item.children.map((child) => (
                    <button key={child.key} onClick={() => setActive(child.key)}
                      className={`w-full text-left px-3 py-1 rounded text-[11px] transition-colors ${active === child.key ? "bg-indigo-600/20 text-indigo-300" : "text-neutral-500 hover:text-neutral-300"}`}>{child.label}</button>
                  ))}</div>
              )}</div>
          ))}</div>
      </nav>
      <div className="flex-1 bg-neutral-800 border border-neutral-700 border-l-0 rounded-r-lg p-4 min-w-0">{renderContent(active)}</div>
    </div>
  );
}
