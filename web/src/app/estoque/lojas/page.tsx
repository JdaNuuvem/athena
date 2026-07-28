"use client";

import { useState, useEffect, useCallback } from "react";
import { listarProdutosLoja, atualizarProdutoLoja, type ProdutoLojaRow } from "@/lib/api";
import { Can } from "@/lib/auth";

interface EditFields {
  preco_custo: string;
  preco_venda: string;
  fornecedor_id: string;
  estoque_minimo: string;
  estoque_maximo: string;
  localizacao_fisica: string;
}

const EMPTY_EDIT: EditFields = {
  preco_custo: "",
  preco_venda: "",
  fornecedor_id: "",
  estoque_minimo: "",
  estoque_maximo: "",
  localizacao_fisica: "",
};

function fmtMoeda(v: number | null) {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function EstoqueLojasPage() {
  const [rows, setRows] = useState<ProdutoLojaRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const [busca, setBusca] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("busca") || "";
  });
  const [pagina, setPagina] = useState(1);
  const POR_PAGINA = 25;

  const [editing, setEditing] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditFields>(EMPTY_EDIT);

  const [lojaFilter, setLojaFilter] = useState(() => {
    if (typeof window === "undefined") return "";
    const v = localStorage.getItem("loja") || "";
    return v === "todas" ? "" : v;
  });

  const load = useCallback(async (search?: string, pg?: number) => {
    if (!lojaFilter) {
      setRows([]);
      setTotal(0);
      setLoading(false);
      return;
    }
    setLoading(true);
    setErro(null);
    try {
      const p = pg ?? 1;
      const r = await listarProdutosLoja(lojaFilter, { busca: search, pagina: p, por_pagina: POR_PAGINA });
      setRows(r.produtos ?? []);
      setTotal(r.total ?? 0);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar produtos da loja");
    } finally {
      setLoading(false);
    }
  }, [lojaFilter]);

  useEffect(() => { load(busca, 1); }, [load]);

  useEffect(() => {
    const handler = () => {
      const l = localStorage.getItem("loja") || "";
      setLojaFilter(l === "todas" ? "" : l);
      load(busca, 1);
    };
    window.addEventListener("loja-changed", handler);
    return () => window.removeEventListener("loja-changed", handler);
  }, [load, busca]);

  const startEdit = (row: ProdutoLojaRow) => {
    setEditing(row.id);
    setEditForm({
      preco_custo: row.preco_custo != null ? String(row.preco_custo) : "",
      preco_venda: row.preco_venda != null ? String(row.preco_venda) : "",
      fornecedor_id: row.fornecedor_id != null ? String(row.fornecedor_id) : "",
      estoque_minimo: row.estoque_minimo != null ? String(row.estoque_minimo) : "",
      estoque_maximo: row.estoque_maximo != null ? String(row.estoque_maximo) : "",
      localizacao_fisica: row.localizacao_fisica ?? "",
    });
  };

  const cancelEdit = () => {
    setEditing(null);
    setEditForm(EMPTY_EDIT);
  };

  const salvarEdicao = async (row: ProdutoLojaRow) => {
    const campos: Record<string, unknown> = {
      preco_custo: editForm.preco_custo === "" ? null : Number(editForm.preco_custo),
      preco_venda: editForm.preco_venda === "" ? null : Number(editForm.preco_venda),
      fornecedor_id: editForm.fornecedor_id === "" ? null : Number(editForm.fornecedor_id),
      estoque_minimo: editForm.estoque_minimo === "" ? null : Number(editForm.estoque_minimo),
      estoque_maximo: editForm.estoque_maximo === "" ? null : Number(editForm.estoque_maximo),
      localizacao_fisica: editForm.localizacao_fisica === "" ? null : editForm.localizacao_fisica,
    };
    try {
      const r = await atualizarProdutoLoja(row.loja, row.sku, campos);
      if (r.erro) {
        setErro(r.erro);
        return;
      }
      setOkMsg(`Dados de ${row.sku} atualizados`);
      setTimeout(() => setOkMsg(null), 2500);
      setEditing(null);
      setEditForm(EMPTY_EDIT);
      load(busca, pagina);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load(busca, 1);
  };

  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-light text-neutral-300">Produtos por Loja</h1>
          <p className="text-xs text-neutral-500 mt-0.5">
            {lojaFilter ? `${total} registro${total !== 1 ? "s" : ""}` : "Selecione uma loja no topo da página"}
          </p>
        </div>
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

      {!lojaFilter ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">
          Selecione uma loja para ver e editar os produtos.
        </div>
      ) : loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : rows.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">
          Nenhum produto encontrado nesta loja. Sincronize os produtos em{" "}
          <a href="/lojas" className="text-indigo-400 underline">Lojas</a>.
        </div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Nome</th>
                  <th className="text-right px-4 py-3 font-medium w-24">Estoque Atual</th>
                  <th className="text-right px-4 py-3 font-medium w-28">Preço Custo</th>
                  <th className="text-right px-4 py-3 font-medium w-28">Preço Venda</th>
                  <th className="text-right px-4 py-3 font-medium w-24">Fornecedor</th>
                  <th className="text-right px-4 py-3 font-medium w-20">Estoque Mín</th>
                  <th className="text-right px-4 py-3 font-medium w-20">Estoque Máx</th>
                  <th className="text-left px-4 py-3 font-medium w-32">Localização</th>
                  <th className="text-center px-4 py-3 font-medium w-20">Ações</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const isEditing = editing === r.id;
                  return (
                    <tr key={r.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/20">
                      <td className="px-4 py-2.5 font-mono text-xs text-neutral-500">{r.sku}</td>
                      <td className="px-4 py-2.5 text-neutral-300 max-w-64 truncate">{r.nome_override || r.nome_mestre || "—"}</td>
                      <td className="px-4 py-2.5 text-right">
                        <span className={`font-mono numeric font-medium ${
                          r.estoque_atual <= 0 ? "text-red-400" : r.estoque_atual < 10 ? "text-amber-400" : "text-emerald-400"
                        }`}>
                          {r.estoque_atual.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.01"
                            value={editForm.preco_custo}
                            onChange={(e) => setEditForm({ ...editForm, preco_custo: e.target.value })}
                            className="w-24 bg-neutral-800 border border-indigo-600 rounded px-2 py-0.5 text-sm text-right text-neutral-200 focus:outline-none"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter") salvarEdicao(r);
                              if (e.key === "Escape") cancelEdit();
                            }}
                          />
                        ) : (
                          <span className="text-neutral-400">{fmtMoeda(r.preco_custo)}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.01"
                            value={editForm.preco_venda}
                            onChange={(e) => setEditForm({ ...editForm, preco_venda: e.target.value })}
                            className="w-24 bg-neutral-800 border border-indigo-600 rounded px-2 py-0.5 text-sm text-right text-neutral-200 focus:outline-none"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") salvarEdicao(r);
                              if (e.key === "Escape") cancelEdit();
                            }}
                          />
                        ) : (
                          <span className="text-neutral-300 font-medium">{fmtMoeda(r.preco_venda)}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {isEditing ? (
                          <input
                            type="number"
                            step="1"
                            value={editForm.fornecedor_id}
                            onChange={(e) => setEditForm({ ...editForm, fornecedor_id: e.target.value })}
                            className="w-20 bg-neutral-800 border border-indigo-600 rounded px-2 py-0.5 text-sm text-right text-neutral-200 focus:outline-none"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") salvarEdicao(r);
                              if (e.key === "Escape") cancelEdit();
                            }}
                          />
                        ) : (
                          <span className="text-neutral-500">{r.fornecedor_id ?? "—"}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.001"
                            value={editForm.estoque_minimo}
                            onChange={(e) => setEditForm({ ...editForm, estoque_minimo: e.target.value })}
                            className="w-16 bg-neutral-800 border border-indigo-600 rounded px-2 py-0.5 text-sm text-right text-neutral-200 focus:outline-none"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") salvarEdicao(r);
                              if (e.key === "Escape") cancelEdit();
                            }}
                          />
                        ) : (
                          <span className="text-neutral-500">{r.estoque_minimo ?? "—"}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.001"
                            value={editForm.estoque_maximo}
                            onChange={(e) => setEditForm({ ...editForm, estoque_maximo: e.target.value })}
                            className="w-16 bg-neutral-800 border border-indigo-600 rounded px-2 py-0.5 text-sm text-right text-neutral-200 focus:outline-none"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") salvarEdicao(r);
                              if (e.key === "Escape") cancelEdit();
                            }}
                          />
                        ) : (
                          <span className="text-neutral-500">{r.estoque_maximo ?? "—"}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-left">
                        {isEditing ? (
                          <input
                            type="text"
                            value={editForm.localizacao_fisica}
                            onChange={(e) => setEditForm({ ...editForm, localizacao_fisica: e.target.value })}
                            className="w-28 bg-neutral-800 border border-indigo-600 rounded px-2 py-0.5 text-sm text-neutral-200 focus:outline-none"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") salvarEdicao(r);
                              if (e.key === "Escape") cancelEdit();
                            }}
                          />
                        ) : (
                          <span className="text-neutral-500 text-xs">{r.localizacao_fisica || "—"}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {isEditing ? (
                          <div className="flex gap-1 justify-center">
                            <button onClick={() => salvarEdicao(r)} className="text-emerald-400 hover:text-emerald-300 text-xs">✓</button>
                            <button onClick={cancelEdit} className="text-red-400 hover:text-red-300 text-xs">✗</button>
                          </div>
                        ) : (
                          <Can permission="ver_estoque">
                            <button onClick={() => startEdit(r)} className="text-indigo-400 hover:text-indigo-300 text-xs">Editar</button>
                          </Can>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {totalPaginas > 1 && (
        <div className="flex items-center justify-center gap-1">
          <button disabled={pagina <= 1} onClick={() => { setPagina(pagina - 1); load(busca, pagina - 1); }}
            className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30">‹</button>
          {Array.from({ length: Math.min(totalPaginas, 7) }, (_, i) => {
            const start = Math.max(1, Math.min(pagina - 3, totalPaginas - 6));
            const p = start + i;
            if (p > totalPaginas) return null;
            return (
              <button key={p} onClick={() => { setPagina(p); load(busca, p); }}
                className={`px-2.5 py-1 text-xs rounded ${p === pagina ? "bg-indigo-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"}`}
              >{p}</button>
            );
          })}
          <button disabled={pagina >= totalPaginas} onClick={() => { setPagina(pagina + 1); load(busca, pagina + 1); }}
            className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30">›</button>
        </div>
      )}
    </div>
  );
}
