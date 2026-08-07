"use client";

import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";

const fornecedoresCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "tipo", label: "Tipo" },
  { key: "documento", label: "Documento" },
  {
    key: "status", label: "Status",
    filterOptions: [{ label: "Ativo", value: "ativo" }, { label: "Inativo", value: "inativo" }],
    render: (v) => {
      const s = String(v ?? "—");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${s === "ativo" ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    },
  },
];

const fornecedoresFields: FieldDef[] = [
  { key: "nome", label: "Nome", required: true },
  { key: "tipo", label: "Tipo", type: "select", options: [{ label: "PJ", value: "PJ" }, { label: "PF", value: "PF" }] },
  { key: "documento", label: "Documento (CPF/CNPJ)", validate: "documento", lookup: "cnpj" },
  { key: "status", label: "Status", type: "select", options: [{ label: "Ativo", value: "ativo" }, { label: "Inativo", value: "inativo" }] },
];

// Fonte única — mesmo cadastro (cad_fornecedores) usado em /cadastros,
// evita ter dois lugares divergentes pra cadastrar fornecedor.
export default function FornecedoresTab() {
  return (
    <CrudPanel
      tabela="fornecedores"
      columns={fornecedoresCols}
      formFields={fornecedoresFields}
      title="Fornecedores"
    />
  );
}
