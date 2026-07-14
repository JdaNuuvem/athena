"use client";

import SidebarLayout from "./SidebarLayout";
import CrudPanel, { type Column, type FieldDef } from "./CrudPanel";
import { fmtBRL } from "@/lib/format";

const transpCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "cnpj", label: "CNPJ" },
  { key: "frota", label: "Frota" },
  { key: "regiao", label: "Região" },
  { key: "status", label: "Status", render: (v) => {
    const s = String(v ?? "—");
    return <span className={`px-2 py-0.5 rounded text-[10px] ${s === "ativa" ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
  }},
];

const transpFields: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "cnpj", label: "CNPJ" },
  { key: "frota", label: "Frota" },
  { key: "regiao", label: "Região" },
  { key: "status", label: "Status", type: "select", options: [{ label: "Ativa", value: "ativa" }, { label: "Inativa", value: "inativa" }] },
];

const freteCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "transportadora_id", label: "Transp. ID" },
  { key: "origem", label: "Origem" },
  { key: "destino", label: "Destino" },
  { key: "valor", label: "Valor", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "prazo", label: "Prazo" },
];

const freteFields: FieldDef[] = [
  { key: "transportadora_id", label: "Transportadora ID", type: "number" },
  { key: "origem", label: "Origem" },
  { key: "destino", label: "Destino" },
  { key: "valor", label: "Valor", type: "number", step: "0.01" },
  { key: "prazo", label: "Prazo" },
];

const contatoCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "transportadora_id", label: "Transp. ID" },
  { key: "nome", label: "Nome" },
  { key: "telefone", label: "Telefone" },
  { key: "email", label: "Email" },
];

const contatoFields: FieldDef[] = [
  { key: "transportadora_id", label: "Transportadora ID", type: "number" },
  { key: "nome", label: "Nome" },
  { key: "telefone", label: "Telefone" },
  { key: "email", label: "Email" },
];

export default function TransportadorasTab() {
  return (
    <SidebarLayout
      subItems={[
        { key: "lista", label: "Lista" },
        { key: "frete", label: "Frete" },
        { key: "contatos", label: "Contatos" },
      ]}
      renderContent={(key) => {
        switch (key) {
          case "lista": return <CrudPanel tabela="transportadoras" columns={transpCols} formFields={transpFields} title="Transportadoras" />;
          case "frete": return <CrudPanel tabela="transp_frete" columns={freteCols} formFields={freteFields} title="Rotas de Frete" />;
          case "contatos": return <CrudPanel tabela="transp_contatos" columns={contatoCols} formFields={contatoFields} title="Contatos" />;
          default: return null;
        }
      }}
    />
  );
}
