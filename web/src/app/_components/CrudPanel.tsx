"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import Icon from "./Icon";

export interface FieldDef {
  key: string;
  label: string;
  type?: "text" | "number" | "select" | "date" | "datetime";
  options?: { label: string; value: string }[];
  step?: string;
  min?: number;
  max?: number;
  // Campo "select" cujo valor deve ser enviado como numero (ex.: FK de id) em vez de string.
  numeric?: boolean;
}

export interface Column {
  key: string;
  label: string;
  render?: (val: unknown, row: Record<string, unknown>) => React.ReactNode;
}

export interface CrudService {
  list: (tabela: string) => Promise<{ data?: unknown[] }>;
  create: (tabela: string, data: Record<string, unknown>) => Promise<unknown>;
  update: (tabela: string, id: number, data: Record<string, unknown>) => Promise<unknown>;
  delete: (tabela: string, id: number) => Promise<unknown>;
}

const defaultService: CrudService = {
  list: api.cadList,
  create: api.cadCreate,
  update: api.cadUpdate,
  delete: api.cadDelete,
};

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
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: Record<string, unknown> }>({ open: false, mode: "create" });
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [busca, setBusca] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await service.list(tabela);
      setData((res.data || []) as Record<string, unknown>[]);
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [tabela, service]);

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
      else if (f.numeric) payload[f.key] = val ? parseInt(val, 10) : null;
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
    if (!busca) return data;
    const q = busca.toLowerCase();
    return data.filter(row =>
      columns.some(c => String(row[c.key] ?? "").toLowerCase().includes(q))
    );
  }, [data, busca, columns]);

  const actionCol = columns.length > 0 ? 1 : 0;
  const canManage = !!formFields && formFields.length > 0;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {title && <h3 className="text-sm font-semibold text-neutral-200">{title}</h3>}
          {!loading && !error && (
            <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-[10px] font-medium text-neutral-400">
              {filtered.length}{busca ? ` de ${data.length}` : ""}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
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
                {columns.map(c => <th key={c.key} className="whitespace-nowrap px-4 py-2.5 font-medium">{c.label}</th>)}
                {(canManage || rowActions) && <th className="px-4 py-2.5 font-medium text-right">Ações</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/70">
              {filtered.map((row, i) => (
                <tr key={String(row.id)} className={`text-neutral-300 transition-colors hover:bg-neutral-800/50 ${i % 2 === 1 ? "bg-neutral-900/30" : ""}`}>
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
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={columns.length + actionCol} className="px-4 py-10">
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

      {modal.open && formFields && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setModal({ open: false, mode: "create" })}>
          <div className="w-full max-w-[440px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Novo registro" : "Editar registro"}</h3>
              <button onClick={() => setModal({ open: false, mode: "create" })} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
                <Icon name="close" size={15} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 px-5 py-4">
              {formFields.filter(f => f.key !== "id").map(f => (
                <div key={f.key} className={f.type === "select" || f.key === "endereco" ? "col-span-2" : "col-span-2 sm:col-span-1"}>
                  <label className="mb-1 block text-[11px] font-medium text-neutral-400">{f.label}</label>
                  {f.type === "select" && f.options ? (
                    <select value={formData[f.key] ?? ""} onChange={e => setFormData(prev => ({ ...prev, [f.key]: e.target.value }))}
                      className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                      <option value="">Selecione...</option>
                      {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  ) : (
                    <input type={f.type === "number" ? "number" : f.type === "date" ? "date" : f.type === "datetime" ? "datetime-local" : "text"}
                      step={f.type === "number" ? (f.step ?? "any") : undefined} min={f.min} max={f.max}
                      value={formData[f.key] ?? ""} onChange={e => setFormData(prev => ({ ...prev, [f.key]: e.target.value }))}
                      className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
                  )}
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={() => setModal({ open: false, mode: "create" })} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={handleSave} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Salvar</button>
            </div>
          </div>
        </div>
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
    </div>
  );
}
