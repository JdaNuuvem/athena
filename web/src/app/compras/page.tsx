"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

interface Card {
  id: number; titulo: string; subtitulo: string; extras?: string;
  status?: string; valor?: number; coluna: string;
}

const COLUNAS = [
  { id: "solicitacoes", titulo: "Solicitacoes", cor: "border-t-amber-500", bg: "bg-amber-500" },
  { id: "cotacoes", titulo: "Cotacoes", cor: "border-t-purple-500", bg: "bg-purple-500" },
  { id: "pedidos", titulo: "Pedidos", cor: "border-t-emerald-500", bg: "bg-emerald-500" },
  { id: "recebimentos", titulo: "Recebimento", cor: "border-t-teal-500", bg: "bg-teal-500" },
  { id: "notas", titulo: "Notas Entrada", cor: "border-t-pink-500", bg: "bg-pink-500" },
] as const;

const API_MAP: Record<string, { list: string; create: string }> = {
  solicitacoes: { list: "/api/compras/solicitacoes", create: "/api/compras/solicitacoes" },
  cotacoes: { list: "/api/compras/cotacoes", create: "/api/compras/cotacoes" },
  pedidos: { list: "/api/compras/pedidos", create: "/api/compras/pedidos" },
  recebimentos: { list: "/api/compras/recebimentos", create: "/api/compras/recebimentos" },
  notas: { list: "/api/compras/notas", create: "/api/compras/notas" },
};

function formatCard(coluna: string, item: any): Card {
  const base: Card = { id: item.id, titulo: "", subtitulo: "", coluna };
  if (coluna === "solicitacoes") { base.titulo = item.descricao || ""; base.subtitulo = item.solicitante || ""; base.status = item.status; }
  else if (coluna === "cotacoes") { base.titulo = "Cotacao #" + item.id; base.subtitulo = "Fornecedor #" + (item.fornecedor_id || ""); base.valor = item.valor_unitario; }
  else if (coluna === "pedidos") { base.titulo = item.numero || ("Pedido #" + item.id); base.subtitulo = "R$ " + ((item.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })); base.status = item.status; }
  else if (coluna === "recebimentos") { base.titulo = "Recebimento #" + item.id; base.subtitulo = item.conferido_por || ""; base.status = item.status; }
  else if (coluna === "notas") { base.titulo = item.numero_nf || ("NF #" + item.id); base.subtitulo = "R$ " + ((item.valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })); base.status = item.status; }
  return base;
}

export default function ComprasKanban() {
  const [board, setBoard] = useState<Record<string, Card[]>>({});
  const [loading, setLoading] = useState(true);
  const [newCardCol, setNewCardCol] = useState<string | null>(null);
  const [newForm, setNewForm] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    const cols: Record<string, Card[]> = {};
    for (const col of COLUNAS) {
      try {
        const r = await fetch(API_MAP[col.id].list);
        const d = await r.json();
        cols[col.id] = (d.data || []).slice(0, 20).map((item: any) => formatCard(col.id, item));
      } catch { cols[col.id] = []; }
    }
    setBoard(cols);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (coluna: string) => {
    const data: Record<string, any> = { ...newForm };
    if (coluna === "solicitacoes") { data.solicitante = data.solicitante || "Admin"; data.status = data.status || "pendente"; }
    if (coluna === "cotacoes") { data.valor_unitario = parseFloat(data.valor_unitario || "0"); }
    if (coluna === "pedidos") { data.valor_total = parseFloat(data.valor_total || "0"); }
    if (coluna === "notas") { data.valor = parseFloat(data.valor || "0"); }
    const r = await fetch(API_MAP[coluna].create, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    const d = await r.json();
    if (!d.error) { setNewCardCol(null); setNewForm({}); load(); }
  };

  const handleDelete = async (coluna: string, id: number) => {
    if (!confirm("Remover?")) return;
    await fetch(API_MAP[coluna].list + "/" + id, { method: "DELETE" });
    load();
  };

  const quickFields = (coluna: string) => {
    if (coluna === "solicitacoes") return [["descricao", "Descricao"], ["solicitante", "Solicitante"]];
    if (coluna === "cotacoes") return [["fornecedor_id", "Fornecedor ID"], ["valor_unitario", "Valor Unit."]];
    if (coluna === "pedidos") return [["numero", "Numero"], ["fornecedor_id", "Fornecedor ID"], ["valor_total", "Valor Total"]];
    if (coluna === "recebimentos") return [["pedido_id", "Pedido ID"], ["conferido_por", "Conferido por"]];
    if (coluna === "notas") return [["pedido_id", "Pedido ID"], ["numero_nf", "Numero NF"], ["valor", "Valor"]];
    return [];
  };

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  return (
    <div className="p-4 h-[calc(100vh-60px)] flex flex-col">
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Compras</h1>
          <p className="text-xs text-neutral-500 mt-1">Pipeline: Solicitacao → Cotacao → Pedido → Recebimento → Nota</p>
        </div>
        <Link href="/compras/fornecedores" className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-500">Fornecedores</Link>
      </div>

      <div className="flex-1 flex gap-3 overflow-x-auto pb-2">
        {COLUNAS.map(col => (
          <div key={col.id} className={"flex-1 min-w-[220px] bg-neutral-900 border border-neutral-800 rounded-lg flex flex-col " + col.cor + " border-t-2"}>
            <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-800">
              <span className="text-xs font-semibold text-neutral-300">{col.titulo}</span>
              <span className={"text-[10px] text-white px-1.5 py-0.5 rounded-full " + col.bg}>{(board[col.id] || []).length}</span>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {(board[col.id] || []).map(card => (
                <div key={card.id} className="bg-neutral-800 border border-neutral-700/50 rounded-lg p-2.5 group hover:border-neutral-600 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-neutral-200 font-medium truncate">{card.titulo}</p>
                      <p className="text-[10px] text-neutral-500 mt-0.5">{card.subtitulo}</p>
                      {card.valor && <p className="text-[10px] text-emerald-400 mt-0.5">R$ {card.valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>}
                    </div>
                    <button onClick={() => handleDelete(col.id, card.id)} className="text-neutral-600 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity ml-1">x</button>
                  </div>
                </div>
              ))}

              {newCardCol === col.id ? (
                <div className="bg-neutral-800 border border-indigo-700/50 rounded-lg p-2.5 space-y-1.5">
                  {quickFields(col.id).map(([k, label]) => (
                    <input key={k} type="text" value={newForm[k] || ""} onChange={e => setNewForm({ ...newForm, [k]: e.target.value })}
                      placeholder={label} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-[10px] text-neutral-200 placeholder-neutral-600" />
                  ))}
                  <div className="flex gap-1">
                    <button onClick={() => handleCreate(col.id)} className="flex-1 px-2 py-1 bg-emerald-600 text-white text-[10px] rounded">Salvar</button>
                    <button onClick={() => { setNewCardCol(null); setNewForm({}); }} className="px-2 py-1 text-[10px] text-neutral-500">Cancelar</button>
                  </div>
                </div>
              ) : (
                <button onClick={() => { setNewCardCol(col.id); setNewForm({}); }}
                  className="w-full py-2 text-[10px] text-neutral-600 hover:text-neutral-400 hover:bg-neutral-800 rounded-lg border border-dashed border-neutral-700 transition-colors">
                  + Adicionar
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
