"use client";

import { useState } from "react";
import { api, estoqueRatear, type RateioResult } from "@/lib/api";

interface LojaShopee {
  id: number;
  nome: string;
  shopee_shop_id: string;
  tem_token: boolean;
}

interface RateioShopeeModalProps {
  sku: string;
  produtoNome?: string;
  lojas: LojaShopee[];
  onClose: () => void;
  onSucesso?: () => void;
}

type PushStatus = "enviando" | "ok" | "erro";

export default function RateioShopeeModal({ sku, produtoNome, lojas, onClose, onSucesso }: RateioShopeeModalProps) {
  const [selecionadas, setSelecionadas] = useState<Set<number>>(new Set(lojas.map(l => l.id)));
  const [total, setTotal] = useState(0);
  const [modo, setModo] = useState<"igual" | "proporcional">("igual");
  const [periodoDias, setPeriodoDias] = useState(30);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<RateioResult | null>(null);
  const [pushStatus, setPushStatus] = useState<Record<string, PushStatus>>({});

  const toggleLoja = (id: number) => {
    setSelecionadas(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleRatear = async () => {
    const nomesSelecionados = lojas.filter(l => selecionadas.has(l.id)).map(l => l.nome);
    if (total <= 0 || nomesSelecionados.length === 0) return;
    setLoading(true);
    setErro(null);
    setResultado(null);
    setPushStatus({});
    try {
      const r = await estoqueRatear({
        sku,
        total,
        modo,
        lojas: nomesSelecionados,
        periodo_dias: modo === "proporcional" ? periodoDias : undefined,
      });
      if (r.erro) {
        setErro(r.erro);
        return;
      }
      setResultado(r);

      const statusInicial: Record<string, PushStatus> = {};
      r.lojas.forEach(l => { statusInicial[l.loja] = "enviando"; });
      setPushStatus(statusInicial);

      await Promise.all(r.lojas.map(async (l) => {
        const loja = lojas.find(lj => lj.nome === l.loja);
        if (!loja) {
          setPushStatus(prev => ({ ...prev, [l.loja]: "erro" }));
          return;
        }
        try {
          const resp = await api.shopeeAtualizarEstoqueProduto(sku, loja.id, Math.round(l.quantidade));
          setPushStatus(prev => ({ ...prev, [l.loja]: resp.error ? "erro" : "ok" }));
        } catch {
          setPushStatus(prev => ({ ...prev, [l.loja]: "erro" }));
        }
      }));
      onSucesso?.();
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
            <h2 className="text-sm font-medium text-neutral-200">Ratear estoque entre lojas Shopee</h2>
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
              <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-2">
                Lojas ({selecionadas.size} de {lojas.length})
              </label>
              {lojas.length === 0 ? (
                <p className="text-xs text-amber-400">Nenhuma loja Shopee com token ativo.</p>
              ) : (
                <div className="max-h-40 overflow-y-auto space-y-1 border border-neutral-800 rounded-lg p-2">
                  {lojas.map(l => (
                    <label key={l.id} className="flex items-center gap-2 text-xs text-neutral-300 px-1 py-1 hover:bg-neutral-800/50 rounded cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selecionadas.has(l.id)}
                        onChange={() => toggleLoja(l.id)}
                        className="accent-indigo-600"
                      />
                      {l.nome}
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">Quantidade Total</label>
              <input
                type="number"
                min="0"
                step="1"
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
                disabled={loading || total <= 0 || selecionadas.size === 0}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-1.5 rounded-lg transition-colors"
              >
                {loading ? "Rateando..." : "Ratear e enviar à Shopee"}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-emerald-400">Rateio calculado ({resultado.modo}) — enviando à Shopee</p>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-2 py-1.5 font-medium">Loja</th>
                  <th className="text-right px-2 py-1.5 font-medium">Qtd</th>
                  <th className="text-right px-2 py-1.5 font-medium">%</th>
                  <th className="text-right px-2 py-1.5 font-medium">Shopee</th>
                </tr>
              </thead>
              <tbody>
                {resultado.lojas.map((l) => (
                  <tr key={l.loja} className="border-b border-neutral-800/30">
                    <td className="px-2 py-1.5 text-neutral-300 text-xs">{l.loja}</td>
                    <td className="px-2 py-1.5 text-right font-mono numeric text-neutral-200 text-xs">
                      {Math.round(l.quantidade)}
                    </td>
                    <td className="px-2 py-1.5 text-right font-mono numeric text-neutral-400 text-xs">
                      {l.percentual.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%
                    </td>
                    <td className="px-2 py-1.5 text-right text-xs">
                      {pushStatus[l.loja] === "enviando" && <span className="text-neutral-500">enviando...</span>}
                      {pushStatus[l.loja] === "ok" && <span className="text-emerald-400">enviado</span>}
                      {pushStatus[l.loja] === "erro" && <span className="text-red-400">falhou</span>}
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
