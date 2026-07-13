"use client";

import { useEffect, useState, useCallback } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import EmptyState from "./shared/EmptyState";
import {
  listarBlingProdutos,
  deletarBlingProduto,
  atualizarSituacaoProdutos,
  sincronizarBlingProdutos,
  BlingProduto,
} from "@/lib/api";

interface BlingProductsTabProps {
  onNewProduct?: () => void;
  onStockManage?: () => void;
}

export default function BlingProductsTab({ onNewProduct, onStockManage }: BlingProductsTabProps) {
  const [produtos, setProdutos] = useState<BlingProduto[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pagina, setPagina] = useState(1);

  const carregar = useCallback(async (p = 1) => {
    try {
      setLoading(true);
      setErro(null);
      const r = await listarBlingProdutos(p, 50);
      if (r.error) throw new Error(r.error);
      setProdutos(r.data || []);
      setPagina(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === produtos.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(produtos.map((p) => p.id)));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remover este produto?")) return;
    try {
      await deletarBlingProduto(id);
      setSucesso("Produto removido");
      carregar(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao remover");
    }
  };

  const handleBulkStatus = async (situacao: string) => {
    if (selected.size === 0) return;
    try {
      await atualizarSituacaoProdutos(Array.from(selected), situacao);
      setSucesso(`${selected.size} produto(s) atualizado(s)`);
      setSelected(new Set());
      carregar(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao atualizar");
    }
  };

  const handleSync = async () => {
    try {
      setLoading(true);
      const r = await sincronizarBlingProdutos();
      setSucesso(`${r.sincronizados || 0} produtos sincronizados`);
      carregar(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro na sincronização");
    } finally {
      setLoading(false);
    }
  };

  if (loading && produtos.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          {onNewProduct && <button onClick={onNewProduct} className="px-3 py-1.5 bg-emerald-600 text-white text-xs rounded-lg hover:bg-emerald-500 transition-colors">+ Novo</button>}
          {onStockManage && <button onClick={onStockManage} className="px-3 py-1.5 bg-amber-600 text-white text-xs rounded-lg hover:bg-amber-500 transition-colors">📦 Estoque</button>}
          <button onClick={handleSync} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors">🔄 Sincronizar</button>
          {selected.size > 0 && (
            <>
              <button onClick={() => handleBulkStatus("A")} className="px-3 py-1.5 bg-emerald-600 text-white text-xs rounded-lg hover:bg-emerald-500">Ativar ({selected.size})</button>
              <button onClick={() => handleBulkStatus("I")} className="px-3 py-1.5 bg-yellow-600 text-white text-xs rounded-lg hover:bg-yellow-500">Inativar ({selected.size})</button>
            </>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={() => carregar(Math.max(1, pagina - 1))} disabled={pagina <= 1} className="px-2 py-1 bg-neutral-700 text-neutral-300 text-xs rounded disabled:opacity-40">←</button>
          <span className="text-xs text-neutral-400 py-1">Pág {pagina}</span>
          <button onClick={() => carregar(pagina + 1)} disabled={produtos.length < 50} className="px-2 py-1 bg-neutral-700 text-neutral-300 text-xs rounded disabled:opacity-40">→</button>
        </div>
      </div>

      {produtos.length === 0 ? (
        <EmptyState icon="📦" title="Nenhum produto" description="Sincronize produtos do Bling para começar." action={{ label: "Sincronizar Agora", onClick: handleSync }} />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400">
                <th className="p-3 w-8"><input type="checkbox" checked={selected.size === produtos.length && produtos.length > 0} onChange={toggleAll} /></th>
                <th className="text-left p-3">SKU</th>
                <th className="text-left p-3">Nome</th>
                <th className="text-right p-3">Preço</th>
                <th className="text-center p-3">Status</th>
                <th className="text-right p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {produtos.map((p, i) => (
                <tr key={p.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3"><input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} /></td>
                  <td className="p-3 text-neutral-200 font-mono">{p.codigo}</td>
                  <td className="p-3 text-neutral-200">{p.descricao}</td>
                  <td className="p-3 text-right text-emerald-400">R$ {(p.preco || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] ${p.situacao === "A" ? "bg-emerald-900/30 text-emerald-400" : "bg-neutral-700 text-neutral-400"}`}>
                      {p.situacao === "A" ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <button onClick={() => handleDelete(p.id)} className="text-red-400 hover:text-red-300">🗑</button>
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
