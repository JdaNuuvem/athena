"use client";

import SidebarLayout from "./SidebarLayout";
import CrudPanel, { type Column, type FieldDef } from "./CrudPanel";

const empresasCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "razao_social", label: "Razão Social" },
  { key: "cnpj", label: "CNPJ" },
  { key: "tipo", label: "Tipo" },
  { key: "regime_tributario", label: "Regime" },
  { key: "porte", label: "Porte" },
  { key: "status", label: "Status", render: (v) => {
    const s = String(v ?? "—");
    return <span className={`px-2 py-0.5 rounded text-[10px] ${s === "ativa" ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
  }},
];

const empresasFields: FieldDef[] = [
  { key: "razao_social", label: "Razão Social" },
  { key: "cnpj", label: "CNPJ" },
  { key: "ie", label: "IE" },
  { key: "im", label: "IM" },
  { key: "regime_tributario", label: "Regime Tributário" },
  { key: "porte", label: "Porte" },
  { key: "tipo", label: "Tipo", type: "select", options: [{ label: "Matriz", value: "matriz" }, { label: "Filial", value: "filial" }] },
  { key: "endereco", label: "Endereço" },
  { key: "telefone", label: "Telefone" },
  { key: "email", label: "Email" },
  { key: "status", label: "Status", type: "select", options: [{ label: "Ativa", value: "ativa" }, { label: "Inativa", value: "inativa" }] },
];

const multiempresaCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "empresa_id", label: "Empresa ID" },
  { key: "tipo_vinculo", label: "Tipo Vínculo" },
];

const multiempresaFields: FieldDef[] = [
  { key: "empresa_id", label: "Empresa ID", type: "number" },
  { key: "tipo_vinculo", label: "Tipo Vínculo" },
];

export default function EmpresasTab() {
  return (
    <SidebarLayout
      subItems={[
        { key: "lista", label: "Lista" },
        { key: "multiempresa", label: "Multiempresa" },
      ]}
      renderContent={(key) => {
        switch (key) {
          case "lista": return <CrudPanel tabela="empresas" columns={empresasCols} formFields={empresasFields} title="Empresas" />;
          case "multiempresa": return <CrudPanel tabela="multiempresa" columns={multiempresaCols} formFields={multiempresaFields} title="Vínculos Multiempresa" />;
          default: return null;
        }
      }}
    />
  );
}
