"use client";

import { useState, useEffect } from "react";
import SidebarLayout from "./SidebarLayout";
import CrudPanel, { type Column, type FieldDef } from "./CrudPanel";
import { api } from "@/lib/api";

const usuariosCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "email", label: "Email" },
  { key: "perfil", label: "Perfil" },
  { key: "mfa_ativo", label: "MFA", render: (v) => v ? <span className="text-emerald-400">Sim</span> : <span className="text-neutral-500">Não</span> },
  { key: "status", label: "Status", render: (v) => {
    const s = String(v ?? "—");
    return <span className={`px-2 py-0.5 rounded text-[10px] ${s === "ativo" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>{s}</span>;
  }},
];

const usuariosFields: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "email", label: "Email" },
  { key: "perfil", label: "Perfil", type: "select", options: [
    { label: "Administrador", value: "Administrador" }, { label: "Gestor", value: "Gestor" },
    { label: "Vendedor", value: "Vendedor" }, { label: "RH", value: "RH" }, { label: "Usuário", value: "usuario" },
  ]},
  { key: "grupo_id", label: "Grupo ID", type: "number" },
  { key: "mfa_ativo", label: "MFA Ativo", type: "select", options: [{ label: "Sim", value: "true" }, { label: "Não", value: "false" }] },
  { key: "status", label: "Status", type: "select", options: [{ label: "Ativo", value: "ativo" }, { label: "Inativo", value: "inativo" }] },
];

const permCols: Column[] = [
  { key: "perfil", label: "Perfil" },
  { key: "modulo", label: "Módulo" },
  { key: "acesso", label: "Acesso", render: (v) => {
    const s = String(v ?? "—");
    const c = s === "total" ? "bg-indigo-500/20 text-indigo-400" : "bg-amber-500/20 text-amber-400";
    return <span className={`px-2 py-0.5 rounded text-[10px] ${c}`}>{s}</span>;
  }},
];

function PermissoesPanel() {
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api.cadPermissoes().then(r => setData((r.data || []) as Record<string, unknown>[])).catch(() => {}).finally(() => setLoading(false)); }, []);
  if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;
  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left">{permCols.map(c => <th key={c.key} className="px-4 py-2 font-medium">{c.label}</th>)}</tr></thead>
        <tbody>{data.map((row, i) => <tr key={i} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">{permCols.map(c => <td key={c.key} className="px-4 py-2.5">{c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

const gruposCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "perfil_padrao", label: "Perfil Padrão" },
];

const gruposFields: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "perfil_padrao", label: "Perfil Padrão", type: "select", options: [
    { label: "Administrador", value: "Administrador" }, { label: "Gestor", value: "Gestor" },
    { label: "Vendedor", value: "Vendedor" }, { label: "RH", value: "RH" }, { label: "Usuário", value: "usuario" },
  ]},
];

const histCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "usuario_id", label: "Usuário ID" },
  { key: "acao", label: "Ação" },
  { key: "ip", label: "IP" },
  { key: "created_at", label: "Data", render: (v) => v ? new Date(String(v)).toLocaleDateString("pt-BR") : "—" },
];

export default function UsuariosTab() {
  return (
    <SidebarLayout
      subItems={[
        { key: "lista", label: "Lista" },
        { key: "permissoes", label: "Permissões" },
        { key: "grupos", label: "Grupos" },
        { key: "historico", label: "Histórico" },
      ]}
      renderContent={(key) => {
        switch (key) {
          case "lista": return <CrudPanel tabela="usuarios" columns={usuariosCols} formFields={usuariosFields} title="Usuários" />;
          case "permissoes": return <div className="space-y-3"><h3 className="text-sm font-semibold text-neutral-200">Permissões por Perfil</h3><PermissoesPanel /></div>;
          case "grupos": return <CrudPanel tabela="grupos" columns={gruposCols} formFields={gruposFields} title="Grupos" />;
          case "historico": return <CrudPanel tabela="historico_acessos" columns={histCols} title="Histórico de Acessos" />;
          default: return null;
        }
      }}
    />
  );
}
