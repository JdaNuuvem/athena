"use client";

import { useState, useEffect } from "react";
import SidebarLayout from "./SidebarLayout";
import CrudPanel, { type Column, type FieldDef } from "./CrudPanel";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";

const fornCols: Column[] = [
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

const fornFields: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "tipo", label: "Tipo", type: "select", options: [{ label: "PJ", value: "PJ" }, { label: "PF", value: "PF" }] },
  { key: "documento", label: "Documento (CPF/CNPJ)" },
  { key: "ie", label: "IE" },
  { key: "im", label: "IM" },
  { key: "limite_credito", label: "Limite de Crédito", type: "number", step: "0.01" },
  { key: "score", label: "Score", type: "number" },
  { key: "status", label: "Status", type: "select", options: [{ label: "Ativo", value: "ativo" }, { label: "Inativo", value: "inativo" }] },
];

const enderecoCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "fornecedor_id", label: "Fornecedor ID" },
  { key: "logradouro", label: "Logradouro" },
  { key: "cidade", label: "Cidade" },
  { key: "uf", label: "UF" },
];

const enderecoFields: FieldDef[] = [
  { key: "fornecedor_id", label: "Fornecedor ID", type: "number" },
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
  { key: "fornecedor_id", label: "Fornecedor ID" },
  { key: "tipo", label: "Tipo" },
  { key: "valor", label: "Valor" },
  { key: "whatsapp", label: "WhatsApp", render: (v) => v ? <span className="text-emerald-400">Sim</span> : <span className="text-neutral-500">Não</span> },
];

const contatoFields: FieldDef[] = [
  { key: "fornecedor_id", label: "Fornecedor ID", type: "number" },
  { key: "tipo", label: "Tipo", type: "select", options: [{ label: "Telefone", value: "telefone" }, { label: "Email", value: "email" }, { label: "Celular", value: "celular" }] },
  { key: "valor", label: "Valor" },
  { key: "whatsapp", label: "WhatsApp", type: "select", options: [{ label: "Sim", value: "true" }, { label: "Não", value: "false" }] },
];

const histCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "fornecedor_id", label: "Fornecedor ID" },
  { key: "descricao", label: "Descrição" },
  { key: "valor_total", label: "Valor Total", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "created_at", label: "Data", render: (v) => v ? new Date(String(v)).toLocaleDateString("pt-BR") : "—" },
];

const tagCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "fornecedor_id", label: "Fornecedor ID" },
  { key: "tag", label: "Tag" },
];

const tagFields: FieldDef[] = [
  { key: "fornecedor_id", label: "Fornecedor ID", type: "number" },
  { key: "tag", label: "Tag" },
];

const resumoCols: Column[] = [
  { key: "nome", label: "Nome" },
  { key: "tipo", label: "Tipo" },
  { key: "documento", label: "Documento" },
  { key: "limite_credito", label: "Limite", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "score", label: "Score" },
  { key: "total_compras", label: "Total Compras", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "status", label: "Status" },
];

function ResumoPanel() {
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.cadFornecedorResumo().then(r => setData((r.data || []) as Record<string, unknown>[])).catch(() => {}).finally(() => setLoading(false)); }, []);
  if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;
  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left">{resumoCols.map(c => <th key={c.key} className="px-4 py-2 font-medium">{c.label}</th>)}</tr></thead>
        <tbody>{data.map((row, i) => <tr key={i} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">{resumoCols.map(c => <td key={c.key} className="px-4 py-2.5">{c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export default function FornecedoresTab() {
  return (
    <SidebarLayout
      subItems={[
        { key: "lista", label: "Lista" },
        { key: "enderecos", label: "Endereços" },
        { key: "contatos", label: "Contatos" },
        { key: "historico", label: "Histórico" },
        { key: "tags", label: "Tags" },
        { key: "resumo", label: "Resumo" },
      ]}
      renderContent={(key) => {
        switch (key) {
          case "lista": return <CrudPanel tabela="fornecedores" columns={fornCols} formFields={fornFields} title="Fornecedores" />;
          case "enderecos": return <CrudPanel tabela="fornecedor_enderecos" columns={enderecoCols} formFields={enderecoFields} title="Endereços" />;
          case "contatos": return <CrudPanel tabela="fornecedor_contatos" columns={contatoCols} formFields={contatoFields} title="Contatos" />;
          case "historico": return <CrudPanel tabela="fornecedor_historico" columns={histCols} title="Histórico" />;
          case "tags": return <CrudPanel tabela="fornecedor_tags" columns={tagCols} formFields={tagFields} title="Tags" />;
          case "resumo": return <div className="space-y-3"><h3 className="text-sm font-semibold text-neutral-200">Resumo de Compras</h3><ResumoPanel /></div>;
          default: return null;
        }
      }}
    />
  );
}
