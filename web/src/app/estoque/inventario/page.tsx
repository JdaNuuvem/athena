"use client";

import { useState, useMemo } from "react";
import type { KpiMetric, Column } from "@/lib/types/ui";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import TabBar from "@/app/_components/TabBar";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import type { Inventario, ItemInventario, TipoInventario } from "@/lib/types/domain";
import type { StatusBadgeVariant } from "@/lib/types/ui";
import { TIPOS_INVENTARIO } from "@/lib/types/domain";
import { formatCurrency } from "../types";
import { INVENTARIOS_MOCK, gerarItensInventario } from "../data/inventario";

const STATUS_VARIANT: Record<string, StatusBadgeVariant> = {
  aberto: "warning", em_andamento: "warning", concluido: "success", cancelado: "neutral",
};
const STATUS_LABEL: Record<string, string> = {
  aberto: "Aberto", em_andamento: "Em andamento", concluido: "Concluído", cancelado: "Cancelado",
};

const TABS = [{ key: "todos", label: "Todos" }, ...Object.entries(TIPOS_INVENTARIO).map(([k, v]) => ({ key: k, label: v }))];

export default function InventarioPage() {
  const [tab, setTab] = useState("todos");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const inventarios = useMemo(() => INVENTARIOS_MOCK, []);
  const filtrados = useMemo(() => tab === "todos" ? inventarios : inventarios.filter(i => i.tipo === tab), [inventarios, tab]);
  const itensExpandidos = useMemo(() => expandedId !== null ? gerarItensInventario(expandedId) : [], [expandedId]);

  const concluidos = inventarios.filter(i => i.status === "concluido");
  const acuraciaMedia = concluidos.length > 0 ? Math.round(concluidos.reduce((s, i) => s + i.acuracia_pct, 0) / concluidos.length * 10) / 10 : 0;

  const kpis: KpiMetric[] = [
    { label: "Inventários", value: String(inventarios.length), color: "text-neutral-100" },
    { label: "Em Andamento", value: String(inventarios.filter(i => i.status === "em_andamento" || i.status === "aberto").length), color: "text-amber-400" },
    { label: "Acurácia Média", value: `${acuraciaMedia}%`, color: acuraciaMedia >= 95 ? "text-emerald-400" : "text-amber-400" },
  ];

  const INV_COLUMNS: Column<Inventario>[] = [
    { key: "data_inicio", label: "Início", render: (v) => <span className="text-neutral-400">{(v as string)?.split("-").reverse().join("/")}</span> },
    { key: "tipo", label: "Tipo", render: (v) => <span className="text-neutral-300">{TIPOS_INVENTARIO[v as TipoInventario]}</span> },
    { key: "deposito", label: "Depósito", render: (v) => <span className="text-neutral-200">{v as string}</span> },
    { key: "status", label: "Status", render: (v, row) => <StatusBadge label={STATUS_LABEL[row.status]} variant={STATUS_VARIANT[row.status] || "neutral"} /> },
    { key: "itens_contados", label: "Contados", align: "center" },
    { key: "itens_divergentes", label: "Divergências", align: "center", render: (v) => (v as number) > 0 ? <span className="text-red-400 font-medium">{v as number}</span> : <span className="text-emerald-400">0</span> },
    { key: "acuracia_pct", label: "Acurácia", align: "center", render: (v) => <span className={`font-medium ${(v as number) >= 95 ? "text-emerald-400" : (v as number) >= 85 ? "text-amber-400" : "text-red-400"}`}>{v as number}%</span> },
    { key: "responsavel", label: "Responsável", render: (v) => <span className="text-neutral-500">{v as string}</span> },
    { key: "id", label: "", align: "center", render: (_, row) => (
      <button onClick={() => setExpandedId(expandedId === row.id ? null : row.id)} className="text-xs text-indigo-400 hover:text-indigo-300">
        {expandedId === row.id ? "▲" : "▼"}
      </button>
    )},
  ];

  const ITEM_COLUMNS: Column<ItemInventario>[] = [
    { key: "sku", label: "SKU", render: (v) => <span className="font-mono text-neutral-300 text-[11px]">{v as string}</span> },
    { key: "produto", label: "Produto" },
    { key: "saldo_sistema", label: "Sistema", align: "right", render: (v) => <span className="font-mono text-neutral-400">{v as number}</span> },
    { key: "saldo_contado", label: "Contado", align: "right", render: (v) => <span className="font-mono text-neutral-200">{v as number}</span> },
    { key: "divergencia", label: "Divergência", align: "right", render: (v) => (v as number) !== 0 ? <span className={`font-mono ${(v as number) > 0 ? "text-emerald-400" : "text-red-400"}`}>{(v as number) > 0 ? "+" : ""}{v as number}</span> : <span className="text-emerald-400">✓</span> },
    { key: "custo_unitario", label: "Custo Unit.", align: "right", render: (v) => <span className="text-neutral-500">{formatCurrency(v as number)}</span> },
    { key: "divergencia_valor", label: "Valor Diverg.", align: "right", render: (v) => (v as number) !== 0 ? <span className={`font-mono text-xs ${(v as number) > 0 ? "text-emerald-400" : "text-red-400"}`}>{formatCurrency(v as number)}</span> : <span className="text-neutral-600">R$ 0,00</span> },
  ];

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Inventário" subtitle="Cíclico, geral, parcial — contagem e acuracidade de estoque" />
      <div className="grid grid-cols-3 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>
      <TabBar tabs={TABS} active={tab} onChange={setTab} />
      <DataTable columns={INV_COLUMNS} data={filtrados} keyExtractor={i => i.id} countLabel={`${filtrados.length} inventários`} />

      {expandedId !== null && (
        <div className="space-y-2 mt-4 border-t border-neutral-700 pt-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-neutral-300">Itens do Inventário #{expandedId}</h3>
            <button onClick={() => setExpandedId(null)} className="text-xs text-neutral-500 hover:text-neutral-300">Fechar ✕</button>
          </div>
          <DataTable columns={ITEM_COLUMNS} data={itensExpandidos} keyExtractor={item => item.id}
            countLabel={`${itensExpandidos.length} itens contados`}
            emptyMessage="Nenhum item registrado neste inventário" />
        </div>
      )}
    </div>
  );
}
