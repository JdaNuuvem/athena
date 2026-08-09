"use client";

import { useEffect, useState } from "react";
import { fiscalList, fiscalCreate, fiscalUpdate, fiscalDelete } from "@/lib/api";
import type { KpiMetric, Column } from "../types";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";

interface TributoRow {
  id: number;
  nome: string;
  sigla: string;
  aliquota: number;
  aliquota_interestadual: number;
  regime: string;
  tipo: string;
  incidencia: string;
  base_calculo: string;
  fato_gerador: string;
  contribuinte: string;
  observacoes: string;
  ativo: boolean;
}

const REGIMES = ["normal", "nao_cumulativo", "lucro_real", "simples_nacional", "monofasico"];
const TIPOS = ["federal", "estadual", "municipal"];

function extrairErro(res: unknown): string | null {
  if (res && typeof res === "object" && "error" in res && (res as { error?: unknown }).error) {
    return String((res as { error: unknown }).error);
  }
  return null;
}

export default function TributosPage() {
  const [tributos, setTributos] = useState<TributoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: TributoRow }>({ open: false, mode: "create" });
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [excluirAlvo, setExcluirAlvo] = useState<TributoRow | null>(null);
  const [excluindo, setExcluindo] = useState(false);

  const carregar = () => {
    setLoading(true);
    fiscalList("tributos")
      .then(r => setTributos((r.data || []) as TributoRow[]))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const abrirNovo = () => {
    setForm({ tipo: "federal", regime: "normal", ativo: "true" });
    setSaveError("");
    setModal({ open: true, mode: "create" });
  };

  const abrirEdicao = (row: TributoRow) => {
    setForm({
      nome: row.nome || "", sigla: row.sigla || "",
      aliquota: String(row.aliquota ?? ""), aliquota_interestadual: String(row.aliquota_interestadual ?? ""),
      regime: row.regime || "normal", tipo: row.tipo || "federal",
      incidencia: row.incidencia || "", base_calculo: row.base_calculo || "",
      fato_gerador: row.fato_gerador || "", contribuinte: row.contribuinte || "",
      observacoes: row.observacoes || "", ativo: row.ativo ? "true" : "false",
    });
    setSaveError("");
    setModal({ open: true, mode: "edit", row });
  };

  const fecharModal = () => { if (!saving) setModal({ open: false, mode: "create" }); };

  const salvar = async () => {
    if (!form.nome?.trim() || !form.sigla?.trim()) { setSaveError("Nome e sigla sao obrigatorios."); return; }
    setSaving(true); setSaveError("");
    const payload = {
      nome: form.nome.trim(), sigla: form.sigla.trim(),
      aliquota: Number(form.aliquota || 0), aliquota_interestadual: Number(form.aliquota_interestadual || 0),
      regime: form.regime || "normal", tipo: form.tipo || "federal",
      incidencia: form.incidencia?.trim() || "", base_calculo: form.base_calculo?.trim() || "",
      fato_gerador: form.fato_gerador?.trim() || "", contribuinte: form.contribuinte?.trim() || "",
      observacoes: form.observacoes?.trim() || "", ativo: form.ativo === "true",
    };
    try {
      const res = modal.mode === "create"
        ? await fiscalCreate("tributos", payload)
        : await fiscalUpdate("tributos", Number(modal.row?.id), payload);
      const erroResp = extrairErro(res);
      if (erroResp) { setSaveError(erroResp); return; }
      setModal({ open: false, mode: "create" });
      carregar();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Erro ao salvar");
    } finally { setSaving(false); }
  };

  const excluir = async () => {
    if (!excluirAlvo) return;
    setExcluindo(true);
    try {
      await fiscalDelete("tributos", excluirAlvo.id);
      setExcluirAlvo(null);
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao excluir");
    } finally { setExcluindo(false); }
  };

  const ativos = tributos.filter(t => t.ativo);
  const kpis: KpiMetric[] = [
    { label: "Tributos ativos", value: String(ativos.length), color: "text-blue-400" },
    { label: "Federais", value: String(ativos.filter(t => t.tipo === "federal").length), color: "text-amber-400" },
    { label: "Estaduais", value: String(ativos.filter(t => t.tipo === "estadual").length), color: "text-emerald-400" },
    { label: "Municipais", value: String(ativos.filter(t => t.tipo === "municipal").length), color: "text-purple-400" },
  ];

  const COLUMNS: Column<TributoRow>[] = [
    { key: "sigla", label: "Sigla" },
    { key: "nome", label: "Tributo" },
    { key: "tipo", label: "Esfera", render: (_, row) => <span className="capitalize">{row.tipo}</span> },
    { key: "aliquota", label: "Alíquota", align: "center", render: (_, row) => `${row.aliquota}%` },
    { key: "regime", label: "Regime", render: (_, row) => <span className="capitalize">{row.regime.replace(/_/g, " ")}</span> },
    { key: "incidencia", label: "Incidência", render: (_, row) => <span className="text-[10px] text-neutral-400 max-w-[200px] block truncate">{row.incidencia}</span> },
    { key: "ativo", label: "Ativo", align: "center", render: (_, row) => (
      <StatusBadge label={row.ativo ? "Ativo" : "Inativo"} variant={row.ativo ? "success" : "neutral"} />
    )},
    { key: "id", label: "Ações", align: "right", render: (_, row) => (
      <div className="flex justify-end gap-1">
        <Can permission="fiscal.editar">
          <button onClick={() => abrirEdicao(row)} title="Editar" className="rounded-md p-1.5 text-neutral-500 hover:bg-indigo-500/10 hover:text-indigo-400">
            <Icon name="pencil" size={13} />
          </button>
        </Can>
        <Can permission="fiscal.excluir">
          <button onClick={() => setExcluirAlvo(row)} title="Excluir" className="rounded-md p-1.5 text-neutral-500 hover:bg-red-500/10 hover:text-red-400">
            <Icon name="trash" size={13} />
          </button>
        </Can>
      </div>
    )},
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader title="Tributos" subtitle="ICMS, IPI, PIS, COFINS, ISS, CSLL e IRPJ" />
        <Can permission="fiscal.criar">
          <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Novo</button>
        </Can>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <ErrorAlert message={erro} />
      {loading ? (
        <LoadingState />
      ) : (
        <DataTable<TributoRow>
          columns={COLUMNS}
          data={tributos}
          keyExtractor={item => item.id}
          emptyMessage="Nenhum tributo cadastrado"
          countLabel={`${tributos.length} tributos`}
        />
      )}

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={fecharModal}>
          <div className="w-full max-w-[520px] rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Novo tributo" : "Editar tributo"}</h3>
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
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Alíquota (%)</label>
                <input type="number" step="0.0001" value={form.aliquota || ""} onChange={e => setForm({ ...form, aliquota: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Alíquota interestadual (%)</label>
                <input type="number" step="0.0001" value={form.aliquota_interestadual || ""} onChange={e => setForm({ ...form, aliquota_interestadual: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Esfera</label>
                <select value={form.tipo || "federal"} onChange={e => setForm({ ...form, tipo: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Regime</label>
                <select value={form.regime || "normal"} onChange={e => setForm({ ...form, regime: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  {REGIMES.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Incidência</label>
                <input type="text" value={form.incidencia || ""} onChange={e => setForm({ ...form, incidencia: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Base de cálculo</label>
                <input type="text" value={form.base_calculo || ""} onChange={e => setForm({ ...form, base_calculo: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Observações</label>
                <textarea value={form.observacoes || ""} onChange={e => setForm({ ...form, observacoes: e.target.value })} rows={2}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="ativo" checked={form.ativo === "true"} onChange={e => setForm({ ...form, ativo: e.target.checked ? "true" : "false" })}
                  className="rounded border-neutral-600 bg-neutral-700 text-indigo-500 focus:ring-indigo-500/50" />
                <label htmlFor="ativo" className="text-[11px] font-medium text-neutral-400">Ativo</label>
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

      {excluirAlvo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setExcluirAlvo(null)}>
          <div className="w-full max-w-[360px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-amber-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Excluir tributo</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">
              &quot;{excluirAlvo.nome}&quot; será excluído. Essa ação não pode ser desfeita pela tela.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setExcluirAlvo(null)} disabled={excluindo} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={excluir} disabled={excluindo} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-red-500 disabled:opacity-50">
                {excluindo ? "Excluindo..." : "Excluir"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
