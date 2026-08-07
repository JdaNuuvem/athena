"use client";

import { useState } from "react";
import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import Icon from "../../_components/Icon";
import { Can } from "@/lib/auth";
import { api } from "@/lib/api";
import { comprasService } from "./comprasService";

const STATUS_COR: Record<string, string> = {
  pendente: "bg-amber-500/20 text-amber-400",
  aprovada: "bg-emerald-500/20 text-emerald-400",
  rejeitada: "bg-red-500/20 text-red-400",
};

function StatusBadge({ status }: { status: unknown }) {
  const s = String(status ?? "—");
  return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
}

const solicitacoesCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "descricao", label: "Descrição" },
  { key: "solicitante", label: "Solicitante" },
  { key: "urgencia", label: "Urgência" },
  {
    key: "status", label: "Status", render: (v) => <StatusBadge status={v} />,
    filterOptions: [
      { label: "Pendente", value: "pendente" }, { label: "Aprovada", value: "aprovada" }, { label: "Rejeitada", value: "rejeitada" },
    ],
  },
];

const solicitacoesFields: FieldDef[] = [
  { key: "descricao", label: "Descrição", required: true, wide: true },
  { key: "solicitante", label: "Solicitante" },
  { key: "departamento", label: "Departamento" },
  {
    key: "urgencia", label: "Urgência", type: "select", options: [
      { label: "Normal", value: "normal" }, { label: "Alta", value: "alta" }, { label: "Urgente", value: "urgente" },
    ],
  },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Pendente", value: "pendente" }, { label: "Aprovada", value: "aprovada" }, { label: "Rejeitada", value: "rejeitada" },
    ],
  },
  { key: "observacoes", label: "Observações", wide: true },
];

export default function SolicitacoesTab() {
  const [reloadKey, setReloadKey] = useState(0);

  const handleAprovar = async (id: number) => {
    try { await api.comprasAprovarSolicitacao(id); setReloadKey(k => k + 1); }
    catch (e) { alert(String(e)); }
  };

  return (
    <CrudPanel
      tabela="solicitacoes"
      columns={solicitacoesCols}
      formFields={solicitacoesFields}
      title="Solicitações de Compra"
      permissionPrefix="compras"
      service={comprasService}
      reloadKey={reloadKey}
      rowActions={(row) => row.status === "pendente" ? (
        <Can permission="compras.aprovar">
          <button
            onClick={() => handleAprovar(Number(row.id))}
            title="Aprovar solicitação"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-emerald-500/10 hover:text-emerald-400"
          >
            <Icon name="check" size={13} />
          </button>
        </Can>
      ) : null}
    />
  );
}
