"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import { Can } from "@/lib/auth";

export interface FieldDef {
  key: string;
  label: string;
  type?: "text" | "number" | "select";
  options?: { label: string; value: string }[];
  step?: string;
}

export interface Column {
  key: string;
  label: string;
  render?: (val: unknown, row: Record<string, unknown>) => React.ReactNode;
}

interface CrudPanelProps {
  tabela: string;
  columns: Column[];
  formFields?: FieldDef[];
  title?: string;
  permissionPrefix?: string;
}

export default function CrudPanel({ tabela, columns, formFields, title, permissionPrefix = "registrations" }: CrudPanelProps) {
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
      const res = await api.cadList(tabela);
      setData((res.data || []) as Record<string, unknown>[]);
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [tabela]);

  useEffect(() => { fetchData(); }, [fetchData]);

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
      payload[f.key] = f.type === "number" ? parseFloat(val) || 0 : val;
    }
    try {
      if (modal.mode === "create") await api.cadCreate(tabela, payload);
      else await api.cadUpdate(tabela, Number(modal.row?.id), payload);
      setModal({ open: false, mode: "create" });
      fetchData();
    } catch (e) { alert(String(e)); }
  };

  const handleDelete = async (id: number) => {
    try { await api.cadDelete(tabela, id); setConfirmDelete(null); fetchData(); }
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

  return (
    <div className="space-y-3">
      {title && <h3 className="text-sm font-semibold text-neutral-200">{title}</h3>}
      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="Buscar..."
          value={busca}
          onChange={e => setBusca(e.target.value)}
          className="w-48 bg-neutral-800 border border-neutral-700 rounded px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
        />
        {formFields && formFields.length > 0 && (
          <Can permission={`${permissionPrefix}:create`}>
            <button onClick={openCreate}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo</button>
          </Can>
        )}
      </div>

      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> :
       error ? <p className="text-xs text-red-400">{error}</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 text-left">
                {columns.map(c => <th key={c.key} className="px-4 py-2 font-medium">{c.label}</th>)}
                {formFields && formFields.length > 0 && <th className="px-4 py-2 font-medium w-24">Ações</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map(row => (
                <tr key={String(row.id)} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">
                  {columns.map(c => (
                    <td key={c.key} className="px-4 py-2.5">
                      {c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}
                    </td>
                  ))}
                  {formFields && formFields.length > 0 && (
                    <td className="px-4 py-2.5">
                      <Can permission={`${permissionPrefix}:edit`}>
                        <button onClick={() => openEdit(row)} className="text-indigo-400 hover:text-indigo-300 mr-2 text-[11px]">Editar</button>
                      </Can>
                      <Can permission={`${permissionPrefix}:delete`}>
                        <button onClick={() => setConfirmDelete(Number(row.id))} className="text-red-400 hover:text-red-300 text-[11px]">Excluir</button>
                      </Can>
                    </td>
                  )}
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={columns.length + actionCol} className="px-4 py-6 text-center text-neutral-500">Nenhum registro encontrado</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {modal.open && formFields && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setModal({ open: false, mode: "create" })}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-6 w-[400px] max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-4">{modal.mode === "create" ? "Novo Registro" : "Editar Registro"}</h3>
            <div className="space-y-3">
              {formFields.filter(f => f.key !== "id").map(f => (
                <div key={f.key}>
                  <label className="block text-[11px] text-neutral-400 mb-1">{f.label}</label>
                  {f.type === "select" && f.options ? (
                    <select value={formData[f.key] ?? ""} onChange={e => setFormData(prev => ({ ...prev, [f.key]: e.target.value }))}
                      className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500">
                      <option value="">Selecione...</option>
                      {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  ) : (
                    <input type={f.type === "number" ? "number" : "text"} step={f.step ?? "any"}
                      value={formData[f.key] ?? ""} onChange={e => setFormData(prev => ({ ...prev, [f.key]: e.target.value }))}
                      className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
                  )}
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setModal({ open: false, mode: "create" })} className="text-xs px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200 transition-colors">Cancelar</button>
              <button onClick={handleSave} className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors">Salvar</button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setConfirmDelete(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-6 w-[320px]" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-2">Confirmar exclusão</h3>
            <p className="text-xs text-neutral-400 mb-4">Tem certeza que deseja excluir este registro?</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="text-xs px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200 transition-colors">Cancelar</button>
              <button onClick={() => handleDelete(confirmDelete)} className="text-xs px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white transition-colors">Excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
