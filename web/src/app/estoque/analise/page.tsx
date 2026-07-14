"use client";

import { useMemo, useState } from "react";
import type { KpiMetric, Column } from "@/lib/types/ui";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import TabBar from "@/app/_components/TabBar";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import type { IndicadorGiro, IndicadorRuptura, IndicadorCobertura } from "@/lib/types/domain";
import type { StatusBadgeVariant } from "@/lib/types/ui";
import { formatCurrency } from "../types";
import { gerarIndicadoresGiro, gerarIndicadoresRuptura, gerarIndicadoresCobertura } from "../data/custos";

const TABS = [
  { key: "giro", label: "Giro de Estoque" },
  { key: "ruptura", label: "Ruptura" },
  { key: "cobertura", label: "Cobertura" },
];

const GIRO_COLUMNS: Column<IndicadorGiro>[] = [
  { key: "sku", label: "SKU", render: (v) => <span className="font-mono text-neutral-300 text-[11px]">{v as string}</span> },
  { key: "produto", label: "Produto" },
  { key: "saidas_30d", label: "Saídas (30d)", align: "center", render: (v) => <span className="text-neutral-200">{v as number}</span> },
  { key: "estoque_medio", label: "Estoque Médio", align: "center" },
  {
    key: "giro", label: "Giro", align: "center",
    render: (v) => {
      const g = v as number;
      return <span className={`font-medium ${g >= 3 ? "text-emerald-400" : g >= 1 ? "text-amber-400" : "text-red-400"}`}>{g}x</span>;
    },
  },
  {
    key: "tendencia", label: "Tendência", align: "center",
    render: (v, row) => {
      const t = row.tendencia;
      return <span className={t === "up" ? "text-emerald-400" : t === "down" ? "text-red-400" : "text-neutral-400"}>
        {t === "up" ? "▲" : t === "down" ? "▼" : "—"}
      </span>;
    },
  },
];

const RUPTURA_COLUMNS: Column<IndicadorRuptura>[] = [
  { key: "sku", label: "SKU", render: (v) => <span className="font-mono text-neutral-300 text-[11px]">{v as string}</span> },
  { key: "produto", label: "Produto" },
  { key: "dias_ruptura", label: "Dias em Ruptura", align: "center", render: (v) => <span className="text-red-400 font-medium">{v as number}</span> },
  { key: "vendas_perdidas_estimadas", label: "Vendas Perdidas", align: "center" },
  { key: "impacto_receita", label: "Impacto Receita", align: "right", render: (v) => <span className="font-mono text-red-400">{formatCurrency(v as number)}</span> },
  { key: "ultimo_abastecimento", label: "Último Abastec.", render: (v) => v ? <span className="text-neutral-500">{(v as string)?.split("-").reverse().join("/")}</span> : <span className="text-neutral-600">—</span> },
];

const COBERTURA_COLUMNS: Column<IndicadorCobertura>[] = [
  { key: "sku", label: "SKU", render: (v) => <span className="font-mono text-neutral-300 text-[11px]">{v as string}</span> },
  { key: "produto", label: "Produto" },
  { key: "estoque_atual", label: "Estoque", align: "center" },
  { key: "demanda_diaria_media", label: "Demanda/dia", align: "center", render: (v) => <span className="text-neutral-300">{v as number}</span> },
  {
    key: "cobertura_dias", label: "Cobertura", align: "center",
    render: (v) => {
      const d = v as number;
      return <span className={`font-medium ${d > 30 ? "text-emerald-400" : d >= 7 ? "text-amber-400" : "text-red-400"}`}>{d} dias</span>;
    },
  },
  { key: "estoque_minimo", label: "Mínimo", align: "center" },
  { key: "estoque_maximo", label: "Máximo", align: "center" },
  {
    key: "status", label: "Status",
    render: (v, row) => {
      const s = row.status;
      const variant: StatusBadgeVariant = s === "excesso" ? "neutral" : s === "normal" ? "success" : s === "baixo" ? "warning" : "danger";
      const label = s === "excesso" ? "Excesso" : s === "normal" ? "Normal" : s === "baixo" ? "Baixo" : "Crítico";
      return <StatusBadge label={label} variant={variant} />;
    },
  },
];

export default function AnalisePage() {
  const [tab, setTab] = useState("giro");

  const giro = useMemo(() => gerarIndicadoresGiro(), []);
  const ruptura = useMemo(() => gerarIndicadoresRuptura(), []);
  const cobertura = useMemo(() => gerarIndicadoresCobertura(), []);

  const giroMedio = Math.round(giro.reduce((s, g) => s + g.giro, 0) / giro.length * 10) / 10;
  const totalRuptura = ruptura.length;
  const impactoRuptura = ruptura.reduce((s, r) => s + r.impacto_receita, 0);
  const coberturaMedia = Math.round(cobertura.reduce((s, c) => s + c.cobertura_dias, 0) / cobertura.length);
  const criticos = cobertura.filter(c => c.status === "critico" || c.status === "baixo").length;

  const kpis: KpiMetric[] = [
    { label: "Giro Médio (30d)", value: `${giroMedio}x`, color: giroMedio >= 2 ? "text-emerald-400" : "text-amber-400" },
    { label: "SKUs em Ruptura", value: String(totalRuptura), color: totalRuptura > 0 ? "text-red-400" : "text-emerald-400" },
    { label: "Impacto Ruptura", value: formatCurrency(impactoRuptura), color: "text-red-400" },
    { label: "Cobertura Média", value: `${coberturaMedia} dias`, color: "text-blue-400" },
    { label: "SKUs Críticos/Baixos", value: String(criticos), color: criticos > 5 ? "text-red-400" : "text-amber-400" },
  ];

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Análise de Estoque" subtitle="Indicadores de giro, ruptura e cobertura para tomada de decisão" />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {tab === "giro" && (
        <div className="space-y-1">
          <p className="text-xs text-neutral-500">Giro = Saídas no período / Estoque médio. Acima de 3x é saudável.</p>
          <DataTable columns={GIRO_COLUMNS} data={giro} keyExtractor={g => g.sku} countLabel={`${giro.length} SKUs`} />
        </div>
      )}

      {tab === "ruptura" && (
        <div className="space-y-1">
          {totalRuptura === 0 ? (
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
              <p className="text-emerald-400 text-sm">✓ Nenhum SKU em ruptura no momento</p>
            </div>
          ) : (
            <>
              <p className="text-xs text-neutral-500">SKUs com estoque abaixo do mínimo. Vendas perdidas estimadas.</p>
              <DataTable columns={RUPTURA_COLUMNS} data={ruptura} keyExtractor={r => r.sku} countLabel={`${ruptura.length} SKUs em ruptura`} />
            </>
          )}
        </div>
      )}

      {tab === "cobertura" && (
        <div className="space-y-1">
          <p className="text-xs text-neutral-500">Cobertura = Estoque atual / Demanda diária média. Ideal: 7-30 dias.</p>
          <DataTable columns={COBERTURA_COLUMNS} data={cobertura} keyExtractor={c => c.sku} countLabel={`${cobertura.length} SKUs`} />
        </div>
      )}
    </div>
  );
}
