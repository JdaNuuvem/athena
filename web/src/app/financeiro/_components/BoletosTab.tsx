"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";

interface Boleto { id: number; beneficiario: string; valor: number; vencimento: string; nosso_numero: string; codigo_barras: string; status: string; }

export default function BoletosTab() {
  const [data, setData] = useState<Boleto[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.finList("boletos").then((r) => setData((r.data || []) as Boleto[])).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3"><button className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo Boleto</button></div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden"><table className="w-full text-xs">
          <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-4 py-2 font-medium">Beneficiário</th><th className="px-4 py-2 font-medium">Valor</th><th className="px-4 py-2 font-medium">Vencimento</th><th className="px-4 py-2 font-medium">Nosso Número</th><th className="px-4 py-2 font-medium">Status</th></tr></thead>
          <tbody>{data.map((b) => {
            const sc = b.status === "pago" ? "bg-emerald-500/20 text-emerald-400" : b.status === "vencido" ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400";
            return <tr key={b.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-4 py-2.5">{b.beneficiario}</td><td className="px-4 py-2.5">{fmt(b.valor)}</td><td className="px-4 py-2.5">{b.vencimento ? new Date(b.vencimento + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td><td className="px-4 py-2.5 text-neutral-400">{b.nosso_numero}</td><td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{b.status}</span></td></tr>;
          })}</tbody>
        </table></div>
      )}</div>
  );
}
