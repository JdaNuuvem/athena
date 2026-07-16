"use client";

import { useEffect, useState } from "react";
import type { Column, TabOption } from "../types";
import PageHeader from "@/app/_components/PageHeader";
import TabBar from "@/app/_components/TabBar";
import DataTable from "@/app/_components/DataTable";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";

interface CfopRow { codigo: string; descricao: string; tipo: string; }
interface NcmRow { codigo: string; descricao: string; }
interface CestRow { codigo: string; descricao: string; ncm?: string; }

const TABS: TabOption[] = [
  { key: "cfop", label: "CFOP" },
  { key: "ncm", label: "NCM" },
  { key: "cest", label: "CEST" },
];

function Badge({ label, variant }: { label: string; variant: "success" | "warning" }) {
  const c = variant === "success" ? "bg-emerald-900/30 text-emerald-400" : "bg-amber-900/30 text-amber-400";
  return <span className={`inline-block px-2 py-0.5 rounded text-[9px] ${c}`}>{label}</span>;
}

const CFOP_COLUMNS: Column<CfopRow>[] = [
  { key: "codigo", label: "Código" },
  { key: "descricao", label: "Descrição" },
  { key: "tipo", label: "Tipo", align: "center", render: (_, row) => {
    const t = (row.tipo || "").toLowerCase().includes("entrada") ? "Entrada" : "Saída";
    return <Badge label={t} variant={t === "Entrada" ? "success" : "warning"} />;
  }},
];

const NCM_COLUMNS: Column<NcmRow>[] = [
  { key: "codigo", label: "Código" },
  { key: "descricao", label: "Descrição" },
];

const CEST_COLUMNS: Column<CestRow>[] = [
  { key: "codigo", label: "Código" },
  { key: "descricao", label: "Descrição" },
  { key: "ncm", label: "NCM Vinculado" },
];

export default function TabelasFiscaisPage() {
  const [tab, setTab] = useState("cfop");
  const [cfop, setCfop] = useState<CfopRow[]>([]);
  const [ncm, setNcm] = useState<NcmRow[]>([]);
  const [cest, setCest] = useState<CestRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const carregar = async () => {
      if (tab === "cfop" && cfop.length > 0) return;
      if (tab === "ncm" && ncm.length > 0) return;
      if (tab === "cest" && cest.length > 0) return;
      setLoading(true); setErro(null);
      try {
        const r = await fetch(`/api/fiscal/tabelas/${tab}`);
        const d: any[] = await r.json();
        if (tab === "cfop") setCfop(d || []);
        else if (tab === "ncm") setNcm(d || []);
        else setCest(d || []);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar");
      } finally { setLoading(false); }
    };
    carregar();
  }, [tab]);

  return (
    <div className="p-4 space-y-4">
      <PageHeader title="Tabelas Fiscais" subtitle="CFOP, NCM e CEST extraídos das NF-e sincronizadas" />
      <TabBar tabs={TABS} active={tab} onChange={setTab} />
      <ErrorAlert message={erro} />

      {loading ? <LoadingState /> : (
        <>
          {tab === "cfop" && (
            <DataTable<CfopRow> columns={CFOP_COLUMNS} data={cfop} keyExtractor={r => r.codigo}
              emptyMessage="Nenhum CFOP encontrado. Sincronize NF-e do Bling primeiro."
              countLabel={`${cfop.length} CFOPs`} />
          )}
          {tab === "ncm" && (
            <DataTable<NcmRow> columns={NCM_COLUMNS} data={ncm} keyExtractor={r => r.codigo}
              emptyMessage="Nenhum NCM encontrado."
              countLabel={`${ncm.length} NCMs`} />
          )}
          {tab === "cest" && (
            <DataTable<CestRow> columns={CEST_COLUMNS} data={cest} keyExtractor={r => r.codigo}
              emptyMessage="Nenhum CEST encontrado."
              countLabel={`${cest.length} CESTs`} />
          )}
        </>
      )}
    </div>
  );
}
