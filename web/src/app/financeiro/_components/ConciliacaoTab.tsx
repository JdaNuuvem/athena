"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt, fmtDataBR } from "@/lib/format";
import ExportButtons from "@/app/_components/ExportButtons";

interface Conciliacao { id: number; banco_id: number; data: string; descricao: string; valor_extrato: number; valor_sistema: number; status: string; }
interface Banco { id: number; nome: string; }

export default function ConciliacaoTab() {
  const [data, setData] = useState<Conciliacao[]>([]);
  const [bancos, setBancos] = useState<Banco[]>([]);
  const [loading, setLoading] = useState(true);
  const [criando, setCriando] = useState(false);
  const [novo, setNovo] = useState({ banco_id: "", data: "", descricao: "", valor_extrato: "", valor_sistema: "" });
  const [erro, setErro] = useState("");

  const load = () => { api.finList("conciliacao").then((r) => setData((r.data || []) as Conciliacao[])).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => {
    load();
    api.finList("bancos").then((r) => setBancos((r.data || []) as Banco[])).catch(() => {});
  }, []);

  const abrirCriar = () => {
    setNovo({ banco_id: bancos[0] ? String(bancos[0].id) : "", data: new Date().toISOString().slice(0, 10), descricao: "", valor_extrato: "", valor_sistema: "" });
    setErro("");
    setCriando(true);
  };

  const confirmarCriar = async () => {
    if (!novo.banco_id || !novo.descricao.trim()) { setErro("Banco e descrição são obrigatórios"); return; }
    try {
      const r = await api.finCreate("conciliacao", {
        banco_id: Number(novo.banco_id),
        data: novo.data,
        descricao: novo.descricao.trim(),
        valor_extrato: Number(novo.valor_extrato) || 0,
        valor_sistema: Number(novo.valor_sistema) || 0,
      });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(false);
      load();
    } catch {
      setErro("Erro ao criar conciliação");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <button onClick={abrirCriar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conciliação</button>
        <ExportButtons
          columns={["Data", "Descrição", "Extrato", "Sistema", "Diferença", "Status"]}
          rows={data.map(c => [c.data ? fmtDataBR(c.data) : "—", c.descricao, fmt(c.valor_extrato), fmt(c.valor_sistema), fmt(c.valor_extrato - c.valor_sistema), c.status])}
          filename="conciliacao" title="Conciliação Bancária"
        />
      </div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 text-left">
                <th className="px-4 py-2 font-medium">Data</th>
                <th className="px-4 py-2 font-medium">Descrição</th>
                <th className="px-4 py-2 font-medium">Extrato</th>
                <th className="px-4 py-2 font-medium">Sistema</th>
                <th className="px-4 py-2 font-medium">Diferença</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => {
                const diff = c.valor_extrato - c.valor_sistema;
                const sc = c.status === "conciliado" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400";
                return (
                  <tr key={c.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">
                    <td className="px-4 py-2.5">{c.data ? new Date(c.data + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td>
                    <td className="px-4 py-2.5">{c.descricao}</td>
                    <td className="px-4 py-2.5">{fmt(c.valor_extrato)}</td>
                    <td className="px-4 py-2.5">{fmt(c.valor_sistema)}</td>
                    <td className={`px-4 py-2.5 font-medium ${diff === 0 ? "text-emerald-400" : "text-red-400"}`}>{fmt(diff)}</td>
                    <td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{c.status}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {criando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(false)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Nova Conciliação</h3>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <select value={novo.banco_id} onChange={e => setNovo({ ...novo, banco_id: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                <option value="">Selecione o banco</option>
                {bancos.map(b => <option key={b.id} value={b.id}>{b.nome}</option>)}
              </select>
              <input type="date" value={novo.data} onChange={e => setNovo({ ...novo, data: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novo.descricao} onChange={e => setNovo({ ...novo, descricao: e.target.value })}
                placeholder="Descrição" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novo.valor_extrato} onChange={e => setNovo({ ...novo, valor_extrato: e.target.value })}
                placeholder="Valor no extrato" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novo.valor_sistema} onChange={e => setNovo({ ...novo, valor_sistema: e.target.value })}
                placeholder="Valor no sistema" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setCriando(false)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarCriar} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Criar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
