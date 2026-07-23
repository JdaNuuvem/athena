"use client";

import { useState, useEffect } from "react";
import { Operador } from "./types";
import { DevolucaoModal } from "./DevolucaoModal";

export function HistoricoTab({ operador, operadorSenha }: { operador: Operador; operadorSenha: string }) {
  const [vendas, setVendas] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [itens, setItens] = useState<any[]>([]);
  const [devolverItem, setDevolverItem] = useState<{ itemId: number; qtd: number; motivo: string } | null>(null);

  useEffect(() => {
    fetch("/api/pdv/historico?limit=50").then(r => r.json()).then(d => setVendas(d.data || [])).catch(() => {});
  }, []);

  const toggleExpand = async (vendaId: number) => {
    if (expanded === vendaId) { setExpanded(null); setItens([]); return; }
    setExpanded(vendaId);
    try {
      const r = await fetch("/api/pdv/itens?venda_id=" + vendaId);
      const d = await r.json();
      setItens(d.data || []);
    } catch { setItens([]); }
  };

  const handleDevolucaoConcluida = () => {
    setDevolverItem(null);
    if (expanded) toggleExpand(expanded);
  };

  return (
    <div className="overflow-auto">
      <table className="w-full text-xs">
        <thead><tr className="text-neutral-500 border-b border-neutral-800 sticky top-0 bg-neutral-950">
          <th className="text-left p-3 w-12">#</th><th className="text-left p-3">Cliente</th><th className="text-right p-3">Total</th>
          <th className="text-left p-3">Data</th><th className="text-center p-3">Status</th><th className="w-8"></th>
        </tr></thead>
        <tbody>
          {vendas.map((v, i) => (<>
            <tr key={v.id} className={"border-b border-neutral-800/50 " + (i % 2 === 0 ? "bg-neutral-900/30" : "") + (expanded === v.id ? " bg-neutral-800/50" : "")}>
              <td className="p-3 text-indigo-400 font-mono">{v.numero || v.id}</td>
              <td className="p-3 text-neutral-300">{v.cliente || "—"}</td>
              <td className="p-3 text-right text-emerald-400">R$ {(v.total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
              <td className="p-3 text-neutral-500">{String(v.data || "").slice(0, 16)}</td>
              <td className="p-3 text-center"><span className={"px-2 py-0.5 rounded text-[10px] " + (v.status === "cancelada" ? "bg-red-900/30 text-red-400" : "bg-emerald-900/30 text-emerald-400")}>{v.status || "finalizada"}</span></td>
              <td className="p-3">
                {v.status !== "cancelada" && (
                  <button onClick={() => toggleExpand(v.id)} className="text-neutral-500 hover:text-neutral-300 text-lg">
                    {expanded === v.id ? "−" : "+"}
                  </button>
                )}
              </td>
            </tr>
            {expanded === v.id && (
              <tr key={v.id + "-items"}><td colSpan={6} className="p-0">
                <div className="bg-neutral-900/50 px-6 py-3 border-b border-neutral-800">
                  <table className="w-full text-xs">
                    <thead><tr className="text-neutral-600"><th className="text-left py-1">Codigo</th><th className="text-left py-1">Descricao</th><th className="text-right py-1">Qtd</th><th className="text-right py-1">Unit</th><th className="text-right py-1">Subtotal</th><th className="w-16"></th></tr></thead>
                    <tbody>
                      {itens.map((it: any) => (
                        <tr key={it.id} className="border-b border-neutral-800/30">
                          <td className="py-1 text-neutral-400 font-mono">{it.produto_codigo}</td>
                          <td className="py-1 text-neutral-300">{it.descricao}</td>
                          <td className="py-1 text-right text-neutral-300">{Number(it.quantidade)}</td>
                          <td className="py-1 text-right text-neutral-400">R$ {Number(it.valor_unitario || 0).toFixed(2)}</td>
                          <td className="py-1 text-right text-emerald-400">R$ {Number(it.valor_total || 0).toFixed(2)}</td>
                          <td className="py-1 text-right">
                            <button onClick={() => setDevolverItem({ itemId: it.id, qtd: 1, motivo: "" })}
                              className="text-[10px] text-red-400 hover:text-red-300">Devolver</button>
                          </td>
                        </tr>
                      ))}
                      {itens.length === 0 && (
                        <tr><td colSpan={6} className="py-2 text-neutral-600">Carregando itens...</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </td></tr>
            )}
          </>))}
        </tbody>
      </table>

      {devolverItem && (
        <DevolucaoModal
          devolverItem={devolverItem}
          onClose={() => setDevolverItem(null)}
          onDevolver={handleDevolucaoConcluida}
          operador={operador}
          operadorSenha={operadorSenha}
        />
      )}
    </div>
  );
}
