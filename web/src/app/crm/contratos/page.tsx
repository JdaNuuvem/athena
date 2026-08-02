"use client";

import { useState, useEffect, useMemo } from "react";
import { Can } from "@/lib/auth";
import { api } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";

interface Contrato {
  id: number;
  negociacao_id: number | null;
  proposta_id: number | null;
  numero: string | null;
  valor: number | string | null;
  status: string;
  data_assinatura: string | null;
}

interface Negociacao {
  id: number;
  titulo: string;
}

interface Proposta {
  id: number;
  numero: string | null;
}

const STATUS_LABEL: Record<string, string> = {
  pendente: "Pendente",
  assinado: "Assinado",
  cancelado: "Cancelado",
};

const STATUS_ORDEM = Object.keys(STATUS_LABEL);

function statusClasses(status: string) {
  if (status === "assinado") return "bg-emerald-900/30 text-emerald-400";
  if (status === "cancelado") return "bg-red-900/30 text-red-400";
  return "bg-amber-900/30 text-amber-400";
}

const FORM_VAZIO = { negociacao_id: "", proposta_id: "", valor: "", status: "pendente", data_assinatura: "" };

export default function Page() {
  const [contratos, setContratos] = useState<Contrato[]>([]);
  const [negociacoes, setNegociacoes] = useState<Negociacao[]>([]);
  const [propostas, setPropostas] = useState<Proposta[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editando, setEditando] = useState<Contrato | null>(null);
  const [form, setForm] = useState(FORM_VAZIO);
  const [salvando, setSalvando] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [busca, setBusca] = useState("");

  const negociacaoPorId = useMemo(() => {
    const m = new Map<number, Negociacao>();
    negociacoes.forEach(n => m.set(n.id, n));
    return m;
  }, [negociacoes]);

  const propostaPorId = useMemo(() => {
    const m = new Map<number, Proposta>();
    propostas.forEach(p => m.set(p.id, p));
    return m;
  }, [propostas]);

  const carregar = async () => {
    setLoading(true);
    setErro(null);
    try {
      const [rc, rn, rp] = await Promise.all([
        api.crmList("contratos"),
        api.crmList("negociacoes"),
        api.crmList("propostas"),
      ]);
      setContratos((rc.data || []) as Contrato[]);
      setNegociacoes((rn.data || []) as Negociacao[]);
      setPropostas((rp.data || []) as Proposta[]);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar contratos");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { carregar(); }, []);

  const abrirNovo = () => {
    setEditando(null);
    setForm(FORM_VAZIO);
    setErro(null);
    setShowForm(true);
  };

  const abrirEdicao = (c: Contrato) => {
    setEditando(c);
    setForm({
      negociacao_id: String(c.negociacao_id ?? ""),
      proposta_id: String(c.proposta_id ?? ""),
      valor: String(c.valor ?? ""),
      status: c.status || "pendente",
      data_assinatura: c.data_assinatura ? c.data_assinatura.slice(0, 10) : "",
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
      data_assinatura: form.data_assinatura || "",
    };
    // negociacao_id/proposta_id so' vao no create — depois de criado, o
    // vinculo de origem nao muda (evita duplicar contrato se o evento
    // "proposta aceita -> converter" rodar de novo pra mesma proposta).
    if (!editando) {
      payload.negociacao_id = Number(form.negociacao_id);
      if (form.proposta_id) payload.proposta_id = Number(form.proposta_id);
    }
    try {
      if (editando) await api.crmUpdate("contratos", editando.id, payload);
      else await api.crmCreate("contratos", payload);
      setShowForm(false);
      setForm(FORM_VAZIO);
      setEditando(null);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar contrato");
    } finally {
      setSalvando(false);
    }
  };

  const remover = async (id: number) => {
    setErro(null);
    try {
      await api.crmDelete("contratos", id);
      setConfirmDelete(null);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao remover contrato");
    }
  };

  const filtrados = useMemo(() => {
    if (!busca.trim()) return contratos;
    const q = busca.trim().toLowerCase();
    return contratos.filter(c => {
      const neg = negociacaoPorId.get(c.negociacao_id ?? -1)?.titulo || "";
      return [c.numero, neg, c.status].some(v => String(v ?? "").toLowerCase().includes(q));
    });
  }, [contratos, busca, negociacaoPorId]);

  // Propostas ainda sem contrato — o caminho normal e' o botao "Converter em
  // contrato" na tela de Propostas, que ja gera o contrato sozinho; este
  // seletor serve pra vincular manualmente em excecoes/correcoes.
  const propostasDisponiveis = useMemo(
    () => propostas.filter(p => !contratos.some(c => c.proposta_id === p.id)),
    [propostas, contratos]
  );

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Contratos</h1>
          <p className="text-xs text-neutral-500 mt-1">Contratos gerados a partir de propostas aceitas, ou criados manualmente</p>
        </div>
        <Can permission="crm.criar">
          <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Novo contrato</button>
        </Can>
      </div>

      <div className="w-full max-w-xs">
        <input
          type="text"
          placeholder="Buscar por número, negociação ou status..."
          value={busca}
          onChange={e => setBusca(e.target.value)}
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500"
        />
      </div>

      {erro && <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>}

      {showForm && (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-neutral-200">{editando ? `Editar contrato ${editando.numero || ""}` : "Novo contrato"}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-neutral-500">Negociação {!editando && "*"}</label>
              {editando ? (
                <p className="text-xs text-neutral-400 mt-1 px-2 py-1.5 bg-neutral-900 border border-neutral-800 rounded">
                  {negociacaoPorId.get(editando.negociacao_id ?? -1)?.titulo || (editando.negociacao_id ? `#${editando.negociacao_id}` : "—")}
                </p>
              ) : (
                <select
                  value={form.negociacao_id}
                  onChange={e => setForm({ ...form, negociacao_id: e.target.value })}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1"
                >
                  <option value="">Selecione a negociação...</option>
                  {negociacoes.map(n => (
                    <option key={n.id} value={n.id}>#{n.id} — {n.titulo}</option>
                  ))}
                </select>
              )}
            </div>
            <div>
              <label className="text-xs text-neutral-500">Proposta de origem</label>
              {editando ? (
                <p className="text-xs text-neutral-400 mt-1 px-2 py-1.5 bg-neutral-900 border border-neutral-800 rounded">
                  {editando.proposta_id ? (propostaPorId.get(editando.proposta_id)?.numero || `#${editando.proposta_id}`) : "— (criado manualmente)"}
                </p>
              ) : (
                <select
                  value={form.proposta_id}
                  onChange={e => setForm({ ...form, proposta_id: e.target.value })}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1"
                >
                  <option value="">Nenhuma (contrato avulso)</option>
                  {propostasDisponiveis.map(p => (
                    <option key={p.id} value={p.id}>{p.numero || `#${p.id}`}</option>
                  ))}
                </select>
              )}
            </div>
            <div>
              <label className="text-xs text-neutral-500">Valor (R$)</label>
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
              <label className="text-xs text-neutral-500">Data de assinatura</label>
              <input type="date" value={form.data_assinatura} onChange={e => setForm({ ...form, data_assinatura: e.target.value })}
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
      ) : filtrados.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">{busca ? "Nenhum contrato corresponde à busca" : "Nenhum contrato cadastrado"}</p>
        </div>
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3">Número</th>
                <th className="text-left p-3">Negociação</th>
                <th className="text-left p-3">Proposta</th>
                <th className="text-right p-3">Valor</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Assinatura</th>
                <th className="text-right p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((c, i) => (
                <tr key={c.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-neutral-300 font-mono">{c.numero || "—"}</td>
                  <td className="p-3 text-neutral-300">{negociacaoPorId.get(c.negociacao_id ?? -1)?.titulo || (c.negociacao_id ? `#${c.negociacao_id}` : "—")}</td>
                  <td className="p-3 text-neutral-400">{c.proposta_id ? (propostaPorId.get(c.proposta_id)?.numero || `#${c.proposta_id}`) : "—"}</td>
                  <td className="p-3 text-right text-neutral-300">{fmtBRL(Number(c.valor) || 0)}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${statusClasses(c.status)}`}>{STATUS_LABEL[c.status] || c.status}</span>
                  </td>
                  <td className="p-3 text-neutral-400">{fmtDataBR(c.data_assinatura)}</td>
                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Can permission="crm.editar">
                        <button onClick={() => abrirEdicao(c)} className="text-neutral-400 hover:text-neutral-200">Editar</button>
                      </Can>
                      <Can permission="crm.excluir">
                        <button onClick={() => setConfirmDelete(c.id)} className="text-red-400 hover:text-red-300">Remover</button>
                      </Can>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setConfirmDelete(null)}>
          <div className="w-full max-w-[340px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-100 mb-2">Confirmar exclusão</h3>
            <p className="mb-4 text-xs text-neutral-400">Tem certeza que deseja excluir este contrato? Essa ação não pode ser desfeita.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={() => remover(confirmDelete)} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-red-500">Excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
