"use client";

import { useEffect, useState, useCallback } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import EmptyState from "./shared/EmptyState";
import { listarContasReceber, listarNotasFiscais } from "@/lib/api";

interface NotaFiscal {
  id: number;
  numero: string;
  dataEmissao?: string;
  dataOperacao?: string;
  contato: { nome: string; numeroDocumento?: string };
  situacao: number;
  tipo: number;
  chaveAcesso?: string;
  loja?: { id: number };
  naturezaOperacao?: { id: number };
  valorNota?: number;
  total?: number;
}

interface ContaReceber {
  id: number;
  numero: string;
  vencimento?: string;
  valor?: number;
  contato: { nome: string };
  situacao: number | string;
}

const NF_SITUACOES: Record<number, string> = { 1: "Emitida", 2: "Cancelada", 3: "Inutilizada", 4: "Denegada" };
const NF_TIPOS: Record<number, string> = { 0: "Saída", 1: "Entrada" };

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
                            className="text-indigo-400 hover:text-indigo-300 text-lg leading-none">
                            {isExpanded ? "▲" : "▼"}
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
