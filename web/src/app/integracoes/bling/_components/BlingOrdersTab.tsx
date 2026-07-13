"use client";

import { useEffect, useState, useCallback } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import EmptyState from "./shared/EmptyState";
import { listarBlingPedidos, sincronizarBlingPedidos } from "@/lib/api";

interface PedidoItem {
  codigo: string;
  quantidade: number;
  valorUnitario: number;
  valorTotal: number;
}

interface Pedido {
  id: number;
  numero: string;
  dataEmissao: string;
  contato: { nome: string };
  total: number;
  situacao: string;
  itens: PedidoItem[];
}

export default function BlingOrdersTab() {
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [pagina, setPagina] = useState(1);

  const carregar = useCallback(async (p = 1) => {
    try {
      setLoading(true);
      setErro(null);
      const r = await listarBlingPedidos(p, 50);
      if (r.error) throw new Error(String(r.error));
      setPedidos((r.data || []) as Pedido[]);
      setPagina(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar pedidos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const handleSync = async () => {
    try {
      setLoading(true);
      const r = await sincronizarBlingPedidos();
      setSucesso(`${r.sincronizados || 0} pedidos sincronizados`);
      carregar(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro na sincronização");
    } finally {
      setLoading(false);
    }
  };

  if (loading && pedidos.length === 0) return <Spinner />;

  const situacaoStyle = (s: string) => {
    const map: Record<string, string> = {
      "1": "bg-yellow-900/30 text-yellow-400",
      "2": "bg-emerald-900/30 text-emerald-400",
      "3": "bg-red-900/30 text-red-400",
    };
    return map[s] || "bg-neutral-700 text-neutral-400";
  };

  const situacaoLabel = (s: string) => {
    const map: Record<string, string> = { "1": "Aberto", "2": "Concluído", "3": "Cancelado" };
    return map[s] || s;
  };

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <div className="flex justify-between items-center">
        <button onClick={handleSync} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">🔄 Sincronizar Pedidos</button>
        <div className="flex gap-2">
          <button onClick={() => carregar(Math.max(1, pagina - 1))} disabled={pagina <= 1} className="px-2 py-1 bg-neutral-700 text-neutral-300 text-xs rounded disabled:opacity-40">←</button>
          <span className="text-xs text-neutral-400 py-1">Pág {pagina}</span>
          <button onClick={() => carregar(pagina + 1)} disabled={pedidos.length < 50} className="px-2 py-1 bg-neutral-700 text-neutral-300 text-xs rounded disabled:opacity-40">→</button>
        </div>
      </div>

      {pedidos.length === 0 ? (
        <EmptyState icon="📋" title="Nenhum pedido" description="Sincronize pedidos do Bling para começar." action={{ label: "Sincronizar Agora", onClick: handleSync }} />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400">
                <th className="text-left p-3">Nº</th>
                <th className="text-left p-3">Cliente</th>
                <th className="text-left p-3">Data</th>
                <th className="text-right p-3">Total</th>
                <th className="text-center p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {pedidos.map((p, i) => (
                <tr key={p.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-neutral-200 font-mono">{p.numero}</td>
                  <td className="p-3 text-neutral-200">{p.contato?.nome || "—"}</td>
                  <td className="p-3 text-neutral-400">{p.dataEmissao?.slice(0, 10)}</td>
                  <td className="p-3 text-right text-emerald-400">R$ {(p.total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-[10px] ${situacaoStyle(p.situacao)}`}>{situacaoLabel(p.situacao)}</span>
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
