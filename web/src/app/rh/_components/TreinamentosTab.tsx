"use client";

import { useState } from "react";
import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import ParticipantesModal from "./ParticipantesModal";
import Icon from "../../_components/Icon";
import { fmtDataBR } from "@/lib/format";
import { rhService } from "./rhService";

const STATUS_COR: Record<string, string> = {
  planejado: "bg-amber-500/20 text-amber-400",
  em_andamento: "bg-indigo-500/20 text-indigo-400",
  concluido: "bg-emerald-500/20 text-emerald-400",
  cancelado: "bg-red-500/20 text-red-400",
};

const treinamentosCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "nome", label: "Nome" },
  { key: "categoria", label: "Categoria" },
  { key: "carga_horaria", label: "Carga Horária" },
  { key: "instrutor", label: "Instrutor" },
  { key: "data_inicio", label: "Início", render: (v) => v ? fmtDataBR(v) : "—" },
  {
    key: "status", label: "Status",
    filterOptions: [
      { label: "Planejado", value: "planejado" }, { label: "Em Andamento", value: "em_andamento" },
      { label: "Concluído", value: "concluido" }, { label: "Cancelado", value: "cancelado" },
    ],
    render: (v) => {
      const s = String(v ?? "—");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    },
  },
];

const treinamentosFields: FieldDef[] = [
  { key: "nome", label: "Nome", required: true },
  { key: "descricao", label: "Descrição", wide: true },
  {
    key: "categoria", label: "Categoria", type: "select", options: [
      { label: "Técnico", value: "tecnico" }, { label: "Comportamental", value: "comportamental" },
      { label: "Liderança", value: "lideranca" }, { label: "Compliance", value: "compliance" }, { label: "Outros", value: "outros" },
    ],
  },
  { key: "carga_horaria", label: "Carga Horária (h)", type: "number" },
  { key: "instrutor", label: "Instrutor" },
  { key: "data_inicio", label: "Data de Início", type: "date" },
  { key: "data_fim", label: "Data de Fim", type: "date" },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Planejado", value: "planejado" }, { label: "Em Andamento", value: "em_andamento" },
      { label: "Concluído", value: "concluido" }, { label: "Cancelado", value: "cancelado" },
    ],
  },
];

export default function TreinamentosTab() {
  const [participantesDe, setParticipantesDe] = useState<{ id: number; nome?: string } | null>(null);

  return (
    <>
      <CrudPanel
        tabela="treinamentos"
        columns={treinamentosCols}
        formFields={treinamentosFields}
        title="Treinamentos"
        permissionPrefix="rh"
        service={rhService}
        rowActions={(row) => (
          <button
            onClick={() => setParticipantesDe({ id: Number(row.id), nome: row.nome ? String(row.nome) : undefined })}
            title="Participantes"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-400"
          >
            <Icon name="rh" size={13} />
          </button>
        )}
      />
      {participantesDe && (
        <ParticipantesModal treinamentoId={participantesDe.id} treinamentoNome={participantesDe.nome} onClose={() => setParticipantesDe(null)} />
      )}
    </>
  );
}
