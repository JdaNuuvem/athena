"use client";

import { useState } from "react";
import type { BlingSituacao } from "@/lib/api";

interface SituacaoFormModalProps {
  situacao?: BlingSituacao | null;
  onClose: () => void;
  onSalvar: (dados: Partial<BlingSituacao>) => Promise<void>;
}

export default function SituacaoFormModal({ situacao, onClose, onSalvar }: SituacaoFormModalProps) {
  const [nome, setNome] = useState(situacao?.nome || "");
  const [cor, setCor] = useState(situacao?.cor || "");
  const [modulo, setModulo] = useState(situacao?.modulo || "");
  const [salvando, setSalvando] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nome.trim()) return;
    setSalvando(true);
    await onSalvar({ nome: nome.trim(), cor: cor.trim(), modulo: modulo.trim() });
    setSalvando(false);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="bg-neutral-900 border border-neutral-700 rounded-lg p-5 w-full max-w-sm space-y-3"
      >
        <h2 className="text-sm font-semibold text-neutral-100">
          {situacao ? "Editar situação" : "Nova situação"}
        </h2>

        <label className="block">
          <span className="text-xs text-neutral-400">Nome</span>
          <input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            autoFocus
            className="mt-1 w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500"
          />
        </label>

        <label className="block">
          <span className="text-xs text-neutral-400">Cor (hex, sem #)</span>
          <input
            value={cor}
            onChange={(e) => setCor(e.target.value)}
            placeholder="FFA500"
            className="mt-1 w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-indigo-500"
          />
        </label>

        <label className="block">
          <span className="text-xs text-neutral-400">Módulo</span>
          <input
            value={modulo}
            onChange={(e) => setModulo(e.target.value)}
            placeholder="pedidos"
            className="mt-1 w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-indigo-500"
          />
        </label>

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 bg-neutral-700 text-neutral-200 text-xs rounded-lg hover:bg-neutral-600"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={salvando || !nome.trim()}
            className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 disabled:opacity-50"
          >
            {salvando ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </form>
    </div>
  );
}
