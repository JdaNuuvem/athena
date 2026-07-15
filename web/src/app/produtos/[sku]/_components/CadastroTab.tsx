"use client";

import { useState } from "react";

function InputGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-1"><label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>{children}</div>;
}
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <fieldset className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4"><legend className="text-sm font-medium text-neutral-300 px-1">{title}</legend>{children}</fieldset>;
}

export default function CadastroTab({ produto, sku, onUpdate }: { produto: Record<string, unknown> | null; sku: string; onUpdate?: () => void }) {
  const [editando, setEditando] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const startEdit = () => { setForm({ descricao: String(produto?.descricao || produto?.nome || ""), categoria: String(produto?.categoria || ""), marca: String(produto?.marca || ""), ncm: String(produto?.ncm || ""), tipo: String(produto?.tipo || "") }); setEditando(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/produtos/" + sku, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      const d = await r.json();
      if (d.error) { setMsg(d.error); return; }
      setMsg("Salvo!");
      setEditando(false);
      onUpdate?.();
      setTimeout(() => setMsg(""), 2000);
    } catch (e) { setMsg("Erro ao salvar"); }
    finally { setSaving(false); }
  };

  const field = (k: string, label: string) => {
    const val = editando ? form[k] || "" : String((produto as any)?.[k] || "");
    if (editando) return <input type="text" value={val || ""} onChange={e => setForm({...form, [k]: e.target.value})} className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500" />;
    return <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">{val || "—"}</div>;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-neutral-400">Dados do Produto</h2>
        <div className="flex gap-2 items-center">
          {msg && <span className="text-xs text-emerald-400">{msg}</span>}
          {editando ? (
            <>
              <button onClick={handleSave} disabled={saving} className="px-3 py-1 bg-emerald-600 text-white text-xs rounded-lg">{saving ? "Salvando..." : "Salvar"}</button>
              <button onClick={() => setEditando(false)} className="px-3 py-1 text-xs text-neutral-400">Cancelar</button>
            </>
          ) : (
            <button onClick={startEdit} className="px-3 py-1 bg-indigo-600 text-white text-xs rounded-lg">Editar</button>
          )}
        </div>
      </div>

      <Section title="Identificacao">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <InputGroup label="SKU"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-indigo-400 font-mono">{sku}</div></InputGroup>
          <InputGroup label="Nome"><InputGroup label="">{field("descricao", "Nome")}</InputGroup></InputGroup>
          <InputGroup label="Categoria">{field("categoria", "Categoria")}</InputGroup>
          <InputGroup label="Marca">{field("marca", "Marca")}</InputGroup>
        </div>
      </Section>

      <Section title="Fiscal">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <InputGroup label="NCM">{field("ncm", "NCM")}</InputGroup>
          <InputGroup label="Tipo">{field("tipo", "Tipo")}</InputGroup>
        </div>
      </Section>

      <div className="text-xs text-neutral-600">
        ID: {String(produto?.id || "—")} | Variacoes: {(produto?.variacoes as any[])?.length || 0}
      </div>
    </div>
  );
}
