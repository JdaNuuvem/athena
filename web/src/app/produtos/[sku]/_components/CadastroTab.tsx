"use client";

import { useState, useRef } from "react";
import Link from "next/link";

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
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const p = produto as any;
  const idBling = p?.id_bling;
  const imagemURL = p?.imagemURL || p?.imagem_url;

  const CAMPOS_EDITAVEIS = [
    "descricao", "categoria", "marca", "ncm", "tipo",
    "codigo_barras", "gtin_embalagem", "descricao_curta", "descricao_complementar",
    "peso_bruto", "peso_liquido", "largura", "altura", "profundidade", "unidade_medida_dimensao",
    "volumes", "itens_por_caixa", "cfop_padrao", "observacoes", "link_externo",
    "fornecedor_nome", "fornecedor_codigo", "preco_custo",
    "estoque_minimo", "estoque_maximo", "estoque_localizacao",
  ];

  const startEdit = () => {
    const f: Record<string, string> = {};
    for (const campo of CAMPOS_EDITAVEIS) f[campo] = String(p?.[campo] ?? "");
    setForm(f);
    setEditando(true);
  };

  const handleSave = async () => {
    setSaving(true); setMsg("");
    try {
      // 1. Save locally
      const r = await fetch("/api/produtos/" + sku, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      const d = await r.json();
      if (d.error) { setMsg(d.error); setSaving(false); return; }

      // 2. Push to Bling (two-way sync)
      if (idBling) {
        try {
          await fetch("/api/bling/produtos/" + idBling, {
            method: "PUT", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ descricao: form.descricao, preco: form.preco }),
          });
        } catch (e) { setMsg("Salvo localmente. Erro ao sincronizar com Bling."); setSaving(false); return; }
      }

      setMsg(idBling ? "Salvo e sincronizado com Bling!" : "Salvo localmente.");
      setEditando(false);
      onUpdate?.();
      setTimeout(() => setMsg(""), 3000);
    } catch (e) { setMsg("Erro ao salvar"); }
    finally { setSaving(false); }
  };

  const handleImageUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true); setUploadMsg("");
    for (const file of Array.from(files)) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("entidade_tipo", "produto");
      formData.append("entidade_id", String(p?.id || ""));
      formData.append("criado_por", "Admin");
      const r = await fetch("/api/documentos", { method: "POST", body: formData });
      const d = await r.json();
      if (d.error) { setUploadMsg(d.error); break; }
    }
    setUploading(false);
    setUploadMsg("Imagem enviada!");
    onUpdate?.();
    setTimeout(() => setUploadMsg(""), 2000);
  };

  const field = (k: string) => {
    const val = editando ? form[k] || "" : String(p?.[k] || "");
    if (editando) return <input type="text" value={val || ""} onChange={e => setForm({...form, [k]: e.target.value})} className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500" />;
    return <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">{val || "—"}</div>;
  };

  const textareaField = (k: string, rows = 3) => {
    const val = editando ? form[k] || "" : String(p?.[k] || "");
    if (editando) return <textarea rows={rows} value={val || ""} onChange={e => setForm({...form, [k]: e.target.value})} className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500" />;
    return <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 whitespace-pre-wrap min-h-[2.5rem]">{val || "—"}</div>;
  };

  const dimensoes = () => {
    if (editando) return null;
    const l = p?.largura, a = p?.altura, prof = p?.profundidade, un = p?.unidade_medida_dimensao || "cm";
    if (!l && !a && !prof) return "—";
    return `${l || 0} x ${a || 0} x ${prof || 0} ${un}`;
  };

  const margemReal = () => {
    const custo = Number(p?.preco_custo || 0);
    const valor = Number(p?.valor || 0);
    if (!custo || !valor) return null;
    return (((valor - custo) / valor) * 100).toFixed(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-neutral-400">Dados do Produto</h2>
        <div className="flex gap-2 items-center">
          {msg && <span className="text-xs text-emerald-400">{msg}</span>}
          {uploadMsg && <span className="text-xs text-blue-400">{uploadMsg}</span>}
          {editando ? (
            <>
              <button onClick={handleSave} disabled={saving} className="px-3 py-1 bg-emerald-600 text-white text-xs rounded-lg">{saving ? "Salvando..." : "Salvar"}</button>
              <button onClick={() => setEditando(false)} className="px-3 py-1 text-xs text-neutral-400">Cancelar</button>
            </>
          ) : (
            <>
              <button onClick={startEdit} className="px-3 py-1 bg-indigo-600 text-white text-xs rounded-lg">Editar</button>
              <Link href={"/pdv?sku=" + sku} className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white text-xs rounded-lg">🛒 Vender</Link>
            </>
          )}
        </div>
      </div>

      {/* Image section */}
      <Section title="Imagem">
        <div className="flex items-start gap-4">
          {imagemURL ? (
            <img src={imagemURL} alt={String(p?.nome || sku)} className="w-24 h-24 object-cover rounded-lg border border-neutral-700" />
          ) : (
            <div className="w-24 h-24 rounded-lg border border-neutral-700 bg-neutral-800 flex items-center justify-center text-neutral-500 text-xs">Sem foto</div>
          )}
          <div>
            <button onClick={() => fileRef.current?.click()} disabled={uploading} className="px-3 py-1.5 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded-lg">
              {uploading ? "Enviando..." : "📤 Upload Imagem"}
            </button>
            <input ref={fileRef} type="file" accept="image/*" onChange={e => handleImageUpload(e.target.files)} className="hidden" />
            <p className="text-[10px] text-neutral-600 mt-1">JPG, PNG, WebP</p>
          </div>
        </div>
      </Section>

      <Section title="Identificacao">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <InputGroup label="SKU"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-indigo-400 font-mono">{sku}</div></InputGroup>
          <InputGroup label="Nome"><div>{field("descricao")}</div></InputGroup>
          <InputGroup label="Categoria">{field("categoria")}</InputGroup>
          <InputGroup label="Marca">{field("marca")}</InputGroup>
          <InputGroup label="Código de Barras (GTIN)">{field("codigo_barras")}</InputGroup>
          <InputGroup label="GTIN Embalagem">{field("gtin_embalagem")}</InputGroup>
          <InputGroup label="Tipo Bling"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-500">{String(p?.bling_tipo || "—")} / {String(p?.formato || "—")}</div></InputGroup>
          <InputGroup label="Situação"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-500">{p?.situacao === "A" ? "Ativo" : p?.situacao === "I" ? "Inativo" : String(p?.situacao || "—")}</div></InputGroup>
        </div>
      </Section>

      <Section title="Fiscal">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <InputGroup label="NCM">{field("ncm")}</InputGroup>
          <InputGroup label="CFOP Padrão">{field("cfop_padrao")}</InputGroup>
          <InputGroup label="Tipo">{field("tipo")}</InputGroup>
          <InputGroup label="Origem"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-500">{String(p?.origem_fiscal || "—")}</div></InputGroup>
        </div>
      </Section>

      <Section title="Logística">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <InputGroup label="Peso Bruto (kg)">{field("peso_bruto")}</InputGroup>
          <InputGroup label="Peso Líquido (kg)">{field("peso_liquido")}</InputGroup>
          <InputGroup label="Largura">{field("largura")}</InputGroup>
          <InputGroup label="Altura">{field("altura")}</InputGroup>
          <InputGroup label="Profundidade">{field("profundidade")}</InputGroup>
          <InputGroup label="Unidade Dimensão">{field("unidade_medida_dimensao")}</InputGroup>
          <InputGroup label="Volumes">{field("volumes")}</InputGroup>
          <InputGroup label="Itens por Caixa">{field("itens_por_caixa")}</InputGroup>
          {!editando && <InputGroup label="Dimensões (L x A x P)"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">{dimensoes()}</div></InputGroup>}
        </div>
      </Section>

      <Section title="Fornecimento">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <InputGroup label="Fornecedor">{field("fornecedor_nome")}</InputGroup>
          <InputGroup label="Código no Fornecedor">{field("fornecedor_codigo")}</InputGroup>
          <InputGroup label="Preço de Custo">{field("preco_custo")}</InputGroup>
          {!editando && (
            <InputGroup label="Margem Real">
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-emerald-400">
                {margemReal() !== null ? `${margemReal()}%` : "—"}
              </div>
            </InputGroup>
          )}
          <InputGroup label="Estoque Mínimo">{field("estoque_minimo")}</InputGroup>
          <InputGroup label="Estoque Máximo">{field("estoque_maximo")}</InputGroup>
          <InputGroup label="Localização">{field("estoque_localizacao")}</InputGroup>
        </div>
      </Section>

      <Section title="Descrição">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <InputGroup label="Descrição Curta">{textareaField("descricao_curta", 2)}</InputGroup>
          <InputGroup label="Link Externo">{field("link_externo")}</InputGroup>
        </div>
        <InputGroup label="Descrição Complementar">{textareaField("descricao_complementar", 4)}</InputGroup>
        <InputGroup label="Observações">{textareaField("observacoes", 2)}</InputGroup>
      </Section>

      <div className="text-xs text-neutral-600 space-y-1">
        <div>ID: {String(p?.id || "—")} | Bling ID: {idBling || "—"} | Variacoes: {(p?.variacoes as any[])?.length || 0}</div>
        {idBling && <div className="text-emerald-600">✓ Sincronizado com Bling (two-way)</div>}
      </div>
    </div>
  );
}
