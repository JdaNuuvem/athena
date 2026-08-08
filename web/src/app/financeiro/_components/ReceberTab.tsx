"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt, fmtDataBR } from "@/lib/format";
import ExportButtons from "@/app/_components/ExportButtons";

interface Conta { id: number; cliente: string; descricao: string; valor: number; vencimento: string; data_recebimento?: string; status: string; forma_pagamento: string; }

const FORMAS = ["boleto", "pix", "ted", "dinheiro", "cartao"];

export default function ReceberTab() {
  const [data, setData] = useState<Conta[]>([]);
  const [loading, setLoading] = useState(true);
  const [criando, setCriando] = useState(false);
  const [novaConta, setNovaConta] = useState({ cliente: "", descricao: "", valor: "", vencimento: "", forma_pagamento: "boleto" });
  const [erro, setErro] = useState("");
  const [erroLista, setErroLista] = useState("");
  const [marcandoId, setMarcandoId] = useState<number | null>(null);

  const load = () => { api.finList("contas_receber").then((r) => setData((r.data || []) as Conta[])).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const abrirCriar = () => {
    setNovaConta({ cliente: "", descricao: "", valor: "", vencimento: "", forma_pagamento: "boleto" });
    setErro("");
    setCriando(true);
  };

  const confirmarCriar = async () => {
    if (!novaConta.cliente.trim() || !novaConta.valor) { setErro("Cliente e valor são obrigatórios"); return; }
    try {
      const r = await api.finCreate("contas_receber", {
        cliente: novaConta.cliente.trim(),
        descricao: novaConta.descricao.trim(),
        valor: Number(novaConta.valor),
        vencimento: novaConta.vencimento || null,
        forma_pagamento: novaConta.forma_pagamento,
      });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(false);
      load();
    } catch {
      setErro("Erro ao criar conta");
    }
  };

  const marcarRecebido = async (c: Conta) => {
    setErroLista("");
    setMarcandoId(c.id);
    try {
      const r = await api.finUpdate("contas_receber", c.id, { status: "pago", data_recebimento: new Date().toISOString().slice(0, 10) });
      if ((r as { error?: string }).error) { setErroLista((r as { error?: string }).error || "Erro ao marcar como recebido"); return; }
      load();
    } catch {
      setErroLista("Erro ao marcar como recebido — tente novamente.");
    } finally {
      setMarcandoId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <button onClick={abrirCriar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conta</button>
        <ExportButtons
          columns={["Cliente", "Descrição", "Valor", "Vencimento", "Forma Pag.", "Status"]}
          rows={data.map(c => [c.cliente, c.descricao, fmt(c.valor), c.vencimento ? fmtDataBR(c.vencimento) : "—", c.forma_pagamento, c.status])}
          filename="contas-receber" title="Contas a Receber"
        />
      </div>
      {erroLista && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{erroLista}</div>}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[{ label: "Total Pendente", v: data.filter(c => c.status !== "pago").reduce((s, c) => s + c.valor, 0), c: "text-amber-400" }, { label: "Total Recebido", v: data.filter(c => c.status === "pago").reduce((s, c) => s + c.valor, 0), c: "text-emerald-400" }, { label: "Vencidas", v: data.filter(c => c.status === "atrasado").length, c: "text-red-400" }, { label: "Total", v: data.length, c: "text-neutral-200" }].map((c) => (
          <div key={c.label} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3"><p className="text-[10px] text-neutral-500">{c.label}</p><p className={`text-sm font-semibold mt-0.5 ${c.c}`}>{c.label === "Vencidas" || c.label === "Total" ? c.v : fmt(c.v)}</p></div>
        ))}</div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden"><table className="w-full text-xs">
          <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-4 py-2 font-medium">Cliente</th><th className="px-4 py-2 font-medium">Descrição</th><th className="px-4 py-2 font-medium">Valor</th><th className="px-4 py-2 font-medium">Vencimento</th><th className="px-4 py-2 font-medium">Forma Pag.</th><th className="px-4 py-2 font-medium">Status</th><th className="px-4 py-2 font-medium"></th></tr></thead>
          <tbody>{data.map((c) => {
            const sc = c.status === "pago" ? "bg-emerald-500/20 text-emerald-400" : c.status === "atrasado" ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400";
            return <tr key={c.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-4 py-2.5">{c.cliente}</td><td className="px-4 py-2.5">{c.descricao}</td><td className="px-4 py-2.5">{fmt(c.valor)}</td><td className="px-4 py-2.5">{c.vencimento ? new Date(c.vencimento + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td><td className="px-4 py-2.5">{c.forma_pagamento}</td><td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{c.status}</span></td>
              <td className="px-4 py-2.5">{c.status !== "pago" && (
                <button onClick={() => marcarRecebido(c)} disabled={marcandoId === c.id}
                  className="text-indigo-400 hover:text-indigo-300 text-[11px] disabled:opacity-50">
                  {marcandoId === c.id ? "Marcando..." : "Marcar como recebido"}
                </button>
              )}</td>
            </tr>;
          })}</tbody>
        </table></div>
      )}

      {criando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(false)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Nova Conta a Receber</h3>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <input value={novaConta.cliente} onChange={e => setNovaConta({ ...novaConta, cliente: e.target.value })}
                placeholder="Cliente" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novaConta.descricao} onChange={e => setNovaConta({ ...novaConta, descricao: e.target.value })}
                placeholder="Descrição" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novaConta.valor} onChange={e => setNovaConta({ ...novaConta, valor: e.target.value })}
                placeholder="Valor" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="date" value={novaConta.vencimento} onChange={e => setNovaConta({ ...novaConta, vencimento: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <select value={novaConta.forma_pagamento} onChange={e => setNovaConta({ ...novaConta, forma_pagamento: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                {FORMAS.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
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
