"use client";

import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import { fmtBRL } from "@/lib/format";
import { rhService } from "./rhService";

const beneficiosCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "tipo", label: "Tipo" },
  { key: "valor_empresa", label: "Valor Empresa", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "valor_funcionario", label: "Valor Funcionário", render: (v) => fmtBRL(Number(v) || 0) },
];

const beneficiosFields: FieldDef[] = [
  { key: "nome", label: "Nome", required: true },
  { key: "tipo", label: "Tipo" },
  { key: "valor_empresa", label: "Valor pago pela Empresa", type: "number", step: "0.01" },
  { key: "valor_funcionario", label: "Valor descontado do Funcionário", type: "number", step: "0.01" },
];

export default function BeneficiosTab() {
  return (
    <CrudPanel
      tabela="beneficios"
      columns={beneficiosCols}
      formFields={beneficiosFields}
      title="Benefícios"
      permissionPrefix="rh"
      service={rhService}
    />
  );
}
