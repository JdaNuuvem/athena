"use client";

import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import { fmtBRL, fmtDataBR } from "@/lib/format";
import { comprasService, fkComprasService } from "./comprasService";

const STATUS_COR: Record<string, string> = {
  pendente: "bg-amber-500/20 text-amber-400",
  confirmada: "bg-emerald-500/20 text-emerald-400",
};

function StatusBadge({ status }: { status: unknown }) {
  const s = String(status ?? "—");
  return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
}

const notasCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "pedido_id", label: "Pedido ID" },
  { key: "numero_nf", label: "Número NF" },
  { key: "valor", label: "Valor", render: (v) => fmtBRL(Number(v) || 0) },
  { key: "data_emissao", label: "Emissão", render: (v) => v ? fmtDataBR(v) : "—" },
  {
    key: "status", label: "Status", render: (v) => <StatusBadge status={v} />,
    filterOptions: [{ label: "Pendente", value: "pendente" }, { label: "Confirmada", value: "confirmada" }],
  },
];

const notasFields: FieldDef[] = [
  { key: "pedido_id", label: "Pedido", type: "fk", fkTabela: "pedidos", fkLabelField: "numero", fkService: fkComprasService, wide: true, required: true },
  { key: "numero_nf", label: "Número NF", required: true },
  { key: "chave_acesso", label: "Chave de Acesso", wide: true },
  { key: "valor", label: "Valor", type: "number", step: "0.01" },
  { key: "data_emissao", label: "Data de Emissão", type: "date" },
  { key: "data_recebimento", label: "Data de Recebimento", type: "date" },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Pendente", value: "pendente" }, { label: "Confirmada", value: "confirmada" },
    ],
  },
];

export default function NotasTab() {
  return (
    <CrudPanel
      tabela="notas_entrada"
      columns={notasCols}
      formFields={notasFields}
      title="Notas de Entrada"
      permissionPrefix="compras"
      service={comprasService}
    />
  );
}
