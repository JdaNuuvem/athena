"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt, fmtDataBR } from "@/lib/format";
import ExportButtons from "@/app/_components/ExportButtons";

interface Pix { id: number; chave: string; tipo_chave: string; descricao: string; valor: number; data_transacao: string; status: string; }

const TIPOS_CHAVE = ["email", "celular", "cpf", "cnpj", "aleatoria"];

export default function PIXTab() {
  const [data, setData] = useState<Pix[]>([]);
  const [loading, setLoading] = useState(true);
  const [criando, setCriando] = useState(false);
  const [novo, setNovo] = useState({ chave: "", tipo_chave: "email", descricao: "", valor: "" });
  const [erro, setErro] = useState("");
  const [erroLista, setErroLista] = useState("");
  const [concluindoId, setConcluindoId] = useState<number | null>(null);

  const load = () => { api.finList("pix").then((r) => setData((r.data || []) as Pix[])).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const marcarConcluido = async (p: Pix) => {
    setErroLista("");
    setConcluindoId(p.id);
    try {
      const r = await api.finUpdate("pix", p.id, { status: "concluido" });
      if ((r as { error?: string }).error) { setErroLista((r as { error?: string }).error || "Erro ao marcar como concluído"); return; }
      load();
    } catch {
      setErroLista("Erro ao marcar como concluído — tente novamente.");
    } finally {
      setConcluindoId(null);
    }
  };

  const abrirCriar = () => {
    setNovo({ chave: "", tipo_chave: "email", descricao: "", valor: "" });
    setErro("");
    setCriando(true);
  };

  const confirmarCriar = async () => {
    if (!novo.chave.trim() || !novo.valor) { setErro("Chave e valor são obrigatórios"); return; }
    try {
      const r = await api.finCreate("pix", {
        chave: novo.chave.trim(),
        tipo_chave: novo.tipo_chave,
        descricao: novo.descricao.trim(),
        valor: Number(novo.valor),
      });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(false);
      load();
    } catch {
      setErro("Erro ao criar transação PIX");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <button onClick={abrirCriar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo PIX</button>
        <ExportButtons
          columns={["Chave", "Tipo", "Descrição", "Valor", "Data", "Status"]}
          rows={data.map(p => [p.chave, p.tipo_chave, p.descricao, fmt(p.valor), p.data_transacao ? fmtDataBR(p.data_transacao) : "—", p.status])}
          filename="pix" title="PIX"
        />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total Transações", v: data.length, c: "text-neutral-200" },
          { label: "Valor Total", v: data.reduce((s, p) => s + p.valor, 0), c: "text-emerald-400" },
          { label: "Concluídos", v: data.filter(p => p.status === "concluido").length, c: "text-blue-400" },
          { label: "Pendentes", v: data.filter(p => p.status === "pendente").length, c: "text-amber-400" },
        ].map((c) => (
          <div key={c.label} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
            <p className="text-[10px] text-neutral-500">{c.label}</p>
            <p className={`text-sm font-semibold mt-0.5 ${c.c}`}>{c.label === "Valor Total" ? fmt(c.v) : c.v}</p>
          </div>
        ))}
      </div>
      {erroLista && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{erroLista}</div>}
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 text-left">
                <th className="px-4 py-2 font-medium">Chave</th>
                <th className="px-4 py-2 font-medium">Tipo</th>
                <th className="px-4 py-2 font-medium">Descrição</th>
                <th className="px-4 py-2 font-medium">Valor</th>
                <th className="px-4 py-2 font-medium">Data</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => {
                const sc = p.status === "concluido" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400";
                return (
                  <tr key={p.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">
                    <td className="px-4 py-2.5">{p.chave}</td>
                    <td className="px-4 py-2.5">{p.tipo_chave}</td>
                    <td className="px-4 py-2.5">{p.descricao}</td>
                    <td className="px-4 py-2.5">{fmt(p.valor)}</td>
                    <td className="px-4 py-2.5">{p.data_transacao ? new Date(p.data_transacao).toLocaleDateString("pt-BR") : "—"}</td>
                    <td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{p.status}</span></td>
                    <td className="px-4 py-2.5">{p.status !== "concluido" && (
                      <button onClick={() => marcarConcluido(p)} disabled={concluindoId === p.id}
                        className="text-indigo-400 hover:text-indigo-300 text-[11px] disabled:opacity-50">
                        {concluindoId === p.id ? "Marcando..." : "Marcar como concluído"}
                      </button>
                    )}</td>
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
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Novo PIX</h3>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <input value={novo.chave} onChange={e => setNovo({ ...novo, chave: e.target.value })}
                placeholder="Chave PIX" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <select value={novo.tipo_chave} onChange={e => setNovo({ ...novo, tipo_chave: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                {TIPOS_CHAVE.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <input value={novo.descricao} onChange={e => setNovo({ ...novo, descricao: e.target.value })}
                placeholder="Descrição" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novo.valor} onChange={e => setNovo({ ...novo, valor: e.target.value })}
                placeholder="Valor" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
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
