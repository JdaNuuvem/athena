"use client";

import { useState, useEffect, useCallback } from "react";
import { listarProdutosLoja, estoqueAtualizar, type ProdutoLojaRow } from "@/lib/api";

interface Props {
  lojaNome: string;
}

export default function EstoqueRapidoVirtual({ lojaNome }: Props) {
  const [itens, setItens] = useState<ProdutoLojaRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [ajustandoSku, setAjustandoSku] = useState<string | null>(null);

  const carregar = useCallback(async (termo?: string) => {
    setLoading(true);
    setErro(null);
    try {
      const r = await listarProdutosLoja(lojaNome, { busca: termo, pagina: 1, por_pagina: 50 });
      setItens(r.produtos || []);
      setTotal(r.total || 0);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar estoque");
    } finally {
      setLoading(false);
    }
  }, [lojaNome]);
  useEffect(() => { carregar(); }, [carregar]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    carregar(busca);
  };

  const ajustar = async (sku: string, delta: number, atual: number) => {
    const novaQtd = Math.max(0, Number(atual) + delta);
    setAjustandoSku(sku);
    setErro(null);
    try {
      const r = await estoqueAtualizar(sku, lojaNome, novaQtd);
      if (r.erro) {
        setErro(r.erro);
        return;
      }
      setSucesso(`${sku}: ${delta > 0 ? "+" : ""}${delta}`);
      setTimeout(() => setSucesso(null), 2000);
      await carregar(busca);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao ajustar estoque");
    } finally {
      setAjustandoSku(null);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-xs text-neutral-500">
        Estoque rapido — <span className="text-neutral-400">{lojaNome}</span> · {total} produto{total !== 1 ? "s" : ""}
      </p>

      {erro && <div className="bg-red-900/30 border border-red-800 text-red-400 text-xs px-3 py-2 rounded-lg">{erro}</div>}
      {sucesso && <div className="bg-emerald-900/30 border border-emerald-800 text-emerald-400 text-xs px-3 py-2 rounded-lg">{sucesso}</div>}

      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <input type="text" value={busca} onChange={e => setBusca(e.target.value)}
          placeholder="Buscar SKU ou nome..."
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
        <button type="submit" className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">Buscar</button>
      </form>

      {loading ? (
        <div className="text-neutral-500 text-sm py-8 text-center">Carregando...</div>
      ) : itens.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">Nenhum produto encontrado</p>
        </div>
      ) : (
        <div className="instrument-enter bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-2">SKU</th>
                <th className="text-left p-2">Nome</th>
                <th className="text-right p-2">Estoque</th>
                <th className="text-center p-2">Ajuste rapido</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((item, i) => {
                const atual = Number(item.estoque_atual) || 0;
                return (
                  <tr key={item.id} className={`instrument-hover border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                    <td className="p-2 text-neutral-200 font-mono text-[11px]">{item.sku}</td>
                    <td className="p-2 text-neutral-300 max-w-[220px] truncate">{item.nome_override || item.nome_mestre || "—"}</td>
                    <td className={`p-2 text-right font-mono numeric font-medium ${atual <= 0 ? "text-red-400" : atual < 10 ? "text-amber-400" : "text-emerald-400"}`}>{atual}</td>
                    <td className="p-2 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button onClick={() => ajustar(item.sku, -1, atual)} disabled={ajustandoSku === item.sku || atual <= 0}
                          className="w-6 h-6 rounded bg-neutral-700 text-neutral-300 hover:bg-red-900/50 hover:text-red-400 disabled:opacity-30">−</button>
                        <button onClick={() => ajustar(item.sku, 1, atual)} disabled={ajustandoSku === item.sku}
                          className="w-6 h-6 rounded bg-neutral-700 text-neutral-300 hover:bg-emerald-900/50 hover:text-emerald-400 disabled:opacity-30">+</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
