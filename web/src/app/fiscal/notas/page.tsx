"use client";

import { useEffect, useState, useCallback } from "react";
import { fiscalList, fiscalSyncNotasFiscais, baixarNFeXML, abrirNFeDANFE } from "@/lib/api";
import DateFilter, { type DateFilterValue } from "@/app/_components/DateFilter";
import { formatCurrency } from "../types";
import type { Column, TabOption } from "../types";
import PageHeader from "@/app/_components/PageHeader";
import TabBar from "@/app/_components/TabBar";
import DataTable from "@/app/_components/DataTable";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";

interface NotaRow {
  id: number;
  numero: string;
  chave_acesso: string;
  tipo: string;
  data_emissao: string;
  contato_nome: string;
  valor_nf: number;
  valor_total_tributos: number;
  status: string;
  bling_id: number;
}

const TABS: TabOption[] = [
  { key: "todas", label: "Todas" },
  { key: "saida", label: "Saída" },
  { key: "entrada", label: "Entrada" },
  { key: "emitida", label: "Emitidas" },
  { key: "cancelada", label: "Canceladas" },
];

function situacaoVariant(s: string) {
  return s === "emitida" ? "success" as const : s === "cancelada" ? "danger" as const : "neutral" as const;
}

function detectarModelo(numero: string) {
  if (numero.startsWith("55")) return "NF-e";
  if (numero.startsWith("65")) return "NFC-e";
  if (numero.match(/^[A-Z]/)) return "NFS-e";
  if (numero.startsWith("57")) return "CT-e";
  return "NF-e";
}

const COLUMNS: Column<NotaRow>[] = [
  { key: "numero", label: "Nº" },
  { key: "tipo_label", label: "Tipo", render: (_, row) => <span className="text-[10px]">{detectarModelo(row.numero)}</span> },
  { key: "contato_nome", label: "Cliente" },
  { key: "data_emissao", label: "Emissão", render: (_, row) => String(row.data_emissao ?? "—").slice(0, 10) },
  { key: "valor_nf", label: "Valor (R$)", align: "right", render: (_, row) => (
    <span className="text-emerald-400">{formatCurrency(row.valor_nf)}</span>
  )},
  { key: "status", label: "Situação", align: "center", render: (_, row) => (
    <StatusBadge label={row.status} variant={situacaoVariant(row.status)} />
  )},
  { key: "acoes", label: "Ações", align: "center", render: (_, row) => (
    <div className="flex gap-1 justify-center">
      {row.bling_id ? (
        <>
          <button onClick={() => baixarNFeXML(row.bling_id)} className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white text-[10px] rounded">XML</button>
          <button onClick={() => abrirNFeDANFE(row.bling_id)} className="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] rounded">DANFE</button>
        </>
      ) : (
        <span className="text-[10px] text-neutral-500">—</span>
      )}
    </div>
  )},
];

export default function NotasFiscaisPage() {
  const [notas, setNotas] = useState<NotaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [tab, setTab] = useState("todas");
  const [dateFilter, setDateFilter] = useState<DateFilterValue>({});

  const carregar = useCallback(() => {
    setLoading(true);
    setErro(null);
    fiscalList("notas_fiscais")
      .then(r => setNotas((r.data || []) as NotaRow[]))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  useEffect(() => {
    const { data_inicio, data_fim, dias } = dateFilter;
    if (!data_inicio && !data_fim && !dias) return;
    const p = new URLSearchParams();
    if (data_inicio) p.set("data_inicio", data_inicio);
    if (data_fim) p.set("data_fim", data_fim);
    if (dias) p.set("dias", String(dias));
    fetch("/api/fiscal/notas_fiscais?" + p)
      .then(r => r.json())
      .then(r => setNotas((r.data || []) as NotaRow[]))
      .catch(() => {});
  }, [dateFilter]);

  const sync = async () => {
    setSyncing(true);
    setErro(null);
    try {
      const r = await fiscalSyncNotasFiscais();
      if (r.error) setErro(r.error);
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao sincronizar");
    } finally {
      setSyncing(false);
    }
  };

  const filtradas = tab === "todas" ? notas : notas.filter(n => n.tipo === tab || n.status === tab);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader title="Notas Fiscais" subtitle="NF-e, NFC-e, NFS-e, CT-e e MDF-e" />
        <div className="flex items-center gap-3">
          <DateFilter value={dateFilter} onChange={setDateFilter} />
          <button
            onClick={sync}
            disabled={syncing}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs rounded whitespace-nowrap"
          >
            {syncing ? "Sincronizando..." : "Sync Bling"}
          </button>
        </div>
      </div>
      <TabBar tabs={TABS} active={tab} onChange={setTab} />
      <ErrorAlert message={erro} />
      {loading ? (
        <LoadingState />
      ) : (
        <DataTable<NotaRow>
          columns={COLUMNS}
          data={filtradas}
          keyExtractor={n => n.id}
          emptyMessage="Nenhuma nota fiscal encontrada. Clique em Sync Bling para puxar dados."
          countLabel={`${filtradas.length} notas`}
        />
      )}
    </div>
  );
}
