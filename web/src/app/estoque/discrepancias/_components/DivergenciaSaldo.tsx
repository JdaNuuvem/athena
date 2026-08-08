"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useStore } from "@/lib/store-context";
import { useAuth } from "@/lib/auth";
import {
  i9logicListarDivergenciasAthena, i9logicAjustarDivergenciaAthena,
  shopeeListarDivergencias, shopeeResolverDivergencia, shopeeAjustarDivergencia,
  type DivergenciaItem, type DivergenciaResponse,
} from "@/lib/api";

const POLL_INTERVAL_MS = 5000;

const CLASSIFICACAO_LABEL: Record<string, string> = {
  sem_acao: "OK", registrado: "Registrado", alerta: "Alerta",
};
const CLASSIFICACAO_CLASSE: Record<string, string> = {
  sem_acao: "text-neutral-500", registrado: "text-amber-400", alerta: "text-red-400",
};

export default function DivergenciaSaldo() {
  const { lojaId, lojas, tipoLojaSelecionada } = useStore();
  const { hasPermission } = useAuth();
  // Sem esse gate, quem so' tem estoque.ver enxergava os botoes de escrita e
  // batia num 403 a cada clique. Nao substitui o RBAC do backend (que continua
  // sendo a autoridade) — so' evita oferecer uma acao que vai ser negada.
  const podeEditar = hasPermission("estoque.editar");
  const loja = lojas.find(l => String(l.id) === lojaId);
  const [itens, setItens] = useState<DivergenciaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [avisoColeta, setAvisoColeta] = useState<string | null>(null);
  const [ajustando, setAjustando] = useState<string | number | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelarPoll = () => {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  };

  const carregar = useCallback(async (primeiraVez = false) => {
    cancelarPoll();
    if (!loja) return;
    if (tipoLojaSelecionada !== "fisica" && tipoLojaSelecionada !== "virtual") {
      // Loja sem tipo classificado: sem fonte determinada, nao consulta nenhuma integracao.
      setLoading(false);
      setAtualizando(false);
      setErro(null);
      return;
    }
    if (primeiraVez) setLoading(true);
    setErro(null);
    try {
      // request<T>() lanca em !res.ok — 403/500 caem no catch abaixo em vez de
      // passar por sucesso silencioso (ver comentario em api.ts).
      const r: DivergenciaResponse = tipoLojaSelecionada === "fisica"
        ? await i9logicListarDivergenciasAthena(loja.nome)
        : await shopeeListarDivergencias(loja.id);
      setItens(r.data || []);
      setAvisoColeta(r.erro_ultima_coleta || null);
      const processando = r.status === "processando";
      setAtualizando(processando);
      if (processando) {
        pollRef.current = setTimeout(() => carregar(false), POLL_INTERVAL_MS);
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar divergencias");
      setAtualizando(false);
    } finally {
      if (primeiraVez) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loja?.id, loja?.nome, tipoLojaSelecionada]);

  useEffect(() => {
    carregar(true);
    return () => cancelarPoll();
  }, [carregar]);

  const ajustar = async (item: DivergenciaItem) => {
    if (!loja || !podeEditar) return;
    if (tipoLojaSelecionada !== "fisica" && tipoLojaSelecionada !== "virtual") return;
    const chave = tipoLojaSelecionada === "fisica" ? item.sku : (item.id as number);
    setAjustando(chave);
    setErro(null);
    try {
      // Sem checagem de `r.erro`: request<T>() ja' lanca em qualquer !res.ok,
      // entao permissao negada / dados desatualizados (409) caem no catch.
      if (tipoLojaSelecionada === "fisica") {
        await i9logicAjustarDivergenciaAthena(item.sku, loja.nome, item.qtd_fisico_i9logic || 0);
      } else {
        await shopeeAjustarDivergencia(item.id as number);
      }
      await carregar(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao aplicar ajuste");
    } finally {
      setAjustando(null);
    }
  };

  const resolver = async (item: DivergenciaItem) => {
    if (!podeEditar) return;
    if (tipoLojaSelecionada !== "virtual" || item.id === undefined) return;
    setAjustando(item.id);
    setErro(null);
    try {
      await shopeeResolverDivergencia(item.id);
      await carregar(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao marcar divergencia como revisada");
    } finally {
      setAjustando(null);
    }
  };

  const fonteLabel = tipoLojaSelecionada === "fisica" ? "i9Logic"
    : tipoLojaSelecionada === "virtual" ? "Shopee"
    : null;

  return (
    <section className="space-y-2">
      <div>
        <h2 className="text-sm font-medium text-neutral-400">Divergência de Saldo</h2>
        <p className="text-xs text-neutral-500 mt-0.5">
          {fonteLabel
            ? `Compara o saldo disponível no Athena contra o saldo real no ${fonteLabel} — aponta onde o saldo local está desatualizado.`
            : "Compara o saldo disponível no Athena contra o saldo real na fonte da loja (i9Logic para lojas físicas, Shopee para lojas virtuais)."}
        </p>
      </div>

      {!loja ? (
        <div className="text-neutral-500 text-xs">Selecione uma loja no topo da página.</div>
      ) : tipoLojaSelecionada !== "fisica" && tipoLojaSelecionada !== "virtual" ? (
        <div className="text-neutral-500 text-xs">Selecione uma loja com tipo definido para ver divergências de saldo.</div>
      ) : erro ? (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      ) : loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <>
          {atualizando && (
            <div className="bg-indigo-900/20 border border-indigo-800/60 text-indigo-300 text-xs px-3 py-2 rounded-lg">
              Coletando saldo atualizado do {fonteLabel} em segundo plano — a lista atualiza sozinha quando terminar.
            </div>
          )}
          {avisoColeta && (
            <div className="bg-amber-900/20 border border-amber-800/60 text-amber-300 text-xs px-3 py-2 rounded-lg">
              A última coleta do {fonteLabel} falhou: {avisoColeta}. Os saldos abaixo podem estar desatualizados.
            </div>
          )}
          {itens.length === 0 ? (
            <div className="text-neutral-500 text-xs">Nenhuma divergência encontrada.</div>
          ) : (
            <div className="overflow-x-auto border border-neutral-800 rounded-lg">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-neutral-900 text-neutral-400 text-left">
                    <th className="px-3 py-2 font-medium">SKU</th>
                    <th className="px-3 py-2 font-medium text-right">Saldo Athena</th>
                    <th className="px-3 py-2 font-medium text-right">Saldo {fonteLabel}</th>
                    <th className="px-3 py-2 font-medium text-right">Divergência</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium text-right">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {itens.map(item => {
                    const chave = tipoLojaSelecionada === "fisica" ? item.sku
                      : tipoLojaSelecionada === "virtual" ? (item.id as number)
                      : item.sku;
                    const saldoExterno = tipoLojaSelecionada === "fisica" ? item.qtd_fisico_i9logic
                      : tipoLojaSelecionada === "virtual" ? item.qtd_shopee
                      : undefined;
                    return (
                      <tr key={chave}
                        className={`border-t border-neutral-800 text-neutral-300 ${item.revisado ? "opacity-50" : ""}`}>
                        <td className="px-3 py-2 font-mono text-neutral-200">{item.sku}</td>
                        <td className="px-3 py-2 text-right numeric">{item.disponivel_athena}</td>
                        <td className="px-3 py-2 text-right numeric">{saldoExterno}</td>
                        <td className="px-3 py-2 text-right numeric font-medium">{item.divergencia > 0 ? `+${item.divergencia}` : item.divergencia}</td>
                        <td className="px-3 py-2 font-medium">
                          <span className={CLASSIFICACAO_CLASSE[item.classificacao]}>
                            {CLASSIFICACAO_LABEL[item.classificacao]}
                          </span>
                          {/* Sem isso o clique em "Marcar revisado" recarregava a lista
                              e nada mudava na tela — indistinguivel de um clique falho. */}
                          {item.revisado && (
                            <span className="ml-2 text-[10px] uppercase tracking-wide text-emerald-400 border border-emerald-800/60 rounded px-1.5 py-0.5">
                              Revisado
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <div className="flex justify-end gap-2">
                            {podeEditar ? (
                              <>
                                <button onClick={() => ajustar(item)} disabled={ajustando === chave}
                                  className="text-indigo-400 hover:text-indigo-300 disabled:opacity-50">
                                  Ajustar
                                </button>
                                {tipoLojaSelecionada === "virtual" && !item.revisado && (
                                  <button onClick={() => resolver(item)} disabled={ajustando === chave}
                                    className="text-neutral-500 hover:text-neutral-300 disabled:opacity-50">
                                    Marcar revisado
                                  </button>
                                )}
                              </>
                            ) : (
                              <span className="text-neutral-600">—</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
