"use client";

import { useState, useEffect } from "react";

interface KitSugestao { sku_a: string; nome_a: string; sku_b: string; nome_b: string; qtd_juntos: number; confianca_pct: number; }
interface ConsistenciaPreco {
  sku: string; preco_nosso: number; total_anuncios: number;
  preco_medio?: number; preco_mediano?: number; preco_min?: number; preco_max?: number;
  preco_acima_pct?: number; alerta?: string; mensagem: string; erro?: string;
}
interface LojaShopee { id: number; nome: string; shopee_shop_id?: string; tipo?: string; }

// fetch(...).then(r => r.json()) explode com "Unexpected token '<'" quando a
// resposta e' uma pagina de erro HTML (404/500) em vez de JSON — troca por
// uma mensagem legivel baseada no status HTTP nesse caso.
async function apiJson<T = any>(url: string): Promise<T> {
  const res = await fetch(url);
  const texto = await res.text();
  try {
    return JSON.parse(texto) as T;
  } catch {
    throw new Error(`Erro ${res.status} do servidor — resposta inesperada`);
  }
}

export default function KitsConsistenciaPage() {
  const [kits, setKits] = useState<KitSugestao[]>([]);
  const [erroKits, setErroKits] = useState("");
  const [consistencia, setConsistencia] = useState<ConsistenciaPreco | null>(null);
  const [erroConsistencia, setErroConsistencia] = useState("");
  const [consistenciaSku, setConsistenciaSku] = useState("");
  const [consistenciaPreco, setConsistenciaPreco] = useState("");
  const [lojas, setLojas] = useState<LojaShopee[]>([]);
  const [lojaAnalise, setLojaAnalise] = useState("");
  const [analisando, setAnalisando] = useState(false);
  const [dias, setDias] = useState(90);
  const [loading, setLoading] = useState(true);

  const lojasShopee = lojas.filter(l => l.shopee_shop_id || l.tipo === "virtual");

  useEffect(() => {
    fetch("/api/lojas/manage").then(r => r.json()).then(d => setLojas(d.lojas || [])).catch(() => {});
  }, []);

  const carregarKits = (d: number) => {
    setLoading(true);
    setErroKits("");
    apiJson<{ data?: KitSugestao[] }>(`/api/shopee/sugestao-kits?dias=${d}&min=2`)
      .then(d => setKits(d.data || []))
      .catch(e => setErroKits(e instanceof Error ? e.message : "Erro ao carregar sugestões de kits"))
      .finally(() => setLoading(false));
  };
  useEffect(() => { carregarKits(dias); }, [dias]);

  const analisar = async () => {
    if (!consistenciaSku.trim()) return;
    setAnalisando(true);
    setErroConsistencia("");
    setConsistencia(null);
    try {
      const params = new URLSearchParams({ sku: consistenciaSku.trim(), preco: consistenciaPreco || "0" });
      if (lojaAnalise) params.set("loja_id", lojaAnalise);
      const d = await apiJson<ConsistenciaPreco>(`/api/shopee/consistencia-precos?${params}`);
      if (d.erro) { setErroConsistencia(d.mensagem || d.erro); return; }
      setConsistencia(d);
    } catch (e) {
      setErroConsistencia(e instanceof Error ? e.message : "Erro ao analisar consistência de preço");
    } finally {
      setAnalisando(false);
    }
  };

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Sugestões de Kits & Consistência de Preço</h1>
        <p className="text-xs text-neutral-500 mt-1">Produtos comprados juntos e comparação de preço do mesmo SKU entre suas lojas</p>
      </div>

      {/* Consistencia de preco entre lojas proprias */}
      <div className="instrument-enter instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-neutral-300">Consistência de Preço entre suas Lojas</h2>
        <p className="text-[11px] text-neutral-500">
          Compara o preço deste SKU com o mesmo produto anunciado em outras lojas Shopee da sua conta —
          não é comparação com concorrentes (a API da Shopee não dá acesso a preços de outros vendedores).
        </p>
        <div className="flex flex-wrap gap-2">
          <input type="text" value={consistenciaSku} onChange={e => setConsistenciaSku(e.target.value)}
            onKeyDown={e => e.key === "Enter" && analisar()}
            placeholder="SKU exato do produto" className="flex-1 min-w-[160px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
          <input type="number" step="0.01" value={consistenciaPreco} onChange={e => setConsistenciaPreco(e.target.value)}
            onKeyDown={e => e.key === "Enter" && analisar()}
            placeholder="Preço a comparar" className="w-32 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
          <select value={lojaAnalise} onChange={e => setLojaAnalise(e.target.value)}
            title="Loja sendo analisada — excluída do cálculo da média das 'outras lojas'"
            className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
            <option value="">Sem excluir nenhuma loja</option>
            {lojasShopee.map(l => <option key={l.id} value={l.id}>Analisando a partir de: {l.nome}</option>)}
          </select>
          <button onClick={analisar} disabled={analisando || !consistenciaSku.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg">
            {analisando ? "Analisando..." : "Analisar"}
          </button>
        </div>
        {erroConsistencia && (
          <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erroConsistencia}</div>
        )}
        {consistencia && !erroConsistencia && (
          <div className={`text-xs px-3 py-2 rounded-lg border ${consistencia.alerta === "critico" ? "bg-red-900/30 border-red-800 text-red-400" : consistencia.alerta === "alerta" ? "bg-amber-900/30 border-amber-800 text-amber-400" : "bg-emerald-900/30 border-emerald-800 text-emerald-400"}`}>
            {consistencia.mensagem}
            {consistencia.total_anuncios > 0 && (
              <div className="mt-1 text-neutral-500">
                Média: R$ {consistencia.preco_medio?.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                {" · "}Faixa: R$ {consistencia.preco_min?.toLocaleString("pt-BR", { minimumFractionDigits: 2 })} – R$ {consistencia.preco_max?.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                {" · "}{consistencia.total_anuncios} anúncio{consistencia.total_anuncios === 1 ? "" : "s"} {lojaAnalise ? "em outras lojas" : "seus"}
                {" · "}{Math.abs(consistencia.preco_acima_pct ?? 0)}% {(consistencia.preco_acima_pct ?? 0) >= 0 ? "acima" : "abaixo"} da média
              </div>
            )}
          </div>
        )}
      </div>

      {/* Kits */}
      <div className="instrument-enter instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <div className="flex justify-between items-center">
          <h2 className="text-sm font-semibold text-neutral-300">Sugestão de Kits</h2>
          <select value={dias} onChange={e => setDias(Number(e.target.value))}
            className="bg-neutral-800 border border-neutral-700 rounded px-3 py-1.5 text-xs text-neutral-200">
            {[30, 60, 90, 180, 365].map(d => <option key={d} value={d}>Últimos {d} dias</option>)}
          </select>
        </div>
        <p className="text-xs text-neutral-500">Produtos Shopee frequentemente comprados no mesmo pedido. Sugestão para criar bundles e aumentar ticket médio.</p>

        {erroKits && (
          <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erroKits}</div>
        )}
        {loading ? <p className="text-neutral-500 text-xs">Analisando vendas...</p> : !erroKits && kits.length === 0 ? (
          <p className="text-neutral-600 text-xs">Nenhum par de produtos vendido junto o suficiente no período. Tente um período maior ou sincronize mais pedidos em Shopee &gt; Pedidos.</p>
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
