"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type VendasPorLojaResp } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";
import ExportButtons from "@/app/_components/ExportButtons";

function primeiroDiaMes(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function hojeISO(): string {
  return new Date().toISOString().slice(0, 10);
}

// Grade dias x lojas — equivalente da planilha VENDAS MES LOJAS.xlsx.
export default function VendasPorLojaTab() {
  const [de, setDe] = useState(primeiroDiaMes());
  const [ate, setAte] = useState(hojeISO());
  const [dados, setDados] = useState<VendasPorLojaResp | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDados = useCallback(async () => {
    setLoading(true);
    try { setDados(await api.finVendasPorLoja(de, ate)); }
    catch { setDados(null); }
    finally { setLoading(false); }
  }, [de, ate]);

  useEffect(() => { fetchDados(); }, [fetchDados]);

  const colunas = dados ? ["Data", ...dados.lojas.map(l => l.nome), "Total"] : [];
  const linhas = dados ? dados.dias.map(dia => [
    fmtDataBR(dia.data),
    ...dados.lojas.map(l => fmtBRL(dia.valores_por_loja[l.id] ?? 0)),
    fmtBRL(dia.total_dia),
  ]) : [];
  const linhaTotais = dados ? ["Total", ...dados.lojas.map(l => fmtBRL(dados.totais_por_loja[l.id] ?? 0)), fmtBRL(Object.values(dados.totais_por_loja).reduce((s, v) => s + v, 0))] : [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <label className="text-xs text-neutral-400">Período</label>
          <input type="date" value={de} onChange={e => setDe(e.target.value)}
            className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
          <span className="text-xs text-neutral-500">até</span>
          <input type="date" value={ate} onChange={e => setAte(e.target.value)}
            className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
        </div>
        <ExportButtons columns={colunas} rows={dados && dados.dias.length > 0 ? [...linhas, linhaTotais] : []} filename="vendas-por-loja" title="Vendas por Loja" />
      </div>

      {loading ? (
        <p className="text-xs text-neutral-500">Carregando...</p>
      ) : !dados || dados.dias.length === 0 ? (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-xs text-neutral-500">
          Nenhuma venda no período selecionado
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-neutral-800">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/60 text-left text-neutral-400">
                {colunas.map(c => <th key={c} className="whitespace-nowrap px-4 py-2.5 font-medium">{c}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/70">
              {linhas.map((linha, i) => (
                <tr key={i} className="text-neutral-300">
                  {linha.map((v, j) => <td key={j} className="whitespace-nowrap px-4 py-2.5">{v}</td>)}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-neutral-700 font-semibold text-neutral-100">
                {linhaTotais.map((v, j) => <td key={j} className="whitespace-nowrap px-4 py-2.5">{v}</td>)}
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
