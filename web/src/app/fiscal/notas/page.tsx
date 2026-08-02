"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { fiscalList, fiscalSyncNotasFiscais, baixarNFeXML, abrirNFeDANFE } from "@/lib/api";
import DateFilter, { type DateFilterValue } from "@/app/_components/DateFilter";
import { formatCurrency } from "../types";
import type { Column, TabOption } from "../types";
import PageHeader from "@/app/_components/PageHeader";
import TabBar from "@/app/_components/TabBar";
import DataTable from "@/app/_components/DataTable";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import { Can } from "@/lib/auth";
import StatusBadge from "@/app/_components/StatusBadge";
import NotaDetalhesModal from "./_components/NotaDetalhesModal";

interface NotaRow {
  id: number;
  numero: string;
  chave_acesso: string;
  tipo: string;
  modelo: string;
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

// ponytail: a versao anterior "adivinhava" o modelo do documento a partir do
// PREFIXO do numero sequencial da nota (numero.startsWith("55") etc) — o
// numero de uma NF-e e' so' um contador sequencial por serie, sem nenhuma
// relacao com o modelo do documento (uma nota #550 batia em "55" por
// coincidencia e virava NF-e errado). fiscal_notas_fiscais.modelo ja' vem
// sincronizado corretamente do Bling (core/fiscal.py::_mapear_nfe_detalhe),
// so' nao estava sendo lido pelo frontend.
const MODELO_LABEL: Record<string, string> = {
  "55": "NF-e", "65": "NFC-e", "57": "CT-e", "58": "MDF-e",
};
function labelModelo(modelo: string) {
  return MODELO_LABEL[modelo] || "NFS-e";
}

export default function NotasFiscaisPage() {
  const [notas, setNotas] = useState<NotaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [tab, setTab] = useState("todas");
  const [dateFilter, setDateFilter] = useState<DateFilterValue>({});
  const [notaDetalhe, setNotaDetalhe] = useState<NotaRow | null>(null);

  const carregar = useCallback(() => {
    setLoading(true);
    setErro(null);
    fiscalList("notas_fiscais", dateFilter)
      .then(r => setNotas((r.data || []) as NotaRow[]))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, [dateFilter]);

  useEffect(() => { carregar(); }, [carregar]);

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

  const columns: Column<NotaRow>[] = useMemo(() => [
    { key: "numero", label: "Nº" },
    { key: "modelo", label: "Tipo", render: (_, row) => <span className="text-[10px]">{labelModelo(row.modelo)}</span> },
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
        <button onClick={() => setNotaDetalhe(row)} className="px-2 py-1 bg-neutral-700 hover:bg-neutral-600 text-white text-[10px] rounded">Detalhes</button>
        {row.bling_id ? (
          <>
            <button onClick={() => baixarNFeXML(row.bling_id)} className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white text-[10px] rounded">XML</button>
            <button onClick={() => abrirNFeDANFE(row.bling_id)} className="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] rounded">DANFE</button>
          </>
        ) : null}
      </div>
    )},
  ], []);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader title="Notas Fiscais" subtitle="NF-e, NFC-e, NFS-e, CT-e e MDF-e" />
        <div className="flex items-center gap-3">
          <DateFilter value={dateFilter} onChange={setDateFilter} />
          <Can permission="fiscal.editar">
          <button
            onClick={sync}
            disabled={syncing}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs rounded whitespace-nowrap"
          >
            {syncing ? "Sincronizando..." : "Sync Bling"}
          </button>
          </Can>
        </div>
      </div>
      <TabBar tabs={TABS} active={tab} onChange={setTab} />
      <ErrorAlert message={erro} />
      {loading ? (
        <LoadingState />
      ) : (
        <DataTable<NotaRow>
          columns={columns}
          data={filtradas}
          keyExtractor={n => n.id}
          emptyMessage="Nenhuma nota fiscal encontrada. Clique em Sync Bling para puxar dados."
          countLabel={`${filtradas.length} notas`}
        />
      )}
      {notaDetalhe && (
        <NotaDetalhesModal
          notaId={notaDetalhe.id}
          numero={notaDetalhe.numero}
          onFechar={() => setNotaDetalhe(null)}
        />
      )}
    </div>
  );
}
