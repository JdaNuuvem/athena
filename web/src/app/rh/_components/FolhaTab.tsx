"use client";

import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import { fmtBRL } from "@/lib/format";
import { rhService, fkRhService } from "./rhService";

const STATUS_COR: Record<string, string> = {
  pendente: "bg-amber-500/20 text-amber-400",
  pago: "bg-emerald-500/20 text-emerald-400",
};

const folhaCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "funcionario_id", label: "Funcionário ID" },
  { key: "mes", label: "Mês" },
  { key: "salario", label: "Salário", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "beneficios", label: "Benefícios", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "descontos", label: "Descontos", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "liquido", label: "Líquido", render: (v) => fmtBRL(Number(v) || 0) },
  {
    key: "status", label: "Status",
    filterOptions: [{ label: "Pendente", value: "pendente" }, { label: "Pago", value: "pago" }],
    render: (v) => {
      const s = String(v ?? "—");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    },
  },
];

const folhaFields: FieldDef[] = [
  { key: "funcionario_id", label: "Funcionário", type: "fk", fkTabela: "funcionarios", fkService: fkRhService, wide: true, required: true },
  { key: "mes", label: "Mês (AAAA-MM)", required: true },
  { key: "salario", label: "Salário", type: "number", step: "0.01" },
  { key: "beneficios", label: "Benefícios", type: "number", step: "0.01" },
  { key: "descontos", label: "Descontos", type: "number", step: "0.01" },
  { key: "liquido", label: "Líquido", type: "number", step: "0.01" },
  { key: "status", label: "Status", type: "select", options: [{ label: "Pendente", value: "pendente" }, { label: "Pago", value: "pago" }] },
];

export default function FolhaTab() {
  return (
    <CrudPanel
      tabela="folha"
      columns={folhaCols}
      formFields={folhaFields}
      title="Folha de Pagamento"
      permissionPrefix="rh"
      service={rhService}
    />
  );
}
