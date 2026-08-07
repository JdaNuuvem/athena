"use client";

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

interface CrudFormModalProps {
  mode: "create" | "edit";
  fields: FieldDef[];
  formData: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onSave: () => void;
  onClose: () => void;
}

export default function CrudFormModal({ mode, fields, formData, onChange, onSave, onClose }: CrudFormModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="w-full max-w-[440px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
          <h3 className="text-sm font-semibold text-neutral-100">{mode === "create" ? "Novo registro" : "Editar registro"}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
            <Icon name="close" size={15} />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3 px-5 py-4">
          {fields.filter(f => f.key !== "id").map(f => (
            <div key={f.key} className={f.type === "select" || f.key === "endereco" ? "col-span-2" : "col-span-2 sm:col-span-1"}>
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">{f.label}</label>
              {f.type === "select" && f.options ? (
                <select value={formData[f.key] ?? ""} onChange={e => onChange(f.key, e.target.value)}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  <option value="">Selecione...</option>
                  {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : (
                <input type={f.type === "number" ? "number" : f.type === "date" ? "date" : f.type === "datetime" ? "datetime-local" : "text"}
                  step={f.type === "number" ? (f.step ?? "any") : undefined} min={f.min} max={f.max}
                  value={formData[f.key] ?? ""} onChange={e => onChange(f.key, e.target.value)}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
          <button onClick={onClose} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
          <button onClick={onSave} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Salvar</button>
        </div>
      </div>
    </div>
  );
}
