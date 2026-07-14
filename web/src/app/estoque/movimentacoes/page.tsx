"use client";

import { useState, useMemo } from "react";
import type { KpiMetric, Column, TabOption } from "@/lib/types/ui";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import TabBar from "@/app/_components/TabBar";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import type { MovimentacaoEstoque, TipoMovimentacao } from "@/lib/types/domain";
import type { StatusBadgeVariant } from "@/lib/types/ui";
import { TIPOS_MOVIMENTACAO, TIPO_MOV_COLORS } from "@/lib/types/domain";
import { formatCurrency, fmtQtd } from "../types";
import { gerarMovimentacoes } from "../data/movimentacoes";

const VERDE = "positive" as unknown as StatusBadgeVariant;
const VERMELHO = "danger" as unknown as StatusBadgeVariant;
const NEUTRO = "neutral" as unknown as StatusBadgeVariant;

function statusVariant(tipo: TipoMovimentacao): StatusBadgeVariant {
  if (["entrada", "producao", "devolucao"].includes(tipo)) return "success";
  if (["saida", "perda", "consumo"].includes(tipo)) return "danger";
  if (["transferencia", "reserva", "separacao", "expedicao"].includes(tipo)) return "warning";
  return "neutral";
}

const TABS: TabOption[] = [
  { key: "todos", label: "Todos" },
  ...Object.entries(TIPOS_MOVIMENTACAO).map(([k, v]) => ({ key: k, label: v })),
];

const COLUMNS: Column<MovimentacaoEstoque>[] = [
  { key: "data", label: "Data", render: (v) => <span className="text-neutral-400">{(v as string)?.split("-").reverse().join("/")}</span> },
  {
    key: "tipo", label: "Tipo", render: (_, row) => (
      <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium ${TIPO_MOV_COLORS[row.tipo]}`}>
        {TIPOS_MOVIMENTACAO[row.tipo]}
      </span>
    ),
  },
  { key: "sku", label: "SKU", render: (v) => <span className="font-mono text-neutral-300 text-[11px]">{v as string}</span> },
  { key: "produto", label: "Produto" },
  {
    key: "quantidade", label: "Qtd", align: "right",
    render: (v, row) => (
      <span className={`font-mono ${(v as number) > 0 ? "text-emerald-400" : "text-red-400"}`}>
        {(v as number) > 0 ? "+" : ""}{fmtQtd(v as number)}
      </span>
    ),
  },
  { key: "deposito_origem", label: "Origem", render: (v) => v ? <span className="text-neutral-400">{v as string}</span> : <span className="text-neutral-600">—</span> },
  { key: "deposito_destino", label: "Destino", render: (v) => v ? <span className="text-neutral-400">{v as string}</span> : <span className="text-neutral-600">—</span> },
  {
    key: "custo_total", label: "Custo Total", align: "right",
    render: (v) => v != null ? <span className="font-mono text-amber-400">{formatCurrency(v as number)}</span> : <span className="text-neutral-600">—</span>,
  },
  { key: "responsavel", label: "Responsável", render: (v) => <span className="text-neutral-500">{v as string}</span> },
];

export default function MovimentacoesPage() {
  const [tab, setTab] = useState("todos");
  const movimentacoes = useMemo(() => gerarMovimentacoes(100), []);

  const filtradas = useMemo(() => {
    if (tab === "todos") return movimentacoes;
    return movimentacoes.filter(m => m.tipo === tab);
  }, [movimentacoes, tab]);

  const entradas = movimentacoes.filter(m => m.tipo === "entrada" || m.tipo === "producao" || m.tipo === "devolucao");
  const saidas = movimentacoes.filter(m => m.tipo === "saida" || m.tipo === "consumo" || m.tipo === "perda");
  const entradasValor = entradas.reduce((s, m) => s + Math.abs(m.custo_total ?? 0), 0);
  const saidasValor = saidas.reduce((s, m) => s + Math.abs(m.custo_total ?? 0), 0);

  const kpis: KpiMetric[] = [
    { label: "Total Movimentações", value: String(movimentacoes.length), color: "text-neutral-100" },
    { label: "Entradas (valor)", value: formatCurrency(entradasValor), color: "text-emerald-400" },
    { label: "Saídas (valor)", value: formatCurrency(saidasValor), color: "text-red-400" },
  ];

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Movimentações de Estoque" subtitle="Entrada, saída, transferência e todos os tipos de movimentação" />

      <div className="grid grid-cols-3 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      <DataTable
        columns={COLUMNS}
        data={filtradas}
        keyExtractor={m => m.id}
        countLabel={`${filtradas.length} movimentações`}
        emptyMessage="Nenhuma movimentação encontrada"
      />
    </div>
  );
}
