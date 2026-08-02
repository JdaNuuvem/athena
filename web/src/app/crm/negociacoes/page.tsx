"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import CrudPanel, { type Column, type FieldDef, type CrudService } from "../../_components/CrudPanel";
import Icon from "../../_components/Icon";
import { Can } from "@/lib/auth";
import { api, evtNegociacaoGanha } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";

const ETAPAS_FUNIL = ["captacao", "qualificacao", "prospeccao", "proposta", "negociacao", "fechamento"];

const ETAPA_CORES: Record<string, string> = {
  captacao: "bg-blue-500/20 text-blue-400",
  qualificacao: "bg-cyan-500/20 text-cyan-400",
  prospeccao: "bg-yellow-500/20 text-yellow-400",
  proposta: "bg-orange-500/20 text-orange-400",
  negociacao: "bg-pink-500/20 text-pink-400",
  fechamento: "bg-emerald-500/20 text-emerald-400",
};

const STATUS_CORES: Record<string, string> = {
  aberta: "bg-indigo-500/20 text-indigo-400",
  ganha: "bg-emerald-500/20 text-emerald-400",
  perdida: "bg-red-500/20 text-red-400",
};

interface Registro { id: number; nome: string; }

const negociacoesService: CrudService = {
  list: (tabela) => api.crmList(tabela),
  create: (tabela, data) => api.crmCreate(tabela, data),
  update: (tabela, id, data) => api.crmUpdate(tabela, id, data),
  delete: (tabela, id) => api.crmDelete(tabela, id),
};

export default function Page() {
  const [leads, setLeads] = useState<Registro[]>([]);
  const [contatos, setContatos] = useState<Registro[]>([]);
  const [empresas, setEmpresas] = useState<Registro[]>([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [processando, setProcessando] = useState<number | null>(null);

  useEffect(() => {
    api.crmList("leads").then(r => setLeads((r.data || []) as Registro[])).catch(() => {});
    api.crmList("contatos").then(r => setContatos((r.data || []) as Registro[])).catch(() => {});
    api.crmList("empresas").then(r => setEmpresas((r.data || []) as Registro[])).catch(() => {});
  }, []);

  const leadsMap = useMemo(() => Object.fromEntries(leads.map(l => [l.id, l.nome])), [leads]);
  const empresasMap = useMemo(() => Object.fromEntries(empresas.map(e => [e.id, e.nome])), [empresas]);

  const marcarGanha = useCallback(async (id: number) => {
    setProcessando(id);
    try {
      const r = await evtNegociacaoGanha(id);
      if (r.error) { alert(String(r.error)); return; }
      setReloadKey(k => k + 1);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Erro ao marcar negociação como ganha");
    } finally {
      setProcessando(null);
    }
  }, []);

  const marcarPerdida = useCallback(async (id: number) => {
    if (!confirm("Marcar esta negociação como perdida?")) return;
    setProcessando(id);
    try {
      await api.crmUpdate("negociacoes", id, { status: "perdida" });
      setReloadKey(k => k + 1);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Erro ao marcar negociação como perdida");
    } finally {
      setProcessando(null);
    }
  }, []);

  const negociacoesCols: Column[] = useMemo(() => [
    { key: "titulo", label: "Título" },
    { key: "lead_id", label: "Lead", render: (v) => v ? (leadsMap[Number(v)] || `#${v}`) : "—" },
    { key: "empresa_id", label: "Empresa", render: (v) => v ? (empresasMap[Number(v)] || `#${v}`) : "—" },
    { key: "valor", label: "Valor", render: (v) => fmtBRL(Number(v) || 0) },
    { key: "etapa_funil", label: "Etapa", render: (v) => {
      const s = String(v ?? "prospeccao");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${ETAPA_CORES[s] || "bg-neutral-500/20 text-neutral-400"}`}>{s.replace(/_/g, " ")}</span>;
    }},
    { key: "probabilidade", label: "Prob.", render: (v) => `${v ?? 0}%` },
    { key: "status", label: "Status", render: (v) => {
      const s = String(v ?? "aberta");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_CORES[s] || "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    }},
    { key: "data_fechamento", label: "Fechamento", render: fmtDataBR },
  ], [leadsMap, empresasMap]);

  const negociacoesFields: FieldDef[] = useMemo(() => [
    { key: "titulo", label: "Título" },
    { key: "lead_id", label: "Lead", type: "select", numeric: true, options: leads.map(l => ({ label: l.nome, value: String(l.id) })) },
    { key: "contato_id", label: "Contato", type: "select", numeric: true, options: contatos.map(c => ({ label: c.nome, value: String(c.id) })) },
    { key: "empresa_id", label: "Empresa", type: "select", numeric: true, options: empresas.map(e => ({ label: e.nome, value: String(e.id) })) },
    { key: "valor", label: "Valor (R$)", type: "number", step: "0.01" },
    { key: "etapa_funil", label: "Etapa do funil", type: "select", options: ETAPAS_FUNIL.map(e => ({ label: e.replace(/_/g, " "), value: e })) },
    { key: "probabilidade", label: "Probabilidade (%)", type: "number", step: "1", min: 0, max: 100 },
    { key: "data_fechamento", label: "Previsão de fechamento", type: "date" },
    { key: "observacoes", label: "Observações" },
  ], [leads, contatos, empresas]);

  const rowActions = useCallback((row: Record<string, unknown>) => {
    if (row.status !== "aberta") return null;
    const id = Number(row.id);
    const busy = processando === id;
    return (
      <>
        <Can permission="crm.editar">
          <button
            onClick={() => marcarGanha(id)}
            disabled={busy}
            title="Marcar como ganha"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-emerald-500/10 hover:text-emerald-400 disabled:opacity-50"
          >
            <Icon name="check" size={13} />
          </button>
          <button
            onClick={() => marcarPerdida(id)}
            disabled={busy}
            title="Marcar como perdida"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
          >
            <Icon name="close" size={13} />
          </button>
        </Can>
      </>
    );
  }, [processando, marcarGanha, marcarPerdida]);

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Negociações</h1>
        <p className="text-xs text-neutral-500 mt-1">Pipeline de vendas — marque como ganha ou perdida para fechar</p>
      </div>
      <CrudPanel
        tabela="negociacoes"
        columns={negociacoesCols}
        formFields={negociacoesFields}
        service={negociacoesService}
        permissionPrefix="crm"
        rowActions={rowActions}
        reloadKey={reloadKey}
      />
    </div>
  );
}
