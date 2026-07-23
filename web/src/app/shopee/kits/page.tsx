"use client";

import { useState, useEffect } from "react";

interface KitSugestao { sku_a: string; nome_a: string; sku_b: string; nome_b: string; qtd_juntos: number; confianca_pct: number; }
interface Concorrencia { sku: string; preco_nosso: number; total_anuncios: number; preco_medio: number; preco_acima_pct: number; alerta?: string; mensagem: string; }

export default function KitsConcorrenciaPage() {
  const [kits, setKits] = useState<KitSugestao[]>([]);
  const [concorrencia, setConcorrencia] = useState<Concorrencia | null>(null);
  const [concorrenciaSku, setConcorrenciaSku] = useState("");
  const [concorrenciaPreco, setConcorrenciaPreco] = useState("");
  const [dias, setDias] = useState(90);
  const [loading, setLoading] = useState(true);

  const carregarKits = (d: number) => {
    setLoading(true);
    fetch(`/api/shopee/sugestao-kits?dias=${d}&min=2`).then(r => r.json()).then(d => setKits(d.data || [])).finally(() => setLoading(false));
  };
  useEffect(() => { carregarKits(dias); }, [dias]);

  const analisar = async () => {
    if (!concorrenciaSku) return;
    const r = await fetch(`/api/shopee/concorrencia?sku=${encodeURIComponent(concorrenciaSku)}&preco=${concorrenciaPreco || "0"}`);
    setConcorrencia(await r.json());
  };

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Sugestões de Kits & Concorrência</h1>
        <p className="text-xs text-neutral-500 mt-1">Produtos comprados juntos e análise de preço vs mercado</p>
      </div>

      {/* Concorrencia */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-neutral-300">Análise de Concorrência</h2>
        <div className="flex gap-2">
          <input type="text" value={concorrenciaSku} onChange={e => setConcorrenciaSku(e.target.value)}
            placeholder="SKU do produto" className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
          <input type="number" step="0.01" value={concorrenciaPreco} onChange={e => setConcorrenciaPreco(e.target.value)}
            placeholder="Preço" className="w-28 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
          <button onClick={analisar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">Analisar</button>
        </div>
        {concorrencia && (
          <div className={`text-xs px-3 py-2 rounded-lg border ${concorrencia.alerta === "critico" ? "bg-red-900/30 border-red-800 text-red-400" : concorrencia.alerta === "alerta" ? "bg-amber-900/30 border-amber-800 text-amber-400" : "bg-emerald-900/30 border-emerald-800 text-emerald-400"}`}>
            {concorrencia.mensagem}
            {concorrencia.total_anuncios > 0 && (
              <div className="mt-1 text-neutral-500">
                Média: R$ {concorrencia.preco_medio?.toFixed(2)} · {concorrencia.total_anuncios} anúncios · {concorrencia.preco_acima_pct}% {concorrencia.preco_acima_pct >= 0 ? "acima" : "abaixo"} da média
              </div>
            )}
          </div>
        )}
      </div>

      {/* Kits */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-sm font-semibold text-neutral-300">Sugestão de Kits</h2>
          <select value={dias} onChange={e => setDias(Number(e.target.value))}
            className="bg-neutral-800 border border-neutral-700 rounded px-3 py-1.5 text-xs text-neutral-200">
            {[30, 60, 90, 180, 365].map(d => <option key={d} value={d}>Últimos {d} dias</option>)}
          </select>
        </div>
        <p className="text-xs text-neutral-500">Produtos frequentemente comprados juntos. Sugestão para criar bundles e aumentar ticket médio.</p>

        {loading ? <p className="text-neutral-500 text-xs">Analisando vendas...</p> : kits.length === 0 ? (
          <p className="text-neutral-600 text-xs">Dados insuficientes. São necessárias mais vendas para gerar sugestões.</p>
        ) : (
          <div className="overflow-auto max-h-[500px]">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-neutral-800 text-neutral-500 sticky top-0 bg-neutral-900">
                <th className="text-left p-2">Produto A</th><th className="text-left p-2">Produto B</th>
                <th className="text-right p-2">Comprados juntos</th><th className="text-right p-2">Confiança</th>
              </tr></thead>
              <tbody>
                {kits.map((k, i) => (
                  <tr key={i} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                    <td className="p-2"><span className="text-indigo-400 font-mono text-[10px]">{k.sku_a}</span><span className="text-neutral-300 ml-1">{k.nome_a}</span></td>
                    <td className="p-2"><span className="text-amber-400 font-mono text-[10px]">{k.sku_b}</span><span className="text-neutral-300 ml-1">{k.nome_b}</span></td>
                    <td className="p-2 text-right text-neutral-200">{k.qtd_juntos}×</td>
                    <td className="p-2 text-right">
                      <span className={`px-2 py-0.5 rounded text-[10px] ${k.confianca_pct >= 30 ? "bg-emerald-900/30 text-emerald-400" : k.confianca_pct >= 15 ? "bg-amber-900/30 text-amber-400" : "bg-neutral-700 text-neutral-400"}`}>
                        {k.confianca_pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
