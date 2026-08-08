"use client";

import { useState, useEffect, useCallback } from "react";
import { useStore } from "@/lib/store-context";
import { api, type MovimentoDiarioResp } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";
import ExportButtons from "@/app/_components/ExportButtons";

function primeiroDiaMes(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function hojeISO(): string {
  return new Date().toISOString().slice(0, 10);
}

const FORMAS = ["pix", "dinheiro", "debito", "credito"];
const CATEGORIAS = ["mat_limpeza", "padaria", "papelaria", "passagem", "outros"];
const CATEGORIA_LABEL: Record<string, string> = {
  mat_limpeza: "Mat. Limpeza", padaria: "Padaria", papelaria: "Papelaria", passagem: "Passagem", outros: "Outros",
};

// Receita por forma de pagamento - despesa por categoria, por dia — equivalente
// da planilha MOV LOJA LEON.xlsx. Despesa vem do Cofre (saida_despesa).
export default function MovimentoDiarioTab() {
  const { lojas, lojaId: lojaIdGlobal } = useStore();
  const [lojaId, setLojaId] = useState<number | null>(null);
  const [de, setDe] = useState(primeiroDiaMes());
  const [ate, setAte] = useState(hojeISO());
  const [dados, setDados] = useState<MovimentoDiarioResp | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (lojaId === null && lojaIdGlobal && lojaIdGlobal !== "todas") setLojaId(Number(lojaIdGlobal));
  }, [lojaIdGlobal, lojaId]);

  const fetchDados = useCallback(async () => {
    if (!lojaId) return;
    setLoading(true);
    try { setDados(await api.finMovimentoDiario(de, ate, lojaId)); }
    catch { setDados(null); }
    finally { setLoading(false); }
  }, [de, ate, lojaId]);

  useEffect(() => { fetchDados(); }, [fetchDados]);

  const colunas = ["Data", ...FORMAS.map(f => f.toUpperCase()), ...CATEGORIAS.map(c => CATEGORIA_LABEL[c]), "Receita", "Despesa", "Líquido"];
  const linhas = (dados?.dias ?? []).map(dia => [
    fmtDataBR(dia.data),
    ...FORMAS.map(f => fmtBRL(dia.receita_por_forma[f] ?? 0)),
    ...CATEGORIAS.map(c => fmtBRL(dia.despesa_por_categoria[c] ?? 0)),
    fmtBRL(dia.receita_total), fmtBRL(dia.despesa_total), fmtBRL(dia.total_liquido),
  ]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-xs text-neutral-400">Loja</label>
          <select value={lojaId ?? ""} onChange={e => setLojaId(e.target.value ? Number(e.target.value) : null)}
            className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
            <option value="">Selecione...</option>
            {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
          </select>
          <label className="text-xs text-neutral-400">Período</label>
          <input type="date" value={de} onChange={e => setDe(e.target.value)}
            className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
          <span className="text-xs text-neutral-500">até</span>
          <input type="date" value={ate} onChange={e => setAte(e.target.value)}
            className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
        </div>
        <ExportButtons columns={colunas} rows={linhas} filename="movimento-diario" title="Movimento Diário" />
      </div>

      {!lojaId ? (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-xs text-neutral-500">Selecione uma loja</div>
      ) : loading ? (
        <p className="text-xs text-neutral-500">Carregando...</p>
      ) : linhas.length === 0 ? (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-xs text-neutral-500">Nenhum movimento no período selecionado</div>
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
          </table>
        </div>
      )}
    </div>
  );
}
