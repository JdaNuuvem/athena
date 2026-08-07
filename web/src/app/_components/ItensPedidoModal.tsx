"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import Icon from "./Icon";

interface Item {
  id: number;
  produto_codigo?: string;
  descricao?: string;
  quantidade?: number;
  unidade?: string;
  valor_unitario?: number;
  valor_total?: number;
}

interface ItensPedidoModalProps {
  pedidoId: number;
  pedidoNumero?: string;
  onClose: () => void;
}

const UNIDADE_DEFAULT = "UN";

// Antes compras_itens nao aparecia em lugar nenhum da UI — o pedido so
// mostrava valor_total digitado a mao, sem nenhuma composicao visivel.
export default function ItensPedidoModal({ pedidoId, pedidoNumero, onClose }: ItensPedidoModalProps) {
  const [itens, setItens] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState<Record<string, string>>({});
  const [editId, setEditId] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const fetchItens = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.comprasListPaginado("itens", 1, 200, undefined, pedidoId);
      setItens((r.data || []) as Item[]);
    } catch { setItens([]); }
    finally { setLoading(false); }
  }, [pedidoId]);

  useEffect(() => { fetchItens(); }, [fetchItens]);

  const totalItens = itens.reduce((s, i) => s + (Number(i.valor_total) || 0), 0);

  const abrirNovo = () => { setForm({ unidade: UNIDADE_DEFAULT }); setEditId(0); };
  const abrirEdicao = (item: Item) => {
    setForm({
      produto_codigo: item.produto_codigo || "",
      descricao: item.descricao || "",
      quantidade: String(item.quantidade ?? ""),
      unidade: item.unidade || UNIDADE_DEFAULT,
      valor_unitario: String(item.valor_unitario ?? ""),
    });
    setEditId(item.id);
  };

  const handleSalvar = async () => {
    const quantidade = parseFloat(form.quantidade || "0") || 0;
    const valor_unitario = parseFloat(form.valor_unitario || "0") || 0;
    const payload = {
      pedido_id: pedidoId,
      produto_codigo: form.produto_codigo || "",
      descricao: form.descricao || "",
      quantidade,
      unidade: form.unidade || UNIDADE_DEFAULT,
      valor_unitario,
      valor_total: quantidade * valor_unitario,
    };
    try {
      if (editId) await api.comprasUpdate("itens", editId, payload);
      else await api.comprasCreate("itens", payload);
      setEditId(null);
      setForm({});
      fetchItens();
    } catch (e) { alert(String(e)); }
  };

  const handleDelete = async (id: number) => {
    try { await api.comprasDelete("itens", id); setConfirmDelete(null); fetchItens(); }
    catch (e) { alert(String(e)); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="w-full max-w-[640px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
          <h3 className="text-sm font-semibold text-neutral-100">Itens{pedidoNumero ? ` — Pedido ${pedidoNumero}` : ""}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
            <Icon name="close" size={15} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-3">
          {loading ? (
            <p className="text-xs text-neutral-500">Carregando...</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-neutral-700">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-700 bg-neutral-900/60 text-left text-neutral-400">
                    <th className="whitespace-nowrap px-3 py-2 font-medium">Produto</th>
                    <th className="whitespace-nowrap px-3 py-2 font-medium">Qtd</th>
                    <th className="whitespace-nowrap px-3 py-2 font-medium">Unid.</th>
                    <th className="whitespace-nowrap px-3 py-2 font-medium">Vlr. Unit.</th>
                    <th className="whitespace-nowrap px-3 py-2 font-medium">Total</th>
                    <th className="whitespace-nowrap px-3 py-2 font-medium text-right">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/70">
                  {itens.map(item => (
                    <tr key={item.id} className="text-neutral-300">
                      <td className="px-3 py-2">
                        <div>{item.descricao || "—"}</div>
                        {item.produto_codigo && <div className="text-[10px] text-neutral-500">{item.produto_codigo}</div>}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2">{item.quantidade ?? "—"}</td>
                      <td className="whitespace-nowrap px-3 py-2">{item.unidade || "—"}</td>
                      <td className="whitespace-nowrap px-3 py-2">{fmtBRL(Number(item.valor_unitario) || 0)}</td>
                      <td className="whitespace-nowrap px-3 py-2">{fmtBRL(Number(item.valor_total) || 0)}</td>
                      <td className="px-3 py-2">
                        <div className="flex justify-end gap-1">
                          <button onClick={() => abrirEdicao(item)} title="Editar" className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-400">
                            <Icon name="pencil" size={13} />
                          </button>
                          <button onClick={() => setConfirmDelete(item.id)} title="Excluir" className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400">
                            <Icon name="trash" size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {itens.length === 0 && (
                    <tr><td colSpan={6} className="px-3 py-6 text-center text-neutral-500">Nenhum item cadastrado</td></tr>
                  )}
                </tbody>
                {itens.length > 0 && (
                  <tfoot>
                    <tr className="border-t border-neutral-700 text-neutral-300">
                      <td colSpan={4} className="px-3 py-2 text-right font-medium">Total</td>
                      <td className="whitespace-nowrap px-3 py-2 font-semibold text-emerald-400">{fmtBRL(totalItens)}</td>
                      <td />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          )}

          {editId !== null ? (
            <div className="rounded-lg border border-indigo-700/50 bg-neutral-900/40 p-3 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <input placeholder="Código do produto" value={form.produto_codigo || ""} onChange={e => setForm({ ...form, produto_codigo: e.target.value })}
                  className="rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
                <input placeholder="Unidade" value={form.unidade || ""} onChange={e => setForm({ ...form, unidade: e.target.value })}
                  className="rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
                <input placeholder="Descrição" value={form.descricao || ""} onChange={e => setForm({ ...form, descricao: e.target.value })}
                  className="col-span-2 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
                <input type="number" step="any" placeholder="Quantidade" value={form.quantidade || ""} onChange={e => setForm({ ...form, quantidade: e.target.value })}
                  className="rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
                <input type="number" step="any" placeholder="Valor unitário" value={form.valor_unitario || ""} onChange={e => setForm({ ...form, valor_unitario: e.target.value })}
                  className="rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => { setEditId(null); setForm({}); }} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
                <button onClick={handleSalvar} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Salvar</button>
              </div>
            </div>
          ) : (
            <button onClick={abrirNovo} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-neutral-700 px-3 py-2 text-xs text-neutral-500 transition-colors hover:bg-neutral-800 hover:text-neutral-300">
              <span className="text-sm leading-none">+</span> Adicionar item
            </button>
          )}
        </div>
      </div>

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setConfirmDelete(null)}>
          <div className="w-full max-w-[320px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-red-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Confirmar exclusão</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">Excluir este item do pedido?</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={() => handleDelete(confirmDelete)} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500">Excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
