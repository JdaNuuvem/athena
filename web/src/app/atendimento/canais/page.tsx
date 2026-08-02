"use client";

import CrudPanel, { type Column, type FieldDef, type CrudService } from "../../_components/CrudPanel";
import { api } from "@/lib/api";

// "ativo" e' um select boolean-like (CrudPanel so' manda string pra select);
// "token" e' write-only — o backend nunca devolve o valor salvo (credencial
// de integracao externa), entao um form de edicao sempre abre com o campo
// vazio. Se mandassemos "" direto, toda edicao (mesmo so' trocar o nome)
// apagaria o token ja configurado. So' inclui a chave no payload se o
// usuario de fato digitou algo novo.
function normalizarPayloadCanal(data: Record<string, unknown>) {
  const payload: Record<string, unknown> = { ...data, ativo: data.ativo === "true" };
  if (payload.token === "") delete payload.token;
  return payload;
}

const canaisService: CrudService = {
  list: (tabela) => api.atendList(tabela),
  create: (tabela, data) => api.atendCreate(tabela, normalizarPayloadCanal(data)),
  update: (tabela, id, data) => api.atendUpdate(tabela, id, normalizarPayloadCanal(data)),
  delete: (tabela, id) => api.atendDelete(tabela, id),
};

const canaisCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "url_webhook", label: "Webhook" },
  { key: "ativo", label: "Status", render: (v) => (
    <span className={`px-2 py-0.5 rounded text-[10px] ${v ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400"}`}>
      {v ? "Ativo" : "Inativo"}
    </span>
  ) },
];

const canaisFields: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "url_webhook", label: "URL do webhook" },
  { key: "token", label: "Token / API key (deixe vazio para não alterar)" },
  { key: "ativo", label: "Status", type: "select", options: [{ label: "Ativo", value: "true" }, { label: "Inativo", value: "false" }] },
];

export default function Page() {
  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Canais</h1>
        <p className="text-xs text-neutral-500 mt-1">Canais de atendimento (WhatsApp, e-mail, chat, redes sociais)</p>
      </div>
      <CrudPanel tabela="canais" columns={canaisCols} formFields={canaisFields} service={canaisService} permissionPrefix="atendimento" />
    </div>
  );
}
