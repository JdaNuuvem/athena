"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function MoldesPage() {
  const [dash, setDash] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.moldesDashboard().then(setDash).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  const moldes = dash?.moldes || [];
  const totalMoldes = moldes.length;
  const ativos = moldes.filter((m: any) => m.status === "ativo" || m.status === "em_producao").length;
  const manutencao = moldes.filter((m: any) => m.status === "manutencao").length;
  const totalCiclos = moldes.reduce((s: number, m: any) => s + (m.ciclos_realizados || 0), 0);
  const totalVidaUtil = moldes.reduce((s: number, m: any) => s + (m.ciclos_uteis || 10000), 0);
  const vidaUtilPct = totalVidaUtil > 0 ? ((totalCiclos / totalVidaUtil) * 100).toFixed(1) : "—";

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Moldes &amp; CNC</h1>
        <p className="text-xs text-neutral-500 mt-1">Cadastro de moldes, historico, jobs CNC e dashboard</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Total Moldes</p>
          <p className="text-xl font-bold text-neutral-100">{totalMoldes}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Ativos</p>
          <p className="text-xl font-bold text-emerald-400">{ativos}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Em Manutencao</p>
          <p className="text-xl font-bold text-amber-400">{manutencao}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Ciclos Totais</p>
          <p className="text-xl font-bold text-blue-400">{totalCiclos.toLocaleString()}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Vida Util</p>
          <p className="text-xl font-bold text-purple-400">{vidaUtilPct}%</p>
        </div>
      </div>

      {moldes.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Moldes Cadastrados</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-neutral-800 text-neutral-500">
                <th className="text-left p-2">Codigo</th><th className="text-left p-2">Produto</th><th className="text-left p-2">Material</th><th className="text-left p-2">Ciclos</th><th className="text-left p-2">Vida Util</th><th className="text-left p-2">Status</th>
              </tr></thead>
              <tbody>
                {moldes.map((m: any, i: number) => (
                  <tr key={i} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                    <td className="p-2 text-neutral-300 font-mono">{m.codigo || m.id}</td>
                    <td className="p-2 text-neutral-400">{m.produto || m.product}</td>
                    <td className="p-2 text-neutral-500">{m.material || "—"}</td>
                    <td className="p-2 text-neutral-300">{m.ciclos_realizados || m.cyclesUsed || 0} / {m.ciclos_uteis || m.cyclesTotal || 0}</td>
                    <td className="p-2">
                      <div className="w-16 bg-neutral-700 rounded-full h-1.5">
                        <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${Math.min(100, ((m.ciclos_realizados || 0) / (m.ciclos_uteis || 10000)) * 100)}%` }} />
                      </div>
                    </td>
                    <td className="p-2">
                      <span className={m.status === "ativo" ? "text-emerald-400" : m.status === "manutencao" ? "text-amber-400" : "text-neutral-500"}>
                        {m.status || "—"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {!moldes.length && (
        <div className="text-neutral-600 text-sm text-center py-20">Nenhum molde cadastrado.</div>
      )}
    </div>
  );
}
