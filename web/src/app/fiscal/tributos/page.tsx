"use client";

import { useEffect, useState } from "react";
import { fiscalList } from "@/lib/api";
import type { KpiMetric, Column } from "../types";
import { formatCurrency } from "../types";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";

interface TributoRow {
  id: number;
  nome: string;
  sigla: string;
  aliquota: number;
  aliquota_interestadual: number;
  regime: string;
  tipo: string;
  incidencia: string;
  ativo: boolean;
}

const COLUMNS: Column<TributoRow>[] = [
  { key: "sigla", label: "Sigla" },
  { key: "nome", label: "Tributo" },
  { key: "tipo", label: "Esfera", render: (_, row) => <span className="capitalize">{row.tipo}</span> },
  { key: "aliquota", label: "Alíquota", align: "center", render: (_, row) => `${row.aliquota}%` },
  { key: "regime", label: "Regime", render: (_, row) => <span className="capitalize">{row.regime.replace(/_/g, " ")}</span> },
  { key: "incidencia", label: "Incidência", render: (_, row) => <span className="text-[10px] text-neutral-400 max-w-[200px] block truncate">{row.incidencia}</span> },
  { key: "ativo", label: "Ativo", align: "center", render: (_, row) => (
    <StatusBadge label={row.ativo ? "Ativo" : "Inativo"} variant={row.ativo ? "success" : "neutral"} />
  )},
];

export default function TributosPage() {
  const [tributos, setTributos] = useState<TributoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    fiscalList("tributos")
      .then(r => setTributos((r.data || []) as TributoRow[]))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  const ativos = tributos.filter(t => t.ativo);
  const kpis: KpiMetric[] = [
    { label: "Tributos ativos", value: String(ativos.length), color: "text-blue-400" },
    { label: "Federais", value: String(ativos.filter(t => t.tipo === "federal").length), color: "text-amber-400" },
    { label: "Estaduais", value: String(ativos.filter(t => t.tipo === "estadual").length), color: "text-emerald-400" },
    { label: "Municipais", value: String(ativos.filter(t => t.tipo === "municipal").length), color: "text-purple-400" },
  ];

  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Tributos" subtitle="ICMS, IPI, PIS, COFINS, ISS, CSLL e IRPJ" />

      <div className="grid grid-cols-4 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <ErrorAlert message={erro} />
      {loading ? (
        <LoadingState />
      ) : (
        <DataTable<TributoRow>
          columns={COLUMNS}
          data={tributos}
          keyExtractor={item => item.id}
          emptyMessage="Nenhum tributo cadastrado"
          countLabel={`${tributos.length} tributos`}
        />
      )}
    </div>
  );
}
