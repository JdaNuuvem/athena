"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";
import FkPicker from "@/app/_components/FkPicker";
import ExportButtons from "@/app/_components/ExportButtons";
import { fkRhService } from "./rhService";

interface Comissao {
  id: number; vendedor_id: number; nome: string; total_vendas: number;
  comissao_pct: number; total_comissoes: number; mes: string; status: string;
}

export default function ComissoesTab() {
  const [items, setItems] = useState<Comissao[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ vendedor_id: "", nome: "", mes: "", total_vendas: "", comissao_pct: "" });

  const load = useCallback(() => {
    setLoading(true);
    api.rhComissoesList().then(r => setItems((r.data || []) as unknown as Comissao[])).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    if (!form.vendedor_id || !form.mes) { alert("Vendedor e mês são obrigatórios"); return; }
    const totalVendas = parseFloat(form.total_vendas) || 0;
    const comissaoPct = parseFloat(form.comissao_pct) || 0;
    await api.rhComissoesCreate({
      ...form, vendedor_id: Number(form.vendedor_id), total_vendas: totalVendas,
      comissao_pct: comissaoPct, total_comissoes: totalVendas * comissaoPct / 100,
    });
    setShowForm(false);
    setForm({ vendedor_id: "", nome: "", mes: "", total_vendas: "", comissao_pct: "" });
    load();
  };

  const handlePagar = async (id: number) => { await api.rhComissoesMarcarPago(id); load(); };

  const totalPendente = items.filter(i => i.status !== "pago").reduce((s, i) => s + (i.total_comissoes || 0), 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Comissões</h3>
          <p className="mt-0.5 text-[10px] text-neutral-500">Pendente: {fmtBRL(totalPendente)}</p>
        </div>
        <div className="flex items-center gap-2">
          <ExportButtons
            columns={["Vendedor", "Mês", "Total Vendas", "%", "Comissão", "Status"]}
            rows={items.map(c => [c.nome, c.mes, fmtBRL(c.total_vendas), `${c.comissao_pct}%`, fmtBRL(c.total_comissoes), c.status])}
            filename="comissoes" title="Comissões"
          />
          <Can permission="rh.criar">
            <button onClick={() => setShowForm(s => !s)} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">
              + Nova Comissão
            </button>
          </Can>
        </div>
      </div>

      {showForm && (
        <div className="space-y-3 rounded-xl border border-indigo-700/50 bg-neutral-900/40 p-4">
          <h4 className="text-xs font-semibold text-neutral-300">Nova Comissão</h4>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">Vendedor</label>
              <FkPicker tabela="vendedores" value={form.vendedor_id} onChange={v => setForm({ ...form, vendedor_id: v })} />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">Mês (AAAA-MM)</label>
              <input value={form.mes} onChange={e => setForm({ ...form, mes: e.target.value })}
                className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">Total de Vendas</label>
              <input type="number" step="0.01" value={form.total_vendas} onChange={e => setForm({ ...form, total_vendas: e.target.value })}
                className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">Comissão (%)</label>
              <input type="number" step="0.1" value={form.comissao_pct} onChange={e => setForm({ ...form, comissao_pct: e.target.value })}
                className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
            <button onClick={handleCreate} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Salvar</button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-xs text-neutral-500">Carregando...</p>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-xs text-neutral-500">Nenhuma comissão registrada</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-neutral-800">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/60 text-left text-neutral-400">
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Vendedor</th>
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Mês</th>
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Total Vendas</th>
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">%</th>
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Comissão</th>
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/70">
              {items.map(c => (
                <tr key={c.id} className="text-neutral-300">
                  <td className="whitespace-nowrap px-4 py-2.5">{c.nome}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">{c.mes}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">{fmtBRL(c.total_vendas)}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">{c.comissao_pct}%</td>
                  <td className="whitespace-nowrap px-4 py-2.5 font-medium text-emerald-400">{fmtBRL(c.total_comissoes)}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <span className={`rounded px-2 py-0.5 text-[10px] ${c.status === "pago" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}>{c.status || "pendente"}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {c.status !== "pago" && (
                      <Can permission="rh.editar">
                        <button onClick={() => handlePagar(c.id)} title="Marcar como pago" className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-emerald-500/10 hover:text-emerald-400">
                          <Icon name="check" size={13} />
                        </button>
                      </Can>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
