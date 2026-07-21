"use client";

import { useState, useEffect } from "react";
import { estoqueRatear, type RateioResult } from "@/lib/api";

interface RateioModalProps {
  sku: string;
  produtoNome?: string;
  onClose: () => void;
  onSucesso?: () => void;
}

export default function RateioModal({ sku, produtoNome, onClose, onSucesso }: RateioModalProps) {
  const [total, setTotal] = useState(0);
  const [modo, setModo] = useState<"igual" | "proporcional">("igual");
  const [periodoDias, setPeriodoDias] = useState(30);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<RateioResult | null>(null);

  const handleRatear = async () => {
    if (total <= 0) return;
    setLoading(true);
    setErro(null);
    setResultado(null);
    try {
      const r = await estoqueRatear({ sku, total, modo, periodo_dias: modo === "proporcional" ? periodoDias : undefined });
      if (r.erro) {
        setErro(r.erro);
      } else {
        setResultado(r);
        onSucesso?.();
      }
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao ratear estoque");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-medium text-neutral-200">Rateio de Estoque</h2>
            <p className="text-xs font-mono text-neutral-500 mt-0.5">{sku}{produtoNome ? ` — ${produtoNome}` : ""}</p>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 text-lg">&times;</button>
        </div>

        {erro && (
          <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3 mb-4">{erro}</div>
        )}

        {!resultado ? (
          <div className="space-y-4">
            <div>
              <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">Quantidade Total</label>
              <input
                type="number"
                step="0.001"
                value={total || ""}
                onChange={(e) => setTotal(Number(e.target.value))}
                placeholder="0"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-2">Modo</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setModo("igual")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    modo === "igual"
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-600/30"
                      : "bg-neutral-800 text-neutral-400 border border-neutral-700"
                  }`}
                >
                  Igual
                </button>
                <button
                  onClick={() => setModo("proporcional")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    modo === "proporcional"
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-600/30"
                      : "bg-neutral-800 text-neutral-400 border border-neutral-700"
                  }`}
                >
                  Proporcional (vendas)
                </button>
              </div>
            </div>
            {modo === "proporcional" && (
              <div>
                <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">Período (dias)</label>
                <input
                  type="number"
                  value={periodoDias}
                  onChange={(e) => setPeriodoDias(Number(e.target.value))}
                  className="w-32 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                />
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={onClose} className="text-xs text-neutral-500 hover:text-neutral-300 px-3 py-1.5">Cancelar</button>
              <button
                onClick={handleRatear}
                disabled={loading || total <= 0}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-1.5 rounded-lg transition-colors"
              >
                {loading ? "Rateando..." : "Ratear"}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-emerald-400">Rateio concluído ({resultado.modo})</p>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-2 py-1.5 font-medium">Loja</th>
                  <th className="text-right px-2 py-1.5 font-medium">Qtd</th>
                  <th className="text-right px-2 py-1.5 font-medium">%</th>
                </tr>
              </thead>
              <tbody>
                {resultado.lojas.map((l) => (
                  <tr key={l.loja} className="border-b border-neutral-800/30">
                    <td className="px-2 py-1.5 text-neutral-300 text-xs">{l.loja}</td>
                    <td className="px-2 py-1.5 text-right font-mono numeric text-neutral-200 text-xs">
                      {l.quantidade.toLocaleString("pt-BR", { minimumFractionDigits: 3 })}
                    </td>
                    <td className="px-2 py-1.5 text-right font-mono numeric text-neutral-400 text-xs">
                      {l.percentual.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex justify-end pt-2">
              <button onClick={onClose} className="text-xs text-neutral-500 hover:text-neutral-300 px-3 py-1.5">Fechar</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
