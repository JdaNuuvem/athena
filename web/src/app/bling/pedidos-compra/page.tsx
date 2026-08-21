"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import {
  listarBlingPedidosCompra,
  sincronizarBlingPedidosCompra,
  receberBlingPedidoCompra,
} from "@/lib/api";
import type { BlingPedidoCompraLocal } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";

const STATUS_CORES: Record<string, string> = {
  emitido: "bg-indigo-900/40 text-indigo-300",
  recebido: "bg-emerald-900/40 text-emerald-300",
  cancelado: "bg-red-900/40 text-red-300",
};

export default function BlingPedidosCompraPage() {
  const [pedidos, setPedidos] = useState<BlingPedidoCompraLocal[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [ambiente, setAmbiente] = useState("producao");
  const [busca, setBusca] = useState("");

  const carregar = useCallback(async (amb: string) => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingPedidosCompra(amb);
    if (r.error) setErro(r.error);
    setPedidos(r.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    carregar(ambiente);
  }, [carregar, ambiente]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = await sincronizarBlingPedidosCompra();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} pedidos de compra sincronizados`);
    setSincronizando(false);
    carregar(ambiente);
  };

  // A rota POST /pedidos-compra/<id>/receber repassa o id pro Bling
  // (bling_erp.marcar_pedido_compra_recebido), entao o parametro e' o bling_id,
  // nao o id local.
  const handleReceber = async (p: BlingPedidoCompraLocal) => {
    if (!p.bling_id) {
      setErro("Pedido sem vínculo com o Bling.");
      return;
    }
    if (!window.confirm(`Marcar o pedido ${p.numero} como recebido no Bling?`)) return;
    setErro(null);
    setSucesso(null);
    const r = await receberBlingPedidoCompra(p.bling_id);
    if (r.error) {
      setErro(r.error);
      return;
    }
    setSucesso(`Pedido ${p.numero} marcado como recebido.`);
    carregar(ambiente);
  };

  const filtrados = pedidos.filter(
    (p) => !busca || String(p.numero).toLowerCase().includes(busca.toLowerCase())
  );

  if (loading && pedidos.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <SyncToolbar
        onSync={handleSync}
        sincronizando={sincronizando}
        total={filtrados.length}
        unidade="pedidos"
      >
        <input
          type="text"
          placeholder="Buscar por nº..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="flex-1 min-w-[180px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
        />
        <select
          value={ambiente}
          onChange={(e) => setAmbiente(e.target.value)}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
        >
          <option value="producao">Produção</option>
          <option value="homologacao">Homologação</option>
          <option value="todos">Todos os ambientes</option>
        </select>
      </SyncToolbar>

      {filtrados.length === 0 ? (
        <EmptyState
          icon="🧾"
          title={busca ? "Nenhum pedido encontrado" : "Nenhum pedido de compra"}
          description={
            busca
              ? "Ajuste a busca."
              : "Sincronize os pedidos de compra do Bling para começar."
          }
          action={busca ? undefined : { label: "Sincronizar Agora", onClick: handleSync }}
        />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 w-[110px]">Nº</th>
                <th className="text-left p-3 w-[100px]">Emissão</th>
                <th className="text-left p-3 w-[110px]">Entrega prev.</th>
                <th className="text-right p-3 w-[120px]">Total</th>
                <th className="text-center p-3 w-[100px]">Status</th>
                <th className="text-center p-3 w-[110px]">Ambiente</th>
                <th className="text-center p-3 w-[120px]">Ação</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((p, i) => (
                <tr
                  key={p.id}
                  className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}
                >
                  <td className="p-3 text-indigo-400 font-mono">{p.numero || "—"}</td>
                  <td className="p-3 text-neutral-400">
                    {p.data_emissao ? fmtDataBR(p.data_emissao) : "—"}
                  </td>
                  <td className="p-3 text-neutral-400">
                    {p.data_entrega_prevista ? fmtDataBR(p.data_entrega_prevista) : "—"}
                  </td>
                  <td className="p-3 text-right text-neutral-200">
                    {fmtBRL(Number(p.valor_total) || 0)}
                  </td>
                  <td className="p-3 text-center">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] ${STATUS_CORES[p.status] || "bg-neutral-700 text-neutral-300"}`}
                    >
                      {p.status || "—"}
                    </span>
                  </td>
                  <td className="p-3 text-center text-[10px] text-neutral-500">{p.ambiente}</td>
                  <td className="p-3 text-center">
                    {p.status === "recebido" ? (
                      <span className="text-[10px] text-neutral-500">—</span>
                    ) : (
                      <button
                        onClick={() => handleReceber(p)}
                        className="px-2 py-1 bg-neutral-700 text-neutral-200 text-[10px] rounded hover:bg-neutral-600 transition-colors"
                      >
                        Marcar recebido
                      </button>
                    )}
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
