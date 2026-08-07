"use client";

import { useState, useEffect } from "react";
import type { KpiMetric, Column } from "@/lib/types/ui";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { formatCurrency } from "../types";
import { listarBlingDepositos, estoqueDepositosKpis, type BlingDeposito, type DepositoKpi } from "@/lib/api";

interface DepositoRow {
  nome: string;
  codigo: string;
  ativo: boolean;
  skus: number | null;
  valor: number | null;
  baixoEstoque: number | null;
}

const SEM_DADO_TITLE = "Sem estoque rastreado neste depósito";

const COLUMNS: Column<DepositoRow>[] = [
  { key: "nome", label: "Depósito", render: (v) => <span className="text-neutral-200">{v as string}</span> },
  { key: "codigo", label: "Código", render: (v) => <span className="font-mono text-neutral-400 text-[11px]">{v as string}</span> },
  {
    key: "skus", label: "SKUs", align: "center",
    render: (v) => v === null
      ? <span className="text-neutral-600" title={SEM_DADO_TITLE}>—</span>
      : <span className="font-mono text-neutral-200">{v as number}</span>,
  },
  {
    key: "valor", label: "Valor Estoque", align: "right",
    render: (v) => v === null
      ? <span className="text-neutral-600" title={SEM_DADO_TITLE}>—</span>
      : <span className="font-mono text-emerald-400">{formatCurrency(v as number)}</span>,
  },
  {
    key: "baixoEstoque", label: "Baixo Estoque", align: "center",
    render: (v) => v === null
      ? <span className="text-neutral-600" title={SEM_DADO_TITLE}>—</span>
      : (v as number) > 0
        ? <StatusBadge label={String(v)} variant="warning" />
        : <span className="text-neutral-500">0</span>,
  },
  { key: "ativo", label: "Status", render: (v, row) => <StatusBadge label={row.ativo ? "Ativo" : "Inativo"} variant={row.ativo ? "success" : "neutral"} /> },
];

export default function DepositosPage() {
  const [depositos, setDepositos] = useState<BlingDeposito[]>([]);
  const [kpis, setKpis] = useState<DepositoKpi[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listarBlingDepositos(), estoqueDepositosKpis()])
      .then(([depRes, kpiRes]) => {
        setDepositos(depRes.data || []);
        setKpis(kpiRes.data || []);
      })
      .catch(e => setError(e instanceof Error ? e.message : "Erro ao carregar depósitos"))
      .finally(() => setLoading(false));
  }, []);

  const kpisPorId = Object.fromEntries(kpis.map(k => [k.deposito_id, k]));

  const rows: DepositoRow[] = depositos.map(d => {
    const kpi = kpisPorId[d.id];
    return {
      nome: d.descricao,
      codigo: String(d.id),
      ativo: d.situacao === "A",
      skus: kpi ? kpi.skus : null,
      valor: kpi ? kpi.valor : null,
      baixoEstoque: kpi ? kpi.baixo_estoque : null,
    };
  });

  const rowsComDado = rows.filter(r => r.skus !== null);
  const kpiCards: KpiMetric[] = [
    { label: "Depósitos Ativos", value: String(rows.filter(r => r.ativo).length), color: "text-emerald-400" },
    { label: "Total SKUs", value: String(rowsComDado.reduce((s, r) => s + (r.skus ?? 0), 0)), color: "text-blue-400" },
    { label: "Valor Total", value: formatCurrency(rowsComDado.reduce((s, r) => s + (r.valor ?? 0), 0)), color: "text-indigo-400" },
    { label: "Itens Baixo Estoque", value: String(rowsComDado.reduce((s, r) => s + (r.baixoEstoque ?? 0), 0)), color: "text-amber-400" },
  ];

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Depósitos" subtitle="Depósitos do Bling com estoque real das lojas vinculadas" />
      {loading ? (
        <LoadingState message="Carregando depósitos..." />
      ) : error ? (
        <ErrorAlert message={error} />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {kpiCards.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
          </div>
          <DataTable columns={COLUMNS} data={rows} keyExtractor={r => r.codigo} countLabel={`${rows.length} depósitos`} />
        </>
      )}
    </div>
  );
}
