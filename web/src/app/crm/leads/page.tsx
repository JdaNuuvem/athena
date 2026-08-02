"use client";

import { useEffect, useMemo, useState } from "react";
import CrudPanel, { type Column, type FieldDef, type CrudService } from "../../_components/CrudPanel";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";

const ETAPAS_FUNIL = ["captacao", "qualificacao", "prospeccao", "proposta", "negociacao", "fechamento"];

const STATUS_CORES: Record<string, string> = {
  novo: "bg-indigo-500/20 text-indigo-400",
  contatado: "bg-amber-500/20 text-amber-400",
  qualificado: "bg-sky-500/20 text-sky-400",
  convertido: "bg-emerald-500/20 text-emerald-400",
  perdido: "bg-red-500/20 text-red-400",
};

// empresa_id e' FK numerica opcional — o formulario generico do CrudPanel
// trata campo "select" como string, entao normaliza pra numero/null antes
// de mandar pro backend (coluna crm_leads.empresa_id e' INT).
function normalizarPayloadLead(data: Record<string, unknown>) {
  const bruto = data.empresa_id;
  const empresa_id = bruto === "" || bruto == null ? null : Number(bruto);
  return { ...data, empresa_id };
}

const leadsService: CrudService = {
  list: (tabela) => api.crmList(tabela),
  create: (tabela, data) => api.crmCreate(tabela, normalizarPayloadLead(data)),
  update: (tabela, id, data) => api.crmUpdate(tabela, id, normalizarPayloadLead(data)),
  delete: (tabela, id) => api.crmDelete(tabela, id),
};

const leadsFieldsBase: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "email", label: "E-mail" },
  { key: "telefone", label: "Telefone" },
  { key: "origem", label: "Origem" },
  { key: "funil_etapa", label: "Etapa do funil", type: "select", options: ETAPAS_FUNIL.map(e => ({ label: e.replace(/_/g, " "), value: e })) },
  { key: "valor_potencial", label: "Valor potencial (R$)", type: "number", step: "0.01" },
  { key: "status", label: "Status", type: "select", options: Object.keys(STATUS_CORES).map(s => ({ label: s, value: s })) },
  { key: "observacoes", label: "Observações" },
];

export default function Page() {
  const [empresas, setEmpresas] = useState<{ id: number; nome: string }[]>([]);

  useEffect(() => {
    api.crmList("empresas")
      .then(res => setEmpresas((res.data || []) as { id: number; nome: string }[]))
      .catch(() => {});
  }, []);

  const empresaOptions = useMemo(
    () => empresas.map(e => ({ label: e.nome, value: String(e.id) })),
    [empresas]
  );
  const empresaNomePorId = useMemo(
    () => Object.fromEntries(empresas.map(e => [String(e.id), e.nome])),
    [empresas]
  );

  const leadsFields = useMemo<FieldDef[]>(() => [
    leadsFieldsBase[0],
    { key: "empresa_id", label: "Empresa", type: "select", options: empresaOptions },
    ...leadsFieldsBase.slice(1),
  ], [empresaOptions]);

  const leadsCols = useMemo<Column[]>(() => [
    { key: "id", label: "ID" },
    { key: "nome", label: "Nome" },
    { key: "empresa_id", label: "Empresa", render: (v) => (v ? empresaNomePorId[String(v)] || `#${v}` : "—") },
    { key: "email", label: "E-mail" },
    { key: "telefone", label: "Telefone" },
    { key: "origem", label: "Origem" },
    { key: "funil_etapa", label: "Etapa do funil" },
    { key: "valor_potencial", label: "Valor potencial", render: (v) => fmtBRL(Number(v) || 0) },
    { key: "status", label: "Status", render: (v) => {
      const s = String(v ?? "novo");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_CORES[s] || "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    }},
  ], [empresaNomePorId]);

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Leads</h1>
        <p className="text-xs text-neutral-500 mt-1">Capte e gerencie novos leads</p>
      </div>
      <CrudPanel tabela="leads" columns={leadsCols} formFields={leadsFields} service={leadsService} permissionPrefix="crm" />
    </div>
  );
}
