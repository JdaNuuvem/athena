"use client";

import { useState, useEffect, useMemo } from "react";
import { api } from "@/lib/api";

interface Proposta {
  id: number;
  negociacao_id: number;
  numero: string | null;
  valor: number | string | null;
  status: string;
  data_envio: string | null;
  data_validade: string | null;
  conteudo: string | null;
}

interface Negociacao {
  id: number;
  titulo: string;
  valor: number | string | null;
}

const STATUS_LABEL: Record<string, string> = {
  rascunho: "Rascunho",
  enviada: "Enviada",
  aceita: "Aceita",
  rejeitada: "Rejeitada",
  vencida: "Vencida",
};

const STATUS_ORDEM = Object.keys(STATUS_LABEL);

function statusClasses(status: string) {
  if (status === "aceita") return "bg-emerald-900/30 text-emerald-400";
  if (status === "rejeitada" || status === "vencida") return "bg-red-900/30 text-red-400";
  if (status === "enviada") return "bg-blue-900/30 text-blue-400";
  return "bg-neutral-700 text-neutral-400";
}

function fmtBRL(v: number | string | null | undefined) {
  return "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtData(iso: string | null) {
  if (!iso) return "—";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

const FORM_VAZIO = { negociacao_id: "", valor: "", status: "rascunho", data_envio: "", data_validade: "", conteudo: "" };

export default function PropostasPage() {
  const [propostas, setPropostas] = useState<Proposta[]>([]);
  const [negociacoes, setNegociacoes] = useState<Negociacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editando, setEditando] = useState<Proposta | null>(null);
  const [form, setForm] = useState(FORM_VAZIO);
  const [salvando, setSalvando] = useState(false);
  const [convertendo, setConvertendo] = useState<number | null>(null);

  const negociacaoPorId = useMemo(() => {
    const m = new Map<number, Negociacao>();
    negociacoes.forEach(n => m.set(n.id, n));
    return m;
  }, [negociacoes]);

  const carregar = async () => {
    setLoading(true);
    setErro(null);
    try {
      const [rp, rn] = await Promise.all([api.crmList("propostas"), api.crmList("negociacoes")]);
      setPropostas((rp.data || []) as Proposta[]);
      setNegociacoes((rn.data || []) as Negociacao[]);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar propostas");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { carregar(); }, []);

  const abrirNova = () => {
    setEditando(null);
    setForm(FORM_VAZIO);
    setErro(null);
    setShowForm(true);
  };

  const abrirEdicao = (p: Proposta) => {
    setEditando(p);
    setForm({
      negociacao_id: String(p.negociacao_id ?? ""),
      valor: String(p.valor ?? ""),
      status: p.status || "rascunho",
      data_envio: p.data_envio ? p.data_envio.slice(0, 10) : "",
      data_validade: p.data_validade ? p.data_validade.slice(0, 10) : "",
      conteudo: p.conteudo || "",
    });
    setErro(null);
    setShowForm(true);
  };

  const salvar = async () => {
    setSalvando(true);
    setErro(null);
    const payload: Record<string, unknown> = {
      valor: form.valor === "" ? 0 : Number(form.valor),
      status: form.status,
      data_envio: form.data_envio || "",
      data_validade: form.data_validade || "",
      conteudo: form.conteudo,
    };
    if (!editando) payload.negociacao_id = Number(form.negociacao_id);
    try {
      if (editando) await api.crmUpdate("propostas", editando.id, payload);
      else await api.crmCreate("propostas", payload);
      setShowForm(false);
      setForm(FORM_VAZIO);
      setEditando(null);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar proposta");
    } finally {
      setSalvando(false);
    }
  };

  const remover = async (id: number) => {
    if (!confirm("Remover esta proposta?")) return;
    setErro(null);
    try {
      await api.crmDelete("propostas", id);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao remover proposta");
    }
  };

  const converterEmContrato = async (id: number) => {
    setConvertendo(id);
    setErro(null);
    setMsg(null);
    try {
      const r = await api.crmConverterPropostaContrato(id);
      if (r.error) setErro(r.error);
      else setMsg(r.ja_processada ? `Já convertida — contrato #${r.contrato_id}` : `Contrato #${r.contrato_id} criado com sucesso`);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao converter proposta em contrato");
    } finally {
      setConvertendo(null);
      setTimeout(() => setMsg(null), 6000);
    }
  };

  const hoje = new Date().toISOString().slice(0, 10);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Propostas</h1>
          <p className="text-xs text-neutral-500 mt-1">Propostas comerciais vinculadas a negociações do CRM</p>
        </div>
        <button onClick={abrirNova} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Nova proposta</button>
      </div>

      {msg && <div className="text-xs px-3 py-2 rounded-lg border bg-green-950/40 border-green-900/50 text-green-400">{msg}</div>}
      {erro && <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>}

      {showForm && (
        <div className="instrument-enter bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-neutral-200">{editando ? `Editar proposta ${editando.numero || ""}` : "Nova proposta"}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs text-neutral-500">Negociação {!editando && "*"}</label>
              {editando ? (
                <p className="text-xs text-neutral-400 mt-1 px-2 py-1.5 bg-neutral-900 border border-neutral-800 rounded">
                  {negociacaoPorId.get(editando.negociacao_id)?.titulo || `#${editando.negociacao_id}`} (não pode ser trocada após criada)
                </p>
              ) : (
                <select
                  value={form.negociacao_id}
                  onChange={e => setForm({ ...form, negociacao_id: e.target.value })}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1"
                >
                  <option value="">Selecione a negociação...</option>
                  {negociacoes.map(n => (
                    <option key={n.id} value={n.id}>#{n.id} — {n.titulo} ({fmtBRL(n.valor)})</option>
                  ))}
                </select>
              )}
            </div>
            <div>
              <label className="text-xs text-neutral-500">Valor</label>
              <input type="number" step="0.01" min="0" value={form.valor}
                onChange={e => setForm({ ...form, valor: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1" />
            </div>
            <div>
              <label className="text-xs text-neutral-500">Status</label>
              <select value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1">
                {STATUS_ORDEM.map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-neutral-500">Data de envio</label>
              <input type="date" value={form.data_envio} onChange={e => setForm({ ...form, data_envio: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1" />
            </div>
            <div>
              <label className="text-xs text-neutral-500">Data de validade</label>
              <input type="date" value={form.data_validade} onChange={e => setForm({ ...form, data_validade: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1" />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-neutral-500">Conteúdo da proposta</label>
              <textarea value={form.conteudo} onChange={e => setForm({ ...form, conteudo: e.target.value })} rows={4}
                placeholder="Escopo, condições, itens propostos..."
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={salvar} disabled={salvando || (!editando && !form.negociacao_id)}
              className="px-3 py-1 bg-emerald-600 text-white text-xs rounded disabled:opacity-50">
              {salvando ? "Salvando..." : "Salvar"}
            </button>
            <button onClick={() => { setShowForm(false); setEditando(null); }} className="px-3 py-1 text-xs text-neutral-400">Cancelar</button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-neutral-500 text-sm">Carregando...</p>
      ) : propostas.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center"><p className="text-neutral-400 text-sm">Nenhuma proposta cadastrada</p></div>
      ) : (
        <div className="instrument-enter bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3">Número</th>
                <th className="text-left p-3">Negociação</th>
                <th className="text-right p-3">Valor</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Envio</th>
                <th className="text-left p-3">Validade</th>
                <th className="text-right p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {propostas.map((p, i) => {
                const vencida = !!p.data_validade && p.data_validade.slice(0, 10) < hoje && (p.status === "enviada" || p.status === "rascunho");
                return (
                  <tr key={p.id} className={`instrument-hover border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                    <td className="p-3 text-neutral-300 font-mono">{p.numero || "—"}</td>
                    <td className="p-3 text-neutral-300">{negociacaoPorId.get(p.negociacao_id)?.titulo || `#${p.negociacao_id}`}</td>
                    <td className="p-3 text-right text-neutral-300 numeric">{fmtBRL(p.valor)}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${statusClasses(p.status)}`}>{STATUS_LABEL[p.status] || p.status}</span>
                      {vencida && <span className="ml-1.5 px-1.5 py-0.5 rounded text-[11px] bg-amber-900/30 text-amber-400" title="Data de validade já passou">vencendo</span>}
                    </td>
                    <td className="p-3 text-neutral-400">{fmtData(p.data_envio)}</td>
                    <td className="p-3 text-neutral-400">{fmtData(p.data_validade)}</td>
                    <td className="p-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {p.status === "aceita" && (
                          <button onClick={() => converterEmContrato(p.id)} disabled={convertendo === p.id}
                            className="text-indigo-400 hover:text-indigo-300 disabled:opacity-50">
                            {convertendo === p.id ? "Convertendo..." : "Converter em contrato"}
                          </button>
                        )}
                        <button onClick={() => abrirEdicao(p)} className="text-neutral-400 hover:text-neutral-200">Editar</button>
                        <button onClick={() => remover(p.id)} className="text-red-400 hover:text-red-300">Remover</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
