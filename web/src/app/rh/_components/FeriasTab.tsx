"use client";

import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import { fmtDataBR } from "@/lib/format";
import { rhService, fkRhService } from "./rhService";

const STATUS_COR: Record<string, string> = {
  agendada: "bg-amber-500/20 text-amber-400",
  andamento: "bg-indigo-500/20 text-indigo-400",
  concluida: "bg-emerald-500/20 text-emerald-400",
};

const feriasCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "funcionario_id", label: "Funcionário ID" },
  { key: "periodo_aquisitivo", label: "Período Aquisitivo" },
  { key: "dias", label: "Dias" },
  { key: "inicio", label: "Início", render: (v) => v ? fmtDataBR(v) : "—" },
  { key: "fim", label: "Fim", render: (v) => v ? fmtDataBR(v) : "—" },
  {
    key: "status", label: "Status",
    filterOptions: [
      { label: "Agendada", value: "agendada" }, { label: "Em Andamento", value: "andamento" }, { label: "Concluída", value: "concluida" },
    ],
    render: (v) => {
      const s = String(v ?? "—");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    },
  },
];

const feriasFields: FieldDef[] = [
  { key: "funcionario_id", label: "Funcionário", type: "fk", fkTabela: "funcionarios", fkService: fkRhService, wide: true, required: true },
  { key: "periodo_aquisitivo", label: "Período Aquisitivo (ex: 2025-2026)" },
  { key: "dias", label: "Dias", type: "number" },
  { key: "inicio", label: "Início", type: "date", required: true },
  { key: "fim", label: "Fim", type: "date", required: true },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Agendada", value: "agendada" }, { label: "Em Andamento", value: "andamento" }, { label: "Concluída", value: "concluida" },
    ],
  },
];

export default function FeriasTab() {
  return (
    <CrudPanel
      tabela="ferias"
      columns={feriasCols}
      formFields={feriasFields}
      title="Férias"
      permissionPrefix="rh"
      service={rhService}
    />
  );
}
