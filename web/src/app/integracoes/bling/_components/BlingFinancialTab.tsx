"use client";

import { useEffect, useState, useCallback } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import EmptyState from "./shared/EmptyState";
import { listarContasReceber, listarNotasFiscais } from "@/lib/api";

interface ContaReceber {
  id: number;
  numero: string;
  vencimento: string;
  valor: number;
  contato: { nome: string };
  situacao: string;
}

interface NotaFiscal {
  id: number;
  numero: string;
  dataEmissao: string;
  total: number;
  contato: { nome: string };
  situacao: string;
}

export default function BlingFinancialTab() {
  const [contas, setContas] = useState<ContaReceber[]>([]);
  const [notas, setNotas] = useState<NotaFiscal[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [tab, setTab] = useState<"contas" | "notas">("contas");

  const carregar = useCallback(async () => {
    try {
      setLoading(true);
      setErro(null);
      if (tab === "contas") {
        const r = await listarContasReceber();
        if (r.error) throw new Error(String(r.error));
        setContas((r.data || []) as ContaReceber[]);
      } else {
        const r = await listarNotasFiscais();
        if (r.error) throw new Error(String(r.error));
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
          <EmptyState icon="💳" title="Nenhuma conta a receber" description="Sem registros no período." />
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
                    <td className="p-3 text-neutral-400">{c.vencimento?.slice(0, 10)}</td>
                    <td className="p-3 text-right text-emerald-400">R$ {(c.valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                    <td className="p-3 text-center">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-neutral-700 text-neutral-400">{c.situacao}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : notas.length === 0 ? (
        <EmptyState icon="📄" title="Nenhuma nota fiscal" description="Sem registros no período." />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400">
                <th className="text-left p-3">Nº</th>
                <th className="text-left p-3">Cliente</th>
                <th className="text-left p-3">Emissão</th>
                <th className="text-right p-3">Total</th>
                <th className="text-center p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {notas.map((n, i) => (
                <tr key={n.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-neutral-200 font-mono">{n.numero}</td>
                  <td className="p-3 text-neutral-200">{n.contato?.nome || "—"}</td>
                  <td className="p-3 text-neutral-400">{n.dataEmissao?.slice(0, 10)}</td>
                  <td className="p-3 text-right text-emerald-400">R$ {(n.total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3 text-center">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-neutral-700 text-neutral-400">{n.situacao}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
