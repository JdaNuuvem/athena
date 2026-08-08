"use client";

import CrudPanel, { type Column, type FieldDef } from "../../_components/CrudPanel";
import { fmtDataBR } from "@/lib/format";
import { rhService, fkRhService } from "./rhService";

const pontoCols: Column[] = [
  { key: "id", label: "ID" },
  { key: "funcionario_id", label: "Funcionário ID" },
  { key: "data", label: "Data", render: (v) => v ? fmtDataBR(v) : "—" },
  { key: "entrada", label: "Entrada" },
  { key: "saida_almoco", label: "Saída Almoço" },
  { key: "volta_almoco", label: "Volta Almoço" },
  { key: "saida", label: "Saída" },
];

const pontoFields: FieldDef[] = [
  { key: "funcionario_id", label: "Funcionário", type: "fk", fkTabela: "funcionarios", fkService: fkRhService, wide: true, required: true },
  { key: "data", label: "Data", type: "date", required: true },
  { key: "entrada", label: "Entrada (HH:MM)" },
  { key: "saida_almoco", label: "Saída Almoço (HH:MM)" },
  { key: "volta_almoco", label: "Volta Almoço (HH:MM)" },
  { key: "saida", label: "Saída (HH:MM)" },
];

export default function PontoTab() {
  return (
    <CrudPanel
      tabela="ponto"
      columns={pontoCols}
      formFields={pontoFields}
      title="Ponto Eletrônico"
      permissionPrefix="rh"
      service={rhService}
    />
  );
}
