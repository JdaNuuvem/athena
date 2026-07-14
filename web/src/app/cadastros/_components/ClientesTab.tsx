"use client";

import SidebarLayout from "./SidebarLayout";
import CrudPanel, { type Column, type FieldDef } from "./CrudPanel";
import { fmtBRL } from "@/lib/format";

const clientesCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "tipo", label: "Tipo" },
  { key: "documento", label: "Documento" },
  { key: "limite_credito", label: "Limite", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "score", label: "Score" },
  { key: "status", label: "Status", render: (v) => {
    const s = String(v ?? "—");
    return <span className={`px-2 py-0.5 rounded text-[10px] ${s === "ativo" ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
  }},
];

const clientesFields: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "tipo", label: "Tipo", type: "select", options: [{ label: "Pessoa Física (PF)", value: "PF" }, { label: "Pessoa Jurídica (PJ)", value: "PJ" }] },
  { key: "documento", label: "Documento (CPF/CNPJ)" },
  { key: "ie", label: "IE" },
  { key: "im", label: "IM" },
  { key: "limite_credito", label: "Limite de Crédito", type: "number", step: "0.01" },
  { key: "score", label: "Score", type: "number" },
  { key: "status", label: "Status", type: "select", options: [{ label: "Ativo", value: "ativo" }, { label: "Inativo", value: "inativo" }] },
];

const enderecoCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "cliente_id", label: "Cliente ID" },
  { key: "logradouro", label: "Logradouro" },
  { key: "numero", label: "Número" },
  { key: "bairro", label: "Bairro" },
  { key: "cidade", label: "Cidade" },
  { key: "uf", label: "UF" },
];

const enderecoFields: FieldDef[] = [
  { key: "cliente_id", label: "Cliente ID", type: "number" },
  { key: "logradouro", label: "Logradouro" },
  { key: "numero", label: "Número" },
  { key: "complemento", label: "Complemento" },
  { key: "bairro", label: "Bairro" },
  { key: "cidade", label: "Cidade" },
  { key: "uf", label: "UF" },
  { key: "cep", label: "CEP" },
];

const contatoCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "cliente_id", label: "Cliente ID" },
  { key: "tipo", label: "Tipo" },
  { key: "valor", label: "Valor" },
  { key: "whatsapp", label: "WhatsApp", render: (v) => v ? <span className="text-emerald-400">Sim</span> : <span className="text-neutral-500">Não</span> },
];

const contatoFields: FieldDef[] = [
  { key: "cliente_id", label: "Cliente ID", type: "number" },
  { key: "tipo", label: "Tipo", type: "select", options: [{ label: "Telefone", value: "telefone" }, { label: "Email", value: "email" }, { label: "Celular", value: "celular" }] },
  { key: "valor", label: "Valor" },
  { key: "whatsapp", label: "WhatsApp", type: "select", options: [{ label: "Sim", value: "true" }, { label: "Não", value: "false" }] },
];

const histCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "cliente_id", label: "Cliente ID" },
  { key: "descricao", label: "Descrição" },
  { key: "created_at", label: "Data", render: (v) => v ? new Date(String(v)).toLocaleDateString("pt-BR") : "—" },
];

const tagCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "cliente_id", label: "Cliente ID" },
  { key: "tag", label: "Tag" },
];

const tagFields: FieldDef[] = [
  { key: "cliente_id", label: "Cliente ID", type: "number" },
  { key: "tag", label: "Tag" },
];

export default function ClientesTab() {
  return (
    <SidebarLayout
      subItems={[
        { key: "lista", label: "Lista" },
        { key: "enderecos", label: "Endereços" },
        { key: "contatos", label: "Contatos" },
        { key: "historico", label: "Histórico" },
        { key: "tags", label: "Tags" },
      ]}
      renderContent={(key) => {
        switch (key) {
          case "lista": return <CrudPanel tabela="clientes" columns={clientesCols} formFields={clientesFields} title="Clientes" />;
          case "enderecos": return <CrudPanel tabela="cliente_enderecos" columns={enderecoCols} formFields={enderecoFields} title="Endereços" />;
          case "contatos": return <CrudPanel tabela="cliente_contatos" columns={contatoCols} formFields={contatoFields} title="Contatos" />;
          case "historico": return <CrudPanel tabela="cliente_historico" columns={histCols} title="Histórico" />;
          case "tags": return <CrudPanel tabela="cliente_tags" columns={tagCols} formFields={tagFields} title="Tags" />;
          default: return null;
        }
      }}
    />
  );
}
