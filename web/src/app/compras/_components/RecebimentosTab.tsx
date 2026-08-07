"use client";

import { useState } from "react";
import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import Icon from "../../_components/Icon";
import { Can } from "@/lib/auth";
import { api } from "@/lib/api";
import { fmtDataBR } from "@/lib/format";
import { comprasService, fkComprasService } from "./comprasService";

const STATUS_COR: Record<string, string> = {
  pendente: "bg-amber-500/20 text-amber-400",
  confirmado: "bg-emerald-500/20 text-emerald-400",
  divergente: "bg-red-500/20 text-red-400",
};

function StatusBadge({ status }: { status: unknown }) {
  const s = String(status ?? "—");
  return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
}

const recebimentosCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "pedido_id", label: "Pedido ID" },
  { key: "data_recebimento", label: "Data", render: (v) => v ? fmtDataBR(v) : "—" },
  { key: "conferido_por", label: "Conferido por" },
  {
    key: "status", label: "Status", render: (v) => <StatusBadge status={v} />,
    filterOptions: [
      { label: "Pendente", value: "pendente" }, { label: "Confirmado", value: "confirmado" }, { label: "Divergente", value: "divergente" },
    ],
  },
];

const recebimentosFields: FieldDef[] = [
  { key: "pedido_id", label: "Pedido", type: "fk", fkTabela: "pedidos", fkLabelField: "numero", fkService: fkComprasService, wide: true, required: true },
  { key: "data_recebimento", label: "Data de Recebimento", type: "date" },
  { key: "conferido_por", label: "Conferido por" },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Pendente", value: "pendente" }, { label: "Confirmado", value: "confirmado" }, { label: "Divergente", value: "divergente" },
    ],
  },
  { key: "divergencias", label: "Divergências", wide: true },
  { key: "observacoes", label: "Observações", wide: true },
];

export default function RecebimentosTab() {
  const [reloadKey, setReloadKey] = useState(0);

  const handleConfirmar = async (id: number) => {
    try { await api.comprasConfirmarRecebimento(id); setReloadKey(k => k + 1); }
    catch (e) { alert(String(e)); }
  };

  return (
    <CrudPanel
      tabela="recebimentos"
      columns={recebimentosCols}
      formFields={recebimentosFields}
      title="Recebimentos"
      permissionPrefix="compras"
      service={comprasService}
      reloadKey={reloadKey}
      rowActions={(row) => row.status !== "confirmado" ? (
        <Can permission="compras.editar">
          <button
            onClick={() => handleConfirmar(Number(row.id))}
            title="Confirmar recebimento"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-emerald-500/10 hover:text-emerald-400"
          >
            <Icon name="check" size={13} />
          </button>
        </Can>
      ) : null}
    />
  );
}
