"use client";

import { useEffect, useState, useCallback } from "react";
import Icon from "@/app/_components/Icon";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import EmptyState from "./shared/EmptyState";
import { listarContasReceber, listarNotasFiscais, baixarNFeXML, abrirNFeDANFE } from "@/lib/api";
import type { NotaFiscal, ContaReceber } from "@/lib/types/domain";
import { NF_SITUACOES, NF_TIPOS } from "@/lib/types/domain";

export default function BlingFinancialTab() {
  const [contas, setContas] = useState<ContaReceber[]>([]);
  const [notas, setNotas] = useState<NotaFiscal[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [tab, setTab] = useState<"contas" | "notas">("notas");
  const [expandedNf, setExpandedNf] = useState<number | null>(null);

  const carregar = useCallback(async () => {
    try {
      setLoading(true);
      setErro(null);
      if (tab === "contas") {
        const r = await listarContasReceber();
        setContas((r.data || []) as ContaReceber[]);
      } else {
        const r = await listarNotasFiscais();
        setNotas((r.data || []) as NotaFiscal[]);
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { carregar(); }, [carregar]);

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />

      <div className="flex gap-1 bg-neutral-800 rounded-lg p-1 w-fit">
        <button onClick={() => setTab("contas")}
          className={`px-4 py-1.5 text-xs rounded-md transition-colors ${tab === "contas" ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200"}`}>
          Contas a Receber
        </button>
        <button onClick={() => setTab("notas")}
          className={`px-4 py-1.5 text-xs rounded-md transition-colors ${tab === "notas" ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200"}`}>
          Notas Fiscais
        </button>
      </div>

      {loading ? (
        <Spinner />
      ) : tab === "contas" ? (
        contas.length === 0 ? (
          <EmptyState icon="💳" title="Nenhuma conta a receber" description="Sem registros ou sem permissão de acesso." />
        ) : (
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-700 text-neutral-400">
                  <th className="text-left p-3">Nº</th>
                  <th className="text-left p-3">Cliente</th>
                  <th className="text-left p-3">Vencimento</th>
                  <th className="text-right p-3">Valor</th>
                  <th className="text-center p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {contas.map((c, i) => (
                  <tr key={c.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                    <td className="p-3 text-neutral-200 font-mono">{c.numero}</td>
                    <td className="p-3 text-neutral-200">{c.contato?.nome || "—"}</td>
                    <td className="p-3 text-neutral-400">{String(c.vencimento ?? "—").slice(0, 10)}</td>
                    <td className="p-3 text-right text-emerald-400">R$ {(c.valor ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                    <td className="p-3 text-center">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-neutral-700 text-neutral-400">{String(c.situacao)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : notas.length === 0 ? (
        <EmptyState icon="📄" title="Nenhuma nota fiscal" description="Sem notas emitidas no período." />
      ) : (
        <div className="space-y-1">
          <div className="text-xs text-neutral-500">{notas.length} notas</div>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                  <th className="text-left p-3 w-[80px]">Nº</th>
                  <th className="text-left p-3">Cliente</th>
                  <th className="text-left p-3 w-[90px]">Emissão</th>
                  <th className="text-center p-3">Tipo</th>
                  <th className="text-center p-3">Situação</th>
                  <th className="text-center p-3 w-[70px]"></th>
                </tr>
              </thead>
              <tbody>
                {notas.map((n, i) => {
                  const isExpanded = expandedNf === n.id;
                  return (
                    <>
                      <tr key={n.id}
                        onClick={() => setExpandedNf(isExpanded ? null : n.id)}
                        className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"} ${isExpanded ? "!bg-neutral-750" : ""} cursor-pointer hover:bg-neutral-750`}
                      >
                        <td className="p-3 text-indigo-400 font-mono">{n.numero}</td>
                        <td className="p-3 text-neutral-200">
                          <div className="font-medium">{n.contato?.nome || "—"}</div>
                          {n.contato?.numeroDocumento && <div className="text-[10px] text-neutral-500">{n.contato.numeroDocumento}</div>}
                        </td>
                        <td className="p-3 text-neutral-400">{String(n.dataEmissao ?? "—").slice(0, 10)}</td>
                        <td className="p-3 text-center">
                          <span className="text-[10px] text-neutral-300">{NF_TIPOS[n.tipo] || `#${n.tipo}`}</span>
                        </td>
                        <td className="p-3 text-center">
                          <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium ${
                            n.situacao === 1 ? "bg-emerald-900/30 text-emerald-400" :
                            n.situacao === 2 ? "bg-red-900/30 text-red-400" : "bg-neutral-700 text-neutral-400"
                          }`}>
                            {NF_SITUACOES[n.situacao] || `#${n.situacao}`}
                          </span>
                        </td>
                        <td className="p-3 text-center">
                          <button onClick={(e) => { e.stopPropagation(); setExpandedNf(isExpanded ? null : n.id); }}
                            className="text-indigo-400 hover:text-indigo-300 leading-none inline-flex">
                            <Icon name="chevronDown" size={14} className={isExpanded ? "rotate-180 transition-transform" : "transition-transform"} />
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${n.id}-detail`} className="border-b border-neutral-700/50 bg-neutral-850">
                          <td colSpan={6} className="p-4">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                              <div>
                                <h4 className="text-neutral-400 font-medium mb-2">Chave de Acesso</h4>
                                <p className="text-neutral-200 font-mono text-[10px] break-all">{n.chaveAcesso || "—"}</p>
                              </div>
                              <div>
                                <h4 className="text-neutral-400 font-medium mb-2">Dados</h4>
                                <p className="text-neutral-200">Loja ID: {n.loja?.id || "—"}</p>
                                <p className="text-neutral-200">Natureza: {n.naturezaOperacao?.id || "—"}</p>
                                <p className="text-neutral-200">Tipo: {NF_TIPOS[n.tipo] || `#${n.tipo}`}</p>
                              </div>
                              <div>
                                <h4 className="text-neutral-400 font-medium mb-2">Valores</h4>
                                <p className="text-neutral-500 italic text-[10px]">Total não disponível no resumo. Acesse o Bling para valores detalhados da NF-e.</p>
                              </div>
                            </div>
                            <div className="flex gap-2 mt-4 pt-3 border-t border-neutral-700/50">
                              <button
                                onClick={(e) => { e.stopPropagation(); baixarNFeXML(n.id); }}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg transition-colors"
                              >
                                <Icon name="documentos" size={14} />
                                Baixar XML
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); abrirNFeDANFE(n.id); }}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded-lg transition-colors"
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0 1 10.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0 .229 2.523a1.125 1.125 0 0 1-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0 0 21 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 0 0-1.913-.247M6.34 18H5.25A2.25 2.25 0 0 1 3 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 0 1 1.913-.247m10.5 0a48.536 48.536 0 0 0-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5Zm-3 0h.008v.008H15V10.5Z" />
                                </svg>
                                DANFE
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
