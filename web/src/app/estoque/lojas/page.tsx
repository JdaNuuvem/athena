"use client";

import { useState, useEffect, useCallback } from "react";
import { estoqueLojas, estoqueAtualizar, request, type EstoqueLojaRow } from "@/lib/api";
import { Can } from "@/lib/auth";

function SyncBadge({ status }: { status?: string }) {
  if (!status || status === "ok") return <span className="text-[10px] text-emerald-500" title="Sincronizado">✓</span>;
  if (status === "pendente") return <span className="text-[10px] text-amber-400 animate-pulse" title="Pendente">⏳</span>;
  return <span className="text-[10px] text-red-400" title="Erro">✗</span>;
}

export default function EstoqueLojasPage() {
  const [rows, setRows] = useState<EstoqueLojaRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const POR_PAGINA = 25;

  const [editing, setEditing] = useState<number | null>(null);
  const [editQty, setEditQty] = useState(0);
  const [lojaFilter, setLojaFilter] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("loja") || "";
  });

  const load = useCallback(async (search?: string, pg?: number) => {
    setLoading(true);
    setErro(null);
    try {
      const p = pg ?? 1;
      const loja = lojaFilter === "todas" ? "" : lojaFilter;
      const q = new URLSearchParams();
      if (search) q.set("busca", search);
      if (loja) q.set("loja", loja);
      q.set("pagina", String(p));
      q.set("por_pagina", String(POR_PAGINA));
      const r = await estoqueLojas(q.toString());
      setRows(r.estoque ?? []);
      setTotal(r.total ?? 0);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar estoque");
    } finally {
      setLoading(false);
    }
  }, [lojaFilter]);

  useEffect(() => { load(busca, 1); }, [load]);

  useEffect(() => {
    const handler = () => {
      const l = localStorage.getItem("loja") || "";
      setLojaFilter(l);
      load(busca, 1);
    };
    window.addEventListener("loja-changed", handler);
    return () => window.removeEventListener("loja-changed", handler);
  }, [load, busca]);

  const startEdit = (row: EstoqueLojaRow) => {
    setEditing(row.id);
    setEditQty(row.quantidade);
  };

  const cancelEdit = () => {
    setEditing(null);
    setEditQty(0);
  };

  const saveEdit = async (row: EstoqueLojaRow) => {
    try {
      const r = await estoqueAtualizar(row.sku, row.loja, editQty);
      setRows(prev => prev.map(r2 => r2.id === row.id ? { ...r2, quantidade: editQty } : r2));
      let msg = `Estoque de ${row.sku} atualizado`;
      if (r.bling_sync && (r.bling_sync as Record<string, unknown>).error) msg += " (Bling: erro)";
      else if (r.bling_sync) msg += " (Bling: ✓)";
      setOkMsg(msg);
      setTimeout(() => setOkMsg(null), 2500);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    }
    setEditing(null);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load(busca, 1);
  };

  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Estoque por Depósito</h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          {total} registro{total !== 1 ? "s" : ""} de estoque
          {lojaFilter && lojaFilter !== "todas" ? ` (filtrado)` : ""}
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={async () => { setRetrying(true); await request("/api/estoque/sync/processar", { method: "POST" }).catch(() => {}); setRetrying(false); load(busca, pagina); }}
          disabled={retrying}
          className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
        >
          {retrying ? "Processando..." : "Retry Sync"}
        </button>
      </div>

      {erro && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      )}
      {okMsg && (
        <div className="text-emerald-400 text-sm bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-4 py-3">{okMsg}</div>
      )}

      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <label htmlFor="buscaEstoque" className="sr-only">Buscar SKU</label>
        <input
          id="buscaEstoque"
          type="text"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por SKU ou nome..."
          className="flex-1 bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent"
        />
        <button type="submit" className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 rounded-lg text-sm transition-colors">
          Buscar
        </button>
      </form>

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : rows.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">
          Nenhum estoque encontrado
        </div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Nome</th>
                  <th className="text-left px-4 py-3 font-medium">Depósito</th>
                  <th className="text-right px-4 py-3 font-medium w-28">Qtd</th>
                  <th className="text-right px-4 py-3 font-medium w-48">Atualizado</th>
                  <th className="text-center px-2 py-3 font-medium w-10">Sync</th>
                  <th className="text-center px-4 py-3 font-medium w-20">Ações</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/20">
                    <td className="px-4 py-2.5 font-mono text-xs text-neutral-500">{r.sku}</td>
                    <td className="px-4 py-2.5 text-neutral-300 max-w-64 truncate">{r.nome}</td>
                    <td className="px-4 py-2.5 text-neutral-400">{r.loja}</td>
                    <td className="px-4 py-2.5 text-right">
                      {editing === r.id ? (
                        <input
                          type="number"
                          step="0.001"
                          value={editQty}
                          onChange={(e) => setEditQty(Number(e.target.value))}
                          className="w-20 bg-neutral-800 border border-indigo-600 rounded px-2 py-0.5 text-sm text-right text-neutral-200 focus:outline-none"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveEdit(r);
                            if (e.key === "Escape") cancelEdit();
                          }}
                        />
                      ) : (
                        <span className={`font-mono numeric ${r.quantidade <= 0 ? "text-red-400" : r.quantidade < 10 ? "text-amber-400" : "text-emerald-400"}`}>
                          {r.quantidade.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right text-xs text-neutral-600">
                      {r.data_atualizacao ? new Date(r.data_atualizacao).toLocaleString("pt-BR") : "—"}
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      <SyncBadge status={r.sync_status} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {editing === r.id ? (
                        <div className="flex gap-1 justify-center">
                          <button onClick={() => saveEdit(r)} className="text-emerald-400 hover:text-emerald-300 text-xs">✓</button>
                          <button onClick={cancelEdit} className="text-red-400 hover:text-red-300 text-xs">✗</button>
                        </div>
                      ) : (
                        <Can permission="ver_estoque">
                          <button onClick={() => startEdit(r)} className="text-indigo-400 hover:text-indigo-300 text-xs">Editar</button>
                        </Can>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {totalPaginas > 1 && (
        <div className="flex items-center justify-center gap-1">
          <button
            disabled={pagina <= 1}
            onClick={() => { setPagina(pagina - 1); load(busca, pagina - 1); }}
            className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30"
          >‹</button>
          {Array.from({ length: Math.min(totalPaginas, 7) }, (_, i) => {
            const start = Math.max(1, Math.min(pagina - 3, totalPaginas - 6));
            const p = start + i;
            if (p > totalPaginas) return null;
            return (
              <button
                key={p}
                onClick={() => { setPagina(p); load(busca, p); }}
                className={`px-2.5 py-1 text-xs rounded ${p === pagina ? "bg-indigo-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"}`}
              >{p}</button>
            );
          })}
          <button
            disabled={pagina >= totalPaginas}
            onClick={() => { setPagina(pagina + 1); load(busca, pagina + 1); }}
            className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30"
          >›</button>
        </div>
      )}
    </div>
  );
}
