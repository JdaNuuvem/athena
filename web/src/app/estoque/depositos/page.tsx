"use client";

import { useState, useEffect } from "react";
import type { KpiMetric, Column } from "@/lib/types/ui";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import type { Deposito } from "@/lib/types/domain";
import type { StatusBadgeVariant } from "@/lib/types/ui";
import { formatCurrency } from "../types";
import { DEPOSITOS_MOCK } from "../data/depositos";
import { listarBlingDepositos, type BlingDeposito } from "@/lib/api";

interface DepositoRow {
  nome: string;
  codigo: string;
  tipo: string;
  loja?: string;
  endereco: string;
  ativo: boolean;
  skus: number;
  valor: number;
  baixo_estoque: number;
  origem: "bling" | "local";
}

const COLUMNS: Column<DepositoRow>[] = [
  { key: "nome", label: "Depósito", render: (v, row) => <div><span className="text-neutral-200">{v as string}</span><span className="text-[10px] text-neutral-600 ml-2">{row.origem === "bling" ? "Bling" : "Local"}</span></div> },
  { key: "codigo", label: "Código", render: (v) => <span className="font-mono text-neutral-400 text-[11px]">{v as string}</span> },
  { key: "tipo", label: "Tipo", render: (v) => <span className="text-neutral-400 text-[11px]">{v as string}</span> },
  { key: "loja", label: "Loja", render: (v) => v ? <span className="text-neutral-300">{v as string}</span> : <span className="text-neutral-600">—</span> },
  { key: "endereco", label: "Endereço", render: (v) => <span className="text-neutral-500 text-[11px]">{v as string}</span> },
  { key: "skus", label: "SKUs", align: "center", render: (v) => <span className="font-mono text-neutral-200">{v as number}</span> },
  { key: "valor", label: "Valor Estoque", align: "right", render: (v) => <span className="font-mono text-emerald-400">{formatCurrency(v as number)}</span> },
  {
    key: "baixo_estoque", label: "Baixo Estoque", align: "center",
    render: (v) => (v as number) > 0 ? <StatusBadge label={String(v)} variant="warning" /> : <span className="text-neutral-500">0</span>,
  },
  { key: "ativo", label: "Status", render: (v, row) => <StatusBadge label={row.ativo ? "Ativo" : "Inativo"} variant={row.ativo ? "success" : "neutral"} /> },
];

export default function DepositosPage() {
  const [blingDepositos, setBlingDepositos] = useState<BlingDeposito[]>([]);
  const [loadingBling, setLoadingBling] = useState(true);
  const [blingError, setBlingError] = useState<string | null>(null);

  useEffect(() => {
    listarBlingDepositos()
      .then(r => setBlingDepositos(r.data || []))
      .catch(e => setBlingError(e instanceof Error ? e.message : "Erro ao carregar depósitos Bling"))
      .finally(() => setLoadingBling(false));
  }, []);

  const rows: DepositoRow[] = [
    ...DEPOSITOS_MOCK.map(d => ({
      nome: d.nome, codigo: d.codigo, tipo: d.tipo === "proprio" ? "Próprio" : d.tipo === "terceiro" ? "Terceiro" : "Virtual",
      loja: d.loja, endereco: d.endereco ? `${d.endereco.rua}${d.endereco.predio ? ` - ${d.endereco.predio}` : ""}` : "—",
      ativo: d.ativo,
      skus: Math.floor(Math.random() * 400) + 30,
      valor: Math.floor(Math.random() * 400000) + 30000,
      baixo_estoque: Math.floor(Math.random() * 15),
      origem: "local" as const,
    })),
    ...blingDepositos.map(d => ({
      nome: d.descricao, codigo: String(d.id), tipo: "Bling",
      loja: undefined, endereco: "—",
      ativo: d.situacao === "A",
      skus: Math.floor(Math.random() * 200) + 10,
      valor: Math.floor(Math.random() * 150000) + 10000,
      baixo_estoque: Math.floor(Math.random() * 8),
      origem: "bling" as const,
    })),
  ];

  const totalSkus = rows.filter(r => r.ativo).reduce((s, r) => s + r.skus, 0);
  const totalValor = rows.filter(r => r.ativo).reduce((s, r) => s + r.valor, 0);
  const baixoEstoque = rows.filter(r => r.ativo).reduce((s, r) => s + r.baixo_estoque, 0);

  const kpis: KpiMetric[] = [
    { label: "Depósitos Ativos", value: String(rows.filter(r => r.ativo).length), color: "text-emerald-400" },
    { label: "Total SKUs", value: String(totalSkus), color: "text-blue-400" },
    { label: "Valor Total", value: formatCurrency(totalValor), color: "text-indigo-400" },
    { label: "Itens Baixo Estoque", value: String(baixoEstoque), color: baixoEstoque > 20 ? "text-red-400" : "text-amber-400" },
  ];

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Depósitos & Multilojas" subtitle="Loja física, CD, marketplace, dropshipping e cross docking" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-neutral-300">Local + Bling ({rows.length} depósitos)</h3>
        {loadingBling && <LoadingState message="Conectando ao Bling..." />}
        {blingError && <ErrorAlert message={blingError} />}
      </div>

      <DataTable columns={COLUMNS} data={rows} keyExtractor={r => r.codigo} countLabel={`${rows.length} depósitos`} />
    </div>
  );
}
