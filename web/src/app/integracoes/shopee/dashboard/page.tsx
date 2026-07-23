"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ShopeeDashboardLoja } from "@/lib/api";

export default function ShopeeDashboardPage() {
  const [lojas, setLojas] = useState<ShopeeDashboardLoja[]>([]);
  const [dias, setDias] = useState(30);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeeDashboard(dias);
      if (r.error) setErro(r.error);
      setLojas(r.lojas || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar painel");
    } finally {
      setLoading(false);
    }
  }, [dias]);

  useEffect(() => { carregar(); }, [carregar]);

  const totalReceita = lojas.reduce((s, l) => s + Number(l.receita || 0), 0);
  const totalUnidades = lojas.reduce((s, l) => s + Number(l.unidades_vendidas || 0), 0);
  const totalAnunciosAtivos = lojas.reduce((s, l) => s + Number(l.anuncios_ativos || 0), 0);
  const totalEstoqueBaixo = lojas.reduce((s, l) => s + Number(l.produtos_estoque_baixo || 0), 0);
  const maiorReceita = Math.max(1, ...lojas.map(l => Number(l.receita || 0)));

  return (
    <div className="p-6 space-y-4 max-w-5xl">
      <div>
        <Link href="/integracoes/shopee" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">← Shopee</Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Painel Consolidado Shopee</h1>
        <p className="text-xs text-neutral-500 mt-0.5">Comparativo entre todas as lojas Shopee conectadas.</p>
      </div>

      <div className="flex items-center gap-2">
        <select
          value={dias}
          onChange={(e) => setDias(Number(e.target.value))}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        >
          <option value={7}>Últimos 7 dias</option>
          <option value={30}>Últimos 30 dias</option>
          <option value={90}>Últimos 90 dias</option>
        </select>
        <button
          onClick={carregar}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {loading ? "Carregando..." : "Atualizar"}
        </button>
      </div>

      {erro && (
        <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>
      )}

      {!loading && lojas.length === 0 && !erro && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
          Nenhuma loja Shopee conectada ainda.
        </div>
      )}

      {lojas.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Receita Total</p>
            <p className="text-lg text-emerald-400 numeric font-medium">R$ {totalReceita.toFixed(2)}</p>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Unidades Vendidas</p>
            <p className="text-lg text-neutral-200 numeric font-medium">{totalUnidades}</p>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Anúncios Ativos</p>
            <p className="text-lg text-neutral-200 numeric font-medium">{totalAnunciosAtivos}</p>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Estoque Baixo</p>
            <p className={`text-lg numeric font-medium ${totalEstoqueBaixo > 0 ? "text-amber-400" : "text-neutral-200"}`}>{totalEstoqueBaixo}</p>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {lojas.map((l) => (
          <div key={l.loja_id} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <p className="text-sm text-neutral-200 font-medium">{l.nome}</p>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${l.tem_token ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"}`}>
                  {l.tem_token ? "● Ativa" : "✗ Sem token"}
                </span>
              </div>
              <span className="text-sm text-emerald-400 numeric font-medium">R$ {Number(l.receita || 0).toFixed(2)}</span>
            </div>
            <div className="w-full bg-neutral-800 rounded-full h-1.5 overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.round((Number(l.receita || 0) / maiorReceita) * 100)}%` }} />
            </div>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div>
                <p className="text-[10px] text-neutral-500">Unidades</p>
                <p className="text-xs text-neutral-300 numeric">{l.unidades_vendidas}</p>
              </div>
              <div>
                <p className="text-[10px] text-neutral-500">SKUs vendidos</p>
                <p className="text-xs text-neutral-300 numeric">{l.skus_vendidos}</p>
              </div>
              <div>
                <p className="text-[10px] text-neutral-500">Anúncios ativos</p>
                <p className="text-xs text-neutral-300 numeric">{l.anuncios_ativos} / {l.anuncios_total}</p>
              </div>
              <div>
                <p className="text-[10px] text-neutral-500">Estoque baixo</p>
                <p className={`text-xs numeric ${l.produtos_estoque_baixo > 0 ? "text-amber-400" : "text-neutral-300"}`}>{l.produtos_estoque_baixo}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
