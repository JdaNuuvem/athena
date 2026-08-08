"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";
import FkPicker from "@/app/_components/FkPicker";
import ExportButtons from "@/app/_components/ExportButtons";
import { fkRhService } from "./rhService";

interface Vale {
  id: number; funcionario_id: number; nome: string; valor: number;
  motivo: string; data: string; status: string;
}

export default function ValeTab() {
  const [items, setItems] = useState<Vale[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ funcionario_id: "", nome: "", valor: "", motivo: "" });

  const load = useCallback(() => {
    setLoading(true);
    api.rhValeList().then(r => setItems((r.data || []) as unknown as Vale[])).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    if (!form.funcionario_id || !form.valor) { alert("Funcionário e valor são obrigatórios"); return; }
    await api.rhValeCreate({ ...form, funcionario_id: Number(form.funcionario_id), valor: parseFloat(form.valor) || 0 });
    setShowForm(false);
    setForm({ funcionario_id: "", nome: "", valor: "", motivo: "" });
    load();
  };

  const handlePagar = async (id: number) => { await api.rhValeMarcarPago(id); load(); };

  const totalPendente = items.filter(i => i.status !== "pago").reduce((s, i) => s + (i.valor || 0), 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Vale / Adiantamento</h3>
          <p className="mt-0.5 text-[10px] text-neutral-500">Pendente: {fmtBRL(totalPendente)}</p>
        </div>
        <div className="flex items-center gap-2">
          <ExportButtons
            columns={["Funcionário", "Valor", "Motivo", "Data", "Status"]}
            rows={items.map(v => [v.nome, fmtBRL(v.valor), v.motivo, fmtDataBR(v.data), v.status])}
            filename="vale-adiantamento" title="Vale / Adiantamento"
          />
          <Can permission="rh.criar">
            <button onClick={() => setShowForm(s => !s)} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">
              + Novo Vale
            </button>
          </Can>
        </div>
      </div>

      {showForm && (
        <div className="space-y-3 rounded-xl border border-indigo-700/50 bg-neutral-900/40 p-4">
          <h4 className="text-xs font-semibold text-neutral-300">Novo Vale</h4>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">Funcionário</label>
              <FkPicker tabela="funcionarios" service={fkRhService} value={form.funcionario_id}
                onChange={v => setForm({ ...form, funcionario_id: v })} />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">Valor</label>
              <input type="number" step="0.01" value={form.valor} onChange={e => setForm({ ...form, valor: e.target.value })}
                className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
            </div>
            <div className="col-span-2">
              <label className="mb-1 block text-[11px] font-medium text-neutral-400">Motivo</label>
              <input value={form.motivo} onChange={e => setForm({ ...form, motivo: e.target.value })}
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
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-xs text-neutral-500">Nenhum vale registrado</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-neutral-800">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-800 bg-neutral-900/60 text-left text-neutral-400">
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Funcionário</th>
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Valor</th>
                <th className="px-4 py-2.5 font-medium">Motivo</th>
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Data</th>
                <th className="whitespace-nowrap px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/70">
              {items.map(v => (
                <tr key={v.id} className="text-neutral-300">
                  <td className="whitespace-nowrap px-4 py-2.5">{v.nome}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 font-medium text-emerald-400">{fmtBRL(v.valor)}</td>
                  <td className="px-4 py-2.5">{v.motivo || "—"}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">{fmtDataBR(v.data)}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <span className={`rounded px-2 py-0.5 text-[10px] ${v.status === "pago" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}>{v.status || "pendente"}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {v.status !== "pago" && (
                      <Can permission="rh.editar">
                        <button onClick={() => handlePagar(v.id)} title="Marcar como pago" className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-emerald-500/10 hover:text-emerald-400">
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
