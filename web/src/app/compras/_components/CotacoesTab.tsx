"use client";

import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import { fmtBRL } from "@/lib/format";
import { comprasService, fkComprasService } from "./comprasService";

const cotacoesCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "solicitacao_id", label: "Solicitação ID" },
  { key: "fornecedor_id", label: "Fornecedor ID" },
  { key: "valor_unitario", label: "Valor Unit.", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "valor_frete", label: "Frete", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "prazo_entrega", label: "Prazo (dias)" },
  {
    key: "status", label: "Status",
    filterOptions: [
      { label: "Enviada", value: "enviada" }, { label: "Recebida", value: "recebida" },
      { label: "Aprovada", value: "aprovada" }, { label: "Recusada", value: "recusada" },
    ],
  },
];

const cotacoesFields: FieldDef[] = [
  { key: "solicitacao_id", label: "Solicitação", type: "fk", fkTabela: "solicitacoes", fkLabelField: "descricao", fkService: fkComprasService, wide: true },
  { key: "fornecedor_id", label: "Fornecedor", type: "fk", fkTabela: "fornecedores", wide: true },
  { key: "valor_unitario", label: "Valor Unitário", type: "number", step: "0.01" },
  { key: "valor_frete", label: "Valor Frete", type: "number", step: "0.01" },
  { key: "prazo_entrega", label: "Prazo de Entrega (dias)", type: "number" },
  { key: "condicoes", label: "Condições", wide: true },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Enviada", value: "enviada" }, { label: "Recebida", value: "recebida" },
      { label: "Aprovada", value: "aprovada" }, { label: "Recusada", value: "recusada" },
    ],
  },
];

export default function CotacoesTab() {
  return (
    <CrudPanel
      tabela="cotacoes"
      columns={cotacoesCols}
      formFields={cotacoesFields}
      title="Cotações"
      permissionPrefix="compras"
      service={comprasService}
    />
  );
}
