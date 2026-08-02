"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface RegraSla {
  id: number;
  prioridade: string;
  tempo_resposta_min: number;
  tempo_resolucao_h: number;
  ativo: boolean;
}

const PRIORIDADES = ["baixa", "normal", "alta", "urgente"];

const PRIORIDADE_LABEL: Record<string, string> = {
  baixa: "Baixa", normal: "Normal", alta: "Alta", urgente: "Urgente",
};

function prioridadeClasses(p: string) {
  if (p === "urgente") return "bg-red-900/30 text-red-400";
  if (p === "alta") return "bg-amber-900/30 text-amber-400";
  if (p === "normal") return "bg-blue-900/30 text-blue-400";
  return "bg-neutral-700 text-neutral-400";
}

function fmtTempoResposta(min: number) {
  if (min % 60 === 0 && min >= 60) return `${min / 60}h`;
  return `${min}min`;
}

const FORM_VAZIO = { prioridade: "", tempo_resposta_min: "60", tempo_resolucao_h: "24" };

export default function SlaPage() {
  const [regras, setRegras] = useState<RegraSla[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editando, setEditando] = useState<RegraSla | null>(null);
  const [form, setForm] = useState(FORM_VAZIO);
  const [salvando, setSalvando] = useState(false);
  const [alternandoId, setAlternandoId] = useState<number | null>(null);

  const carregar = async () => {
    setLoading(true);
    setErro(null);
    try {
      const r = await api.atendList("sla");
      setRegras((r.data || []) as RegraSla[]);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar regras de SLA");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { carregar(); }, []);

  const prioridadesEmUso = new Set(regras.map(r => r.prioridade));
  const prioridadesDisponiveis = PRIORIDADES.filter(p => !prioridadesEmUso.has(p));

  const abrirNova = () => {
    setEditando(null);
    setForm({ ...FORM_VAZIO, prioridade: prioridadesDisponiveis[0] || "" });
    setErro(null);
    setShowForm(true);
  };

  const abrirEdicao = (r: RegraSla) => {
    setEditando(r);
    setForm({
      prioridade: r.prioridade,
      tempo_resposta_min: String(r.tempo_resposta_min ?? ""),
      tempo_resolucao_h: String(r.tempo_resolucao_h ?? ""),
    });
    setErro(null);
    setShowForm(true);
  };

  const salvar = async () => {
    setSalvando(true);
    setErro(null);
    const payload: Record<string, unknown> = {
      tempo_resposta_min: Number(form.tempo_resposta_min),
      tempo_resolucao_h: Number(form.tempo_resolucao_h),
    };
    if (!editando) payload.prioridade = form.prioridade;
    try {
      if (editando) await api.atendUpdate("sla", editando.id, payload);
      else await api.atendCreate("sla", payload);
      setShowForm(false);
      setForm(FORM_VAZIO);
      setEditando(null);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar regra de SLA");
    } finally {
      setSalvando(false);
    }
  };

  const alternarAtivo = async (r: RegraSla) => {
    setAlternandoId(r.id);
    setErro(null);
    try {
      await api.atendUpdate("sla", r.id, { ativo: !r.ativo });
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao atualizar regra de SLA");
    } finally {
      setAlternandoId(null);
    }
  };

  const remover = async (r: RegraSla) => {
    if (!confirm(`Remover a regra de SLA "${PRIORIDADE_LABEL[r.prioridade] || r.prioridade}"? Novos tickets com essa prioridade deixarao de ter prazo de SLA calculado.`)) return;
    setErro(null);
    try {
      await api.atendDelete("sla", r.id);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao remover regra de SLA");
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">SLA</h1>
          <p className="text-xs text-neutral-500 mt-1">Prazos de resposta e resolucao por prioridade de ticket</p>
        </div>
        {prioridadesDisponiveis.length > 0 && (
          <button onClick={abrirNova} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Nova regra</button>
        )}
      </div>

      {erro && <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>}

      {showForm && (
        <div className="instrument-enter bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-neutral-200">{editando ? `Editar regra — ${PRIORIDADE_LABEL[editando.prioridade]}` : "Nova regra de SLA"}</h3>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-neutral-500">Prioridade</label>
              {editando ? (
                <p className="text-xs text-neutral-400 mt-1 px-2 py-1.5 bg-neutral-900 border border-neutral-800 rounded">
                  {PRIORIDADE_LABEL[editando.prioridade]} (nao pode ser trocada)
                </p>
              ) : (
                <select
                  value={form.prioridade}
                  onChange={e => setForm({ ...form, prioridade: e.target.value })}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1"
                >
                  {prioridadesDisponiveis.map(p => <option key={p} value={p}>{PRIORIDADE_LABEL[p]}</option>)}
                </select>
              )}
            </div>
            <div>
              <label className="text-xs text-neutral-500">Tempo de resposta (min)</label>
              <input type="number" min="1" step="1" value={form.tempo_resposta_min}
                onChange={e => setForm({ ...form, tempo_resposta_min: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1" />
            </div>
            <div>
              <label className="text-xs text-neutral-500">Tempo de resolucao (h)</label>
              <input type="number" min="1" step="1" value={form.tempo_resolucao_h}
                onChange={e => setForm({ ...form, tempo_resolucao_h: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={salvar} disabled={salvando || (!editando && !form.prioridade)}
              className="px-3 py-1 bg-emerald-600 text-white text-xs rounded disabled:opacity-50">
              {salvando ? "Salvando..." : "Salvar"}
            </button>
            <button onClick={() => { setShowForm(false); setEditando(null); }} className="px-3 py-1 text-xs text-neutral-400">Cancelar</button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-neutral-500 text-sm">Carregando...</p>
      ) : regras.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center"><p className="text-neutral-400 text-sm">Nenhuma regra de SLA cadastrada</p></div>
      ) : (
        <div className="instrument-enter bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3">Prioridade</th>
                <th className="text-left p-3">Tempo de resposta</th>
                <th className="text-left p-3">Tempo de resolucao</th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {regras.map((r, i) => (
                <tr key={r.id} className={`instrument-hover border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${prioridadeClasses(r.prioridade)}`}>{PRIORIDADE_LABEL[r.prioridade] || r.prioridade}</span>
                  </td>
                  <td className="p-3 text-neutral-300 numeric">{fmtTempoResposta(r.tempo_resposta_min)}</td>
                  <td className="p-3 text-neutral-300 numeric">{r.tempo_resolucao_h}h</td>
                  <td className="p-3">
                    <button onClick={() => alternarAtivo(r)} disabled={alternandoId === r.id}
                      className={`px-2 py-0.5 rounded text-xs disabled:opacity-50 ${r.ativo ? "bg-emerald-900/30 text-emerald-400" : "bg-neutral-700 text-neutral-400"}`}>
                      {alternandoId === r.id ? "..." : r.ativo ? "Ativo" : "Inativo"}
                    </button>
                  </td>
                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => abrirEdicao(r)} className="text-neutral-400 hover:text-neutral-200">Editar</button>
                      <button onClick={() => remover(r)} className="text-red-400 hover:text-red-300">Remover</button>
                    </div>
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
