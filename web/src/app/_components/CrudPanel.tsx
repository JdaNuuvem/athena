"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import Icon from "./Icon";
import CrudFormModal, { type FieldDef } from "./CrudFormModal";
export type { FieldDef };

export interface Column {
  key: string;
  label: string;
  render?: (val: unknown, row: Record<string, unknown>) => React.ReactNode;
  // quando presente, mostra um seletor de filtro pra essa coluna na barra
  // de topo (ex.: Status: Todos/Ativo/Inativo) — filtra so' os registros
  // ja carregados, mesma limitacao do sort de coluna.
  filterOptions?: { label: string; value: string }[];
}

export interface CrudService {
  list: (tabela: string) => Promise<{ data?: unknown[] }>;
  // Opcional — quando presente, o CrudPanel busca em paginas no servidor em
  // vez de carregar a tabela inteira (essencial pra tabelas grandes, ex.
  // cad_clientes com 250k+ linhas). Servicos sem essa funcao (CRM,
  // atendimento) continuam no modo antigo: fetch total + filtro client-side.
  listPaginado?: (tabela: string, pagina: number, porPagina: number, busca?: string) => Promise<{
    data?: unknown[]; total?: number; pagina?: number; por_pagina?: number; total_paginas?: number;
  }>;
  create: (tabela: string, data: Record<string, unknown>) => Promise<unknown>;
  update: (tabela: string, id: number, data: Record<string, unknown>) => Promise<unknown>;
  delete: (tabela: string, id: number) => Promise<unknown>;
}

const defaultService: CrudService = {
  list: api.cadList,
  listPaginado: api.cadListPaginado,
  create: api.cadCreate,
  update: api.cadUpdate,
  delete: api.cadDelete,
};

const POR_PAGINA_OPCOES = [25, 50, 100, 200];

interface CrudPanelProps {
  tabela: string;
  columns: Column[];
  formFields?: FieldDef[];
  title?: string;
  // Modulo RBAC (bate com o codigo real das permissoes: "<modulo>.criar",
  // "<modulo>.editar", "<modulo>.excluir" — ex: "cadastros", "crm").
  permissionPrefix?: string;
  // Cliente HTTP usado pelo CRUD — default aponta pro modulo Cadastros
  // (/api/cadastros/*); outros modulos (ex. CRM, /api/crm/*) passam o seu.
  service?: CrudService;
  // Botoes extras por linha (ex.: "Marcar como Ganha"), renderizados antes de Editar/Excluir.
  rowActions?: (row: Record<string, unknown>) => React.ReactNode;
  // Incrementar esse valor (de fora) forca um refetch — usado quando uma acao externa
  // (rowActions) muda dados sem passar por create/update/delete deste componente.
  reloadKey?: number;
}

export default function CrudPanel({ tabela, columns, formFields, title, permissionPrefix = "cadastros", service = defaultService, rowActions, reloadKey }: CrudPanelProps) {
  const paginado = !!service.listPaginado;
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: Record<string, unknown> }>({ open: false, mode: "create" });
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [busca, setBusca] = useState("");
  const [buscaDebounced, setBuscaDebounced] = useState("");
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(50);
  const [total, setTotal] = useState(0);
  const [totalPaginas, setTotalPaginas] = useState(1);

  // troca de sub-tabela (ex.: Lista -> Enderecos) reseta pagina/busca —
  // senao a pagina 7 de Clientes "vaza" pra dentro de Enderecos, que pode
  // ter so' 1 pagina de dados.
  useEffect(() => { setPagina(1); setBusca(""); setBuscaDebounced(""); }, [tabela]);

  // busca so' dispara fetch no servidor 400ms depois da ultima tecla —
  // sem isso, cada tecla digitada em cad_clientes (250k+ linhas) vira uma
  // query nova.
  useEffect(() => {
    const t = setTimeout(() => { setBuscaDebounced(busca); setPagina(1); }, 400);
    return () => clearTimeout(t);
  }, [busca]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (paginado) {
        const res = await service.listPaginado!(tabela, pagina, porPagina, buscaDebounced || undefined);
        setData((res.data || []) as Record<string, unknown>[]);
        setTotal(res.total ?? 0);
        setTotalPaginas(res.total_paginas ?? 1);
      } else {
        const res = await service.list(tabela);
        setData((res.data || []) as Record<string, unknown>[]);
      }
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [tabela, service, paginado, pagina, porPagina, buscaDebounced]);

  useEffect(() => { fetchData(); }, [fetchData, reloadKey]);

  const openCreate = () => {
    setFormData({});
    setModal({ open: true, mode: "create" });
  };

  const openEdit = (row: Record<string, unknown>) => {
    const fd: Record<string, string> = {};
    if (formFields) {
      for (const f of formFields) fd[f.key] = String(row[f.key] ?? "");
    }
    setFormData(fd);
    setModal({ open: true, mode: "edit", row });
  };

  const handleSave = async () => {
    if (!formFields) return;
    const payload: Record<string, unknown> = {};
    for (const f of formFields) {
      const val = formData[f.key] ?? "";
      if (f.type === "number") payload[f.key] = parseFloat(val) || 0;
      else if (f.type === "date" || f.type === "datetime") payload[f.key] = val || null;
      else if (f.type === "fk" || f.numeric) payload[f.key] = val ? parseInt(val, 10) : null;
      else payload[f.key] = val;
    }
    try {
      if (modal.mode === "create") await service.create(tabela, payload);
      else await service.update(tabela, Number(modal.row?.id), payload);
      setModal({ open: false, mode: "create" });
      fetchData();
    } catch (e) { alert(String(e)); }
  };

  const handleDelete = async (id: number) => {
    try { await service.delete(tabela, id); setConfirmDelete(null); fetchData(); }
    catch (e) { alert(String(e)); }
  };

  const filtered = useMemo(() => {
    if (paginado) return data;
    if (!busca) return data;
    const q = busca.toLowerCase();
    return data.filter(row =>
      columns.some(c => String(row[c.key] ?? "").toLowerCase().includes(q))
    );
  }, [data, busca, columns, paginado]);

  // filtro por coluna (ex.: Status) — assim como o sort, so' enxerga os
  // registros ja carregados.
  const [filtroColuna, setFiltroColuna] = useState<Record<string, string>>({});
  const colunasFiltraveis = useMemo(() => columns.filter(c => c.filterOptions && c.filterOptions.length > 0), [columns]);

  const filtradosPorColuna = useMemo(() => {
    const ativos = Object.entries(filtroColuna).filter(([, v]) => v);
    if (ativos.length === 0) return filtered;
    return filtered.filter(row => ativos.every(([key, valor]) => String(row[key] ?? "") === valor));
  }, [filtered, filtroColuna]);

  const filtroAtivo = (!paginado && !!busca) || Object.values(filtroColuna).some(v => v);

  // ordena so' os registros ja carregados (pagina atual, quando paginado) —
  // nao existe um "sort global" no servidor pra todas as tabelas ainda,
  // mas ordenar a pagina corrente ja resolve o caso de uso comum.
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const ordenados = useMemo(() => {
    if (!sortCol) return filtradosPorColuna;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtradosPorColuna].sort((a, b) => {
      const va = a[sortCol]; const vb = b[sortCol];
      const na = Number(va); const nb = Number(vb);
      if (va != null && vb != null && !Number.isNaN(na) && !Number.isNaN(nb) && va !== "" && vb !== "") {
        return (na - nb) * dir;
      }
      return String(va ?? "").localeCompare(String(vb ?? ""), "pt-BR") * dir;
    });
  }, [filtradosPorColuna, sortCol, sortDir]);

  const alternarSort = (key: string) => {
    if (sortCol === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(key); setSortDir("asc"); }
  };

  const actionCol = columns.length > 0 ? 1 : 0;
  const canManage = !!formFields && formFields.length > 0;
  const bulkCol = canManage ? 1 : 0;

  const [selecionados, setSelecionados] = useState<Set<number>>(new Set());
  // troca de pagina/tabela/busca invalida a selecao — evita excluir em massa
  // linhas de uma pagina que o usuario ja nao esta mais vendo.
  useEffect(() => { setSelecionados(new Set()); }, [data]);

  const alternarSelecao = (id: number) => {
    setSelecionados(prev => {
      const novo = new Set(prev);
      if (novo.has(id)) novo.delete(id); else novo.add(id);
      return novo;
    });
  };

  const idsVisiveis = ordenados.map(r => Number(r.id));
  const todosSelecionados = idsVisiveis.length > 0 && idsVisiveis.every(id => selecionados.has(id));
  const alternarSelecaoTodos = () => setSelecionados(todosSelecionados ? new Set() : new Set(idsVisiveis));

  const [confirmDeleteMassa, setConfirmDeleteMassa] = useState(false);
  const [excluindoEmMassa, setExcluindoEmMassa] = useState(false);

  const handleDeleteMassa = async () => {
    setExcluindoEmMassa(true);
    try {
      await Promise.all([...selecionados].map(id => service.delete(tabela, id)));
      setSelecionados(new Set());
      setConfirmDeleteMassa(false);
      fetchData();
    } catch (e) { alert(String(e)); }
    finally { setExcluindoEmMassa(false); }
  };

  const exportarCSV = () => {
    const escapar = (v: unknown) => {
      const s = String(v ?? "");
      return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const linhas = [
      columns.map(c => escapar(c.label)).join(";"),
      ...ordenados.map(row => columns.map(c => escapar(row[c.key])).join(";")),
    ];
    const csv = "﻿" + linhas.join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${tabela}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {title && <h3 className="text-sm font-semibold text-neutral-200">{title}</h3>}
          {!loading && !error && (
            <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-[10px] font-medium text-neutral-400">
              {filtroAtivo ? `${ordenados.length} de ` : ""}{paginado ? total : data.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {colunasFiltraveis.map(c => (
            <select
              key={c.key}
              value={filtroColuna[c.key] ?? ""}
              onChange={e => setFiltroColuna(prev => ({ ...prev, [c.key]: e.target.value }))}
              className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            >
              <option value="">{c.label}: Todos</option>
              {c.filterOptions!.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ))}
          <div className="relative">
            <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              placeholder="Buscar..."
              value={busca}
              onChange={e => setBusca(e.target.value)}
              className="w-52 rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 pl-8 pr-3 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            />
          </div>
          {paginado && (
            <select
              value={porPagina}
              onChange={e => { setPorPagina(Number(e.target.value)); setPagina(1); }}
              className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            >
              {POR_PAGINA_OPCOES.map(n => <option key={n} value={n}>{n}/pág.</option>)}
            </select>
          )}
          {!loading && !error && ordenados.length > 0 && (
            <button
              onClick={exportarCSV}
              title={paginado ? "Exporta os registros da página atual" : "Exportar CSV"}
              className="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-300 transition-colors hover:bg-neutral-700"
            >
              <Icon name="download" size={13} /> CSV
            </button>
          )}
          {canManage && (
            <Can permission={`${permissionPrefix}.criar`}>
              <button
                onClick={openCreate}
                className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500"
              >
                <span className="text-sm leading-none">+</span> Novo
              </button>
            </Can>
          )}
        </div>
      </div>

      {canManage && selecionados.size > 0 && (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-indigo-700/50 bg-indigo-950/30 px-3 py-2">
          <span className="text-xs text-indigo-300">{selecionados.size} selecionado{selecionados.size > 1 ? "s" : ""}</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setSelecionados(new Set())} className="text-xs text-neutral-400 hover:text-neutral-200">Limpar</button>
            <Can permission={`${permissionPrefix}.excluir`}>
              <button
                onClick={() => setConfirmDeleteMassa(true)}
                className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500"
              >
                Excluir selecionados
              </button>
            </Can>
          </div>
        </div>
      )}

      {loading ? (
        <div className="overflow-hidden rounded-xl border border-neutral-800">
          <div className="divide-y divide-neutral-800/70">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-4 py-3">
                {columns.map((c) => (
                  <div key={c.key} className="h-3 flex-1 animate-pulse rounded bg-neutral-800" />
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-400">
          <Icon name="alert" size={15} className="shrink-0" />
          {error}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-neutral-800">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/60 text-left text-neutral-400">
                {bulkCol > 0 && (
                  <th className="w-8 px-4 py-2.5">
                    <input type="checkbox" checked={todosSelecionados} onChange={alternarSelecaoTodos} className="rounded border-neutral-600 bg-neutral-700 accent-indigo-600" />
                  </th>
                )}
                {columns.map(c => (
                  <th key={c.key} onClick={() => alternarSort(c.key)} className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium transition-colors hover:text-neutral-200">
                    <span className="inline-flex items-center gap-1">
                      {c.label}
                      {sortCol === c.key && <Icon name="chevronDown" size={11} className={sortDir === "asc" ? "rotate-180" : ""} />}
                    </span>
                  </th>
                ))}
                {(canManage || rowActions) && <th className="px-4 py-2.5 font-medium text-right">Ações</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/70">
              {ordenados.map((row, i) => (
                <tr key={String(row.id)} className={`text-neutral-300 transition-colors hover:bg-neutral-800/50 ${i % 2 === 1 ? "bg-neutral-900/30" : ""}`}>
                  {bulkCol > 0 && (
                    <td className="px-4 py-2.5">
                      <input type="checkbox" checked={selecionados.has(Number(row.id))} onChange={() => alternarSelecao(Number(row.id))} className="rounded border-neutral-600 bg-neutral-700 accent-indigo-600" />
                    </td>
                  )}
                  {columns.map(c => (
                    <td key={c.key} className="whitespace-nowrap px-4 py-2.5">
                      {c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}
                    </td>
                  ))}
                  {(canManage || rowActions) && (
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end items-center gap-1">
                        {rowActions?.(row)}
                        <Can permission={`${permissionPrefix}.editar`}>
                          <button
                            onClick={() => openEdit(row)}
                            title="Editar"
                            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-400"
                          >
                            <Icon name="pencil" size={13} />
                          </button>
                        </Can>
                        <Can permission={`${permissionPrefix}.excluir`}>
                          <button
                            onClick={() => setConfirmDelete(Number(row.id))}
                            title="Excluir"
                            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400"
                          >
                            <Icon name="trash" size={13} />
                          </button>
                        </Can>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {ordenados.length === 0 && (
                <tr>
                  <td colSpan={columns.length + actionCol + bulkCol} className="px-4 py-10">
                    <div className="flex flex-col items-center gap-2 text-neutral-500">
                      <Icon name="inbox" size={22} />
                      <span className="text-xs">{busca ? "Nenhum registro corresponde à busca" : "Nenhum registro cadastrado"}</span>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {paginado && !loading && !error && totalPaginas > 1 && (
        <div className="flex items-center justify-between gap-2 text-xs text-neutral-400">
          <span>Página {pagina} de {totalPaginas}</span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPagina(p => Math.max(1, p - 1))}
              disabled={pagina <= 1}
              className="rounded-lg border border-neutral-700 px-2.5 py-1.5 text-neutral-300 transition-colors hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <Icon name="chevronLeft" size={13} />
            </button>
            <button
              onClick={() => setPagina(p => Math.min(totalPaginas, p + 1))}
              disabled={pagina >= totalPaginas}
              className="rounded-lg border border-neutral-700 px-2.5 py-1.5 text-neutral-300 transition-colors hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <Icon name="chevronRight" size={13} />
            </button>
          </div>
        </div>
      )}

      {modal.open && formFields && (
        <CrudFormModal
          mode={modal.mode}
          fields={formFields}
          formData={formData}
          onChange={(key, value) => setFormData(prev => ({ ...prev, [key]: value }))}
          onSave={handleSave}
          onClose={() => setModal({ open: false, mode: "create" })}
        />
      )}

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setConfirmDelete(null)}>
          <div className="w-full max-w-[340px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-red-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Confirmar exclusão</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">Tem certeza que deseja excluir este registro? Essa ação não pode ser desfeita.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={() => handleDelete(confirmDelete)} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500">Excluir</button>
            </div>
          </div>
        </div>
      )}

      {confirmDeleteMassa && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setConfirmDeleteMassa(false)}>
          <div className="w-full max-w-[340px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-red-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Confirmar exclusão em massa</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">Tem certeza que deseja excluir {selecionados.size} registro{selecionados.size > 1 ? "s" : ""}? Essa ação não pode ser desfeita.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDeleteMassa(false)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={handleDeleteMassa} disabled={excluindoEmMassa} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500 disabled:opacity-50">
                {excluindoEmMassa ? "Excluindo..." : "Excluir"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
