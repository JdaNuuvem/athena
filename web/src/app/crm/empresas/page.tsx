"use client";

import CrudPanel, { type Column, type FieldDef, type CrudService } from "../../_components/CrudPanel";
import { api } from "@/lib/api";

const empresasService: CrudService = {
  list: (tabela) => api.crmList(tabela),
  create: (tabela, data) => api.crmCreate(tabela, data),
  update: (tabela, id, data) => api.crmUpdate(tabela, id, data),
  delete: (tabela, id) => api.crmDelete(tabela, id),
};

const empresasCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "cnpj", label: "CNPJ" },
  { key: "segmento", label: "Segmento" },
  { key: "porte", label: "Porte" },
  { key: "telefone", label: "Telefone" },
  { key: "email", label: "E-mail" },
  { key: "website", label: "Website" },
];

const empresasFields: FieldDef[] = [
  { key: "nome", label: "Nome" },
  { key: "cnpj", label: "CNPJ" },
  { key: "segmento", label: "Segmento" },
  { key: "porte", label: "Porte" },
  { key: "telefone", label: "Telefone" },
  { key: "email", label: "E-mail" },
  { key: "website", label: "Website" },
  { key: "endereco", label: "Endereço" },
  { key: "observacoes", label: "Observações" },
];

export default function Page() {
  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Empresas</h1>
        <p className="text-xs text-neutral-500 mt-1">Empresas e organizações do funil de vendas (CRM)</p>
      </div>
      <CrudPanel tabela="empresas" columns={empresasCols} formFields={empresasFields} service={empresasService} permissionPrefix="crm" />
    </div>
  );
}
