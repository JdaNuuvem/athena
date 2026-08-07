"use client";

import { useState } from "react";
import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import ItensPedidoModal from "../../_components/ItensPedidoModal";
import Icon from "../../_components/Icon";
import { fmtBRL, fmtDataBR } from "@/lib/format";
import { comprasService } from "./comprasService";

const STATUS_COR: Record<string, string> = {
  emitido: "bg-amber-500/20 text-amber-400",
  enviado: "bg-indigo-500/20 text-indigo-400",
  recebido: "bg-emerald-500/20 text-emerald-400",
  cancelado: "bg-red-500/20 text-red-400",
};

function StatusBadge({ status }: { status: unknown }) {
  const s = String(status ?? "—");
  return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
}

const pedidosCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "numero", label: "Número" },
  { key: "fornecedor_id", label: "Fornecedor ID" },
  { key: "valor_total", label: "Valor Total", render: (v) => fmtBRL(Number(v) || 0) },
  {
    key: "status", label: "Status", render: (v) => <StatusBadge status={v} />,
    filterOptions: [
      { label: "Emitido", value: "emitido" }, { label: "Enviado", value: "enviado" },
      { label: "Recebido", value: "recebido" }, { label: "Cancelado", value: "cancelado" },
    ],
  },
  { key: "data_emissao", label: "Emissão", render: (v) => v ? fmtDataBR(v) : "—" },
  { key: "data_entrega_prevista", label: "Entrega Prevista", render: (v) => v ? fmtDataBR(v) : "—" },
];

const pedidosFields: FieldDef[] = [
  { key: "numero", label: "Número", required: true },
  { key: "fornecedor_id", label: "Fornecedor", type: "fk", fkTabela: "fornecedores", wide: true },
  { key: "valor_total", label: "Valor Total", type: "number", step: "0.01" },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Emitido", value: "emitido" }, { label: "Enviado", value: "enviado" },
      { label: "Recebido", value: "recebido" }, { label: "Cancelado", value: "cancelado" },
    ],
  },
  { key: "data_emissao", label: "Data Emissão", type: "date" },
  { key: "data_entrega_prevista", label: "Entrega Prevista", type: "date" },
  { key: "observacoes", label: "Observações", wide: true },
];

export default function PedidosTab() {
  const [itensDe, setItensDe] = useState<{ id: number; numero?: string } | null>(null);

  return (
    <>
      <CrudPanel
        tabela="pedidos"
        columns={pedidosCols}
        formFields={pedidosFields}
        title="Pedidos de Compra"
        permissionPrefix="compras"
        service={comprasService}
        rowActions={(row) => (
          <button
            onClick={() => setItensDe({ id: Number(row.id), numero: row.numero ? String(row.numero) : undefined })}
            title="Itens do pedido"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-400"
          >
            <Icon name="inbox" size={13} />
          </button>
        )}
      />
      {itensDe && (
        <ItensPedidoModal pedidoId={itensDe.id} pedidoNumero={itensDe.numero} onClose={() => setItensDe(null)} />
      )}
    </>
  );
}
