"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

interface Fornecedor { id: number; nome: string; }

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500";

export default function NovoProdutoPage() {
  const router = useRouter();
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.cadList("fornecedores").then(r => setFornecedores((r.data ?? []) as Fornecedor[])).catch(() => {});
  }, []);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro(""); setSaving(true);
    try {
      const payload: Record<string, unknown> = { ...form };
      if (!form.fornecedor_id) delete payload.fornecedor_id;
      const r = await api.criarProduto(payload);
      if (r.error) { setErro(r.error); setSaving(false); return; }
      router.push(`/produtos/${form.sku}`);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao criar produto");
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <div>
        <Link href="/produtos" className="text-xs text-neutral-500 hover:text-neutral-300">&larr; Produtos</Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Novo Produto</h1>
        <p className="text-xs text-neutral-500 mt-0.5">Cadastro local — nao depende de sync com o Bling</p>
      </div>

      {erro && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <fieldset className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4">
          <legend className="text-sm font-medium text-neutral-300 px-1">Identificacao</legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="SKU *">
              <input required value={form.sku || ""} onChange={set("sku")} className={inputCls} placeholder="Ex: PROD-001" />
            </Field>
            <Field label="Descricao *">
              <input required value={form.descricao || ""} onChange={set("descricao")} className={inputCls} placeholder="Nome do produto" />
            </Field>
            <Field label="Categoria">
              <input value={form.categoria || ""} onChange={set("categoria")} className={inputCls} />
            </Field>
            <Field label="Marca">
              <input value={form.marca || ""} onChange={set("marca")} className={inputCls} />
            </Field>
            <Field label="Codigo de Barras">
              <input value={form.codigo_barras || ""} onChange={set("codigo_barras")} className={inputCls} placeholder="EAN/GTIN" />
            </Field>
          </div>
        </fieldset>

        <fieldset className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4">
          <legend className="text-sm font-medium text-neutral-300 px-1">Precos</legend>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Field label="Preco de Custo (R$)">
              <input type="number" step="0.01" min="0" value={form.preco_custo || ""} onChange={set("preco_custo")} className={inputCls} />
            </Field>
            <Field label="Custo de Transporte (R$)">
              <input type="number" step="0.01" min="0" value={form.custo_transporte || ""} onChange={set("custo_transporte")} className={inputCls} />
            </Field>
            <Field label="Preco de Venda (R$)">
              <input type="number" step="0.01" min="0" value={form.preco_venda || ""} onChange={set("preco_venda")} className={inputCls} />
            </Field>
          </div>
        </fieldset>

        <fieldset className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4">
          <legend className="text-sm font-medium text-neutral-300 px-1">Fornecimento</legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Fornecedor">
              <select value={form.fornecedor_id || ""} onChange={set("fornecedor_id")} className={inputCls}>
                <option value="">— Nenhum —</option>
                {fornecedores.map(f => <option key={f.id} value={f.id}>{f.nome}</option>)}
              </select>
            </Field>
            <Field label="Codigo no Fornecedor">
              <input value={form.fornecedor_codigo || ""} onChange={set("fornecedor_codigo")} className={inputCls} />
            </Field>
            <Field label="Estoque Minimo">
              <input type="number" step="1" min="0" value={form.estoque_minimo || ""} onChange={set("estoque_minimo")} className={inputCls} />
            </Field>
            <Field label="Estoque Maximo">
              <input type="number" step="1" min="0" value={form.estoque_maximo || ""} onChange={set("estoque_maximo")} className={inputCls} />
            </Field>
          </div>
        </fieldset>

        <div className="flex gap-2">
          <button type="submit" disabled={saving} className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors">
            {saving ? "Salvando..." : "Criar Produto"}
          </button>
          <Link href="/produtos" className="text-sm text-neutral-400 hover:text-neutral-200 px-4 py-2">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}
