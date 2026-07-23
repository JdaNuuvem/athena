"use client";

import { useState } from "react";
import { Operador } from "./types";

export function DevolucaoModal({ devolverItem, onClose, onDevolver, operador, operadorSenha }: {
  devolverItem: { itemId: number; qtd: number; motivo: string };
  onClose: () => void;
  onDevolver: () => void;
  operador: Operador;
  operadorSenha: string;
}) {
  const [item, setItem] = useState(devolverItem);
  const [devolverSenha, setDevolverSenha] = useState("");

  const handleDevolver = async () => {
    if (!item || !item.qtd) return;
    try {
      const r = await fetch("/api/pdv/venda/" + item.itemId + "/devolver-item", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantidade: item.qtd, motivo: item.motivo,
          operador: operador.nome, operador_id: operador.id, senha: devolverSenha || operadorSenha }),
      });
      const d = await r.json();
      if (d.error) { alert(d.error); return; }
      alert(`Devolvido: ${item.qtd} un — R$ ${d.valor_devolvido?.toFixed(2)}`);
      onDevolver();
    } catch { alert("Erro ao devolver"); }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-80" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Devolver Item</h3>
        <div className="space-y-2">
          <input type="number" min={0.001} step="0.001" value={item.qtd}
            onChange={e => setItem({ ...item, qtd: Number(e.target.value) })}
            placeholder="Quantidade" autoFocus
            className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
          <input type="text" value={item.motivo}
            onChange={e => setItem({ ...item, motivo: e.target.value })}
            placeholder="Motivo (opcional)"
            className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
          <input type="password" value={devolverSenha}
            onChange={e => setDevolverSenha(e.target.value)}
            placeholder="Senha"
            className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
          <div className="flex gap-2 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
            <button onClick={handleDevolver} className="flex-1 py-2 bg-red-600 text-white text-sm rounded-lg">Devolver</button>
          </div>
        </div>
      </div>
    </div>
  );
}
