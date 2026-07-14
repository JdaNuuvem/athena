"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";

interface Conta { id: number; cliente: string; descricao: string; valor: number; vencimento: string; data_recebimento?: string; status: string; forma_pagamento: string; }

export default function ReceberTab() {
  const [data, setData] = useState<Conta[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.finList("contas_receber").then((r) => setData((r.data || []) as Conta[])).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><button className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conta</button></div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[{ label: "Total Pendente", v: data.filter(c => c.status !== "pago").reduce((s, c) => s + c.valor, 0), c: "text-amber-400" }, { label: "Total Recebido", v: data.filter(c => c.status === "pago").reduce((s, c) => s + c.valor, 0), c: "text-emerald-400" }, { label: "Vencidas", v: data.filter(c => c.status === "atrasado").length, c: "text-red-400" }, { label: "Total", v: data.length, c: "text-neutral-200" }].map((c) => (
          <div key={c.label} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3"><p className="text-[10px] text-neutral-500">{c.label}</p><p className={`text-sm font-semibold mt-0.5 ${c.c}`}>{c.label === "Vencidas" || c.label === "Total" ? c.v : fmt(c.v)}</p></div>
        ))}</div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden"><table className="w-full text-xs">
          <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-4 py-2 font-medium">Cliente</th><th className="px-4 py-2 font-medium">Descrição</th><th className="px-4 py-2 font-medium">Valor</th><th className="px-4 py-2 font-medium">Vencimento</th><th className="px-4 py-2 font-medium">Forma Pag.</th><th className="px-4 py-2 font-medium">Status</th></tr></thead>
          <tbody>{data.map((c) => {
            const sc = c.status === "pago" ? "bg-emerald-500/20 text-emerald-400" : c.status === "atrasado" ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400";
            return <tr key={c.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-4 py-2.5">{c.cliente}</td><td className="px-4 py-2.5">{c.descricao}</td><td className="px-4 py-2.5">{fmt(c.valor)}</td><td className="px-4 py-2.5">{c.vencimento ? new Date(c.vencimento + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td><td className="px-4 py-2.5">{c.forma_pagamento}</td><td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{c.status}</span></td></tr>;
          })}</tbody>
        </table></div>
      )}</div>
  );
}
