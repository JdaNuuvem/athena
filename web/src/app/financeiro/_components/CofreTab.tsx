"use client";

import { useState, useEffect, useCallback } from "react";
import { useStore } from "@/lib/store-context";
import { api } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";
import Icon from "@/app/_components/Icon";
import { Can } from "@/lib/auth";

const TIPO_LABEL: Record<string, string> = {
  entrada_sangria: "Entrada (sangria)",
  saida_troco: "Saída (troco)",
  saida_despesa: "Saída (despesa)",
  ajuste: "Ajuste",
};
const TIPO_COR: Record<string, string> = {
  entrada_sangria: "text-emerald-400",
  saida_troco: "text-amber-400",
  saida_despesa: "text-red-400",
  ajuste: "text-indigo-400",
};
const CATEGORIA_LABEL: Record<string, string> = {
  mat_limpeza: "Material de Limpeza",
  padaria: "Padaria",
  papelaria: "Papelaria",
  passagem: "Passagem",
  outros: "Outros",
};

// Cofre por loja — Fase 2 da spec de Caixa/Cofre. Sangria de fechamento de
// caixa entra aqui automaticamente (core/entidades.py::ao_fechar_caixa_pdv);
// saidas de despesa/troco e ajustes entram manualmente por esta tela.
export default function CofreTab() {
  const { lojas, lojaId: lojaIdGlobal } = useStore();
  const [lojaId, setLojaId] = useState<number | null>(null);
  const [saldo, setSaldo] = useState(0);
  const [movimentos, setMovimentos] = useState<Awaited<ReturnType<typeof api.cofreExtrato>>["movimentos"]>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<"saida" | "ajuste" | null>(null);
  const [form, setForm] = useState({ tipo: "saida_despesa", valor: "", categoria: "mat_limpeza", descricao: "" });
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  useEffect(() => {
    if (lojaId === null && lojaIdGlobal && lojaIdGlobal !== "todas") setLojaId(Number(lojaIdGlobal));
  }, [lojaIdGlobal, lojaId]);

  const fetchExtrato = useCallback(async () => {
    if (!lojaId) return;
    setLoading(true);
    try {
      const r = await api.cofreExtrato(lojaId, 90);
      setSaldo(r.saldo_atual || 0);
      setMovimentos(r.movimentos || []);
    } catch { setMovimentos([]); }
    finally { setLoading(false); }
  }, [lojaId]);

  useEffect(() => { fetchExtrato(); }, [fetchExtrato]);

  const abrirModal = (tipo: "saida" | "ajuste") => {
    setForm({ tipo: tipo === "ajuste" ? "ajuste" : "saida_despesa", valor: "", categoria: "mat_limpeza", descricao: "" });
    setModal(tipo);
  };

  const handleSalvar = async () => {
    if (!lojaId) return;
    const valor = parseFloat(form.valor || "0");
    if (!valor) { alert("Informe um valor"); return; }
    const r = await api.cofreCriarMovimento({
      loja_id: lojaId, tipo: form.tipo, valor,
      categoria: form.tipo === "saida_despesa" ? form.categoria : undefined,
      descricao: form.descricao || undefined,
    });
    if (r.error) { alert(r.error); return; }
    setModal(null);
    fetchExtrato();
  };

  const handleExcluir = async (id: number) => {
    try { await api.cofreExcluirMovimento(id); setConfirmDelete(null); fetchExtrato(); }
    catch (e) { alert(String(e)); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <label className="text-xs text-neutral-400">Loja</label>
          <select
            value={lojaId ?? ""}
            onChange={e => setLojaId(e.target.value ? Number(e.target.value) : null)}
            className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          >
            <option value="">Selecione...</option>
            {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
          </select>
        </div>
        {lojaId && (
          <div className="flex items-center gap-2">
            <Can permission="financeiro.criar">
              <button onClick={() => abrirModal("saida")} className="rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700">
                Nova Saída
              </button>
            </Can>
            <Can permission="financeiro.aprovar">
              <button onClick={() => abrirModal("ajuste")} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">
                Ajuste
              </button>
            </Can>
          </div>
        )}
      </div>

      {!lojaId ? (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-xs text-neutral-500">
          Selecione uma loja pra ver o cofre
        </div>
      ) : (
        <>
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
            <p className="text-[10px] text-neutral-500">Saldo Atual</p>
            <p className="mt-0.5 text-2xl font-semibold text-emerald-400">{fmtBRL(saldo)}</p>
          </div>

          {loading ? (
            <p className="text-xs text-neutral-500">Carregando...</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-neutral-800">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-800 bg-neutral-900/60 text-left text-neutral-400">
                    <th className="whitespace-nowrap px-4 py-2.5 font-medium">Data</th>
                    <th className="whitespace-nowrap px-4 py-2.5 font-medium">Tipo</th>
                    <th className="whitespace-nowrap px-4 py-2.5 font-medium">Categoria</th>
                    <th className="px-4 py-2.5 font-medium">Descrição</th>
                    <th className="whitespace-nowrap px-4 py-2.5 font-medium">Valor</th>
                    <th className="px-4 py-2.5 font-medium text-right">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/70">
                  {movimentos.map(m => (
                    <tr key={m.id} className="text-neutral-300">
                      <td className="whitespace-nowrap px-4 py-2.5">{fmtDataBR(m.data)}</td>
                      <td className="whitespace-nowrap px-4 py-2.5"><span className={TIPO_COR[m.tipo]}>{TIPO_LABEL[m.tipo] ?? m.tipo}</span></td>
                      <td className="whitespace-nowrap px-4 py-2.5">{m.categoria ? (CATEGORIA_LABEL[m.categoria] ?? m.categoria) : "—"}</td>
                      <td className="px-4 py-2.5">{m.descricao || "—"}</td>
                      <td className={`whitespace-nowrap px-4 py-2.5 font-medium ${TIPO_COR[m.tipo]}`}>
                        {m.tipo.startsWith("entrada") ? "+" : m.tipo === "ajuste" ? "" : "-"}{fmtBRL(Math.abs(m.valor))}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Can permission="financeiro.excluir">
                          <button onClick={() => setConfirmDelete(m.id)} title="Excluir" className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400">
                            <Icon name="trash" size={13} />
                          </button>
                        </Can>
                      </td>
                    </tr>
                  ))}
                  {movimentos.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-10 text-center text-neutral-500">Nenhum movimento nos últimos 90 dias</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setModal(null)}>
          <div className="w-full max-w-[380px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="mb-3 text-sm font-semibold text-neutral-100">{modal === "ajuste" ? "Ajuste de Cofre" : "Nova Saída"}</h3>
            {modal === "ajuste" && (
              <p className="mb-3 text-[11px] text-amber-400">Ajuste exige aprovação e fica registrado no extrato — use só pra corrigir divergências reais.</p>
            )}
            <div className="space-y-2.5">
              {modal === "saida" && (
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-neutral-400">Tipo</label>
                  <select value={form.tipo} onChange={e => setForm({ ...form, tipo: e.target.value })}
                    className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                    <option value="saida_despesa">Despesa</option>
                    <option value="saida_troco">Troco</option>
                  </select>
                </div>
              )}
              {form.tipo === "saida_despesa" && (
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-neutral-400">Categoria</label>
                  <select value={form.categoria} onChange={e => setForm({ ...form, categoria: e.target.value })}
                    className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                    {Object.entries(CATEGORIA_LABEL).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Valor{modal === "ajuste" ? " (negativo pra reduzir)" : ""}</label>
                <input type="number" step="0.01" value={form.valor} onChange={e => setForm({ ...form, valor: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Descrição</label>
                <input value={form.descricao} onChange={e => setForm({ ...form, descricao: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setModal(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={handleSalvar} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Salvar</button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setConfirmDelete(null)}>
          <div className="w-full max-w-[320px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-red-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Confirmar exclusão</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">Excluir este movimento? O saldo do cofre será ajustado de volta.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={() => handleExcluir(confirmDelete)} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500">Excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
