"use client";

import { useState } from "react";
import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import CompetenciasModal from "./CompetenciasModal";
import Icon from "../../_components/Icon";
import { fmtDataBR } from "@/lib/format";
import { rhService, fkRhService } from "./rhService";

const STATUS_COR: Record<string, string> = {
  pendente: "bg-amber-500/20 text-amber-400",
  em_andamento: "bg-indigo-500/20 text-indigo-400",
  concluida: "bg-emerald-500/20 text-emerald-400",
};

const avaliacoesCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "funcionario_id", label: "Funcionário ID" },
  { key: "periodo", label: "Período" },
  { key: "tipo", label: "Tipo" },
  { key: "nota_geral", label: "Nota Geral" },
  { key: "avaliador_nome", label: "Avaliador" },
  { key: "data_avaliacao", label: "Data", render: (v) => v ? fmtDataBR(v) : "—" },
  {
    key: "status", label: "Status",
    filterOptions: [
      { label: "Pendente", value: "pendente" }, { label: "Em Andamento", value: "em_andamento" }, { label: "Concluída", value: "concluida" },
    ],
    render: (v) => {
      const s = String(v ?? "—");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_COR[s] ?? "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    },
  },
];

const avaliacoesFields: FieldDef[] = [
  { key: "funcionario_id", label: "Funcionário", type: "fk", fkTabela: "funcionarios", fkService: fkRhService, wide: true, required: true },
  { key: "avaliador_nome", label: "Avaliador" },
  { key: "periodo", label: "Período (ex: 2026-S1)", required: true },
  {
    key: "tipo", label: "Tipo", type: "select", options: [
      { label: "Desempenho", value: "desempenho" }, { label: "Autoavaliação", value: "autoavaliacao" }, { label: "360°", value: "360" },
    ],
  },
  { key: "nota_geral", label: "Nota Geral (0-10)", type: "number", step: "0.1", min: 0, max: 10 },
  { key: "data_avaliacao", label: "Data da Avaliação", type: "date" },
  {
    key: "status", label: "Status", type: "select", options: [
      { label: "Pendente", value: "pendente" }, { label: "Em Andamento", value: "em_andamento" }, { label: "Concluída", value: "concluida" },
    ],
  },
  { key: "pontos_fortes", label: "Pontos Fortes", wide: true },
  { key: "pontos_melhoria", label: "Pontos de Melhoria", wide: true },
  { key: "plano_acao", label: "Plano de Ação (PDI)", wide: true },
];

export default function AvaliacoesTab() {
  const [competenciasDe, setCompetenciasDe] = useState<{ id: number; funcionario?: string } | null>(null);

  return (
    <>
      <CrudPanel
        tabela="avaliacoes"
        columns={avaliacoesCols}
        formFields={avaliacoesFields}
        title="Avaliações de Desempenho"
        permissionPrefix="rh"
        service={rhService}
        rowActions={(row) => (
          <button
            onClick={() => setCompetenciasDe({ id: Number(row.id) })}
            title="Competências avaliadas"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-400"
          >
            <Icon name="bi" size={13} />
          </button>
        )}
      />
      {competenciasDe && (
        <CompetenciasModal avaliacaoId={competenciasDe.id} funcionarioNome={competenciasDe.funcionario} onClose={() => setCompetenciasDe(null)} />
      )}
    </>
  );
}
