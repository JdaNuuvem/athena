"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt, fmtDataBR } from "@/lib/format";
import ExportButtons from "@/app/_components/ExportButtons";

interface Lancamento { id: number; data: string; descricao: string; tipo: string; valor: number; categoria: string; }

export default function FluxoCaixaTab() {
  const [data, setData] = useState<Lancamento[]>([]);
  const [resumo, setResumo] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [criando, setCriando] = useState(false);
  const [novo, setNovo] = useState({ tipo: "entrada", descricao: "", valor: "", data: "", categoria: "" });
  const [erro, setErro] = useState("");

  const load = () => {
    api.finFluxoResumo()
      .then((r) => { setData((r.diario || []) as Lancamento[]); setResumo(r.resumo || {}); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const abrirCriar = () => {
    setNovo({ tipo: "entrada", descricao: "", valor: "", data: new Date().toISOString().slice(0, 10), categoria: "" });
    setErro("");
    setCriando(true);
  };

  const confirmarCriar = async () => {
    if (!novo.descricao.trim() || !novo.valor || !novo.data) { setErro("Descrição, valor e data são obrigatórios"); return; }
    try {
      const r = await api.finCreate("fluxo_caixa", {
        tipo: novo.tipo,
        descricao: novo.descricao.trim(),
        valor: Number(novo.valor),
        data: novo.data,
        categoria: novo.categoria.trim(),
      });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(false);
      load();
    } catch {
      setErro("Erro ao criar lançamento");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <button onClick={abrirCriar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo Lançamento</button>
        <ExportButtons
          columns={["Data", "Descrição", "Categoria", "Tipo", "Valor"]}
          rows={data.map(f => [fmtDataBR(f.data), f.descricao, f.categoria, f.tipo, fmt(f.valor)])}
          filename="fluxo-caixa" title="Fluxo de Caixa"
        />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Entradas", v: Number(resumo.total_entradas) || 0, c: "text-emerald-400" },
          { label: "Saídas", v: Number(resumo.total_saidas) || 0, c: "text-red-400" },
          { label: "Saldo", v: (Number(resumo.total_entradas) || 0) - (Number(resumo.total_saidas) || 0), c: "text-blue-400" },
          { label: "Lançamentos", v: data.length, c: "text-neutral-200" },
        ].map((c) => (
          <div key={c.label} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
            <p className="text-[10px] text-neutral-500">{c.label}</p>
            <p className={`text-sm font-semibold mt-0.5 ${c.c}`}>{c.label === "Lançamentos" ? c.v : fmt(c.v)}</p>
          </div>
        ))}
      </div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 text-left">
                <th className="px-4 py-2 font-medium">Data</th>
                <th className="px-4 py-2 font-medium">Descrição</th>
                <th className="px-4 py-2 font-medium">Categoria</th>
                <th className="px-4 py-2 font-medium">Valor</th>
                <th className="px-4 py-2 font-medium">Tipo</th>
              </tr>
            </thead>
            <tbody>
              {data.map((f) => (
                <tr key={f.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">
                  <td className="px-4 py-2.5">{f.data ? new Date(f.data + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td>
                  <td className="px-4 py-2.5">{f.descricao}</td>
                  <td className="px-4 py-2.5">{f.categoria}</td>
                  <td className={`px-4 py-2.5 font-medium ${f.tipo === "entrada" ? "text-emerald-400" : "text-red-400"}`}>{f.tipo === "entrada" ? "+" : "-"}{fmt(f.valor)}</td>
                  <td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${f.tipo === "entrada" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{f.tipo}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {criando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(false)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Novo Lançamento</h3>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <select value={novo.tipo} onChange={e => setNovo({ ...novo, tipo: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                <option value="entrada">Entrada</option>
                <option value="saida">Saída</option>
              </select>
              <input value={novo.descricao} onChange={e => setNovo({ ...novo, descricao: e.target.value })}
                placeholder="Descrição" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novo.valor} onChange={e => setNovo({ ...novo, valor: e.target.value })}
                placeholder="Valor" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="date" value={novo.data} onChange={e => setNovo({ ...novo, data: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novo.categoria} onChange={e => setNovo({ ...novo, categoria: e.target.value })}
                placeholder="Categoria" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
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
