"use client";

import { useState } from "react";
import Alert from "./shared/Alert";
import { criarBlingProduto, atualizarBlingProduto, BlingProduto } from "@/lib/api";

interface ProductFormModalProps {
  produto?: BlingProduto | null;
  onClose: () => void;
  onSaved: () => void;
}

export default function ProductFormModal({ produto, onClose, onSaved }: ProductFormModalProps) {
  const isEdit = !!produto;
  const [form, setForm] = useState({
    codigo: produto?.codigo || "",
    descricao: produto?.descricao || "",
    preco: produto?.preco || 0,
    situacao: produto?.situacao || "A",
  });
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.codigo.trim() || !form.descricao.trim()) {
      setErro("SKU e Nome são obrigatórios");
      return;
    }
    try {
      setLoading(true);
      setErro(null);
      if (isEdit && produto) {
        await atualizarBlingProduto(produto.id, form);
      } else {
        await criarBlingProduto(form);
      }
      onSaved();
      onClose();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao salvar produto");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-neutral-850 border border-neutral-700 rounded-xl w-full max-w-md mx-4 shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-neutral-700">
          <h3 className="text-sm font-semibold text-neutral-100">{isEdit ? "Editar Produto" : "Novo Produto"}</h3>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 text-lg leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <Alert message={erro} type="error" />

          <div>
            <label className="block text-xs text-neutral-400 mb-1">SKU *</label>
            <input type="text" value={form.codigo} onChange={(e) => setForm({ ...form, codigo: e.target.value })}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500"
              placeholder="MEU-SKU-001" disabled={isEdit} />
          </div>

          <div>
            <label className="block text-xs text-neutral-400 mb-1">Nome *</label>
            <input type="text" value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500"
              placeholder="Nome do produto" />
          </div>

          <div>
            <label className="block text-xs text-neutral-400 mb-1">Preço (R$)</label>
            <input type="number" step="0.01" min="0" value={form.preco}
              onChange={(e) => setForm({ ...form, preco: parseFloat(e.target.value) || 0 })}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
          </div>

          <div>
            <label className="block text-xs text-neutral-400 mb-1">Situação</label>
            <select value={form.situacao} onChange={(e) => setForm({ ...form, situacao: e.target.value })}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500">
              <option value="A">Ativo</option>
              <option value="I">Inativo</option>
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-xs text-neutral-400 hover:text-neutral-200">Cancelar</button>
            <button type="submit" disabled={loading}
              className="px-4 py-2 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 disabled:opacity-50 transition-colors">
              {loading ? "Salvando..." : isEdit ? "Atualizar" : "Criar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
