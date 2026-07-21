"use client";

import { useState } from "react";
import { estoqueRatear, type RateioResult } from "@/lib/api";
import Link from "next/link";

export default function RateioPage() {
  const [sku, setSku] = useState("");
  const [total, setTotal] = useState(0);
  const [modo, setModo] = useState<"igual" | "proporcional">("igual");
  const [periodoDias, setPeriodoDias] = useState(30);
  const [lojasTexto, setLojasTexto] = useState("");
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<RateioResult | null>(null);
  const [buscaUnica, setBuscaUnica] = useState(true);

  const handleRatear = async () => {
    if (!sku.trim() || total <= 0) return;
    setLoading(true);
    setErro(null);
    setResultado(null);
    try {
      const lojas = lojasTexto
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const r = await estoqueRatear({
        sku: sku.trim(),
        total,
        modo,
        lojas: lojas.length > 0 ? lojas : undefined,
        periodo_dias: modo === "proporcional" ? periodoDias : undefined,
      });
      if (r.erro) {
        setErro(r.erro);
      } else {
        setResultado(r);
      }
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao ratear estoque");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <Link href="/estoque/lojas" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Estoque por Depósito
        </Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Rateio de Estoque</h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          Distribui um montante total de um produto entre as lojas, igualmente ou proporcional às vendas.
        </p>
      </div>

      {erro && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      )}

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">SKU *</label>
            <input
              type="text"
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              placeholder="Ex: PROD-001"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600 font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">Quantidade Total *</label>
            <input
              type="number"
              step="0.001"
              value={total || ""}
              onChange={(e) => setTotal(Number(e.target.value))}
              placeholder="0"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600"
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-2">Modo de Rateio</label>
          <div className="flex gap-2">
            <button
              onClick={() => setModo("igual")}
              className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
                modo === "igual"
                  ? "bg-indigo-600/20 text-indigo-300 border border-indigo-600/30"
                  : "bg-neutral-800 text-neutral-400 border border-neutral-700 hover:border-neutral-600"
              }`}
            >
              Igual — divide igual entre as lojas
            </button>
            <button
              onClick={() => setModo("proporcional")}
              className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
                modo === "proporcional"
                  ? "bg-indigo-600/20 text-indigo-300 border border-indigo-600/30"
                  : "bg-neutral-800 text-neutral-400 border border-neutral-700 hover:border-neutral-600"
              }`}
            >
              Proporcional — baseado nas vendas
            </button>
          </div>
        </div>

        {modo === "proporcional" && (
          <div>
            <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">
              Período de vendas (dias)
            </label>
            <input
              type="number"
              value={periodoDias}
              onChange={(e) => setPeriodoDias(Number(e.target.value))}
              className="w-32 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:ring-2 focus:ring-indigo-600"
            />
          </div>
        )}

        <div>
          <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">
            Lojas (opcional — separadas por vírgula; vazio = todas ativas)
          </label>
          <input
            type="text"
            value={lojasTexto}
            onChange={(e) => setLojasTexto(e.target.value)}
            placeholder="Ex: Matriz, Filial Centro, Filial Norte"
            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600"
          />
        </div>

        <button
          onClick={handleRatear}
          disabled={loading || !sku.trim() || total <= 0}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-5 py-2 rounded-lg transition-colors"
        >
          {loading ? "Rateando..." : "Ratear Estoque"}
        </button>
      </div>

      {resultado && (
        <div className="bg-neutral-900 border border-emerald-800/50 rounded-lg p-5 space-y-4">
          <h2 className="text-sm font-medium text-emerald-400">Rateio Concluído</h2>
          <div className="text-xs text-neutral-400">
            SKU: <span className="text-neutral-200 font-mono">{resultado.sku}</span>
            {" | "}Total: <span className="text-neutral-200">{resultado.total}</span>
            {" | "}Modo: <span className="text-neutral-200">{resultado.modo}</span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                <th className="text-left px-3 py-2 font-medium">Loja</th>
                <th className="text-right px-3 py-2 font-medium">Quantidade</th>
                <th className="text-right px-3 py-2 font-medium">%</th>
              </tr>
            </thead>
            <tbody>
              {resultado.lojas.map((l) => (
                <tr key={l.loja} className="border-b border-neutral-800/50">
                  <td className="px-3 py-2 text-neutral-300">{l.loja}</td>
                  <td className="px-3 py-2 text-right font-mono numeric text-neutral-200">
                    {l.quantidade.toLocaleString("pt-BR", { minimumFractionDigits: 3 })}
                  </td>
                  <td className="px-3 py-2 text-right font-mono numeric text-neutral-400">
                    {l.percentual.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
