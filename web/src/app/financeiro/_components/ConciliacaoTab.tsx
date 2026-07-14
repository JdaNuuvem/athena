"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";

interface Conciliacao { id: number; banco_id: number; data: string; descricao: string; valor_extrato: number; valor_sistema: number; status: string; }

export default function ConciliacaoTab() {
  const [data, setData] = useState<Conciliacao[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.finList("conciliacao").then((r) => setData((r.data || []) as Conciliacao[])).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><button className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conciliação</button></div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden"><table className="w-full text-xs">
          <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-4 py-2 font-medium">Data</th><th className="px-4 py-2 font-medium">Descrição</th><th className="px-4 py-2 font-medium">Extrato</th><th className="px-4 py-2 font-medium">Sistema</th><th className="px-4 py-2 font-medium">Diferença</th><th className="px-4 py-2 font-medium">Status</th></tr></thead>
          <tbody>{data.map((c) => {
            const diff = c.valor_extrato - c.valor_sistema;
            const sc = c.status === "conciliado" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400";
            return <tr key={c.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-4 py-2.5">{c.data ? new Date(c.data + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td><td className="px-4 py-2.5">{c.descricao}</td><td className="px-4 py-2.5">{fmt(c.valor_extrato)}</td><td className="px-4 py-2.5">{fmt(c.valor_sistema)}</td><td className={`px-4 py-2.5 font-medium ${diff === 0 ? "text-emerald-400" : "text-red-400"}`}>{fmt(diff)}</td><td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{c.status}</span></td></tr>;
          })}</tbody>
        </table></div>
      )}</div>
  );
}
