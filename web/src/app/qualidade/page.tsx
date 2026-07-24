"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function QualidadePage() {
  const [taxa, setTaxa] = useState<any>(null);
  const [defeitos, setDefeitos] = useState<any[]>([]);
  const [capas, setCapas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.qualidadeTaxaDefeitos(30),
      api.qualidadeDefeitos(),
      api.qualidadeCAPAS(),
    ]).then(([t, d, c]) => {
      setTaxa(t);
      setDefeitos((d as any).defeitos || []);
      setCapas((c as any).capas || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Qualidade</h1>
        <p className="text-xs text-neutral-500 mt-1">Inspecoes, defeitos, CAPAs e analise Pareto</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Taxa de Defeitos</p>
          <p className="text-xl font-bold text-red-400">{taxa?.taxa_pct ?? "—"}%</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Defeitos (30d)</p>
          <p className="text-xl font-bold text-amber-400">{taxa?.total_defeitos ?? defeitos.length}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">CAPAs Abertas</p>
          <p className="text-xl font-bold text-blue-400">{capas.length}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Inspecoes (30d)</p>
          <p className="text-xl font-bold text-emerald-400">{taxa?.total_inspecoes ?? "—"}</p>
        </div>
      </div>

      {defeitos.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Defeitos Registrados</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-neutral-800 text-neutral-500">
                <th className="text-left p-2">Codigo</th><th className="text-left p-2">Descricao</th><th className="text-left p-2">Categoria</th><th className="text-left p-2">Gravidade</th>
              </tr></thead>
              <tbody>
                {defeitos.map((d: any, i: number) => (
                  <tr key={i} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                    <td className="p-2 text-neutral-300 font-mono">{d.codigo || d.id}</td>
                    <td className="p-2 text-neutral-400">{d.descricao || d.nome}</td>
                    <td className="p-2 text-neutral-500">{d.categoria || "—"}</td>
                    <td className="p-2">
                      <span className={(d.gravidade === "critica" ? "text-red-400" : d.gravidade === "alta" ? "text-amber-400" : "text-neutral-500")}>
                        {d.gravidade || "—"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {capas.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">CAPAs</h2>
          <div className="space-y-2">
            {capas.map((c: any, i: number) => (
              <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-lg px-4 py-3 flex items-center justify-between">
                <div>
                  <p className="text-xs text-neutral-300">{c.descricao || c.origem}</p>
                  <p className="text-[10px] text-neutral-500">Origem: {c.origem} #{c.origem_id}</p>
                </div>
                <span className="bg-blue-500/10 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded text-[10px]">{c.status || "aberta"}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!defeitos.length && !capas.length && (
        <div className="text-neutral-600 text-sm text-center py-20">Nenhum registro de qualidade encontrado.</div>
      )}
    </div>
  );
}
