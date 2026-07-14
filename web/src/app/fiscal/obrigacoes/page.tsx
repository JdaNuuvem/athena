"use client";

import { useEffect, useState, useCallback } from "react";
import { fiscalObrigacoesProximas, fiscalObrigacoesAtrasadas, fiscalBaixarObrigacao, fiscalList } from "@/lib/api";
import PageHeader from "@/app/_components/PageHeader";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";

interface ObrigacaoRow {
  id: number;
  nome: string;
  sigla: string;
  descricao: string;
  periodicidade: string;
  data_vencimento: string;
  orgao: string;
  regime: string;
  status: string;
  responsavel: string;
  multa_por_atraso: number;
}

function statusVariant(s: string) {
  if (s === "entregue") return "success" as const;
  if (s === "pendente") return "warning" as const;
  return "neutral" as const;
}

function statusLabel(s: string) {
  const map: Record<string, string> = { entregue: "Entregue", pendente: "Pendente", em_andamento: "Em andamento", vencida: "Vencida" };
  return map[s] || s;
}

export default function ObrigacoesPage() {
  const [todas, setTodas] = useState<ObrigacaoRow[]>([]);
  const [atrasadas, setAtrasadas] = useState<ObrigacaoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(() => {
    setLoading(true);
    setErro(null);
    Promise.all([fiscalList("obrigacoes"), fiscalObrigacoesAtrasadas()])
      .then(([r1, r2]) => {
        setTodas((r1.data || []) as ObrigacaoRow[]);
        setAtrasadas((r2.data || []) as ObrigacaoRow[]);
      })
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const baixar = async (id: number) => {
    await fiscalBaixarObrigacao(id);
    carregar();
  };

  const renderObrigacao = (o: ObrigacaoRow) => (
    <div key={o.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-100">{o.nome}</h3>
        <StatusBadge label={statusLabel(o.status)} variant={statusVariant(o.status)} />
      </div>
      <p className="text-xs text-neutral-500">{o.descricao}</p>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div>
          <p className="text-neutral-500">Vencimento</p>
          <p className={o.status === "pendente" && o.data_vencimento ? "text-amber-400" : "text-neutral-300"}>
            {o.data_vencimento ? o.data_vencimento.slice(0, 10).split("-").reverse().join("/") : "—"}
          </p>
        </div>
        <div>
          <p className="text-neutral-500">Periodicidade</p>
          <p className="text-neutral-300 capitalize">{o.periodicidade}</p>
        </div>
        <div>
          <p className="text-neutral-500">Órgão</p>
          <p className="text-neutral-300">{o.orgao}</p>
        </div>
        <div>
          <p className="text-neutral-500">Responsável</p>
          <p className="text-neutral-300">{o.responsavel || "—"}</p>
        </div>
      </div>
      {o.status === "pendente" && (
        <button
          onClick={() => baixar(o.id)}
          className="w-full mt-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded"
        >
          Marcar como Entregue
        </button>
      )}
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Obrigações Acessórias" subtitle="SPED, EFD, DCTF, GIA, SINTEGRA e DAS" />

      <ErrorAlert message={erro} />
      {loading ? (
        <LoadingState />
      ) : (
        <>
          {atrasadas.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-red-400 mb-3">Atrasadas ({atrasadas.length})</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {atrasadas.map(renderObrigacao)}
              </div>
            </div>
          )}

          <div>
            <h2 className="text-sm font-semibold text-neutral-300 mb-3">Todas ({todas.length})</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {todas.map(renderObrigacao)}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
