"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";

interface Pix { id: number; chave: string; tipo_chave: string; descricao: string; valor: number; data_transacao: string; status: string; }

export default function PIXTab() {
  const [data, setData] = useState<Pix[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.finList("pix").then((r) => setData((r.data || []) as Pix[])).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><button className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo PIX</button></div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[{ label: "Total Transações", v: data.length, c: "text-neutral-200" }, { label: "Valor Total", v: data.reduce((s, p) => s + p.valor, 0), c: "text-emerald-400" }, { label: "Concluídos", v: data.filter(p => p.status === "concluido").length, c: "text-blue-400" }, { label: "Pendentes", v: data.filter(p => p.status === "pendente").length, c: "text-amber-400" }].map((c) => (
          <div key={c.label} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3"><p className="text-[10px] text-neutral-500">{c.label}</p><p className={`text-sm font-semibold mt-0.5 ${c.c}`}>{c.label === "Valor Total" ? fmt(c.v) : c.v}</p></div>
        ))}</div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden"><table className="w-full text-xs">
          <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-4 py-2 font-medium">Chave</th><th className="px-4 py-2 font-medium">Tipo</th><th className="px-4 py-2 font-medium">Descrição</th><th className="px-4 py-2 font-medium">Valor</th><th className="px-4 py-2 font-medium">Data</th><th className="px-4 py-2 font-medium">Status</th></tr></thead>
          <tbody>{data.map((p) => {
            const sc = p.status === "concluido" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400";
            return <tr key={p.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-4 py-2.5">{p.chave}</td><td className="px-4 py-2.5">{p.tipo_chave}</td><td className="px-4 py-2.5">{p.descricao}</td><td className="px-4 py-2.5">{fmt(p.valor)}</td><td className="px-4 py-2.5">{p.data_transacao ? new Date(p.data_transacao).toLocaleDateString("pt-BR") : "—"}</td><td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{p.status}</span></td></tr>;
          })}</tbody>
        </table></div>
      )}</div>
  );
}
