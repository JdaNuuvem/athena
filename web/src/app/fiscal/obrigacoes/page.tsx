"use client";

import { useEffect, useState, useCallback } from "react";
import { fiscalObrigacoesOcorrencias, fiscalBaixarObrigacao, fiscalList, fiscalCreate, fiscalUpdate } from "@/lib/api";
import PageHeader from "@/app/_components/PageHeader";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";

interface OcorrenciaRow {
  id: number;
  obrigacao_id: number;
  competencia: string;
  data_vencimento: string;
  status: string;
  data_entrega: string | null;
  responsavel: string | null;
  nome: string;
  sigla: string;
  orgao: string;
  periodicidade: string;
  regime: string;
  descricao: string;
}

interface ObrigacaoCadastro {
  id: number;
  nome: string;
  sigla: string;
  descricao: string;
  periodicidade: string;
  dia_vencimento: number | null;
  orgao: string;
  regime: string;
  ativo: boolean;
}

function extrairErro(res: unknown): string | null {
  if (res && typeof res === "object" && "error" in res && (res as { error?: unknown }).error) {
    return String((res as { error: unknown }).error);
  }
  return null;
}

function fmtData(s: string | null) {
  if (!s) return "—";
  return s.slice(0, 10).split("-").reverse().join("/");
}

export default function ObrigacoesPage() {
  const [ocorrencias, setOcorrencias] = useState<OcorrenciaRow[]>([]);
  const [cadastro, setCadastro] = useState<ObrigacaoCadastro[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: ObrigacaoCadastro }>({ open: false, mode: "create" });
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const carregar = useCallback(() => {
    setLoading(true);
    setErro(null);
    Promise.all([fiscalObrigacoesOcorrencias(), fiscalList("obrigacoes")])
      .then(([r1, r2]) => {
        setOcorrencias((r1.data || []) as OcorrenciaRow[]);
        setCadastro((r2.data || []) as ObrigacaoCadastro[]);
      })
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const baixar = async (id: number) => {
    try {
      await fiscalBaixarObrigacao(id);
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao marcar como entregue");
    }
  };

  const abrirNovo = () => {
    setForm({ periodicidade: "mensal", dia_vencimento: "1", ativo: "true" });
    setSaveError("");
    setModal({ open: true, mode: "create" });
  };

  const abrirEdicao = (o: ObrigacaoCadastro) => {
    setForm({
      nome: o.nome || "", sigla: o.sigla || "", descricao: o.descricao || "",
      periodicidade: o.periodicidade || "mensal", dia_vencimento: String(o.dia_vencimento ?? 1),
      orgao: o.orgao || "", regime: o.regime || "normal", ativo: o.ativo ? "true" : "false",
    });
    setSaveError("");
    setModal({ open: true, mode: "edit", row: o });
  };

  const fecharModal = () => { if (!saving) setModal({ open: false, mode: "create" }); };

  const salvar = async () => {
    if (!form.nome?.trim() || !form.sigla?.trim()) { setSaveError("Nome e sigla sao obrigatorios."); return; }
    const dia = Number(form.dia_vencimento || 1);
    if (dia < 1 || dia > 31) { setSaveError("Dia de vencimento precisa estar entre 1 e 31."); return; }
    setSaving(true); setSaveError("");
    const payload = {
      nome: form.nome.trim(), sigla: form.sigla.trim(), descricao: form.descricao?.trim() || "",
      periodicidade: form.periodicidade || "mensal", dia_vencimento: dia,
      orgao: form.orgao?.trim() || "", regime: form.regime?.trim() || "normal",
      ativo: form.ativo === "true",
    };
    try {
      const res = modal.mode === "create"
        ? await fiscalCreate("obrigacoes", payload)
        : await fiscalUpdate("obrigacoes", Number(modal.row?.id), payload);
      const erroResp = extrairErro(res);
      if (erroResp) { setSaveError(erroResp); return; }
      setModal({ open: false, mode: "create" });
      carregar();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Erro ao salvar");
    } finally { setSaving(false); }
  };

  const hojeISO = new Date().toLocaleDateString("en-CA");
  const atrasadas = ocorrencias.filter(o => o.status === "pendente" && o.data_vencimento.slice(0, 10) < hojeISO);
  const pendentesNoPrazo = ocorrencias.filter(o => o.status === "pendente" && !atrasadas.includes(o));
  const entregues = ocorrencias.filter(o => o.status === "entregue");

  const renderOcorrencia = (o: OcorrenciaRow, atrasada: boolean) => (
    <div key={o.id} className={`bg-neutral-800 border rounded-lg p-4 space-y-3 ${atrasada ? "border-red-800/60" : "border-neutral-700"}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-100">{o.nome}</h3>
        <StatusBadge
          label={o.status === "entregue" ? "Entregue" : atrasada ? "Atrasada" : "Pendente"}
          variant={o.status === "entregue" ? "success" : atrasada ? "danger" : "warning"}
        />
      </div>
      <p className="text-xs text-neutral-500">{o.descricao}</p>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div>
          <p className="text-neutral-500">Vencimento</p>
          <p className={atrasada ? "text-red-400" : "text-neutral-300"}>{fmtData(o.data_vencimento)}</p>
        </div>
        <div>
          <p className="text-neutral-500">Competência</p>
          <p className="text-neutral-300">{o.competencia}</p>
        </div>
        <div>
          <p className="text-neutral-500">Órgão</p>
          <p className="text-neutral-300">{o.orgao}</p>
        </div>
        <div>
          <p className="text-neutral-500">Responsável</p>
          <p className="text-neutral-300">{o.responsavel || "—"}</p>
        </div>
      </div>
      {o.status === "pendente" && (
        <Can permission="fiscal.editar">
          <button
            onClick={() => baixar(o.id)}
            className="w-full mt-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded"
          >
            Marcar como Entregue
          </button>
        </Can>
      )}
    </div>
  );

  return (
    <div className="p-6 space-y-8">
      <PageHeader title="Obrigações Acessórias" subtitle="SPED, EFD, DCTF, GIA, SINTEGRA e DAS" />

      <ErrorAlert message={erro} />
      {loading ? (
        <LoadingState />
      ) : (
        <>
          {atrasadas.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-red-400 mb-3">Atrasadas ({atrasadas.length})</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {atrasadas.map(o => renderOcorrencia(o, true))}
              </div>
            </div>
          )}

          <div>
            <h2 className="text-sm font-semibold text-neutral-300 mb-3">Pendentes este mês ({pendentesNoPrazo.length})</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {pendentesNoPrazo.length === 0 ? (
                <p className="text-xs text-neutral-500 col-span-3">Nenhuma obrigação pendente este mês.</p>
              ) : pendentesNoPrazo.map(o => renderOcorrencia(o, false))}
            </div>
          </div>

          {entregues.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-neutral-500 mb-3">Entregues este mês ({entregues.length})</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {entregues.map(o => renderOcorrencia(o, false))}
              </div>
            </div>
          )}

          <div className="border-t border-neutral-800 pt-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-neutral-300">Obrigações cadastradas ({cadastro.length})</h2>
              <Can permission="fiscal.criar">
                <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Nova obrigação</button>
              </Can>
            </div>
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-700 text-neutral-400">
                    <th className="text-left p-3">Sigla</th>
                    <th className="text-left p-3">Nome</th>
                    <th className="text-left p-3">Periodicidade</th>
                    <th className="text-center p-3">Dia venc.</th>
                    <th className="text-left p-3">Órgão</th>
                    <th className="text-center p-3">Ativo</th>
                    <th className="text-right p-3">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {cadastro.map(o => (
                    <tr key={o.id} className="border-b border-neutral-700/50">
                      <td className="p-3 text-neutral-300">{o.sigla}</td>
                      <td className="p-3 text-neutral-300">{o.nome}</td>
                      <td className="p-3 text-neutral-300 capitalize">{o.periodicidade}</td>
                      <td className="p-3 text-center text-neutral-300">{o.dia_vencimento ?? "—"}</td>
                      <td className="p-3 text-neutral-300">{o.orgao}</td>
                      <td className="p-3 text-center">
                        <StatusBadge label={o.ativo ? "Ativo" : "Inativo"} variant={o.ativo ? "success" : "neutral"} />
                      </td>
                      <td className="p-3">
                        <div className="flex justify-end gap-1">
                          <Can permission="fiscal.editar">
                            <button onClick={() => abrirEdicao(o)} title="Editar" className="rounded-md p-1.5 text-neutral-500 hover:bg-indigo-500/10 hover:text-indigo-400">
                              <Icon name="pencil" size={13} />
                            </button>
                          </Can>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={fecharModal}>
          <div className="w-full max-w-[480px] rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Nova obrigação" : "Editar obrigação"}</h3>
              <button onClick={fecharModal} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
                <Icon name="close" size={15} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 px-5 py-4">
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Nome *</label>
                <input type="text" value={form.nome || ""} onChange={e => setForm({ ...form, nome: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Sigla *</label>
                <input type="text" value={form.sigla || ""} onChange={e => setForm({ ...form, sigla: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Descrição</label>
                <input type="text" value={form.descricao || ""} onChange={e => setForm({ ...form, descricao: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Periodicidade</label>
                <select value={form.periodicidade || "mensal"} onChange={e => setForm({ ...form, periodicidade: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  <option value="mensal">Mensal</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Dia de vencimento *</label>
                <input type="number" min={1} max={31} value={form.dia_vencimento || "1"} onChange={e => setForm({ ...form, dia_vencimento: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Órgão</label>
                <input type="text" value={form.orgao || ""} onChange={e => setForm({ ...form, orgao: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="flex items-center gap-2 pt-5">
                <input type="checkbox" id="ativo" checked={form.ativo === "true"} onChange={e => setForm({ ...form, ativo: e.target.checked ? "true" : "false" })}
                  className="rounded border-neutral-600 bg-neutral-700 text-indigo-500 focus:ring-indigo-500/50" />
                <label htmlFor="ativo" className="text-[11px] font-medium text-neutral-400">Ativa (gera ocorrência mensal)</label>
              </div>
              {saveError && (
                <div className="col-span-2 text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{saveError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={fecharModal} disabled={saving} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={salvar} disabled={saving} className="rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
