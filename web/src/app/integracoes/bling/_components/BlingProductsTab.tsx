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
  listarBlingDepositos,
  obterSaldoDeposito,
  atualizarEstoqueDeposito,
  BlingProduto,
  BlingDeposito,
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
  const [depositos, setDepositos] = useState<BlingDeposito[]>([]);

  // Stock inline editor state
  const [editStockId, setEditStockId] = useState<number | null>(null);
  const [editStockQty, setEditStockQty] = useState(0);
  const [editStockDeposit, setEditStockDeposit] = useState<number>(0);

  const carregar = useCallback(async (p = 1) => {
    try {
      setLoading(true);
      setErro(null);
      const [r, d] = await Promise.all([
        listarBlingProdutos(p, 50),
        listarBlingDepositos().catch(() => ({ data: [] })),
      ]);
      if (r.error) throw new Error(r.error);
      setProdutos(r.data || []);
      setDepositos(d.data || []);
      if (d.data?.length && !editStockDeposit) setEditStockDeposit(d.data[0].id);
      setPagina(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const getStock = (p: BlingProduto) => {
    const s = (p as any).estoque;
    return s?.saldoFisicoTotal ?? (p as any).saldoFisicoTotal ?? 0;
  };

  const handleQuickStock = async (prod: BlingProduto, delta: number) => {
    if (!editStockDeposit) return;
    try {
      await atualizarEstoqueDeposito({
        idDeposito: editStockDeposit,
        idProduto: prod.id,
        operacao: delta > 0 ? "E" : "S",
        quantidade: Math.abs(delta),
      });
      setSucesso(`${prod.codigo}: estoque ${delta > 0 ? "+" : ""}${delta}`);
      carregar(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao ajustar estoque");
    }
  };

  const handleStockApply = async (prod: BlingProduto) => {
    if (!editStockDeposit || editStockQty <= 0) return;
    try {
      await atualizarEstoqueDeposito({
        idDeposito: editStockDeposit,
        idProduto: prod.id,
        operacao: "B",
        quantidade: editStockQty,
      });
      setSucesso(`${prod.codigo}: estoque ajustado para ${editStockQty}`);
      setEditStockId(null);
      carregar(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao ajustar estoque");
    }
  };

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

  const stockColor = (qty: number) => {
    if (qty <= 0) return "text-red-400";
    if (qty < 10) return "text-yellow-400";
    return "text-emerald-400";
  };

  if (loading && produtos.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          {onNewProduct && <button onClick={onNewProduct} className="px-3 py-1.5 bg-emerald-600 text-white text-xs rounded-lg hover:bg-emerald-500 transition-colors">+ Novo</button>}
          <button onClick={handleSync} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors">🔄 Sincronizar</button>
          {selected.size > 0 && (
            <>
              <button onClick={() => handleBulkStatus("A")} className="px-3 py-1.5 bg-emerald-600 text-white text-xs rounded-lg hover:bg-emerald-500">Ativar ({selected.size})</button>
              <button onClick={() => handleBulkStatus("I")} className="px-3 py-1.5 bg-yellow-600 text-white text-xs rounded-lg hover:bg-yellow-500">Inativar ({selected.size})</button>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {depositos.length > 0 && (
            <select value={editStockDeposit} onChange={(e) => setEditStockDeposit(Number(e.target.value))}
              className="bg-neutral-700 border border-neutral-600 rounded px-2 py-1 text-xs text-neutral-200">
              {depositos.map((d) => (
                <option key={d.id} value={d.id}>{d.descricao}</option>
              ))}
            </select>
          )}
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
                <th className="text-center p-3 w-40">Estoque</th>
                <th className="text-left p-3">Categoria</th>
                <th className="text-center p-3">Status</th>
                <th className="text-right p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {produtos.map((p, i) => {
                const stock = getStock(p);
                const isEditing = editStockId === p.id;
                return (
                <tr key={p.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3"><input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} /></td>
                  <td className="p-3 text-neutral-200 font-mono">{p.codigo}</td>
                  <td className="p-3 text-neutral-200 max-w-[200px] truncate" title={p.descricao}>{p.descricao || "—"}</td>
                  <td className="p-3 text-right text-emerald-400">R$ {(p.preco || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3 text-center">
                    {isEditing ? (
                      <div className="flex items-center gap-1 justify-center">
                        <input
                          type="number"
                          min="0"
                          value={editStockQty}
                          onChange={(e) => setEditStockQty(Number(e.target.value))}
                          className="w-16 bg-neutral-900 border border-neutral-600 rounded px-2 py-1 text-xs text-neutral-200 text-center"
                          autoFocus
                          onKeyDown={(e) => { if (e.key === "Enter") handleStockApply(p); if (e.key === "Escape") setEditStockId(null); }}
                        />
                        <button onClick={() => handleStockApply(p)} className="text-emerald-400 hover:text-emerald-300 font-bold text-xs px-1">✓</button>
                        <button onClick={() => setEditStockId(null)} className="text-neutral-500 hover:text-neutral-300 font-bold text-xs px-1">✕</button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => handleQuickStock(p, -1)}
                          className="text-neutral-500 hover:text-red-400 text-xs font-bold leading-none px-1"
                          title="Remover 1"
                        >−</button>
                        <span
                          className={`font-mono cursor-pointer hover:underline ${stockColor(Number(stock))}`}
                          onClick={() => { setEditStockId(p.id); setEditStockQty(Number(stock)); }}
                          title="Clique para editar"
                        >{stock}</span>
                        <button
                          onClick={() => handleQuickStock(p, 1)}
                          className="text-neutral-500 hover:text-emerald-400 text-xs font-bold leading-none px-1"
                          title="Adicionar 1"
                        >+</button>
                      </div>
                    )}
                  </td>
                  <td className="p-3 text-neutral-400 text-[10px]">{((p as any).categoria?.descricao || "—")}</td>
                  <td className="p-3 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] ${p.situacao === "A" ? "bg-emerald-900/30 text-emerald-400" : "bg-neutral-700 text-neutral-400"}`}>
                      {p.situacao === "A" ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <button onClick={() => handleDelete(p.id)} className="text-red-400 hover:text-red-300">🗑</button>
                  </td>
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
