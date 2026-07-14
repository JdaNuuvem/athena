"use client";

import { useState, useEffect } from "react";
import SidebarLayout from "./SidebarLayout";
import CrudPanel, { type Column, type FieldDef } from "./CrudPanel";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";

const vendCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "email", label: "Email" },
  { key: "regiao", label: "Região" },
  { key: "comissao_pct", label: "Comissão %", render: (v) => `${Number(v || 0).toFixed(1)}%` },
];

const vendFields: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "email", label: "Email" },
  { key: "regiao", label: "Região" },
  { key: "comissao_pct", label: "Comissão (%)", type: "number", step: "0.1" },
];

const metaCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "vendedor_id", label: "Vendedor ID" },
  { key: "nome", label: "Vendedor" },
  { key: "mes", label: "Mês" },
  { key: "meta_valor", label: "Meta", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "realizado", label: "Realizado", render: (v) => fmtBRL(Number(v) || 0) },
];

function MetasPanel() {
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.cadVendedorMetas().then(r => setData((r.data || []) as Record<string, unknown>[])).catch(() => {}).finally(() => setLoading(false)); }, []);
  if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;
  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left">{metaCols.map(c => <th key={c.key} className="px-4 py-2 font-medium">{c.label}</th>)}</tr></thead>
        <tbody>{data.map((row, i) => <tr key={i} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">{metaCols.map(c => <td key={c.key} className="px-4 py-2.5">{c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

const comissaoCols: Column[] = [
  { key: "nome", label: "Vendedor" },
  { key: "regiao", label: "Região" },
  { key: "comissao_pct", label: "Comissão %", render: (v) => `${Number(v || 0).toFixed(1)}%` },
  { key: "total_vendas", label: "Total Vendas", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "meta_valor", label: "Meta", render: (v) => fmtBRL(Number(v) || 0) },
];

function ComissaoPanel() {
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.cadVendedorComissao().then(r => {
      setData((r.vendedores || []) as Record<string, unknown>[]);
      setTotal(r.total_comissoes || 0);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-2">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
          <p className="text-[10px] text-neutral-500">Total Comissões (Mês Atual)</p>
          <p className="text-sm font-semibold text-indigo-400 mt-0.5">{fmtBRL(total)}</p>
        </div>
      </div>
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left">{comissaoCols.map(c => <th key={c.key} className="px-4 py-2 font-medium">{c.label}</th>)}</tr></thead>
          <tbody>{data.map((row, i) => <tr key={i} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">{comissaoCols.map(c => <td key={c.key} className="px-4 py-2.5">{c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

export default function VendedoresTab() {
  return (
    <SidebarLayout
      subItems={[
        { key: "lista", label: "Lista" },
        { key: "metas", label: "Metas" },
        { key: "comissao", label: "Comissão" },
      ]}
      renderContent={(key) => {
        switch (key) {
          case "lista": return <CrudPanel tabela="vendedores" columns={vendCols} formFields={vendFields} title="Vendedores" />;
          case "metas": return <div className="space-y-3"><h3 className="text-sm font-semibold text-neutral-200">Metas Mensais</h3><MetasPanel /></div>;
          case "comissao": return <div className="space-y-3"><h3 className="text-sm font-semibold text-neutral-200">Resumo de Comissões</h3><ComissaoPanel /></div>;
          default: return null;
        }
      }}
    />
  );
}
