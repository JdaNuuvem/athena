"use client";

import { useState } from "react";
import type { CfopRecord, NcmRecord, CestRecord, IbptRecord, Column, TabOption } from "../types";
import { CFOP_DATA, NCM_DATA, CEST_DATA, IBPT_DATA } from "../data/tabelas";
import PageHeader from "@/app/_components/PageHeader";
import TabBar from "@/app/_components/TabBar";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";

const TABS: TabOption[] = [
  { key: "cfop", label: "CFOP" },
  { key: "ncm", label: "NCM" },
  { key: "cest", label: "CEST" },
  { key: "ibpt", label: "IBPT" },
];

const CFOP_COLUMNS: Column<CfopRecord>[] = [
  { key: "codigo", label: "Código" },
  { key: "descricao", label: "Descrição" },
  { key: "tipo", label: "Tipo", align: "center", render: (_, row) => (
    <StatusBadge label={row.tipo} variant={row.tipo === "Entrada" ? "success" : "warning"} />
  )},
];

const NCM_COLUMNS: Column<NcmRecord>[] = [
  { key: "codigo", label: "Código" },
  { key: "descricao", label: "Descrição" },
  { key: "aliquotaIPI", label: "IPI", align: "center" },
  { key: "aliquotaNacional", label: "Alíquota Nacional", align: "center" },
];

const CEST_COLUMNS: Column<CestRecord>[] = [
  { key: "codigo", label: "Código" },
  { key: "descricao", label: "Descrição" },
  { key: "ncm", label: "NCM Vinculado" },
];

const IBPT_COLUMNS: Column<IbptRecord>[] = [
  { key: "ncm", label: "NCM" },
  { key: "aliquotaFederal", label: "Alíquota Federal", align: "center" },
  { key: "aliquotaEstadual", label: "Alíquota Estadual", align: "center" },
  { key: "aliquotaMunicipal", label: "Alíquota Municipal", align: "center" },
];

export default function TabelasFiscaisPage() {
  const [tab, setTab] = useState("cfop");

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Tabelas Fiscais" subtitle="CFOP, NCM, CEST e IBPT" />
      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {tab === "cfop" && (
        <DataTable<CfopRecord> columns={CFOP_COLUMNS} data={CFOP_DATA} keyExtractor={item => item.codigo} />
      )}
      {tab === "ncm" && (
        <DataTable<NcmRecord> columns={NCM_COLUMNS} data={NCM_DATA} keyExtractor={item => item.codigo} />
      )}
      {tab === "cest" && (
        <DataTable<CestRecord> columns={CEST_COLUMNS} data={CEST_DATA} keyExtractor={item => item.codigo} />
      )}
      {tab === "ibpt" && (
        <DataTable<IbptRecord> columns={IBPT_COLUMNS} data={IBPT_DATA} keyExtractor={item => item.ncm} />
      )}
    </div>
  );
}
