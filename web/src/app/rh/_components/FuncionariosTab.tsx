"use client";

import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import { fmtDataBR } from "@/lib/format";
import { rhService } from "./rhService";

const STATUS_COR: Record<string, string> = {
  ativo: "bg-emerald-500/20 text-emerald-400",
  ferias: "bg-amber-500/20 text-amber-400",
  afastado: "bg-red-500/20 text-red-400",
  desligado: "bg-neutral-500/20 text-neutral-400",
};

const funcionariosCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "cargo", label: "Cargo" },
  { key: "departamento", label: "Departamento" },
  { key: "email", label: "Email" },
  { key: "data_admissao", label: "Admissão", render: (v) => v ? fmtDataBR(v) : "—" },
  {
    key: "status", label: "Status",
    filterOptions: [
      { label: "Ativo", value: "ativo" }, { label: "Férias", value: "ferias" },
      { label: "Afastado", value: "afastado" }, { label: "Desligado", value: "desligado" },
    ],
    render: (v) => {
      const s = String(v ?? "—");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    },
  },
];

const funcionariosFields: FieldDef[] = [
  { key: "nome", label: "Nome", required: true },
  { key: "cargo", label: "Cargo" },
  { key: "departamento", label: "Departamento" },
  { key: "email", label: "Email", validate: "email" },
  { key: "telefone", label: "Telefone" },
  { key: "data_admissao", label: "Data de Admissão", type: "date" },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Ativo", value: "ativo" }, { label: "Férias", value: "ferias" },
      { label: "Afastado", value: "afastado" }, { label: "Desligado", value: "desligado" },
    ],
  },
];

export default function FuncionariosTab() {
  return (
    <CrudPanel
      tabela="funcionarios"
      columns={funcionariosCols}
      formFields={funcionariosFields}
      title="Funcionários"
      permissionPrefix="rh"
      service={rhService}
    />
  );
}
